"""The responsive test matrix (docs/upgrade-plan-2027q2.md, M1).

Every route is opened at the widths people actually read the site on and
checked for the four things the 2026-10-21 review found broken or
unenforced:

1. No horizontal page scroll: ``scrollWidth <= innerWidth``. Only an
   explicit ``.table-scroll`` (or another element that scrolls itself) may
   be wider than the viewport.
2. On phones, every nav item, sub-tab, chip, segmented control, board tile
   and team-strip tile is at least 44x44px (U7's tap target).
3. On phones, every input, select and textarea computes to at least 16px,
   so iOS Safari doesn't zoom the page on focus.
4. The sticky chrome (the top bar, the phone's bottom bar and anything else
   fixed or sticky) is at most 120px tall on phones and 200px elsewhere
   (U2's targets).

The full sweep (every MATRIX_ROUTES entry at every FULL_WIDTHS width, plus
the SPOT_WIDTHS spot checks) runs when ``CI`` or ``DASHBOARD_FULL_MATRIX``
is set; otherwise a three-route smoke keeps ``make test`` quick. With
``DASHBOARD_SCREENSHOT_DIR`` set, each page is also saved there as a PNG,
which CI uploads as an artifact so reviewers can see the phone layout.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

# One route per view (and per sub-view whose layout differs), so the sweep
# stays about 100 page loads (docs/upgrade-plan-2027q2.md, risks).
MATRIX_ROUTES = [
    "",
    "#/tiers",
    "#/usage",
    "#/usage/win-rate",
    "#/speed",
    "#/pokemon/garchomp",
    "#/pokemon/garchomp/cores",
    "#/compare/garchomp,kingambit",
    "#/matchup/rillaboom/sneasler",
    "#/teams",
    "#/teams/converged",
    "#/events",
    "#/event/EVT-LOU",
    "#/archetypes",
    "#/cores/incineroar",
    "#/players",
    "#/player/P000",
    "#/builder",
    "#/data",
    "#/data/dictionary",
]
SMOKE_ROUTES = ["", "#/pokemon/garchomp", "#/event/EVT-LOU"]

# (label, width, height)
FULL_WIDTHS = [
    ("phone-360", 360, 780),
    ("phone-390", 390, 844),
    ("tablet-768", 768, 1024),
    ("tablet-1024", 1024, 768),
    ("desktop-1440", 1440, 900),
]
SPOT_WIDTHS = [
    ("phone-430", 430, 932),
    ("tablet-721", 721, 1024),
    ("landscape-844", 844, 390),
]
SMOKE_WIDTHS = [FULL_WIDTHS[0], FULL_WIDTHS[2], FULL_WIDTHS[4]]

PHONE_MAX_WIDTH = 480
TAP_MIN_PX = 44
INPUT_MIN_FONT_PX = 16
CHROME_MAX_PHONE_PX = 120
CHROME_MAX_PX = 200

# What counts as a tap target on a phone (M1, check 2).
TAP_TARGETS = ", ".join(
    [
        ".section-btn",
        ".tab-btn",
        ".subtab-btn",
        ".tier-chip",
        ".toggle-chip",
        ".set-tab",
        ".set-level-btn",
        ".movers-toggle button",
        ".calc-mode-btn",
        ".segmented button",
        ".board-tile",
        ".team-strip-slot",
        ".round-tab",
        ".type-popover-btn",
        ".more-menu-btn",
    ]
)


def _full_matrix() -> bool:
    return bool(os.environ.get("CI") or os.environ.get("DASHBOARD_FULL_MATRIX"))


def _cases():
    if _full_matrix():
        widths = FULL_WIDTHS + SPOT_WIDTHS
        return [(label, w, h, MATRIX_ROUTES) for label, w, h in widths]
    return [(label, w, h, SMOKE_ROUTES) for label, w, h in SMOKE_WIDTHS]


# Runs in the page: the four measurements, with the offending elements named
# so a failure says what to fix rather than only that something is wide.
_MEASURE = """
({tapSelector, phone}) => {
  const vw = window.innerWidth;
  const describe = (el) => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    if (el.classList.length) s += '.' + Array.from(el.classList).slice(0, 3).join('.');
    return s;
  };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) return false;
    const style = getComputedStyle(el);
    return style.visibility !== 'hidden' && style.display !== 'none';
  };
  // An element wider than the viewport is fine inside something that
  // scrolls or clips horizontally on its own (a .table-scroll, a tab row),
  // as long as that ancestor actually contains it: an absolutely
  // positioned element escapes every unpositioned ancestor between it and
  // its containing block, overflow or not.
  const insideScroller = (el) => {
    let escaping = ['absolute', 'fixed'].includes(getComputedStyle(el).position);
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const style = getComputedStyle(p);
      if (escaping) {
        if (style.position === 'static') continue;
        escaping = ['absolute', 'fixed'].includes(style.position);
      }
      const ox = style.overflowX;
      if ((ox === 'auto' || ox === 'scroll' || ox === 'hidden' || ox === 'clip') &&
          p.getBoundingClientRect().right <= vw + 1) return true;
    }
    return false;
  };
  const wide = [];
  if (document.documentElement.scrollWidth > vw) {
    for (const el of document.body.querySelectorAll('*')) {
      const r = el.getBoundingClientRect();
      if (r.right > vw + 1 && r.width && !insideScroller(el)) {
        wide.push(describe(el) + ' right=' + Math.round(r.right));
        if (wide.length >= 4) break;
      }
    }
  }
  const small = [];
  if (phone) {
    for (const el of document.querySelectorAll(tapSelector)) {
      if (!visible(el) || el.closest('[hidden]')) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 44 - 0.5 || r.height < 44 - 0.5) {
        small.push(describe(el) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
      }
    }
  }
  const tinyInputs = [];
  if (phone) {
    for (const el of document.querySelectorAll('input, select, textarea')) {
      if (!visible(el) || el.type === 'range' || el.type === 'checkbox' || el.type === 'radio') continue;
      const size = parseFloat(getComputedStyle(el).fontSize);
      if (size < 16 - 0.01) tinyInputs.push(describe(el) + ' ' + size + 'px');
    }
  }
  // Bars docked to the top or bottom edge, full width or nearly: a fixed
  // popover or an open sheet isn't chrome. A bar nested inside another
  // (the phone's bottom bar lives in the top bar's markup) counts once,
  // by its own rect.
  const bars = [];
  for (const el of document.body.querySelectorAll('*')) {
    const pos = getComputedStyle(el).position;
    if (pos !== 'sticky' && pos !== 'fixed') continue;
    if (!visible(el) || el.closest('table') || el.closest('.tip-bubble')) continue;
    const r = el.getBoundingClientRect();
    const docked = r.top <= 1 || r.bottom >= window.innerHeight - 1;
    if (!docked || r.width < vw * 0.6) continue;
    bars.push({el, r});
  }
  let chrome = 0;
  const chromeParts = [];
  for (const bar of bars) {
    const within = bars.some((other) => other !== bar &&
      bar.r.top >= other.r.top && bar.r.bottom <= other.r.bottom);
    if (within) continue;
    chrome += bar.r.height;
    chromeParts.push(describe(bar.el) + ' ' + Math.round(bar.r.height));
  }
  return {
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: vw,
    wide, small, tinyInputs,
    chrome: Math.round(chrome), chromeParts,
  };
}
"""


def _slug(route: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", route.lower()).strip("-") or "overview"


@pytest.mark.parametrize("label,width,height,routes", _cases(), ids=[c[0] for c in _cases()])
def test_every_route_fits_and_is_tappable(site_url, open_page, label, width, height, routes):
    phone = width <= PHONE_MAX_WIDTH
    page = open_page(width, height, touch=phone)
    shots = os.environ.get("DASHBOARD_SCREENSHOT_DIR")
    failures = []
    for route in routes:
        name = route or "/"
        page.goto("about:blank")
        page.goto(site_url + route)
        page.wait_for_load_state("networkidle")
        m = page.evaluate(_MEASURE, {"tapSelector": TAP_TARGETS, "phone": phone})
        if m["scrollWidth"] > m["innerWidth"]:
            failures.append(
                f"{name}: scrollWidth {m['scrollWidth']} > {m['innerWidth']} ({'; '.join(m['wide'])})"
            )
        if m["small"]:
            failures.append(
                f"{name}: tap targets under {TAP_MIN_PX}px: {'; '.join(m['small'][:6])}"
            )
        if m["tinyInputs"]:
            failures.append(
                f"{name}: inputs under {INPUT_MIN_FONT_PX}px: {'; '.join(m['tinyInputs'][:6])}"
            )
        limit = CHROME_MAX_PHONE_PX if phone else CHROME_MAX_PX
        if m["chrome"] > limit:
            failures.append(
                f"{name}: sticky chrome {m['chrome']}px > {limit}px ({'; '.join(m['chromeParts'])})"
            )
        if shots:
            out = Path(shots) / label
            out.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(out / f"{_slug(route)}.png"), full_page=True)
        failures.extend(f"{name}: {error}" for error in page.errors)
        page.errors.clear()
    assert not failures, f"{label} ({width}x{height}):\n" + "\n".join(failures)
