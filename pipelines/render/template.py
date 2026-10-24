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
    # Sampled from the emblems in pipelines/dashboard/static/icons/types/,
    # so a type's pill, tile and logo are one colour.
    "normal": "#9099A1",
    "fighting": "#CE4069",
    "flying": "#8FA8DD",
    "poison": "#AB6AC8",
    "ground": "#D97746",
    "rock": "#C7B78B",
    "bug": "#90C12C",
    "ghost": "#5269AC",
    "steel": "#5A8EA1",
    "fire": "#FF9C54",
    "water": "#4D90D5",
    "grass": "#63BB5B",
    "electric": "#F3D23B",
    "psychic": "#F97176",
    "ice": "#74CEC0",
    "dragon": "#0A6DC4",
    "dark": "#5A5366",
    "fairy": "#EC8FE6",
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
    # The type emblem, one logo for the site and its PNG cards.
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
