"""PokéAPI extraction.

Contract: data/staging/pokeapi.schema.json,
data/staging/pokeapi_move.schema.json,
data/staging/pokeapi_ability.schema.json,
data/staging/pokeapi_item.schema.json,
data/staging/pokeapi_artwork.schema.json,
data/staging/pokeapi_names.schema.json
Spec reference: docs/dataset-spec.md, "Source-specific extraction contracts > PokéAPI"

Captures Pokémon/form identity rows and base stat rows, weekly refresh
cadence. Fetches every entry in PokéAPI's `/pokemon` list — base species
plus Mega/regional/alternate forms (e.g. `charizard-mega-x`,
`raichu-alola`) — not just the base national-dex range, so that
form-specific rows from OP.GG and MunchStats have a canonical row to join
against (dataset-spec.md's "Multi-form species that need explicit mapping
rather than name-only joins" known risk).

`pokemon_id` is the species' National Dex number, read from each form's
`species.url` rather than the form's own PokéAPI resource id — the latter
is an internal, non-dex id for alt forms (e.g. `charizard-mega-x` is
resource id 10034 but species id 6), and `pokemon_id` must stay the shared
identifier across all forms of one species. `form_name` is the form's own
PokéAPI slug (equal to the species name for the default/base form).
`type_1`/`type_2` (type_2 nullable) come off the same `/pokemon/{form}`
payload already fetched for stats, so adding them costs no extra HTTP call.

`extract_moves`/`extract_abilities`/`extract_items` are separate functions
writing separate staging files (move/ability/item grain, not
Pokémon/form grain) — added for the dashboard's Pokémon Profile
descriptions and Matchup-tab damage calculator (docs/todo.md M6 backlog:
"type-effectiveness / head-to-head matchups"). Each is scoped to an
explicit iterable of names (the moves/abilities/items actually reported in
MunchStats tournament roster data — `data/staging/munchstats.csv`'s
`moves`/`ability`/`item_name` fields) rather than PokéAPI's full
~900-move/~370-item catalog, since the dashboard only ever needs detail
for names that already appear in real tournament roster data.

`extract_artwork` is a fifth staging file at yet another grain: one
high-resolution PokéMon HOME render per form, downloaded from PokéAPI's
sprite *repository* rather than its JSON API. It exists because the
Bulbagarden menu sprites that back `pokemon_asset` today are 128x128 —
fine in a 40px table cell, blurry in the dashboard's 96px/128px hero
slots. Like the detail fetches it is scoped to an explicit iterable
(the forms that already have a Champions menu sprite) rather than
PokéAPI's full ~1,350-form list, and like `bulbagarden.py` it writes
binary image bytes alongside its CSV.

`extract_names` is the sixth (docs/upgrade-plan-2027q2.md, Q4): each
form's name in Japanese, Spanish, French and German, for the dashboard's
name-language switch. It reads PokéAPI's own source CSVs off GitHub (five
files) rather than ~600 species and form calls. PokéAPI gives every
species' localised name but full form names only unevenly (French and
Japanese Megas, a few German and Spanish ones), so `localised_name`
composes the rest from the species name and the official conventions:
"Méga-Dracaufeu Y", "メガリザードンＹ", "Arcanine de Hisui", "Hisui-Arkani",
"ウインディ（ヒスイのすがた）". Portuguese isn't extracted: the Brazilian games
use the English names.
"""

from __future__ import annotations

import csv
import hashlib
import io
import struct
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import requests

from pipelines.extract.http import get_with_retry

SOURCE_NAME = "PokéAPI"
API_BASE_URL = "https://pokeapi.co/api/v2"
DEFAULT_DATASET_VERSION = "0.0.0-dev"

# Large enough to cover PokéAPI's full /pokemon list (base species plus
# Mega/regional/alternate forms) in a single page.
_LIST_PAGE_SIZE = 5000

# PokéAPI's sprite bundle is published as a plain GitHub repo, not through
# the JSON API, so artwork is fetched from raw.githubusercontent.com rather
# than API_BASE_URL. `other/home` (512x512) is used over
# `other/official-artwork` (475x475) because HOME renders are a uniform
# square with a transparent background and cover Mega/regional/alternate
# forms under their own 10xxx resource ids.
ARTWORK_BASE_URL = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/home"
)
ARTWORK_IMAGE_KIND = "home_render"
DEFAULT_ARTWORK_CACHE_DIR = Path("data") / "assets" / "pokeapi_artwork"

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

FIELDNAMES = [
    "pokemon_id",
    "pokemon_name",
    "form_name",
    "hp",
    "attack",
    "defense",
    "sp_attack",
    "sp_defense",
    "speed",
    "stat_total",
    "type_1",
    "type_2",
    "source_name",
    "source_url",
    "source_record_id",
    "extracted_at_utc",
    "dataset_version",
]

MOVE_FIELDNAMES = [
    "move_name",
    "move_type",
    "power",
    "accuracy",
    "category",
    "priority",
    "pp",
    "short_effect",
    "source_name",
    "source_url",
    "source_record_id",
    "extracted_at_utc",
    "dataset_version",
]

ABILITY_FIELDNAMES = [
    "ability_name",
    "short_effect",
    "source_name",
    "source_url",
    "source_record_id",
    "extracted_at_utc",
    "dataset_version",
]

ITEM_FIELDNAMES = [
    "item_name",
    "short_effect",
    "source_name",
    "source_url",
    "source_record_id",
    "extracted_at_utc",
    "dataset_version",
]

# Deliberately parallel to bulbagarden.py's FIELDNAMES: both are image
# manifests feeding the same `pokemon_asset` entity, differing only in how
# the form is identified (a PokéAPI form slug here, a Bulbagarden file title
# there), so the two staging models stay near-copies of each other.
ARTWORK_FIELDNAMES = [
    "form_name",
    "pokeapi_resource_id",
    "image_kind",
    "local_cache_path",
    "sha1",
    "width",
    "height",
    "mime_type",
    "file_size_bytes",
    "source_name",
    "source_url",
    "source_record_id",
    "extracted_at_utc",
    "dataset_version",
]

NAMES_FIELDNAMES = [
    "form_name",
    "language",
    "localised_name",
    "name_rule",
    "source_name",
    "source_url",
    "source_record_id",
    "extracted_at_utc",
    "dataset_version",
]
NAMES_CSV_BASE_URL = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv"
# The name languages (Q4) and PokéAPI's identifiers for them. PokéAPI files
# Japanese under both "ja" (kanji where the games use it) and "ja-hrkt"
# (kana); Pokémon names are kana either way, and "ja" is the games' own.
NAME_LANGUAGES = {"ja": ("ja", "ja-hrkt"), "es": ("es",), "fr": ("fr",), "de": ("de",)}
_REGIONS = {
    "alola": ("Alola", "アローラ"),
    "galar": ("Galar", "ガラル"),
    "hisui": ("Hisui", "ヒスイ"),
    "paldea": ("Paldea", "パルデア"),
}
_MEGA_PREFIX = {"ja": "メガ", "es": "Mega-", "fr": "Méga-", "de": "Mega-"}

_STAT_NAME_TO_FIELD = {
    "hp": "hp",
    "attack": "attack",
    "defense": "defense",
    "special-attack": "sp_attack",
    "special-defense": "sp_defense",
    "speed": "speed",
}


def _fetch_pokemon_list(session: requests.Session) -> list[str]:
    url = f"{API_BASE_URL}/pokemon?limit={_LIST_PAGE_SIZE}"
    response = get_with_retry(session, url, timeout=30)
    return [entry["name"] for entry in response.json()["results"]]


def _fetch_pokemon(session: requests.Session, form_name: str) -> dict:
    url = f"{API_BASE_URL}/pokemon/{form_name}"
    response = get_with_retry(session, url, timeout=30)
    return response.json()


def _species_id(payload: dict) -> int:
    species_url = payload["species"]["url"]
    return int(species_url.rstrip("/").rsplit("/", 1)[-1])


def _types(payload: dict) -> tuple[str, str | None]:
    ordered = sorted(payload["types"], key=lambda entry: entry["slot"])
    names = [entry["type"]["name"] for entry in ordered]
    type_1 = names[0]
    type_2 = names[1] if len(names) > 1 else None
    return type_1, type_2


def _row_from_payload(payload: dict, *, extracted_at_utc: str, dataset_version: str) -> dict:
    form_name = payload["name"]
    stats = {
        _STAT_NAME_TO_FIELD[entry["stat"]["name"]]: entry["base_stat"]
        for entry in payload["stats"]
        if entry["stat"]["name"] in _STAT_NAME_TO_FIELD
    }
    type_1, type_2 = _types(payload)
    return {
        "pokemon_id": _species_id(payload),
        "pokemon_name": payload["species"]["name"],
        "form_name": form_name,
        **stats,
        "stat_total": sum(stats.values()),
        "type_1": type_1,
        "type_2": type_2,
        "source_name": SOURCE_NAME,
        "source_url": f"{API_BASE_URL}/pokemon/{form_name}",
        "source_record_id": str(payload["id"]),
        "extracted_at_utc": extracted_at_utc,
        "dataset_version": dataset_version,
    }


def extract(
    output_path: Path,
    pokemon_identifiers: Iterable[str | int] | None = None,
    *,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    session: requests.Session | None = None,
) -> None:
    """Fetch PokéAPI identity + base stat rows and write them to output_path
    as CSV matching the field list in data/staging/pokeapi.schema.json,
    including provenance fields (source_name, source_url, source_record_id,
    extracted_at_utc, dataset_version).

    `pokemon_identifiers` defaults to every entry in PokéAPI's `/pokemon`
    list (base species plus Mega/regional/alternate forms); pass an
    explicit iterable of names or ids to scope the extract.
    """
    http = session if session is not None else requests.Session()
    identifiers = (
        pokemon_identifiers if pokemon_identifiers is not None else _fetch_pokemon_list(http)
    )
    extracted_at_utc = datetime.now(UTC).isoformat()

    rows = [
        _row_from_payload(
            _fetch_pokemon(http, identifier),
            extracted_at_utc=extracted_at_utc,
            dataset_version=dataset_version,
        )
        for identifier in identifiers
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _slugify(display_name: str) -> str:
    """PokéAPI resource slugs are lowercase-hyphenated (e.g. "Choice Band"
    -> "choice-band", "King's Rock" -> "kings-rock"); dashboard-facing move/
    item/ability names elsewhere in this pipeline are Title Case (see
    dbt/seeds/pokeapi_move_types.csv's "move display name, Title Case"
    convention), so both directions are needed at the extraction boundary.

    Strips both the straight apostrophe (') and the Unicode right/left
    single quotation marks (’/‘) some real tournament roster text
    uses in place of a straight apostrophe (e.g. "King’s Shield") — left
    unstripped, the curly form survives into the URL as a percent-encoded
    byte sequence PokéAPI's router 400s on, rather than resolving the same
    as the straight-apostrophe form.
    """
    return display_name.lower().replace("'", "").replace("’", "").replace("‘", "").replace(" ", "-")


def _english_short_effect(payload: dict) -> str | None:
    for entry in payload.get("effect_entries", []):
        if entry["language"]["name"] == "en":
            return " ".join(entry["short_effect"].split())
    return None


def _fetch_resource_or_none(session: requests.Session, resource: str, slug: str) -> dict | None:
    """Like a direct GET, but returns None instead of raising when a single
    move/ability/item can't be fetched, rather than aborting extraction for
    every other name:
    - A 404 means the name doesn't resolve to any PokéAPI resource (a
      genuine data-quality issue in the upstream source, e.g. a truncated
      move name) — returns None immediately.
    - A transient error (5xx, connection/timeout) is retried by
      get_with_retry; if it never recovers, treated the same as a 404 (skip,
      don't crash the whole run) — a single flaky response out of hundreds
      of lookups shouldn't lose everything else already fetched.
    """
    url = f"{API_BASE_URL}/{resource}/{slug}"
    try:
        response = get_with_retry(session, url, timeout=30)
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return None
        print(f"Giving up on {resource}/{slug}: {exc}", file=sys.stderr)
        return None
    except requests.exceptions.RequestException as exc:
        print(f"Giving up on {resource}/{slug}: {exc}", file=sys.stderr)
        return None
    return response.json()


def extract_moves(
    output_path: Path,
    move_names: Iterable[str],
    *,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    session: requests.Session | None = None,
) -> None:
    """Fetch PokéAPI move detail (type/power/accuracy/category/priority/pp/
    short_effect) for the given display names and write them to output_path
    as CSV matching data/staging/pokeapi_move.schema.json.

    Scoped to an explicit iterable (the moves actually referenced by
    tournament roster data) rather than PokéAPI's full move catalog.
    """
    http = session if session is not None else requests.Session()
    extracted_at_utc = datetime.now(UTC).isoformat()

    rows = []
    for move_name in move_names:
        slug = _slugify(move_name)
        payload = _fetch_resource_or_none(http, "move", slug)
        if payload is None:
            print(f"Skipping unresolved move: {move_name!r} (slug {slug!r})", file=sys.stderr)
            continue
        rows.append(
            {
                "move_name": move_name,
                "move_type": payload["type"]["name"],
                "power": payload["power"],
                "accuracy": payload["accuracy"],
                "category": payload["damage_class"]["name"],
                "priority": payload["priority"],
                "pp": payload["pp"],
                "short_effect": _english_short_effect(payload),
                "source_name": SOURCE_NAME,
                "source_url": f"{API_BASE_URL}/move/{slug}",
                "source_record_id": str(payload["id"]),
                "extracted_at_utc": extracted_at_utc,
                "dataset_version": dataset_version,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MOVE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def extract_abilities(
    output_path: Path,
    ability_names: Iterable[str],
    *,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    session: requests.Session | None = None,
) -> None:
    """Fetch PokéAPI ability effect text for the given display names and
    write them to output_path as CSV matching
    data/staging/pokeapi_ability.schema.json.
    """
    http = session if session is not None else requests.Session()
    extracted_at_utc = datetime.now(UTC).isoformat()

    rows = []
    for ability_name in ability_names:
        slug = _slugify(ability_name)
        payload = _fetch_resource_or_none(http, "ability", slug)
        if payload is None:
            print(f"Skipping unresolved ability: {ability_name!r} (slug {slug!r})", file=sys.stderr)
            continue
        rows.append(
            {
                "ability_name": ability_name,
                "short_effect": _english_short_effect(payload),
                "source_name": SOURCE_NAME,
                "source_url": f"{API_BASE_URL}/ability/{slug}",
                "source_record_id": str(payload["id"]),
                "extracted_at_utc": extracted_at_utc,
                "dataset_version": dataset_version,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=ABILITY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def extract_items(
    output_path: Path,
    item_names: Iterable[str],
    *,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    session: requests.Session | None = None,
) -> None:
    """Fetch PokéAPI held-item effect text for the given display names and
    write them to output_path as CSV matching
    data/staging/pokeapi_item.schema.json.
    """
    http = session if session is not None else requests.Session()
    extracted_at_utc = datetime.now(UTC).isoformat()

    rows = []
    for item_name in item_names:
        slug = _slugify(item_name)
        payload = _fetch_resource_or_none(http, "item", slug)
        if payload is None:
            print(f"Skipping unresolved item: {item_name!r} (slug {slug!r})", file=sys.stderr)
            continue
        rows.append(
            {
                "item_name": item_name,
                "short_effect": _english_short_effect(payload),
                "source_name": SOURCE_NAME,
                "source_url": f"{API_BASE_URL}/item/{slug}",
                "source_record_id": str(payload["id"]),
                "extracted_at_utc": extracted_at_utc,
                "dataset_version": dataset_version,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=ITEM_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _png_dimensions(data: bytes) -> tuple[int, int] | None:
    """Width/height straight out of the PNG IHDR chunk: after the 8-byte
    signature and the 8-byte chunk length/type header, the first two fields
    are big-endian uint32 width and height. Reading the header directly
    keeps extraction dependency-free -- Pillow is only needed for the
    dashboard's downscale step, not for recording an image's real size.
    Returns None for anything that isn't a PNG, so a truncated or
    HTML-error-page response is skipped rather than recorded with garbage
    dimensions.
    """
    if len(data) < 24 or not data.startswith(_PNG_SIGNATURE):
        return None
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _fetch_artwork_or_none(session: requests.Session, url: str) -> bytes | None:
    """Same graceful-skip contract as _fetch_resource_or_none: a form whose
    artwork isn't published (404) or never recovers from a transient error
    is skipped, so one missing render doesn't lose every other form already
    fetched. Missing rows then show up as a coverage-gate number rather
    than as an aborted run."""
    try:
        response = get_with_retry(session, url, timeout=30)
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return None
        print(f"Giving up on artwork {url}: {exc}", file=sys.stderr)
        return None
    except requests.exceptions.RequestException as exc:
        print(f"Giving up on artwork {url}: {exc}", file=sys.stderr)
        return None
    return response.content


def extract_artwork(
    output_path: Path,
    form_resource_ids: Iterable[tuple[str, str]],
    *,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    session: requests.Session | None = None,
    cache_dir: Path = DEFAULT_ARTWORK_CACHE_DIR,
    skip_existing: bool = True,
) -> None:
    """Download high-resolution PokéMon HOME renders and write a manifest CSV
    to output_path matching data/staging/pokeapi_artwork.schema.json,
    including provenance fields.

    `form_resource_ids` is an iterable of `(form_name, pokeapi_resource_id)`
    pairs. The resource id is the form's *own* PokéAPI id (10034 for
    `charizard-mega-x`), not the species' National Dex number -- PokéAPI's
    sprite repo is keyed by the former, and `extract()` already records it
    as `source_record_id`, so no extra lookup or mapping seed is needed to
    resolve one from the other.

    Like bulbagarden.py, this is one of only two extractors that writes
    binary image bytes (to cache_dir) alongside its CSV row. `skip_existing`
    reuses an already-cached file instead of re-downloading; unlike
    Bulbagarden there's no upstream sha1 to compare against, so a cached
    file is trusted on presence and re-verified only for its own digest.
    """
    http = session if session is not None else requests.Session()
    extracted_at_utc = datetime.now(UTC).isoformat()

    rows = []
    for form_name, resource_id in form_resource_ids:
        local_cache_path = f"{form_name}.png"
        dest_path = cache_dir / local_cache_path
        url = f"{ARTWORK_BASE_URL}/{resource_id}.png"

        reused_cache = skip_existing and dest_path.exists()
        if reused_cache:
            data = dest_path.read_bytes()
        else:
            data = _fetch_artwork_or_none(http, url)
            if data is None:
                print(
                    f"Skipping unresolved artwork: {form_name!r} (resource id {resource_id!r})",
                    file=sys.stderr,
                )
                continue

        dimensions = _png_dimensions(data)
        if dimensions is None:
            print(
                f"Skipping non-PNG artwork response: {form_name!r} "
                f"(resource id {resource_id!r}, {len(data)} bytes)",
                file=sys.stderr,
            )
            continue
        width, height = dimensions

        # Write whenever the bytes came off the network, not just when the
        # destination is absent: a skip_existing=False run exists precisely
        # to replace a stale cached file, and skipping the write there would
        # leave the old bytes on disk under a manifest describing the new
        # ones.
        if not reused_cache:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(data)

        rows.append(
            {
                "form_name": form_name,
                "pokeapi_resource_id": resource_id,
                "image_kind": ARTWORK_IMAGE_KIND,
                "local_cache_path": local_cache_path,
                "sha1": hashlib.sha1(data).hexdigest(),
                "width": width,
                "height": height,
                "mime_type": "image/png",
                "file_size_bytes": len(data),
                "source_name": SOURCE_NAME,
                "source_url": url,
                "source_record_id": resource_id,
                "extracted_at_utc": extracted_at_utc,
                "dataset_version": dataset_version,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=ARTWORK_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _gender_sign(form_identifier: str) -> str:
    parts = form_identifier.split("-")
    return " ♂" if "male" in parts else " ♀" if "female" in parts else ""


def localised_name(
    language: str,
    species: str,
    *,
    form_identifier: str,
    is_mega: bool,
    form_name: str = "",
    full_name: str = "",
    is_default_variety: bool = False,
) -> tuple[str, str]:
    """(name, rule) for one form in one language. `species` is the species'
    name in the language, `form_name`/`full_name` PokéAPI's form label and
    full form name in it (either may be empty), `is_default_variety` whether
    the form is its species' default Pokémon. The rule says which convention
    produced the name, so the composed ones can be audited."""
    if full_name:
        return full_name, "pokeapi_form"
    if not form_identifier:
        return species, "species"
    if form_name and species in form_name:
        # "ウォッシュロトム", "Rotom Lavado": the label is the full name.
        return form_name, "pokeapi_form"
    if is_mega:
        if language == "ja" and form_name.startswith("メガ"):
            return form_name, "pokeapi_form"
        letter = form_identifier.rsplit("-", 1)[-1]
        suffix = letter.upper() if letter in ("x", "y", "z") else ""
        if language == "ja":
            return (
                f"{_MEGA_PREFIX[language]}{species}{suffix}{_gender_sign(form_identifier)}",
                "mega",
            )
        tail = f" {suffix}" if suffix else ""
        return f"{_MEGA_PREFIX[language]}{species}{tail}{_gender_sign(form_identifier)}", "mega"
    if form_name:
        if language == "ja":
            return f"{species}（{form_name}）", "form_label"
        return f"{species} ({form_name})", "form_label"
    region = _REGIONS.get(form_identifier.split("-")[0])
    if region:
        latin, kana = region
        if language == "ja":
            return f"{species}（{kana}のすがた）", "regional"
        if language == "de":
            return f"{latin}-{species}", "regional"
        return f"{species} de {latin}", "regional"
    sign = _gender_sign(form_identifier)
    if sign:
        return f"{species}{sign}", "gender"
    if is_default_variety:
        # PokéAPI labels some single-form species' default form ("plant"
        # Mothim): the game calls it by the species name.
        return species, "species"
    label = " ".join(part.capitalize() for part in form_identifier.split("-"))
    return f"{species} ({label})", "fallback"


def _read_names_csv(session: requests.Session, name: str) -> list[dict]:
    response = get_with_retry(session, f"{NAMES_CSV_BASE_URL}/{name}.csv", timeout=60)
    return list(csv.DictReader(io.StringIO(response.text)))


def extract_names(
    output_path: Path,
    form_names: Iterable[str],
    *,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    session: requests.Session | None = None,
) -> None:
    """Write each form's name in NAME_LANGUAGES to output_path as CSV
    matching data/staging/pokeapi_names.schema.json. `form_names` are
    PokéAPI /pokemon slugs (this dataset's pokemon_key); one that PokéAPI's
    CSVs don't know is skipped."""
    http = session if session is not None else requests.Session()
    extracted_at_utc = datetime.now(UTC).isoformat()
    languages = {row["id"]: row["identifier"] for row in _read_names_csv(http, "languages")}
    pokemon = {row["identifier"]: row for row in _read_names_csv(http, "pokemon")}
    forms = {
        row["pokemon_id"]: row
        for row in _read_names_csv(http, "pokemon_forms")
        if row["is_default"] == "1"
    }
    species_names: dict[tuple[str, str], str] = {}
    for row in _read_names_csv(http, "pokemon_species_names"):
        species_names[(row["pokemon_species_id"], languages.get(row["local_language_id"], ""))] = (
            row["name"]
        )
    form_labels: dict[tuple[str, str], tuple[str, str]] = {}
    for row in _read_names_csv(http, "pokemon_form_names"):
        key = (row["pokemon_form_id"], languages.get(row["local_language_id"], ""))
        form_labels[key] = (row["form_name"], row["pokemon_name"])

    rows = []
    for form_name in form_names:
        entry = pokemon.get(form_name)
        form = forms.get(entry["id"]) if entry else None
        if entry is None or form is None:
            continue
        for language, identifiers in NAME_LANGUAGES.items():
            species = next(
                (
                    species_names[(entry["species_id"], i)]
                    for i in identifiers
                    if (entry["species_id"], i) in species_names
                ),
                None,
            )
            if not species:
                continue
            label, full = next(
                (
                    form_labels[(form["id"], i)]
                    for i in identifiers
                    if (form["id"], i) in form_labels
                ),
                ("", ""),
            )
            name, rule = localised_name(
                language,
                species,
                form_identifier=form["form_identifier"],
                is_mega=form["is_mega"] == "1",
                form_name=label,
                full_name=full,
                is_default_variety=entry["is_default"] == "1",
            )
            rows.append(
                {
                    "form_name": form_name,
                    "language": language,
                    "localised_name": name,
                    "name_rule": rule,
                    "source_name": SOURCE_NAME,
                    "source_url": f"{NAMES_CSV_BASE_URL}/pokemon_form_names.csv",
                    "source_record_id": f"{form_name}:{language}",
                    "extracted_at_utc": extracted_at_utc,
                    "dataset_version": dataset_version,
                }
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=NAMES_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
