"""Bulbagarden Archives (Champions menu sprites) extraction.

Contract: data/staging/bulbagarden.schema.json
Spec reference: docs/dataset-spec.md, "Source-specific extraction contracts > Bulbagarden Archives"

PokéAPI's sprite set is stale for the newest Pokémon relevant to the
Champions format; Bulbagarden Archives' "Champions menu sprites" category
(https://archives.bulbagarden.net/wiki/Category:Champions_menu_sprites)
has the missing art. Bulbagarden Archives is a MediaWiki install and
exposes a full JSON API at /w/api.php, so this extractor is pure
JSON-over-HTTP (like munchstats.py) rather than HTML scraping (like
opgg.py/pokebase.py) — no HTML parser dependency is needed:

  - `action=query&list=categorymembers&cmtitle=Category:Champions_menu_sprites`
    lists the category's files as `{"pageid", "ns", "title"}` entries,
    paginated via the response's `continue.cmcontinue` token.
  - `action=query&titles=<pipe-joined titles>&prop=imageinfo&iiprop=url|size|mime|sha1`
    (batched, since MediaWiki accepts multiple `|`-joined titles per call)
    resolves each title to its real CDN download URL plus size/mime/sha1.

File titles follow the pattern `File:Menu Champs <4-digit Pokédex
number>[-<Form descriptor>].png` (e.g. "Menu Champs 0003-Mega.png", "Menu
Champs 0128-Paldea Aqua.png") — flat, no subcategories. Bulbagarden renamed
every file from the older "Menu CP" prefix by 2026-10. Both prefixes are
accepted, so a cached or partially renamed category still parses, but the
mapping seed is keyed on the current "Menu Champs" titles. `_parse_title` splits this into raw,
*unresolved* `pokedex_number_raw`/`form_suffix_raw` fields; like
opgg.py/pokebase.py, this extractor doesn't resolve cross-source identity
itself — that's dbt's job, via the
dbt/seeds/bulbagarden_title_to_pokeapi_form.csv mapping seed (Bulbagarden's
form-suffix tokens are not guaranteed to match OP.GG's or PokéAPI's own
conventions, so this is a dedicated seed, not a reuse of the OP.GG one — see
that seed's schema.yml entry for the reconciliation notes).

Unlike the other four extractors, this one downloads binary image bytes
to a local, gitignored cache (data/assets/bulbagarden/ by default) in
addition to writing a CSV manifest row per image — the CSV never embeds
image bytes, only `local_cache_path` + `sha1` + size/mime metadata.
`skip_existing` avoids re-downloading a file whose cached copy already
matches the upstream sha1, since sprite art doesn't change once posted.

Known risk: Bulbagarden's MediaWiki API's rate-limiting/ToS posture for
sustained/scheduled automated access hasn't been independently verified
beyond confirming the API works for a one-off extract — worth checking
before wiring this into any frequent scheduled refresh.
"""

from __future__ import annotations

import csv
import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

import requests

from pipelines.extract.http import get_with_retry

SOURCE_NAME = "Bulbagarden Archives"
API_BASE_URL = "https://archives.bulbagarden.net/w/api.php"
CATEGORY_TITLE = "Category:Champions_menu_sprites"
DEFAULT_DATASET_VERSION = "0.0.0-dev"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = REPO_ROOT / "data" / "assets" / "bulbagarden"

# MediaWiki tolerates multi-title batches via `|`-joined `titles=`; keep
# batches modest to stay well under typical URL-length limits.
_TITLE_BATCH_SIZE = 50

_TITLE_PATTERN = re.compile(r"^File:Menu (?:CP|Champs) (\d{4})(?:-(.+))?\.png$")

FIELDNAMES = [
    "bulbagarden_title",
    "pokedex_number_raw",
    "form_suffix_raw",
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


def _api_get(session: requests.Session, params: dict) -> dict:
    response = get_with_retry(
        session, API_BASE_URL, params={**params, "format": "json"}, timeout=30
    )
    return response.json()


def _list_category_members(session: requests.Session) -> list[dict]:
    """Return every {"pageid", "ns", "title"} entry in CATEGORY_TITLE,
    following the API's `continue.cmcontinue` pagination token."""
    members: list[dict] = []
    cmcontinue: str | None = None
    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": CATEGORY_TITLE,
            "cmlimit": "500",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        payload = _api_get(session, params)
        members.extend(payload.get("query", {}).get("categorymembers", []))
        cmcontinue = payload.get("continue", {}).get("cmcontinue")
        if not cmcontinue:
            return members


def _resolve_file_info(session: requests.Session, titles: list[str]) -> dict[str, dict]:
    """Batched title -> imageinfo dict (url/size/width/height/mime/sha1)."""
    resolved: dict[str, dict] = {}
    for start in range(0, len(titles), _TITLE_BATCH_SIZE):
        batch = titles[start : start + _TITLE_BATCH_SIZE]
        payload = _api_get(
            session,
            {
                "action": "query",
                "titles": "|".join(batch),
                "prop": "imageinfo",
                "iiprop": "url|size|mime|sha1",
            },
        )
        for page in payload.get("query", {}).get("pages", {}).values():
            imageinfo = page.get("imageinfo")
            if imageinfo:
                resolved[page["title"]] = imageinfo[0]
    return resolved


def _parse_title(title: str) -> tuple[str, str | None] | None:
    match = _TITLE_PATTERN.match(title)
    if not match:
        return None
    pokedex_number_raw, form_suffix_raw = match.groups()
    return pokedex_number_raw, form_suffix_raw


def _local_cache_path(pokedex_number_raw: str, form_suffix_raw: str | None) -> str:
    suffix = f"-{form_suffix_raw}" if form_suffix_raw else ""
    return f"{pokedex_number_raw}{suffix}.png"


def _download_image(session: requests.Session, url: str, dest_path: Path) -> None:
    response = get_with_retry(session, url, timeout=30)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(response.content)


def extract(
    output_path: Path,
    *,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    session: requests.Session | None = None,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    skip_existing: bool = True,
) -> None:
    """Fetch the Bulbagarden Champions-menu-sprites category listing,
    resolve each file's real image URL/metadata, download the bytes to
    cache_dir, and write a manifest CSV to output_path matching the field
    list in data/staging/bulbagarden.schema.json, including provenance
    fields. Titles that don't match the expected "Menu Champs <NNNN>[-<Form>]"
    pattern are skipped (not written) rather than guessed at."""
    http = session if session is not None else requests.Session()
    members = _list_category_members(http)
    titles = [member["title"] for member in members]
    imageinfo_by_title = _resolve_file_info(http, titles)
    extracted_at_utc = datetime.now(UTC).isoformat()

    rows = []
    for title in titles:
        parsed = _parse_title(title)
        imageinfo = imageinfo_by_title.get(title)
        if parsed is None or imageinfo is None:
            continue
        pokedex_number_raw, form_suffix_raw = parsed
        local_cache_path = _local_cache_path(pokedex_number_raw, form_suffix_raw)
        dest_path = cache_dir / local_cache_path
        sha1 = imageinfo.get("sha1", "")
        if not (skip_existing and dest_path.exists() and _sha1_of(dest_path) == sha1):
            _download_image(http, imageinfo["url"], dest_path)

        rows.append(
            {
                "bulbagarden_title": title,
                "pokedex_number_raw": pokedex_number_raw,
                "form_suffix_raw": form_suffix_raw or "",
                "image_kind": "menu_sprite",
                "local_cache_path": local_cache_path,
                "sha1": sha1,
                "width": imageinfo.get("width", ""),
                "height": imageinfo.get("height", ""),
                "mime_type": imageinfo.get("mime", ""),
                "file_size_bytes": imageinfo.get("size", ""),
                "source_name": SOURCE_NAME,
                "source_url": imageinfo["url"],
                "source_record_id": title,
                "extracted_at_utc": extracted_at_utc,
                "dataset_version": dataset_version,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _sha1_of(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()
