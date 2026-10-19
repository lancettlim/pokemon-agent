"""PokéBase app extraction.

Contract: data/staging/pokebase.schema.json
Spec reference: docs/dataset-spec.md, "Source-specific extraction contracts > PokéBase"

Captures per-regulation legal-pool membership for Pokémon Champions from
pokebase.app/pokemon-champions/pokemon. Like OP.GG's Champions Pokédex page
(see pipelines/extract/opgg.py's docstring), this is server-rendered by
Next.js and ships its full paginated pokemon list (a `docs` array, 1360
entries, single page — `hasNextPage: false`) as a JSON payload embedded in
a React Server Components "Flight" script chunk
(`self.__next_f.push([1, "..."])`), so a plain HTTP GET is enough despite
the page appearing JS-driven; no browser automation is required.
`_extract_pokemon_payloads` locates and unescapes it using the same
technique as opgg.py.

Each pokemon entry that's part of the Champions legal pool carries a
`regulationSets` array (e.g. `[{"name": "M-A", "slug": "m-a", ...}]`)
naming every regulation it's legal under; entries with no `regulationSets`
field aren't currently in the legal pool and are skipped. One staging row
is emitted per (pokemon, regulation) pair. `nationalNumber` is PokéBase's
own National Dex field and is correct for Mega/regional/alternate forms
too (unlike OP.GG's fabricated per-form ids), so it's used directly as
`pokemon_id`. `slug` already follows PokéAPI's own form-naming convention
for the large majority of entries (e.g. `charizard-mega-x`); the handful
that don't (bare species names PokéAPI splits into named sub-forms with no
default-equals-species-name entry) are resolved downstream by the
pokebase_slug_to_pokeapi_form seed, same as OP.GG/MunchStats.

Page shape as of 2026-10 (the "regulation-ordered" shape): PokéBase
redesigned the page. The list now sits under `"data":{"pokemon":[...]}`,
and each entry carries `dex` (instead of `nationalNumber`) and
`addedIn: "m-c"` (the regulation it entered the pool in) instead of a
`regulationSets` array. A separate `"regulations":[...]` array lists every
set in release order. An entry is emitted as legal in its `addedIn`
regulation and every later one, which gives true per-regulation membership:
"legal in M-C" is the full M-C pool, not only M-C's additions. The page
publishes no removals, the same positive-signal-only limitation
legality_summary_by_regulation.sql already documents. The older
`docs`/`regulationSets` shape is still parsed if PokéBase reverts.
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from pipelines.extract.http import get_with_retry

SOURCE_NAME = "PokéBase"
PAGE_URL = "https://pokebase.app/pokemon-champions/pokemon"
DEFAULT_DATASET_VERSION = "0.0.0-dev"

FIELDNAMES = [
    "pokemon_id",
    "pokemon_name",
    "form_name",
    "regulation_code",
    "is_legal",
    "source_name",
    "source_url",
    "source_record_id",
    "extracted_at_utc",
    "dataset_version",
]

_ARRAY_MARKER = '\\"data\\":{\\"docs\\":['
_POKEMON_ARRAY_MARKER = '\\"data\\":{\\"pokemon\\":['
_REGULATIONS_ARRAY_MARKER = '\\"regulations\\":['


def _fetch_page_html(session: requests.Session) -> str:
    response = get_with_retry(session, PAGE_URL, timeout=30)
    return response.text


def _find_array_end(text: str, open_bracket_index: int) -> int:
    """Scan forward from an opening `[` to its matching `]`, treating the
    escaped-quote sequence `\\"` as a single quote-toggle token so brackets
    inside string values aren't counted."""
    depth = 0
    in_string = False
    i = open_bracket_index
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text) and text[i + 1] == '"':
            in_string = not in_string
            i += 2
            continue
        if not in_string:
            if text[i] == "[":
                depth += 1
            elif text[i] == "]":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise ValueError("Unbalanced brackets while scanning embedded pokemon payload")


def _extract_embedded_array(html: str, marker: str) -> list | None:
    marker_index = html.find(marker)
    if marker_index == -1:
        return None
    array_start = marker_index + len(marker) - 1
    array_end = _find_array_end(html, array_start)
    escaped_array = html[array_start : array_end + 1]
    unescaped_array = json.loads(f'"{escaped_array}"')
    return json.loads(unescaped_array)


def _extract_pokemon_payloads(html: str) -> list[dict]:
    for marker in (_POKEMON_ARRAY_MARKER, _ARRAY_MARKER):
        payloads = _extract_embedded_array(html, marker)
        if payloads is not None:
            return payloads
    raise ValueError("Could not find embedded pokemon payload in PokéBase page HTML")


def _extract_regulation_order(html: str) -> list[str]:
    """Regulation slugs in release order, from the page's own
    `regulations` array (empty for the older page shape, which doesn't need
    it)."""
    regulations = _extract_embedded_array(html, _REGULATIONS_ARRAY_MARKER) or []
    return [regulation["slug"] for regulation in regulations]


def _legal_regulations(payload: dict, regulation_order: list[str]) -> list[tuple[str, str]]:
    """(regulation slug, source_record_id suffix) for every regulation
    this entry is legal under, from whichever page shape it came from."""
    if payload.get("regulationSets"):
        return [(r["slug"], r["id"]) for r in payload["regulationSets"]]
    added_in = payload.get("addedIn")
    if not added_in or added_in not in regulation_order:
        return []
    return [(slug, slug) for slug in regulation_order[regulation_order.index(added_in) :]]


def _rows_from_pokemon(
    payload: dict,
    *,
    extracted_at_utc: str,
    dataset_version: str,
    regulation_order: list[str] | None = None,
) -> list[dict]:
    rows = []
    pokemon_id = payload.get("nationalNumber", payload.get("dex"))
    for regulation_slug, record_suffix in _legal_regulations(payload, regulation_order or []):
        rows.append(
            {
                "pokemon_id": pokemon_id,
                "pokemon_name": payload["name"],
                "form_name": payload["slug"],
                "regulation_code": regulation_slug,
                "is_legal": True,
                "source_name": SOURCE_NAME,
                "source_url": f"{PAGE_URL}/{payload['slug']}",
                "source_record_id": f"{payload['id']}:{record_suffix}",
                "extracted_at_utc": extracted_at_utc,
                "dataset_version": dataset_version,
            }
        )
    return rows


def extract(
    output_path: Path,
    *,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    session: requests.Session | None = None,
) -> None:
    """Fetch the PokéBase Champions Pokédex page, extract its embedded
    per-regulation legal-pool membership, and write it to output_path as
    CSV matching the field list in data/staging/pokebase.schema.json,
    including provenance fields."""
    http = session if session is not None else requests.Session()
    html = _fetch_page_html(http)
    payloads = _extract_pokemon_payloads(html)
    regulation_order = _extract_regulation_order(html)
    extracted_at_utc = datetime.now(UTC).isoformat()

    rows = []
    for payload in payloads:
        rows.extend(
            _rows_from_pokemon(
                payload,
                extracted_at_utc=extracted_at_utc,
                dataset_version=dataset_version,
                regulation_order=regulation_order,
            )
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
