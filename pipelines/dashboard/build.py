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

import hashlib
import json
import shutil
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape

from pipelines.dashboard import data, dictionary, graph, sprites
from pipelines.regulations import Regulation
from pipelines.render import assets as render_assets
from pipelines.render import bulbagarden_items
from pipelines.render import template as render_template
from pipelines.render import type_glyphs

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_ICONS_DIR = STATIC_DIR / "icons"
STATIC_FONTS_DIR = STATIC_DIR / "fonts"
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
    "localised_names",
    "form_species",
    "reference_teams",
    "regulations",
    "kpis_by_scope",
    "default_scope",
    "scope_regulations",
    "min_default_scope_teams",
    "mart_files",
    "share_cards",
    "site",
    "type_glyphs",
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
#   data/<mart>-<scope>.json  large scoped marts only one tab reads, split
#                             per scope and fetched on demand like the
#                             above, but only the selected scope's file
# The page's scripts, in load order (templates/index.html.jinja's <script>
# tags). Each is copied verbatim next to index.html.
SCRIPT_NAMES = (
    "app.js",
    "matchup.js",
    "teams.js",
    "expansions.js",
    "events.js",
    "players.js",
    "ladder.js",
    "search.js",
    # Not a <script> tag: app.js loads it when the Meta Graph first opens
    # (LAZY_TAB_SCRIPTS), keeping it out of the first view's budget.
    "graph.js",
)

SHARD_DIR = "data"
ON_DEMAND_MARTS = (
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
    "player_index",
    # docs/upgrade-plan-2027q2.md: team share widened the usage marts, so
    # two more single-view marts left core.json to hold its budget: the
    # Players tab's region view and Top Teams' converged lists.
    "pokemon_usage_by_country",
    "team_list_convergence",
    # The Mega usage panel (E3), on event pages and the Usage tab's Megas
    # view; one file holds every scope's and event's rows.
    "mega_stone_usage",
    "team_mega_count",
    # The Events tab's online list (docs/upgrade-plan-2027q2.md, S1) and
    # its upcoming tournaments (list #31).
    "online_event_summary",
    "online_upcoming_events",
    # Event pages' Day 2 conversion, bracket and paths (E1, E2). The board's
    # Day 2 switch reads the inline KPIs instead.
    "pokemon_event_phase_usage",
    "tournament_top_cut_matches",
    "tournament_top_cut_paths",
    # The Showdown ladder lens (S2): the Usage tab's Ladder view and the
    # profile's Checks and counters and Stat Point spreads panels.
    "ladder_pokemon_usage",
    "ladder_checks_counters",
    "ladder_stat_point_spreads",
    # Showdown ladder replays (S3): bring rates and lead pairs on the Ladder
    # view, a bring line on the profile.
    "ladder_bring_rate",
    "ladder_lead_pairs",
    # The Archetypes tab's matchup heatmap (list #30).
    "archetype_matchups",
)
# Scoped, and read only by Matchup and the Graph view (docs/plan-synergy-
# checks-graph.md): head-to-head became scoped in G1, which multiplied its
# rows by the number of scopes, and the matchup summary with it, which
# would otherwise ride in every scope file and break the core budget.
SCOPED_ON_DEMAND_MARTS = (
    "pokemon_head_to_head",
    "pokemon_matchup_summary",
    "pokemon_check_edges",
    "pokemon_graph",
)

# Per-move, per-item and per-ability details (type, power, effect text...)
# repeat on every Pokémon's row in the usage marts. The shards carry them
# once, as <details> marts in core.json, and static/app.js joins them back
# onto the rows ("detail_joins"): about 20KB off every regulation shard,
# which keeps the first view inside its 500KB budget (tests/browser).
#   mart -> (key column, details mart, detail columns)
DETAIL_SPLITS = {
    "pokemon_move_usage": (
        "move_name",
        "move_details",
        ("move_type", "power", "accuracy", "category", "priority", "pp", "short_effect"),
    ),
    "pokemon_item_usage": ("item_name", "item_details", ("short_effect",)),
    "pokemon_ability_usage": ("ability", "ability_details", ("short_effect",)),
}

# Marts the build summarises into the inline payload and no view reads raw:
# kept out of every shard file. pokemon_regulation_movers feeds "What
# changed" through compute_kpis' summarize_movers; pokemon_localised_names
# becomes the inline localised_names maps (data.localised_names).
BUILD_ONLY_MARTS = ("pokemon_regulation_movers", "pokemon_localised_names")


def _write_service_worker(output_dir: Path, payload: dict[str, Any]) -> None:
    """Offline at the venue (docs/upgrade-plan-2027q2.md, Q5): static/sw.js
    with its precache list (the page, scripts, font, the core shard and the
    default regulation's shard) and a build id hashed from those files, so a
    rebuild that changes none of them keeps visitors' caches."""
    files = payload.get("mart_files") or {}
    default_shard = (files.get("scopes") or {}).get(payload.get("default_scope"))
    precache = ["./", "index.html", *SCRIPT_NAMES]
    precache += sorted(f"fonts/{path.name}" for path in (output_dir / "fonts").glob("*.woff2"))
    precache += [path for path in (files.get("core"), default_shard) if path]
    # index.html embeds the build time, so it is hashed as its inline
    # payload without that, beside the other files' bytes.
    critical = {k: v for k, v in _critical_payload(payload).items() if k != "generated_at_utc"}
    digest = hashlib.sha1(json.dumps(critical, sort_keys=True, default=str).encode("utf-8"))
    digest.update((TEMPLATES_DIR / "index.html.jinja").read_bytes())
    for path in precache[2:]:
        file = output_dir / path
        if file.exists():
            digest.update(file.read_bytes())
    source = (STATIC_DIR / "sw.js").read_text(encoding="utf-8")
    source = source.replace("__BUILD_ID__", digest.hexdigest()[:12]).replace(
        "__PRECACHE__", json.dumps(precache)
    )
    (output_dir / "sw.js").write_text(source, encoding="utf-8")


def _write_mart_shards(
    marts: dict[str, list[dict[str, Any]]],
    scopes: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    """Writes the mart shards under output_dir/data/ and returns their
    index ({"core": path, "scopes": {scope: path}, "on_demand": {mart:
    path}, "on_demand_scoped": {mart: {scope: path}}}), paths relative to
    output_dir. Stale shards from a previous
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

    def without_details(mart: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if mart not in DETAIL_SPLITS:
            return rows
        drop = DETAIL_SPLITS[mart][2]
        return [{k: v for k, v in row.items() if k not in drop} for row in rows]

    def write(name: str, content: dict[str, Any]) -> str:
        slim = {mart: without_details(mart, without_names(rows)) for mart, rows in content.items()}
        (shard_dir / f"{name}.json").write_text(json.dumps(slim, default=str), encoding="utf-8")
        return f"{SHARD_DIR}/{name}.json"

    # A scoped mart is split across the scope files unless it's on-demand:
    # those load whole, with the page that needs them, and copying one into
    # every scope file too would put it in the default view's download.
    on_demand = set(ON_DEMAND_MARTS) | set(SCOPED_ON_DEMAND_MARTS)
    scoped_names = [
        n
        for n, rows in marts.items()
        if rows
        and "regulation_scope" in rows[0]
        and n not in on_demand
        and n not in BUILD_ONLY_MARTS
    ]
    core = {
        name: rows
        for name, rows in marts.items()
        if name not in scoped_names and name not in on_demand and name not in BUILD_ONLY_MARTS
    }
    detail_joins = []
    for mart, (key, details_mart, fields) in DETAIL_SPLITS.items():
        details: dict[Any, dict[str, Any]] = {}
        for row in marts.get(mart, []):
            if row.get(key) is not None and row[key] not in details:
                details[row[key]] = {key: row[key], **{f: row.get(f) for f in fields}}
        if details:
            core[details_mart] = list(details.values())
            detail_joins.append([mart, key, details_mart, list(fields)])
    index: dict[str, Any] = {
        "core": write("core", core),
        "scopes": {},
        "on_demand": {},
        "on_demand_scoped": {},
        "build_only": [name for name in BUILD_ONLY_MARTS if name in marts],
        "name_fields": [list(pair) for pair in data.NAME_JOINS],
        "detail_joins": detail_joins,
    }
    # A population scope ("m-c:online", docs/upgrade-plan-2027q2.md, S1)
    # whose rows a mart doesn't have (player records are official-only)
    # carries the official scope's rows instead, listed under
    # official_fallback so the page labels them; static/app.js's
    # applyRegulationScope reads them under the official scope.
    # An on-demand mart loads whole, so it only needs listing.
    index["official_fallback"] = {}
    scoped_on_demand = [
        n for n in ON_DEMAND_MARTS if marts.get(n) and "regulation_scope" in marts[n][0]
    ]
    for scope in scopes:
        content = {}
        population_scope = data.scope_population(scope) != data.OFFICIAL
        official = data.scope_regulation(scope)
        for name in scoped_names + scoped_on_demand:
            rows = [r for r in marts[name] if r.get("regulation_scope") == scope]
            if not rows and population_scope:
                rows = [r for r in marts[name] if r.get("regulation_scope") == official]
                if rows:
                    index["official_fallback"].setdefault(scope, []).append(name)
            if name in scoped_names:
                content[name] = rows
        index["scopes"][scope] = write(f"scope-{scope.replace(':', '-')}", content)
    for name in ON_DEMAND_MARTS:
        if name in marts:
            index["on_demand"][name] = write(name, {name: marts[name]})
    # One file per scope. Head-to-head and check edges are official-only
    # (RK9 pairings), so a population scope falls back to its official
    # rows, listed under official_fallback like the scope files above.
    for name in SCOPED_ON_DEMAND_MARTS:
        if name not in marts:
            continue
        index["on_demand_scoped"][name] = {}
        for scope in scopes:
            rows = [r for r in marts[name] if r.get("regulation_scope") == scope]
            if not rows and data.scope_population(scope) != data.OFFICIAL:
                official = data.scope_regulation(scope)
                rows = [r for r in marts[name] if r.get("regulation_scope") == official]
                if rows:
                    index["official_fallback"].setdefault(scope, []).append(name)
            index["on_demand_scoped"][name][scope] = write(
                f"{name}-{scope.replace(':', '-')}", {name: rows}
            )
    return index


def _build_graphs(marts_dir: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """The Graph view's per-scope graphs (pipelines/dashboard/graph.py).
    Reads the full pokemon_team_synergy mart rather than the payload's
    copy, which is sliced by lift: the graph keeps each node's edges by
    synergy_z instead."""
    marts = payload["marts"]
    return graph.build_graphs(
        data.load_mart(marts_dir, "pokemon_team_synergy", sliced=False),
        marts.get("pokemon_check_edges", []),
        marts.get("pokemon_usage_summary", []),
        {
            scope: (kpis or {}).get("team_count") or 0
            for scope, kpis in payload["kpis_by_scope"].items()
        },
        marts.get("detected_archetype_summary", []),
    )


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
    # Top 12 cards (V8): {"regulation"|"event": {key: {phase: {layout: path}}}}.
    top12 = manifest.get("top12") or {}
    manifest["top12"] = {
        kind: {
            key: {
                phase: {
                    layout: path for layout, path in layouts.items() if (output_dir / path).exists()
                }
                for phase, layouts in phases.items()
            }
            for key, phases in (top12.get(kind) or {}).items()
        }
        for kind in ("regulation", "event")
    }
    if manifest.get("og_image") and not (output_dir / manifest["og_image"]).exists():
        manifest["og_image"] = None
    return manifest


def _site_meta(payload: dict[str, Any]) -> dict[str, Any]:
    """Open Graph title/description for link unfurls (docs/upgrade-plan-
    2027q1.md, C4), refreshed on every build from the default regulation's
    headline, in team share (docs/upgrade-plan-2027q2.md, V1): "Reg M-C:
    Rillaboom is on 51.9% of 3,770 teams from 5 events."""
    kpis = payload.get("kpis") or {}
    scope = payload.get("default_scope") or data.ALL_SCOPE
    regulation = data.scope_regulation(scope)
    label = "All regulations" if regulation == data.ALL_SCOPE else f"Reg {regulation.upper()}"
    if data.scope_population(scope) == data.ONLINE:
        label += " online"
    top = kpis.get("top_used_pokemon")
    description = f"{label}: usage, real sets, events and teams from Pokémon Champions tournaments."
    if top and top.get("team_share") is not None:
        description = (
            f"{label}: {top.get('pokemon_name')} is on {top['team_share'] * 100:.1f}% of "
            f"{kpis.get('team_count') or 0:,} teams from {kpis.get('event_count') or 0} events. "
            "Real sets, event pages and a team builder."
        )
    og_image = (payload.get("share_cards") or {}).get("og_image")
    return {
        "url": SITE_URL,
        "title": f"Pokémon Champions Data — {label}",
        "description": description,
        "og_image": SITE_URL + og_image if og_image else None,
    }


def _embed_tile(tile: dict[str, Any]) -> dict[str, Any]:
    return {
        "k": tile.get("pokemon_key"),
        "n": tile.get("pokemon_name"),
        "s": tile.get("team_share"),
    }


def _embed_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """The embeddable widget's own payload (docs/upgrade-plan-2027q2.md,
    list #33): every regulation's Top 12 boards as the Overview shows them
    (All players, Day 2, Online), cut to key, name and team share, with
    their images and localised names. About 20KB, so the widget never
    loads the dashboard's shards."""
    kpis_by_scope = payload.get("kpis_by_scope") or {}
    boards: dict[str, dict[str, Any]] = {}
    keys: set[str] = set()
    for code in payload.get("scope_regulations") or []:
        entry: dict[str, Any] = {}
        official = (kpis_by_scope.get(code) or {}).get("top_12_boards") or {}
        online = (kpis_by_scope.get(data.population_scope(code, data.ONLINE)) or {}).get(
            "top_12_boards"
        ) or {}
        sources = dict(official)
        if "online" not in sources and online.get("all"):
            sources["online"] = online["all"]
        for board_id, board in sources.items():
            entry[board_id] = {
                "label": board.get("label"),
                "team_count": board.get("team_count"),
                "event_count": board.get("event_count"),
                **{
                    group: [_embed_tile(tile) for tile in board.get(group) or []]
                    for group in ("forms", "species")
                },
            }
            for group in ("forms", "species"):
                keys.update(t["k"] for t in entry[board_id][group] if t["k"])
        if entry:
            boards[code] = entry
    art = {**(payload.get("sprites") or {}), **(payload.get("hero_art") or {})}
    names = {
        language: {key: by_key[key] for key in sorted(keys) if key in by_key}
        for language, by_key in (payload.get("localised_names") or {}).items()
    }
    return {
        "generated_at_utc": payload.get("generated_at_utc"),
        "default_regulation": data.scope_regulation(payload.get("default_scope") or data.ALL_SCOPE),
        "site_url": SITE_URL,
        "boards": boards,
        "images": {key: art[key] for key in sorted(keys) if key in art},
        "names": names,
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
    manifests_dir: Path = dictionary.DEFAULT_MANIFESTS_DIR,
    item_icons: bool = True,
    hero_art_keys: Callable[[dict[str, Any]], set[str]] | None = None,
) -> dict[str, Any]:
    """Renders templates/index.html.jinja with the marts payload baked in,
    copies static/app.js alongside it, and populates output_dir/images/
    with Pokémon sprites, move-type icons, and item icons. Returns the
    payload that was rendered (including the sprite/icon maps).

    fetch_icons controls whether item icons are fetched over the network
    (see _resolve_item_icons); pass False for offline/test builds.
    regulations/today override the regulation registry and build date, for
    tests that exercise a regulation rollover; manifests_dir, where the
    Data section's release table cards are read from. item_icons=False
    leaves item icons out (items show as their names) and hero_art_keys,
    given the payload, narrows which Pokémon get hero art (the rest fall
    back to their sprite): pipelines/dashboard/artifact.py uses both to fit
    the claude.ai artifact's file limit.
    """
    payload = data.build_payload(marts_dir, normalized_dir, regulations=regulations, today=today)
    payload["marts"]["pokemon_graph"] = _build_graphs(marts_dir, payload)

    referenced_keys = _referenced_pokemon_keys(payload["marts"])
    payload["sprites"] = sprites.copy_sprites(
        referenced_keys,
        output_dir=output_dir,
        normalized_dir=normalized_dir,
        asset_cache_dir=asset_cache_dir,
    )
    hero_keys = (
        referenced_keys if hero_art_keys is None else referenced_keys & hero_art_keys(payload)
    )
    payload["hero_art"] = sprites.copy_hero_art(
        hero_keys,
        output_dir=output_dir,
        normalized_dir=normalized_dir,
        artwork_cache_dir=artwork_cache_dir,
    )
    payload["type_icons"] = _copy_type_icons(output_dir)
    payload["type_colors"] = _type_colors()
    # Our own white glyphs for the square type badge (V6), shared with the
    # share-card templates.
    payload["type_glyphs"] = type_glyphs.GLYPHS
    payload["item_icons"] = (
        _resolve_item_icons(
            payload["marts"],
            output_dir=output_dir,
            icon_cache_dir=item_icon_cache_dir,
            fetch_icons=fetch_icons,
        )
        if item_icons
        else {}
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
    # The Data section's dictionary and table cards (docs/upgrade-plan-
    # 2027q1.md, D2): generated here, from schema.yml and the newest
    # manifest, so they can't drift. One on-demand shard holds both.
    reference = {
        "data_dictionary": dictionary.mart_dictionary(
            payload["marts"],
            payload["mart_files"],
            hidden_columns=tuple(name for _key, name in data.NAME_JOINS),
        ),
        "release_tables": dictionary.release_tables(manifests_dir),
    }
    reference_path = f"{SHARD_DIR}/data_dictionary.json"
    (output_dir / reference_path).write_text(json.dumps(reference, default=str), encoding="utf-8")
    for name in reference:
        payload["mart_files"]["on_demand"][name] = reference_path

    env = _make_environment()
    template = env.get_template("index.html.jinja")
    html = template.render(payload=payload, data_json=_safe_json(_critical_payload(payload)))

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    # The embeddable Top 12 widget (list #33), beside the page.
    embed = env.get_template("embed.html.jinja").render(
        embed_json=_safe_json(_embed_payload(payload))
    )
    (output_dir / "embed.html").write_text(embed, encoding="utf-8")
    for script_name in SCRIPT_NAMES:
        shutil.copyfile(STATIC_DIR / script_name, output_dir / script_name)
    # The one self-hosted display font and its licence (docs/upgrade-plan-
    # 2027q2.md, D4), served from fonts/ beside the page.
    if STATIC_FONTS_DIR.exists():
        shutil.copytree(STATIC_FONTS_DIR, output_dir / "fonts", dirs_exist_ok=True)
    _write_service_worker(output_dir, payload)
    # backlog.md #32's JSON feed: data.json carries every non-mart key plus
    # `mart_files`, the index of the shard files holding the marts (see
    # _write_mart_shards). Together they are the complete payload, still
    # scriptable with curl/jq or a notebook without re-running dbt.
    feed = {key: value for key, value in payload.items() if key != "marts"}
    (output_dir / "data.json").write_text(json.dumps(feed, default=str), encoding="utf-8")

    return payload
