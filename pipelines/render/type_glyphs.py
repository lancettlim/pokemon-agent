"""Our own white type glyphs for the square type badge (docs/upgrade-plan-
2027q2.md, V6): one simple shape per type, drawn for this project in a
24x24 box. They are deliberately not the official type icons, which the
plan rules out for broadcast components; the circular emblems in
pipelines/dashboard/static/icons/types/ stay in dense tables.

One definition feeds both pipelines: pipelines/dashboard/build.py ships the
map to the page (static/app.js's typeBadgeSquare) and the share-card
templates call square_badge_html, so the site and its PNG cards draw the
same badge. Each value is the SVG's inner markup, filled white with the
even-odd rule (holes in a glyph, such as the steel nut's, are subpaths).
"""

from __future__ import annotations

from markupsafe import Markup, escape

from pipelines.render.template import TYPE_COLORS

GLYPHS: dict[str, str] = {
    "normal": '<path d="M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18zm0 4a5 5 0 1 1 0 10a5 5 0 1 1 0-10z"/>',
    "fire": (
        '<path d="M12 2C9 7 6 9.5 6 14a6 6 0 0 0 12 0c0-2.4-1-4.3-2.5-6-.2 1.8-1 3-2.3 3.6'
        'C13.9 8.4 13.2 5 12 2z"/>'
    ),
    "water": '<path d="M12 2.5C9 7 5.5 10.5 5.5 14.5a6.5 6.5 0 0 0 13 0C18.5 10.5 15 7 12 2.5z"/>',
    "electric": '<path d="M13.5 2 5 13.5h5.5L9.5 22 19 9.5h-5.5z"/>',
    "grass": (
        '<path d="M20 4C11 4 5 8.5 5 15c0 1.3.3 2.5.8 3.5L4 20.3l1.4 1.4 1.8-1.8c1 .6 2.3 1 3.8 1'
        'C17 20.9 20 13 20 4zM9.7 18.2c1.9-3.8 4.4-6.6 7.6-8.9-2.9 2.6-5 5.6-6.5 9.4z"/>'
    ),
    "ice": (
        '<rect x="10.9" y="2" width="2.2" height="20" rx="1.1"/>'
        '<rect x="10.9" y="2" width="2.2" height="20" rx="1.1" transform="rotate(60 12 12)"/>'
        '<rect x="10.9" y="2" width="2.2" height="20" rx="1.1" transform="rotate(120 12 12)"/>'
    ),
    "fighting": (
        '<path d="M7 9.5V6.8a1.8 1.8 0 0 1 3.6 0V9h.4V5.8a1.8 1.8 0 0 1 3.6 0V9h.4V6.8'
        'a1.8 1.8 0 0 1 3.6 0V14a7 7 0 0 1-7 7h-1A5.6 5.6 0 0 1 5 15.4V11a1.5 1.5 0 0 1 2-1.5z"/>'
    ),
    "poison": (
        '<circle cx="9.5" cy="14.5" r="5"/><circle cx="16.5" cy="7.5" r="3.4"/>'
        '<circle cx="17.5" cy="16.5" r="2.4"/>'
    ),
    "ground": '<path d="M2.5 19.5h19l-5-8.5-3.2 4.6L9 7.5z"/>',
    "flying": (
        '<path d="M3 15.5c4.5-.8 8-3.8 10.5-10 .9 3.6.2 6.6-1.8 8.8 3.1-.2 6-1.4 8.8-3.8'
        '-1.4 5.4-5.6 8.4-11 8.9-1.8.2-3.6 0-5.3-.6L2.6 20.4 1.4 19.2l1.4-1.6z"/>'
    ),
    "psychic": (
        '<path d="M12 6C7 6 3.3 9.3 2 12c1.3 2.7 5 6 10 6s8.7-3.3 10-6c-1.3-2.7-5-6-10-6z'
        'm0 9.5a3.5 3.5 0 1 1 0-7a3.5 3.5 0 0 1 0 7z"/>'
    ),
    "bug": (
        '<ellipse cx="12" cy="14.5" rx="5.5" ry="6.5"/><circle cx="12" cy="6.8" r="2.8"/>'
        '<path d="M9.6 4.9 7 2.3l1-1 2.8 2.8zM14.4 4.9 17 2.3l-1-1-2.8 2.8z"/>'
    ),
    "rock": '<path d="M7.5 3.5h8l5 5v7.5l-5 4.5h-8L3 15.5V8z"/>',
    "ghost": (
        '<path d="M12 3a7 7 0 0 0-7 7v11l2.3-2 2.3 2 2.4-2 2.4 2 2.3-2 2.3 2V10a7 7 0 0 0-7-7z'
        'm-2.5 6a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3zm5 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3z"/>'
    ),
    "dragon": (
        '<path d="M4.5 3c4 3 6 8 5 18-2-6-4-11-5-18zm6 0c3.2 3.5 5 8 4 18-1.5-6-3-11-4-18z'
        'm6 1c2.6 3 3.6 7 3 13-1.5-4.5-2.5-8.5-3-13z"/>'
    ),
    "dark": '<path d="M15.5 3A9 9 0 1 0 21 17.5 7.5 7.5 0 0 1 15.5 3z"/>',
    "steel": (
        '<path d="M12 2.5 20.2 7.3v9.4L12 21.5l-8.2-4.8V7.3zm0 6a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z"/>'
    ),
    "fairy": '<path d="M12 2l2.2 7.8L22 12l-7.8 2.2L12 22l-2.2-7.8L2 12l7.8-2.2z"/>',
}


def square_badge_html(type_name: str | None, size: int = 24) -> Markup:
    """A square badge: the type's colour filled, our white glyph on it.
    The same markup static/app.js's typeBadgeSquare builds, for the
    share-card templates. Unknown or empty types -> empty markup."""
    glyph = GLYPHS.get(str(type_name or "").lower())
    if not glyph:
        return Markup("")
    color = TYPE_COLORS.get(str(type_name).lower(), TYPE_COLORS[None])
    inner = round(size * 0.72)
    return Markup(
        f'<span class="type-sq" role="img" aria-label="{escape(type_name)} type" '
        f'style="width:{size}px;height:{size}px;background:{color}">'
        f'<svg viewBox="0 0 24 24" width="{inner}" height="{inner}" fill="#fff" '
        f'fill-rule="evenodd" aria-hidden="true">{glyph}</svg></span>'
    )
