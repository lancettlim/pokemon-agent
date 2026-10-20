"""The page opens on the right regulation across a set change
(docs/upgrade-plan-2027q1.md, U3).

The fixture registry adds an M-D that starts the day M-C ends, with no
events played under it. The browser clock is set to just after that date.
"""

from __future__ import annotations

import json

DAY_AFTER_MC_ENDS = "2026-12-03T12:00:00Z"
DURING_MC = "2026-10-20T12:00:00Z"


def _scope(page) -> str:
    return page.locator("#regulation-scope").input_value()


def test_a_new_regulation_without_results_falls_back_with_a_banner(rollover_site_url, open_page):
    page = open_page(clock=DAY_AFTER_MC_ENDS)
    page.goto(rollover_site_url)
    page.wait_for_load_state("networkidle")
    assert _scope(page) == "m-c"
    banner = page.locator("#rollover-banner")
    assert banner.is_visible()
    text = banner.inner_text()
    assert "Reg M-D started 2026-12-02" in text
    assert "showing Reg M-C" in text
    # Nothing has been played under M-D, so there is nothing to switch to.
    assert "Switch to" not in text
    assert not page.errors


def test_a_choice_remembered_under_the_old_regulation_is_dropped(rollover_site_url, open_page):
    remembered = json.dumps({"code": "m-b", "in_force": "m-c", "chosen_on": "2026-10-20"})
    page = open_page(clock=DAY_AFTER_MC_ENDS, storage={"dashboard-regulation": remembered})
    page.goto(rollover_site_url)
    page.wait_for_load_state("networkidle")
    assert _scope(page) == "m-c"


def test_a_choice_remembered_under_the_same_regulation_is_kept(rollover_site_url, open_page):
    remembered = json.dumps({"code": "m-b", "in_force": "m-c", "chosen_on": "2026-10-20"})
    page = open_page(clock=DURING_MC, storage={"dashboard-regulation": remembered})
    page.goto(rollover_site_url)
    page.wait_for_load_state("networkidle")
    assert _scope(page) == "m-b"
    assert not page.locator("#rollover-banner").is_visible()


def test_a_pre_rollover_bare_string_choice_is_ignored(rollover_site_url, open_page):
    page = open_page(clock=DURING_MC, storage={"dashboard-regulation": "m-b"})
    page.goto(rollover_site_url)
    page.wait_for_load_state("networkidle")
    assert _scope(page) == "m-c"


def test_reg_in_the_link_wins_over_everything(rollover_site_url, open_page):
    page = open_page(clock=DAY_AFTER_MC_ENDS)
    page.goto(rollover_site_url + "?reg=m-b")
    page.wait_for_load_state("networkidle")
    assert _scope(page) == "m-b"
    assert not page.locator("#rollover-banner").is_visible()


def test_changing_the_regulation_remembers_when_it_was_chosen(rollover_site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(rollover_site_url)
    page.wait_for_load_state("networkidle")
    # Changing the regulation reloads the page with ?reg=.
    with page.expect_navigation():
        page.select_option("#regulation-scope", "m-b")
    page.wait_for_load_state("networkidle")
    assert "reg=m-b" in page.url
    saved = json.loads(page.evaluate("localStorage.getItem('dashboard-regulation')"))
    assert saved["code"] == "m-b"
    assert saved["in_force"] == "m-c"
