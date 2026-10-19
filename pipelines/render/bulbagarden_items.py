"""Bulbagarden-sourced held-item icon resolution, with a PokéAPI fallback.

Like pipelines/render/assets.py's type/item icons, these are
rendering-support assets, not dataset entities — no provenance row, no
dataset_version, no release gate (see docs/dataset-spec.md's
"pokemon_asset" entity, the actual dataset entity for Pokémon sprites).

Bulbagarden Archives — the same MediaWiki wiki pipelines/extract/
bulbagarden.py sources Champions-menu species sprites from — also hosts
held-item artwork. The classic "File:Bag <Item Name> Sprite.png" is a
24x24 pixel sprite that turns into a blocky smear once a dashboard tile
scales it up, so the 160x160 smooth renders from the newest games are
tried first: "Bag <Item Name> ZA Sprite.png" (Legends: Z-A, which carries
the Mega Stones Champions brings back), then the Scarlet/Violet "SV"
variant, then the Dream World art. The pixel sprite is only a fallback
for an item none of those cover. Unlike the species
sprite extractor, there's no single category listing every item to page
through ahead of time, so this resolves one item at a time: it queries
prop=imageinfo for a small set of guessed title variants (MediaWiki
accepts multiple `|`-joined titles per call, same batching technique
bulbagarden.py's _resolve_file_info uses) and takes the first one that
resolves to a real file.

Not every item's naming variant has been independently verified — callers
must fall back to pipelines.render.assets.ensure_item_icon (PokéAPI) on a
resolution miss (see pipelines/dashboard/build.py's _resolve_item_icons),
the same graceful-degradation convention every other icon/sprite helper in
this codebase follows.

Cached under a "bulbagarden_items_hd/" subdirectory of cache_dir, distinct
from pipelines.render.assets.ensure_item_icon's "items/" subdirectory —
sharing one cache path between the two sources would let a PokéAPI
fallback silently poison the cache slot a later, successful Bulbagarden
lookup should have filled. The "_hd" suffix also keeps a cache filled by
the old pixel-sprite-first lookup from being served as if it were current.
"""

from __future__ import annotations

from pathlib import Path

import requests

API_BASE_URL = "https://archives.bulbagarden.net/w/api.php"


def _title_candidates(item_name: str) -> list[str]:
    """Naming variants to try, sharpest first: the 160px Z-A and SV bag
    renders and the Dream World art, then the 24px "Bag <Item Name>
    Sprite.png" pixel sprite, then two fallbacks for items that follow
    none of those conventions."""
    name = item_name.strip()
    return [
        f"File:Bag {name} ZA Sprite.png",
        f"File:Bag {name} SV Sprite.png",
        f"File:Dream {name} Sprite.png",
        f"File:Bag {name} Sprite.png",
        f"File:{name} Sprite.png",
        f"File:{name}.png",
    ]


def _slugify(item_name: str) -> str:
    return item_name.strip().lower().replace(" ", "-").replace("'", "")


def _api_get(session: requests.Session, params: dict) -> dict:
    response = session.get(API_BASE_URL, params={**params, "format": "json"}, timeout=30)
    response.raise_for_status()
    return response.json()


def _resolve_url(session: requests.Session, item_name: str) -> str | None:
    """Returns the first candidate title's resolved CDN image URL, or None
    if none of the candidates are real Bulbagarden files."""
    candidates = _title_candidates(item_name)
    payload = _api_get(
        session,
        {
            "action": "query",
            "titles": "|".join(candidates),
            "prop": "imageinfo",
            "iiprop": "url",
        },
    )
    url_by_title: dict[str, str] = {}
    for page in payload.get("query", {}).get("pages", {}).values():
        imageinfo = page.get("imageinfo")
        if imageinfo:
            url_by_title[page["title"]] = imageinfo[0]["url"]
    for title in candidates:
        if title in url_by_title:
            return url_by_title[title]
    return None


def ensure_item_icon_bulbagarden(
    item_name: str,
    *,
    cache_dir: Path,
    session: requests.Session | None = None,
) -> Path | None:
    """Return a local cached path to item_name's Bulbagarden icon,
    downloading it on a cache miss. Returns None (rather than raising) if
    no candidate title resolves to a real file, or the lookup/download
    fails — the caller (pipelines/dashboard/build.py's
    _resolve_item_icons) falls back to the PokéAPI-sourced icon in that
    case, so a bad/missing Bulbagarden entry doesn't remove an item's icon
    outright."""
    dest_path = cache_dir / "bulbagarden_items_hd" / f"{_slugify(item_name)}.png"
    if dest_path.exists():
        return dest_path

    http = session if session is not None else requests.Session()
    try:
        url = _resolve_url(http, item_name)
        if url is None:
            return None
        response = http.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException:
        return None

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(response.content)
    return dest_path
