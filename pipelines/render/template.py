"""Builds the HTML string for a team card from a CardModel, for
pipelines/render/team_card.py to screenshot via Playwright.

Sprite/icon images are inlined as base64 data URIs rather than referenced
via file:// paths — this sidesteps a class of path-resolution and
Playwright local-content-loading quirks, and the source files are already
small local PNGs by render time, so the encoding cost is negligible.
"""

from __future__ import annotations

import base64
from pathlib import Path

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape

from pipelines.render import assets
from pipelines.render.assets import TYPE_NAMES
from pipelines.render.data_source import CardModel

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ICON_CACHE_DIR = REPO_ROOT / "data" / "assets" / "pokeapi_sprites"

# A muted, colorblind-conscious per-type color set (roughly matching each
# type's traditional in-game color, dimmed slightly for contrast/legibility
# as light-on-dark pill backgrounds).
TYPE_COLORS = {
    "normal": "#9CA3AF",
    "fighting": "#C0392B",
    "flying": "#93A9D6",
    "poison": "#9B59B6",
    "ground": "#C9A227",
    "rock": "#A08245",
    "bug": "#8CA61A",
    "ghost": "#5C4E8C",
    "steel": "#8E99A8",
    "fire": "#E8622C",
    "water": "#3B82C4",
    "grass": "#4C9A4C",
    "electric": "#D9B92C",
    "psychic": "#DB5A88",
    "ice": "#5FBFC0",
    "dragon": "#5B4FCF",
    "dark": "#4B4046",
    "fairy": "#E38AAE",
    None: "#6B7280",
}


def _data_uri(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _type_color(type_name: str | None) -> str:
    if not type_name:
        return TYPE_COLORS[None]
    return TYPE_COLORS.get(type_name.lower(), TYPE_COLORS[None])


def _make_environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["data_uri"] = _data_uri
    env.filters["type_color"] = _type_color
    # V6's square type badge (docs/upgrade-plan-2027q2.md), our own glyphs.
    # Imported here, not at module top: type_glyphs reads TYPE_COLORS from
    # this module.
    from pipelines.render.type_glyphs import square_badge_html

    env.globals["square_badge"] = square_badge_html
    return env


def _resolve_icons(
    card: CardModel,
    *,
    icon_cache_dir: Path,
    session: requests.Session | None,
) -> dict[str, str]:
    """Fills in each slot's item_icon_path/tera_icon_path in place and
    returns a move-type (lowercased) -> data-URI lookup for move rows."""
    type_icons: dict[str, str] = {}
    for slot in card.slots:
        if slot.item_name and slot.item_icon_path is None:
            slot.item_icon_path = assets.ensure_item_icon(
                slot.item_name, cache_dir=icon_cache_dir, session=session
            )
        if slot.tera_type and slot.tera_icon_path is None:
            slot.tera_icon_path = assets.ensure_type_icon(
                slot.tera_type, cache_dir=icon_cache_dir, session=session
            )
        for move_type in slot.move_types:
            if not move_type:
                continue
            key = move_type.lower()
            if key not in type_icons:
                icon_path = assets.ensure_type_icon(
                    move_type, cache_dir=icon_cache_dir, session=session
                )
                type_icons[key] = _data_uri(icon_path)
    return type_icons


def render_html(
    card: CardModel,
    *,
    icon_cache_dir: Path = DEFAULT_ICON_CACHE_DIR,
    session: requests.Session | None = None,
) -> str:
    type_icons = _resolve_icons(card, icon_cache_dir=icon_cache_dir, session=session)
    env = _make_environment()
    template = env.get_template("team_card.html.jinja")
    return template.render(card=card, all_types=TYPE_NAMES, type_icons=type_icons)
