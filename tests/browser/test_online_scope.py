"""Official / Online / All (docs/upgrade-plan-2027q2.md, S1).

The fixture gives M-C two Limitless online tournaments of 200 teams each,
with the usage order reversed against the official figures, so a test can
tell which population a view is showing. Official stays the default.
"""

from __future__ import annotations

DAY_AFTER_MC_ENDS = "2026-12-03T12:00:00Z"
DURING_MC = "2026-10-20T12:00:00Z"


def _first_tile(page) -> str:
    return page.locator("#top-board .board-tile").first.get_attribute("href") or ""




















def test_the_online_rollover_has_no_online_latest_event_card(online_rollover_site_url, open_page):
    page = open_page(clock=DAY_AFTER_MC_ENDS)
    page.goto(online_rollover_site_url)
    page.wait_for_load_state("networkidle")
    # Online events have no event pages: no card links to an "LP-" id.
    assert page.locator("#overview-latest-event a[href*='LP-']").count() == 0
    # No official M-D result yet, so no way back to official M-D either.
    assert page.locator("#population-banner a[data-set-scope]").count() == 0
