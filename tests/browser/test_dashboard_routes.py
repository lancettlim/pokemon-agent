"""Every dashboard route renders, links route, Back works
(docs/upgrade-plan-2027q1.md, U1 and U8)."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

ROUTES = [
    "",
    "#/tiers",
    "#/usage",
    "#/usage/win-rate",
    "#/usage/success",
    "#/usage/trends",
    "#/speed",
    "#/pokemon/garchomp",
    "#/pokemon/garchomp/abilities",
    "#/pokemon/garchomp/moves",
    "#/pokemon/garchomp/cores",
    "#/compare/garchomp,kingambit",
    "#/matchup/rillaboom/sneasler",
    "#/teams",
    "#/teams?tier=regional&sort=win-rate",
    "#/teams/converged",
    "#/events",
    "#/event/EVT-LOU",
    "#/event/EVT-WCS",
    "#/archetypes",
    "#/cores/incineroar",
    "#/cores/incineroar/triple",
    "#/players",
    "#/players/signatures",
    "#/builder",
    "#/data",
    "#/data/gates",
]

VIEWPORTS = [(1440, 900), (390, 844)]

# Elements that only exist once a view has rendered data, not just its
# static intro text.
CONTENT_SELECTOR = (
    ".grid-6xn-tile, tbody tr, .tier-chip, .mover-list li, .expansion-card, "
    ".compare-card, .roster-item, .type-effect-tile, .event-card, .team-card, "
    ".set-card, .data-card"
)


def _active_panel_state(page):
    return page.evaluate(
        """(selector) => {
            const panel = document.querySelector('.tab-panel:not([hidden])');
            if (!panel) return {panel: null};
            return {
                panel: panel.getAttribute('data-panel'),
                content: panel.querySelectorAll(selector).length,
                loadError: !!panel.querySelector('.data-load-error'),
            };
        }""",
        CONTENT_SELECTOR,
    )


@pytest.mark.parametrize("width,height", VIEWPORTS)
def test_every_route_renders_without_errors(site_url, open_page, width, height):
    page = open_page(width, height)
    failures = []
    for route in ROUTES:
        page.errors.clear()
        # A fresh load per route: each is opened as a deep link, and a goto
        # that only changes the hash wouldn't reload the page.
        page.goto("about:blank")
        page.goto(site_url + route)
        page.wait_for_load_state("networkidle")
        state = _active_panel_state(page)
        if not state["panel"]:
            failures.append(f"{route or '/'}: no panel shown")
        elif state["loadError"] or not state["content"]:
            failures.append(f"{route or '/'}: panel {state['panel']} is empty")
        failures.extend(f"{route or '/'}: {error}" for error in page.errors)
    assert not failures, "\n".join(failures)


def test_back_returns_to_the_deep_link_with_the_same_pokemon(site_url, open_page):
    page = open_page()
    page.goto(site_url + "#/pokemon/garchomp")
    page.wait_for_load_state("networkidle")
    assert page.locator("#pokemon-profile-filter").input_value() == "garchomp"

    page.click('.section-btn[data-section="meta"]')
    page.wait_for_function("location.hash === '#/overview'")
    page.click('.tab-btn[data-tab="usage"]')
    page.wait_for_function("location.hash === '#/usage'")

    page.go_back()
    page.wait_for_function("location.hash === '#/overview'")
    page.go_back()
    page.wait_for_function("location.hash === '#/pokemon/garchomp'")
    assert _active_panel_state(page)["panel"] == "pokemon-profile"
    assert page.locator("#pokemon-profile-filter").input_value() == "garchomp"
    assert "Garchomp" in page.locator("#pokemon-profile-stats").inner_text()
    assert not page.errors


def test_pokemon_links_route_to_the_profile_and_back(site_url, open_page):
    page = open_page()
    page.goto(site_url + "#/tiers")
    page.wait_for_load_state("networkidle")
    page.click('.tier-chip[href="#/pokemon/kingambit"]')
    page.wait_for_function("location.hash === '#/pokemon/kingambit'")
    page.wait_for_function(
        "document.getElementById('pokemon-profile-stats').innerText.includes('Kingambit')"
    )
    page.go_back()
    page.wait_for_function("location.hash === '#/tiers'")
    assert _active_panel_state(page)["panel"] == "tiers"
    assert not page.errors


def test_picking_a_pokemon_records_a_history_entry(site_url, open_page):
    page = open_page()
    page.goto(site_url + "#/pokemon/garchomp")
    page.wait_for_load_state("networkidle")
    page.select_option("#pokemon-profile-filter", "sneasler")
    page.wait_for_function("location.hash === '#/pokemon/sneasler'")
    page.go_back()
    page.wait_for_function("location.hash === '#/pokemon/garchomp'")
    page.wait_for_function(
        "document.getElementById('pokemon-profile-stats').innerText.includes('Garchomp')"
    )


def test_sub_tabs_live_in_the_route(site_url, open_page):
    page = open_page()
    page.goto(site_url + "#/usage")
    page.wait_for_load_state("networkidle")
    page.click('[data-panel="usage"] .subtab-btn[data-route="trends"]')
    page.wait_for_function("location.hash === '#/usage/trends'")
    page.goto(site_url + "#/usage/success")
    page.wait_for_load_state("networkidle")
    selected = page.locator('[data-panel="usage"] .subtab-btn[aria-selected="true"]')
    assert selected.get_attribute("data-route") == "success"


@pytest.mark.parametrize(
    "legacy,expected",
    [
        ("#usage", "#/usage"),
        ("#pokemon-profile", "#/pokemon"),
        ("?tab=compare&a=sneasler&b=garchomp", "#/compare/sneasler,garchomp"),
        ("?tab=core-explorer&core=incineroar&size=triple", "#/cores/incineroar/triple"),
    ],
)
def test_links_from_before_routing_still_open(site_url, open_page, legacy, expected):
    page = open_page()
    page.goto(site_url + legacy)
    page.wait_for_load_state("networkidle")
    assert page.evaluate("location.hash") == expected
    assert "tab=" not in page.evaluate("location.search")
    assert _active_panel_state(page)["content"]


def test_default_view_stays_within_its_fetch_budget(site_url, open_page):
    """U8: the default view makes no more than 3 data fetches."""
    page = open_page()
    fetched = []
    page.on("request", lambda request: fetched.append(request.url))
    page.goto(site_url)
    page.wait_for_load_state("networkidle")
    data_fetches = [url for url in fetched if "/data/" in url and url.endswith(".json")]
    assert len(data_fetches) <= 3, data_fetches


# The payload budget is checked against the committed, real-data site, not
# the fixture: it's the real marts that grow.
PUBLISHED_SITE = Path(__file__).resolve().parents[2] / "docs" / "dashboard"
CORE_PAYLOAD_BUDGET_BYTES = 500 * 1024


def _gzip_size(path: Path) -> int:
    return len(gzip.compress(path.read_bytes(), compresslevel=6))


def test_core_payload_stays_under_budget():
    """U8: the page, its scripts, data/core.json and the default regulation's
    shard (what the first data view downloads) stay under 500KB
    compressed."""
    index = PUBLISHED_SITE / "index.html"
    if not index.exists():
        pytest.skip("docs/dashboard has not been built")
    html = index.read_text(encoding="utf-8")
    start = html.index("window.DASHBOARD_DATA = ") + len("window.DASHBOARD_DATA = ")
    critical = json.loads(html[start : html.index("</script>", start)].rstrip().rstrip(";"))
    files = [index] + sorted(PUBLISHED_SITE.glob("*.js"))
    mart_files = critical.get("mart_files") or {}
    if mart_files:
        files.append(PUBLISHED_SITE / mart_files["core"])
        scope = mart_files["scopes"].get(critical.get("default_scope"))
        if scope:
            files.append(PUBLISHED_SITE / scope)
    total = sum(_gzip_size(path) for path in files)
    assert total <= CORE_PAYLOAD_BUDGET_BYTES, (
        f"core payload is {total / 1024:.0f}KB compressed, over the "
        f"{CORE_PAYLOAD_BUDGET_BYTES / 1024:.0f}KB budget: "
        + ", ".join(f"{p.name} {_gzip_size(p) / 1024:.0f}KB" for p in files)
    )
