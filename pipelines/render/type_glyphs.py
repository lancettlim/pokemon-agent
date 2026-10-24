"""The type logo for the share-card and team-card templates: the in-game
round emblems committed under pipelines/dashboard/static/icons/types/,
inlined as data URIs so a card is one self-contained page. The site draws
the same emblems from static/app.js's typeIconImg, so the dashboard and its
PNG cards show one logo per type (docs/design-system.md, "Type logo").
"""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

from markupsafe import Markup, escape

ICON_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "static" / "icons" / "types"


@lru_cache(maxsize=None)
def _data_uri(type_name: str) -> str:
    path = ICON_DIR / f"{type_name}.png"
    if not path.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def square_badge_html(type_name: str | None, size: int = 24) -> Markup:
    """The type's emblem at `size` px. Unknown or empty types -> empty
    markup. (The name predates the emblem; callers still say "badge".)"""
    key = str(type_name or "").lower()
    uri = _data_uri(key) if key else ""
    if not uri:
        return Markup("")
    return Markup(
        f'<img class="type-emblem" src="{uri}" width="{size}" height="{size}" '
        f'alt="" role="img" aria-label="{escape(type_name)} type" '
        f'style="width:{size}px;height:{size}px">'
    )
