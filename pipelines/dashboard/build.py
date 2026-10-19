"""Builds the static analytics dashboard site (docs/dashboard/) from
data/marts/*.csv, per docs/prd.md's M6 milestone.

The dashboard is a self-contained static HTML/CSS/vanilla-JS page (no
charting library, no backend, no build tooling) so it can be hosted for
free on GitHub Pages — see docs/dashboard.md.

The payload is split in two. The critical keys (KPIs, sprite/hero/icon
maps, display names — see _CRITICAL_PAYLOAD_KEYS) are baked into the page
as an inline `window.DASHBOARD_DATA = {...}` assignment, so the header, the
KPI row and the Overview tab render with no network round-trip at all. The
marts, which are ~8MB, go only into the sibling data.json that static/app.js
fetches on the first activation of a tab that needs them. Inlining
everything used to make index.html an 8MB file whose first paint blocked on
parsing all of it. The cost of the split is that fetch() is blocked over
file://, so opening index.html by double-clicking now shows the header and
Overview but reports a load error on the deeper tabs; app.js names the fix
(serve the directory) in that message.

Pokémon sprites, hero art, move-type icons, and item icons are copied/resolved
alongside the HTML into output_dir/images/ (see pipelines/dashboard/
sprites.py and pipelines/render/assets.py) rather than inlined as base64,
to keep the committed HTML file small and its diffs readable. Species
sprites and type icons are purely local file copies (offline); item icons
are the one part of a dashboard build that needs network access, since
item names are data-dependent and not practical to bundle in advance — see
the fetch_icons parameter below.

The Team Builder tab's Pro Team Gallery (curated real tournament teams
rendered as broadcast-style cards) is likewise a local file copy, not a
network fetch or a Playwright render at build time — see
_load_reference_teams and docs/dashboard.md's "Pro Team Gallery" section
for how those card PNGs are produced ahead of time.
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape

from pipelines.dashboard import data, sprites
from pipelines.regulations import Regulation
from pipelines.render import assets as render_assets
from pipelines.render import bulbagarden_items
from pipelines.render import template as render_template

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_ICONS_DIR = STATIC_DIR / "icons"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "dashboard"
DEFAULT_ITEM_ICON_CACHE_DIR = REPO_ROOT / "data" / "assets" / "dashboard_icons"
DEFAULT_REFERENCE_TEAMS_DIR = REPO_ROOT / "data" / "reference_teams"


def _make_environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def _safe_json(payload: dict[str, Any]) -> str:
    # Guard against a stray "</script>" in the data breaking out of the
    # inline <script> block it's embedded in.
    return json.dumps(payload, default=str).replace("<", "\\u003c")


# Everything except "marts". These are the keys the page header, the KPI
# row and the Overview tab render from, plus the sprite/hero/icon/display-
# name lookups every other tab needs the moment its rows arrive — a few
# hundred KB in total, against ~8MB for the marts. Inlining this much and
# fetching the rest is what lets the page paint immediately instead of
# blocking on an 8MB JSON parse (see static/app.js's ensureData).
_CRITICAL_PAYLOAD_KEYS = (
    "generated_at_utc",
    "kpis",
    "provenance",
    "sprites",
    "hero_art",
    "type_icons",
    "type_colors",
    "item_icons",
    "pokemon_names",
    "reference_teams",
    "regulations",
    "kpis_by_scope",
    "default_scope",
    "min_default_scope_teams",
    "mart_files",
    "share_cards",
    "site",
)

# The marts are split into shards so the page downloads only what the view
# in front of it needs (docs/upgrade-plan-2026q4.md, B7). Once marts gained
# a regulation_scope partition, one data.json holding everything reached
# 22MB, most of it rows for scopes or tabs the viewer never opens.
#   data/core.json            unscoped marts the common tabs read
#   data/scope-<scope>.json   one regulation's rows of every scoped mart
#   data/<mart>.json          the largest unscoped marts, each fetched only
#                             by the tab that reads it (registerTab's
#                             extraMarts in static/app.js)
# The page's scripts, in load order (templates/index.html.jinja's <script>
# tags). Each is copied verbatim next to index.html.
SCRIPT_NAMES = ("app.js", "matchup.js", "teams.js", "expansions.js", "events.js")

SHARD_DIR = "data"
ON_DEMAND_MARTS = (
    "pokemon_head_to_head",
    "pokemon_team_core_triple_usage",
    "player_signature_pokemon",
    # Event-, team- and player-grain marts (docs/upgrade-plan-2027q1.md,
    # C1-C4): only the event, team, player and Builder views and the
    # event-window filter read them. Keeping them out of core.json holds
    # the core payload under its 500KB budget (tests/browser).
    "pokemon_event_usage_vs_regulation",
    "tournament_team_results",
    "tournament_team_sheets",
    "team_list_sheets",
    "player_archetype_record",
)


def _write_mart_shards(
    marts: dict[str, list[dict[str, Any]]],
    scopes: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    """Writes the mart shards under output_dir/data/ and returns their
    index ({"core": path, "scopes": {scope: path}, "on_demand": {mart:
    path}}), paths relative to output_dir. Stale shards from a previous
    build (a scope or mart that no longer exists) are removed first."""
    shard_dir = output_dir / SHARD_DIR
    shard_dir.mkdir(parents=True, exist_ok=True)
    for stale in shard_dir.glob("*.json"):
        stale.unlink()

    # Display-name columns (pokemon_name, partner_pokemon_name, ...) repeat
    # one of a few hundred names on every row, and the page already holds
    # the full pokemon_key -> name map inline. They are dropped from the
    # shard files and restored client-side from "name_fields" (static/
    # app.js's fetchShard), which keeps the core payload within its budget.
    name_fields = [name for _key, name in data.NAME_JOINS]

    def without_names(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{k: v for k, v in row.items() if k not in name_fields} for row in rows]

    def write(name: str, content: dict[str, Any]) -> str:
        slim = {mart: without_names(rows) for mart, rows in content.items()}
        (shard_dir / f"{name}.json").write_text(json.dumps(slim, default=str), encoding="utf-8")
        return f"{SHARD_DIR}/{name}.json"

    scoped_names = [n for n, rows in marts.items() if rows and "regulation_scope" in rows[0]]
    core = {
        name: rows
        for name, rows in marts.items()
        if name not in scoped_names and name not in ON_DEMAND_MARTS
    }
    index: dict[str, Any] = {
        "core": write("core", core),
        "scopes": {},
        "on_demand": {},
        "name_fields": [list(pair) for pair in data.NAME_JOINS],
    }
    for scope in scopes:
        index["scopes"][scope] = write(
            f"scope-{scope}",
            {
                name: [r for r in marts[name] if r.get("regulation_scope") == scope]
                for name in scoped_names
            },
        )
    for name in ON_DEMAND_MARTS:
        if name in marts:
            index["on_demand"][name] = write(name, {name: marts[name]})
    return index


def _asset_coverage(payload: dict[str, Any], referenced_keys: set[str]) -> list[dict[str, Any]]:
    """How much of the imagery the marts reference actually resolved.

    Reported per asset kind as resolved/referenced, so a partial sprite
    cache or a run of unresolvable item names is visible on the page rather
    than only as silently text-only cells.
    """
    distinct_items = {
        row["item_name"]
        for row in payload["marts"].get("pokemon_item_usage", [])
        if row.get("item_name")
    }
    return [
        {
            "asset": "Menu sprites",
            "resolved": len(payload.get("sprites", {})),
            "referenced": len(referenced_keys),
        },
        {
            "asset": "Hero art",
            "resolved": len(payload.get("hero_art", {})),
            "referenced": len(referenced_keys),
        },
        {
            "asset": "Item icons",
            "resolved": len(payload.get("item_icons", {})),
            "referenced": len(distinct_items),
        },
        {
            "asset": "Type icons",
            "resolved": len(payload.get("type_icons", {})),
            "referenced": 18,
        },
    ]


# The published site's address: Open Graph tags need absolute URLs.
SITE_URL = "https://lancettlim.github.io/pokemon-agent/dashboard/"


def _load_share_cards(output_dir: Path) -> dict[str, Any]:
    """The manifest `render-share-cards` writes (pipelines/render/
    share_cards.py), or {} when it hasn't run: the site then shows no
    download buttons and no Open Graph image."""
    path = output_dir / "images" / "cards" / "manifest.json"
    if not path.exists():
        return {}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    # Only cards whose PNG is actually there.
    manifest["teams"] = {
        k: v for k, v in (manifest.get("teams") or {}).items() if (output_dir / v).exists()
    }
    manifest["whats_changed"] = {
        k: v for k, v in (manifest.get("whats_changed") or {}).items() if (output_dir / v).exists()
    }
    if manifest.get("og_image") and not (output_dir / manifest["og_image"]).exists():
        manifest["og_image"] = None
    return manifest


def _site_meta(payload: dict[str, Any]) -> dict[str, Any]:
    """Open Graph title/description for link unfurls (docs/upgrade-plan-
    2027q1.md, C4), refreshed on every build from the default regulation's
    headline: "Reg M-C: Rillaboom leads at 8.7% of roster slots across
    3,770 teams from 5 events."""
    kpis = payload.get("kpis") or {}
    scope = payload.get("default_scope") or data.ALL_SCOPE
    label = "All regulations" if scope == data.ALL_SCOPE else f"Reg {scope.upper()}"
    top = kpis.get("top_used_pokemon")
    description = f"{label}: usage, real sets, events and teams from Pokémon Champions tournaments."
    if top and top.get("usage_share") is not None:
        description = (
            f"{label}: {top.get('pokemon_name')} leads at {top['usage_share'] * 100:.1f}% of "
            f"roster slots across {kpis.get('team_count') or 0:,} teams from "
            f"{kpis.get('event_count') or 0} events. Real sets, event pages and a team builder."
        )
    og_image = (payload.get("share_cards") or {}).get("og_image")
    return {
        "url": SITE_URL,
        "title": f"Pokémon Champions Data — {label}",
        "description": description,
        "og_image": SITE_URL + og_image if og_image else None,
    }


def _critical_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """The subset of the payload inlined into index.html. Missing keys are
    skipped rather than defaulted, so this stays correct if build() ever
    stops producing one."""
    return {key: payload[key] for key in _CRITICAL_PAYLOAD_KEYS if key in payload}


def _referenced_pokemon_keys(marts: dict[str, list[dict[str, Any]]]) -> set[str]:
    keys: set[str] = set()
    for rows in marts.values():
        for row in rows:
            if row.get("pokemon_key"):
                keys.add(row["pokemon_key"])
            if row.get("partner_pokemon_key"):
                keys.add(row["partner_pokemon_key"])
            if row.get("pokemon_keys"):
                keys.update(row["pokemon_keys"].split("|"))
    return keys


def _type_colors() -> dict[str, str]:
    """The 18 per-type accent colors, as {type_name: hex}.

    Imported from pipelines/render/template.py rather than restated here so
    the dashboard and the team-card renderer stay one palette, not two that
    drift. The None key that module uses for its own "unknown type"
    fallback is dropped: the dashboard's fallback is a CSS var default at
    the point of use, and a null JSON key would be meaningless to the
    template anyway.
    """
    return {name: value for name, value in render_template.TYPE_COLORS.items() if name}


def _copy_type_icons(output_dir: Path) -> dict[str, str]:
    """Copies the 18 committed move-type icons (pipelines/dashboard/static/
    icons/types/) into output_dir/images/icons/types/ and returns a
    {type_name: "images/icons/types/<type>.png"} map. Purely a local file
    copy — no network access, since types never change."""
    dest_dir = output_dir / "images" / "icons" / "types"
    dest_dir.mkdir(parents=True, exist_ok=True)
    resolved: dict[str, str] = {}
    source_dir = STATIC_ICONS_DIR / "types"
    if not source_dir.exists():
        return resolved
    for source_path in sorted(source_dir.glob("*.png")):
        shutil.copyfile(source_path, dest_dir / source_path.name)
        resolved[source_path.stem] = f"images/icons/types/{source_path.name}"
    return resolved


def _resolve_item_icons(
    marts: dict[str, list[dict[str, Any]]],
    *,
    output_dir: Path,
    icon_cache_dir: Path,
    fetch_icons: bool,
) -> dict[str, str]:
    """Resolves an icon for each distinct item_name in pokemon_item_usage,
    preferring pipelines.render.bulbagarden_items.ensure_item_icon_bulbagarden
    (Bulbagarden Archives held-item sprites) and falling back to
    pipelines.render.assets.ensure_item_icon (PokéAPI community sprites) on
    a per-item resolution miss, both cached under icon_cache_dir. Copies
    whichever source resolved into output_dir/images/icons/items/. Returns
    a {item_name: relative_path} map of what succeeded; unresolved items
    are simply absent, degrading to a text-only item name in the UI. When
    fetch_icons is False (offline builds, tests), no network calls are
    made and this returns {}."""
    item_names = sorted(
        {row["item_name"] for row in marts.get("pokemon_item_usage", []) if row.get("item_name")}
    )
    if not item_names or not fetch_icons:
        return {}

    dest_dir = output_dir / "images" / "icons" / "items"
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Prune by name before repopulating, the same discipline sprites.py
    # applies to images/ (backlog.md #47) — without it, icons for items
    # that have dropped out of the usage mart accumulate in git build after
    # build. Not an rmtree: this directory is a sibling of others that
    # build.py populates independently.
    for stale_icon in dest_dir.glob("*"):
        if stale_icon.is_file():
            stale_icon.unlink()

    resolved: dict[str, str] = {}
    session = requests.Session()
    for item_name in item_names:
        source_path = bulbagarden_items.ensure_item_icon_bulbagarden(
            item_name, cache_dir=icon_cache_dir, session=session
        )
        if not source_path or not source_path.exists():
            source_path = render_assets.ensure_item_icon(
                item_name, cache_dir=icon_cache_dir, session=session
            )
        if not source_path or not source_path.exists():
            continue
        dest_path = dest_dir / source_path.name
        shutil.copyfile(source_path, dest_path)
        resolved[item_name] = f"images/icons/items/{source_path.name}"
    return resolved


def _load_reference_teams(output_dir: Path, reference_teams_dir: Path) -> list[dict[str, Any]]:
    """Pro Team Gallery feed (Team Builder tab): reads curated real-team
    metadata from reference_teams_dir/reference_teams.json and copies each
    entry's pre-rendered card PNG (reference_teams_dir/cards/<file>) into
    output_dir/images/reference_teams/. Cards are pre-rendered ahead of
    time via `render-card` (see docs/dashboard.md's "Pro Team Gallery"
    section) -- this function only copies already-built PNGs, so a
    dashboard build never needs Playwright/Chromium itself. Degrades to []
    (not an error) if the directory or metadata file doesn't exist yet,
    matching every other mart/asset's missing-input behavior."""
    metadata_path = reference_teams_dir / "reference_teams.json"
    if not metadata_path.exists():
        return []

    entries = json.loads(metadata_path.read_text(encoding="utf-8"))
    dest_dir = output_dir / "images" / "reference_teams"
    dest_dir.mkdir(parents=True, exist_ok=True)

    resolved: list[dict[str, Any]] = []
    for entry in entries:
        entry = dict(entry)
        card_image = entry.get("card_image")
        if card_image:
            source_path = reference_teams_dir / "cards" / card_image
            if source_path.exists():
                shutil.copyfile(source_path, dest_dir / source_path.name)
                entry["card_image"] = f"images/reference_teams/{source_path.name}"
            else:
                entry["card_image"] = None
        resolved.append(entry)
    return resolved


def build(
    *,
    marts_dir: Path = data.DEFAULT_MARTS_DIR,
    normalized_dir: Path = data.DEFAULT_NORMALIZED_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    asset_cache_dir: Path = sprites.DEFAULT_ASSET_CACHE_DIR,
    artwork_cache_dir: Path = sprites.DEFAULT_ARTWORK_CACHE_DIR,
    item_icon_cache_dir: Path = DEFAULT_ITEM_ICON_CACHE_DIR,
    reference_teams_dir: Path = DEFAULT_REFERENCE_TEAMS_DIR,
    fetch_icons: bool = True,
    regulations: list[Regulation] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Renders templates/index.html.jinja with the marts payload baked in,
    copies static/app.js alongside it, and populates output_dir/images/
    with Pokémon sprites, move-type icons, and item icons. Returns the
    payload that was rendered (including the sprite/icon maps).

    fetch_icons controls whether item icons are fetched over the network
    (see _resolve_item_icons); pass False for offline/test builds.
    regulations/today override the regulation registry and build date, for
    tests that exercise a regulation rollover.
    """
    payload = data.build_payload(marts_dir, normalized_dir, regulations=regulations, today=today)

    referenced_keys = _referenced_pokemon_keys(payload["marts"])
    payload["sprites"] = sprites.copy_sprites(
        referenced_keys,
        output_dir=output_dir,
        normalized_dir=normalized_dir,
        asset_cache_dir=asset_cache_dir,
    )
    payload["hero_art"] = sprites.copy_hero_art(
        referenced_keys,
        output_dir=output_dir,
        normalized_dir=normalized_dir,
        artwork_cache_dir=artwork_cache_dir,
    )
    payload["type_icons"] = _copy_type_icons(output_dir)
    payload["type_colors"] = _type_colors()
    payload["item_icons"] = _resolve_item_icons(
        payload["marts"],
        output_dir=output_dir,
        icon_cache_dir=item_icon_cache_dir,
        fetch_icons=fetch_icons,
    )
    payload["reference_teams"] = _load_reference_teams(output_dir, reference_teams_dir)
    payload["share_cards"] = _load_share_cards(output_dir)
    payload["site"] = _site_meta(payload)
    # Asset coverage is only knowable here, after the copies have run: it's
    # the ratio of what actually resolved to what the marts reference. The
    # Data & Sources tab reports it alongside the dbt release gates so the
    # imagery has the same visible accounting as the numbers do.
    payload["provenance"]["asset_coverage"] = _asset_coverage(payload, referenced_keys)

    payload["mart_files"] = _write_mart_shards(
        payload["marts"], payload["kpis_by_scope"], output_dir
    )

    env = _make_environment()
    template = env.get_template("index.html.jinja")
    html = template.render(payload=payload, data_json=_safe_json(_critical_payload(payload)))

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    for script_name in SCRIPT_NAMES:
        shutil.copyfile(STATIC_DIR / script_name, output_dir / script_name)
    # backlog.md #32's JSON feed: data.json carries every non-mart key plus
    # `mart_files`, the index of the shard files holding the marts (see
    # _write_mart_shards). Together they are the complete payload, still
    # scriptable with curl/jq or a notebook without re-running dbt.
    feed = {key: value for key, value in payload.items() if key != "marts"}
    (output_dir / "data.json").write_text(json.dumps(feed, default=str), encoding="utf-8")

    return payload
