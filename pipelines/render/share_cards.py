"""Pre-rendered share images for the dashboard (docs/upgrade-plan-2027q1.md,
C4): the newest event's top 8 as team-card PNGs, and a 1200x630 "What
changed" card per regulation, the default regulation's doubling as the
site's Open Graph image.

This is a separate step from the dashboard build (`python -m pipelines.cli
render-share-cards`, run before `build-dashboard`) because it needs
Playwright's Chromium, which the dashboard build deliberately does not (see
pipelines/dashboard/build.py's docstring). It writes PNGs under
<output_dir>/images/cards/ plus a manifest.json the dashboard build reads;
without that manifest the site simply shows no download buttons.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

from pipelines.dashboard import data as dashboard_data
from pipelines.render import data_source
from pipelines.render import template as card_template

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
                "share": f"{(entry.get('usage_share') or 0) * 100:.1f}%",
                "delta": _points(entry.get("usage_share_delta")),
                "delta_points": (entry.get("usage_share_delta") or 0) * 100,
            }
            for entry in entries[:MAX_MOVERS_ON_CARD]
        ]

    footer_bits = [
        f"dataset {dataset_version}" if dataset_version else None,
        "shares of roster slots",
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
    manifest: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": None,
        "teams": {},
        "whats_changed": {},
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
        context = whats_changed_context(
            kpis, scope, sprite_uri, dataset_version=version, site=site_url
        )
        if context is None:
            continue
        name = f"whats-changed-{scope}.png"
        jobs.append((whats_changed.render(**context), cards_dir / name))
        manifest["whats_changed"][scope] = (CARDS_SUBDIR / name).as_posix()

    launch_kwargs = {}
    if os.path.exists(_PREINSTALLED_CHROMIUM):
        launch_kwargs["executable_path"] = _PREINSTALLED_CHROMIUM
    if jobs:
        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kwargs)
            try:
                page = browser.new_page(viewport={"width": 1240, "height": 900})
                for html, path in jobs:
                    page.set_content(html, wait_until="load")
                    page.locator(".card-wrap").screenshot(path=str(path))
            finally:
                browser.close()

    default_card = manifest["whats_changed"].get(payload.get("default_scope"))
    if default_card:
        og_path = cards_dir / "og.png"
        shutil.copyfile(output_dir / default_card, og_path)
        manifest["og_image"] = (CARDS_SUBDIR / "og.png").as_posix()
    (cards_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
