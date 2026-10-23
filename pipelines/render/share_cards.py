"""Pre-rendered share images for the dashboard (docs/upgrade-plan-2027q1.md,
C4): the newest event's top 8 as team-card PNGs, a 1200x630 "What changed"
card per regulation, and the Top 12 board as a card
(docs/upgrade-plan-2027q2.md, V8) in 16:9, 4:5 and 9:16, per regulation and
per event, for All players and Day 2. The default regulation's 16:9 Top 12
card is the site's Open Graph image.

This is a separate step from the dashboard build (`python -m pipelines.cli
render-share-cards`, run before `build-dashboard`) because it needs
Playwright's Chromium, which the dashboard build deliberately does not (see
pipelines/dashboard/build.py's docstring). It writes PNGs under
<output_dir>/images/cards/ plus a manifest.json the dashboard build reads;
without that manifest the site simply shows no download buttons.
"""

from __future__ import annotations

import base64
import io
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

from pipelines.dashboard import data as dashboard_data
from pipelines.dashboard import sprites as dashboard_sprites
from pipelines.render import data_source
from pipelines.render import template as card_template
from pipelines.render.type_glyphs import square_badge_html

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "dashboard"
CARDS_SUBDIR = Path("images") / "cards"
MANIFEST_NAME = "manifest.json"
# The published site's address, for the Open Graph image's absolute URL
# and the card footer.
SITE_URL = "https://lancettlim.github.io/pokemon-agent/dashboard/"
TOP_N = 8
MAX_MOVERS_ON_CARD = 5
# The Top 12 card's formats (V8): name -> (width, height). Landscape is the
# desktop board, the two portrait ones the phone board (band on top, three
# columns), for the share sheet's feed and story slots.
TOP12_FORMATS = {"landscape": (1920, 1080), "portrait": (1080, 1350), "story": (1080, 1920)}
TOP12_SIZE = 12
# The default regulation's cards and its events' come in every format; the
# other regulations' in 16:9 only, and older regulations' events get none,
# which keeps a rebuild to about forty PNGs rather than eighty.
MAX_TOP12_EVENTS = 8
TOP12_ART_PX = 320
FONT_PATH = REPO_ROOT / "pipelines" / "dashboard" / "static" / "fonts" / "oswald-latin-wght.woff2"
_PREINSTALLED_CHROMIUM = "/opt/pw-browsers/chromium"


def _short_regulation(code: str) -> str:
    return "All regulations" if code == dashboard_data.ALL_SCOPE else f"Reg {code.upper()}"


def _points(delta: float | None) -> str:
    if delta is None:
        return ""
    points = delta * 100
    return f"{'+' if points > 0 else ''}{points:.1f} pts"


def _plural(n: int | None, word: str) -> str:
    n = n or 0
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def _pct(share: float | None) -> str:
    return f"{(share or 0) * 100:.1f}%"


def regulation_top12(kpis: dict[str, Any], phase: str) -> list[dict[str, Any]]:
    """A regulation's Top 12 tiles for the card: the board the Overview
    shows (kpis' top_12_boards; 'all' or 'day2'), Forms grouping."""
    board = (kpis.get("top_12_boards") or {}).get(phase) or {}
    return [
        {
            "pokemon_key": tile["pokemon_key"],
            "name": tile.get("pokemon_name") or tile["pokemon_key"],
            "share": tile.get("team_share"),
            "type_1": tile.get("type_1"),
            "type_2": tile.get("type_2"),
        }
        for tile in (board.get("forms") or [])[:TOP12_SIZE]
    ]


def event_top12(
    marts: dict[str, list[dict[str, Any]]], event: dict[str, Any], phase: str
) -> tuple[list[dict[str, Any]], int | None]:
    """An event's Top 12 tiles and its n: every team there
    (pokemon_event_usage_vs_regulation) or the teams that reached Day 2
    (pokemon_event_phase_usage, E1)."""
    event_id = event["event_id"]
    profile = {
        r["pokemon_key"]: r
        for r in marts.get("pokemon_champions_profile", [])
        if r.get("regulation_scope") == event.get("regulation_code")
    }
    if phase == "day2":
        rows = sorted(
            (
                r
                for r in marts.get("pokemon_event_phase_usage", [])
                if r.get("scope_kind") == "event"
                and r.get("event_id") == event_id
                and r.get("phase") == "day2"
            ),
            key=lambda r: r.get("usage_rank") or 10**9,
        )
        n = rows[0].get("phase_team_count") if rows else None
        share_field, count_field = "team_share", "team_count"
    else:
        rows = sorted(
            (
                r
                for r in marts.get("pokemon_event_usage_vs_regulation", [])
                if r.get("event_id") == event_id
            ),
            key=lambda r: (-(r.get("usage_count") or 0), r["pokemon_key"]),
        )
        n = rows[0].get("event_team_count") if rows else None
        share_field, count_field = "event_team_share", "usage_count"
    tiles = [
        {
            "pokemon_key": r["pokemon_key"],
            "name": r.get("pokemon_name")
            or profile.get(r["pokemon_key"], {}).get("pokemon_name")
            or r["pokemon_key"],
            "share": r.get(share_field),
            "count": r.get(count_field),
            "type_1": profile.get(r["pokemon_key"], {}).get("type_1"),
            "type_2": profile.get(r["pokemon_key"], {}).get("type_2"),
        }
        for r in rows[:TOP12_SIZE]
    ]
    return tiles, n


def top12_context(
    tiles: list[dict[str, Any]],
    *,
    layout: str,
    scope_label: str,
    sample: str,
    phase: str,
    citation: str,
    art_uri,
    font_uri: str,
    scope_note: str = "",
    site: str = SITE_URL,
) -> dict[str, Any]:
    """Template context for one Top 12 card (templates/top12.html.jinja)."""
    badge = 40 if layout == "story" else 34
    return {
        "layout": layout,
        "font_uri": font_uri,
        "scope_label": scope_label,
        "sample": sample,
        "phase": phase,
        "phase_label": "Day 2" if phase == "day2" else "All players",
        "scope_note": scope_note,
        "tiles": [
            {
                "name": tile["name"],
                "share": _pct(tile.get("share")),
                "art": art_uri(tile["pokemon_key"]),
                "types": square_badge_html(tile.get("type_1"), badge)
                + square_badge_html(tile.get("type_2"), badge),
            }
            for tile in tiles
        ],
        "citation": citation,
        "site": site.replace("https://", "").rstrip("/"),
    }


def _quantize_png(path: Path) -> None:
    """Re-save a card as a 256-colour PNG: about a third of the size, with
    no visible change on flat broadcast colours."""
    try:
        from PIL import Image
    except ImportError:
        return
    with Image.open(path) as image:
        quantized = image.convert("RGB").quantize(colors=256)
    quantized.save(path, optimize=True)


def _top12_jobs(
    env: Environment,
    payload: dict[str, Any],
    manifest: dict[str, Any],
    cards_dir: Path,
    sprite_uri,
    normalized_dir: Path,
    site_url: str,
    version: str | None,
) -> list[tuple[str, Path, tuple[int, int]]]:
    """The Top 12 cards (V8): every official regulation with a board, and
    the default regulation's events, for All players and (where the data
    has one) Day 2. Records each card in manifest["top12"]."""
    template = env.get_template("top12.html.jinja")
    font_uri = (
        "data:font/woff2;base64," + base64.b64encode(FONT_PATH.read_bytes()).decode("ascii")
        if FONT_PATH.exists()
        else ""
    )
    artwork = dashboard_sprites.load_asset_map(normalized_dir, image_kind="home_render")
    art_cache: dict[str, str] = {}

    def art_uri(pokemon_key: str) -> str:
        if pokemon_key not in art_cache:
            art_cache[pokemon_key] = _artwork_uri(artwork.get(pokemon_key)) or sprite_uri(
                pokemon_key
            )
        return art_cache[pokemon_key]

    version_bit = f"dataset {version} · " if version else ""
    default_regulation = str(payload.get("default_scope") or "").split(":", 1)[0]
    jobs: list[tuple[str, Path, tuple[int, int]]] = []

    def add(kind: str, key: str, phase: str, layouts, tiles, **context) -> None:
        if len(tiles) < TOP12_SIZE:
            return
        entry = manifest["top12"][kind].setdefault(key, {}).setdefault(phase, {})
        for layout in layouts:
            name = f"top12-{kind}-{key}-{phase}-{layout}.png"
            html = template.render(
                **top12_context(
                    tiles,
                    layout=layout,
                    phase=phase,
                    art_uri=art_uri,
                    font_uri=font_uri,
                    site=site_url,
                    **context,
                )
            )
            jobs.append((html, cards_dir / name, TOP12_FORMATS[layout]))
            entry[layout] = (CARDS_SUBDIR / name).as_posix()

    for scope, kpis in (payload.get("kpis_by_scope") or {}).items():
        if ":" in scope:
            continue
        layouts = list(TOP12_FORMATS) if scope == default_regulation else ["landscape"]
        for phase in ("all", "day2"):
            board = (kpis.get("top_12_boards") or {}).get(phase)
            if not board:
                continue
            sample = f"{_plural(board.get('team_count'), 'team')} · {_plural(board.get('event_count'), 'event')}"
            add(
                "regulation",
                scope,
                phase,
                layouts,
                regulation_top12(kpis, phase),
                scope_label=_short_regulation(scope),
                sample=sample,
                scope_note="Teams that played Day 2" if phase == "day2" else "Every team on record",
                citation=f"{version_bit}{_short_regulation(scope)}, n = {board.get('team_count') or 0:,} teams"
                + (", Day 2 teams" if phase == "day2" else ""),
            )

    events = sorted(
        (
            e
            for e in payload["marts"].get("tournament_event_summary", [])
            if default_regulation in (dashboard_data.ALL_SCOPE, e.get("regulation_code"))
        ),
        key=lambda e: (e.get("event_date") or "", e.get("event_id") or ""),
        reverse=True,
    )
    for event in events[:MAX_TOP12_EVENTS]:
        short = dashboard_data.short_event_name(event.get("event_name"))
        for phase in ("all", "day2"):
            tiles, n = event_top12(payload["marts"], event, phase)
            add(
                "event",
                event["event_id"],
                phase,
                list(TOP12_FORMATS),
                tiles,
                scope_label=short,
                sample=f"{_plural(n, 'team')} · {event.get('event_date')}",
                scope_note=_short_regulation(event.get("regulation_code") or ""),
                citation=f"{version_bit}{short}, n = {n or 0:,} teams"
                + (", Day 2 teams" if phase == "day2" else ""),
            )
    return jobs


def _artwork_uri(local_cache_path: str | None) -> str | None:
    """A HOME render from the artwork cache as a TOP12_ART_PX PNG data URI,
    or None when it isn't cached (the card falls back to the menu sprite)."""
    if not local_cache_path:
        return None
    source = dashboard_sprites.DEFAULT_ARTWORK_CACHE_DIR / local_cache_path
    if not source.exists():
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    with Image.open(source) as image:
        image = image.convert("RGBA")
        image.thumbnail((TOP12_ART_PX, TOP12_ART_PX))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def og_card(cards: dict[str, str], payload: dict[str, Any]) -> str | None:
    """The "What changed" card that doubles as the site's Open Graph image:
    the default scope's regulation's, else the newest earlier regulation
    with one. The fallback covers a rollover that opens on a new set's
    online events (docs/upgrade-plan-2027q2.md, S1) before the set has a
    reliable official comparison: the card the page would have opened on
    before that rule existed."""
    regulation = str(payload.get("default_scope") or "").split(":", 1)[0]
    if regulation in cards:
        return cards[regulation]
    codes = [r.get("regulation_code") for r in payload.get("regulations") or []]
    earlier = codes[: codes.index(regulation)] if regulation in codes else codes
    return next((cards[code] for code in reversed(earlier) if code in cards), None)


def whats_changed_context(
    kpis: dict[str, Any],
    scope: str,
    sprite_uri,
    *,
    dataset_version: str | None,
    site: str = SITE_URL,
) -> dict[str, Any] | None:
    """Template context for one regulation's "What changed" card, using the
    same comparison the Overview opens on: early vs recent events when the
    previous regulation is a thin baseline, the previous regulation
    otherwise. None when the regulation has nothing reliable to compare."""
    movers = kpis.get("movers")
    windowed = kpis.get("window_movers")
    use_window = bool(windowed) and (not movers or movers.get("baseline_thin"))
    summary = windowed if use_window else movers
    if not summary or not summary.get("reliable"):
        return None
    if use_window:
        title = f"What changed within {_short_regulation(scope)}"
        subtitle = (
            f"{', '.join(windowed['recent_events'])} ({_plural(windowed['team_count'], 'team')}) "
            f"vs {', '.join(windowed['early_events'])} "
            f"({_plural(windowed['previous_team_count'], 'team')})"
        )
    else:
        title = f"What changed in {_short_regulation(scope)}"
        subtitle = (
            f"vs {_short_regulation(movers['previous_regulation_code'])} · "
            f"{_plural(movers['team_count'], 'team')} against "
            f"{_plural(movers['previous_team_count'], 'team')}"
        )

    def rows(entries):
        return [
            {
                "name": entry.get("pokemon_name") or entry["pokemon_key"],
                "sprite": sprite_uri(entry["pokemon_key"]),
                "share": f"{(entry.get('team_share') or 0) * 100:.1f}%",
                "delta": _points(entry.get("team_share_delta")),
                "delta_points": (entry.get("team_share_delta") or 0) * 100,
            }
            for entry in entries[:MAX_MOVERS_ON_CARD]
        ]

    footer_bits = [
        f"dataset {dataset_version}" if dataset_version else None,
        "shares of teams",
    ]
    return {
        "title": title,
        "subtitle": subtitle,
        "columns": [
            {"label": "Rising", "rows": rows(summary.get("risers") or [])},
            {"label": "Falling", "rows": rows(summary.get("fallers") or [])},
        ],
        "footer": " · ".join(bit for bit in footer_bits if bit),
        "site": site.replace("https://", "").rstrip("/"),
    }


def _ordinal(n: int) -> str:
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def newest_event_top_cut(payload: dict[str, Any], top_n: int = TOP_N) -> tuple[dict, list[dict]]:
    """The newest event in the payload and its top `top_n` teams, by
    placement. ({}, []) when there are no events."""
    events = payload["marts"].get("tournament_event_summary", [])
    if not events:
        return {}, []
    event = max(events, key=lambda e: (e.get("event_date") or "", e.get("event_id") or ""))
    teams = sorted(
        (
            t
            for t in payload["marts"].get("tournament_team_results", [])
            if t.get("event_id") == event["event_id"]
            and t.get("placement")
            and t["placement"] <= top_n
        ),
        key=lambda t: t["placement"],
    )
    return event, teams


def render_share_cards(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    payload: dict[str, Any] | None = None,
    normalized_dir: Path = data_source.DEFAULT_NORMALIZED_DIR,
    asset_cache_dir: Path = data_source.DEFAULT_ASSET_CACHE_DIR,
    site_url: str = SITE_URL,
) -> dict[str, Any]:
    """Renders the share cards into output_dir/images/cards/ (replacing any
    from a previous run) and returns the manifest it writes there."""
    payload = payload or dashboard_data.build_payload()
    cards_dir = output_dir / CARDS_SUBDIR
    if cards_dir.exists():
        shutil.rmtree(cards_dir)
    cards_dir.mkdir(parents=True, exist_ok=True)

    assets = data_source._menu_sprite_assets_by_key(normalized_dir)

    def sprite_uri(pokemon_key: str) -> str:
        path = data_source._sprite_and_icon_lookup(
            pokemon_key, pokemon_assets=assets, asset_cache_dir=asset_cache_dir
        )
        return card_template._data_uri(path)

    jobs: list[tuple[str, Path]] = []
    # Top 12 cards render at their own size and are quantized afterwards.
    sized_jobs: list[tuple[str, Path, tuple[int, int]]] = []
    manifest: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": None,
        "teams": {},
        "whats_changed": {},
        "top12": {"regulation": {}, "event": {}},
        "og_image": None,
    }

    event, teams = newest_event_top_cut(payload)
    if event:
        short = dashboard_data.short_event_name(event.get("event_name"))
        manifest["event"] = {"event_id": event["event_id"], "event_name": event.get("event_name")}
        for team in teams:
            try:
                card = data_source.load_from_team_id(
                    team["team_id"], normalized_dir=normalized_dir, asset_cache_dir=asset_cache_dir
                )
            except data_source.TeamNotFoundError:
                continue
            record = (
                f" · {team['record_wins']}–{team['record_losses']}"
                if team.get("record_wins") is not None
                else ""
            )
            card.team_name = f"{_ordinal(team['placement'])} · {short}"
            card.subtitle = f"{event.get('event_date')}{record}"
            name = f"{event['event_id']}-{team['placement']}.png"
            jobs.append((card_template.render_html(card), cards_dir / name))
            manifest["teams"][team["team_id"]] = (CARDS_SUBDIR / name).as_posix()

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=select_autoescape(["html"])
    )
    whats_changed = env.get_template("whats_changed.html.jinja")
    version = payload.get("provenance", {}).get("dataset_version")
    for scope, kpis in payload.get("kpis_by_scope", {}).items():
        # "What changed" compares official events, so a population scope
        # ("m-c:online", docs/upgrade-plan-2027q2.md, S1) shares its
        # official scope's card rather than rendering a copy.
        if ":" in scope:
            continue
        context = whats_changed_context(
            kpis, scope, sprite_uri, dataset_version=version, site=site_url
        )
        if context is None:
            continue
        name = f"whats-changed-{scope}.png"
        jobs.append((whats_changed.render(**context), cards_dir / name))
        manifest["whats_changed"][scope] = (CARDS_SUBDIR / name).as_posix()

    sized_jobs.extend(
        _top12_jobs(
            env, payload, manifest, cards_dir, sprite_uri, normalized_dir, site_url, version
        )
    )

    launch_kwargs = {}
    if os.path.exists(_PREINSTALLED_CHROMIUM):
        launch_kwargs["executable_path"] = _PREINSTALLED_CHROMIUM
    if jobs or sized_jobs:
        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kwargs)
            try:
                page = browser.new_page(viewport={"width": 1240, "height": 900})
                for html, path in jobs:
                    page.set_content(html, wait_until="load")
                    page.locator(".card-wrap").screenshot(path=str(path))
                for html, path, (width, height) in sized_jobs:
                    page.set_viewport_size({"width": width, "height": height})
                    page.set_content(html, wait_until="load")
                    page.locator(".card-wrap").screenshot(path=str(path))
                    _quantize_png(path)
            finally:
                browser.close()

    # The Open Graph image is the default regulation's 16:9 Top 12 card
    # (V8), else its "What changed" card.
    default_regulation = str(payload.get("default_scope") or "").split(":", 1)[0]
    default_top12 = (
        manifest["top12"]["regulation"].get(default_regulation, {}).get("all", {}).get("landscape")
    )
    default_card = default_top12 or og_card(manifest["whats_changed"], payload)
    if default_card:
        og_path = cards_dir / "og.png"
        shutil.copyfile(output_dir / default_card, og_path)
        manifest["og_image"] = (CARDS_SUBDIR / "og.png").as_posix()
    (cards_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
