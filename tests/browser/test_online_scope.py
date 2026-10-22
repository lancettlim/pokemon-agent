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


def test_official_is_the_default_and_carries_no_population_banner(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url)
    page.wait_for_load_state("networkidle")
    assert page.locator("#regulation-scope").input_value() == "m-c"
    assert page.locator("#population-scope").input_value() == "official"
    assert not page.locator("#population-banner").is_visible()
    assert "rillaboom" in _first_tile(page)
    assert not page.errors


def test_choosing_online_reloads_on_the_online_scope_with_a_banner(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url)
    page.wait_for_load_state("networkidle")
    with page.expect_navigation():
        page.select_option("#population-scope", "online")
    page.wait_for_load_state("networkidle")
    assert "reg=m-c%3Aonline" in page.url or "reg=m-c:online" in page.url
    assert page.locator("#regulation-scope").input_value() == "m-c"
    banner = page.locator("#population-banner")
    assert banner.is_visible()
    text = banner.text_content()
    assert "400 teams from 2 Limitless online tournaments in Reg M-C" in text
    assert banner.locator(".phase-chip.is-online").count() == 1
    # The online usage order, not the official one.
    assert "pelipper" in _first_tile(page)
    # "What changed" stays the official comparison, and says so.
    movers = page.locator("#movers-panel")
    if movers.is_visible():
        assert "official events only" in movers.text_content()
    assert not page.errors


def test_the_official_board_has_an_online_switch(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url)
    page.wait_for_load_state("networkidle")
    page.locator('[data-board-scope="online"]').click()
    assert "pelipper" in _first_tile(page)
    assert page.locator("#top-board .phase-chip.is-online").count() == 1
    assert "400 teams" in page.locator("#top-board .board-band-mark").text_content()


def test_a_regulation_without_online_data_greys_out_online(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url + "?reg=m-b")
    page.wait_for_load_state("networkidle")
    disabled = page.evaluate(
        "Array.from(document.querySelectorAll('#population-scope option'))"
        ".map(o => [o.value, o.disabled])"
    )
    assert dict(disabled) == {"official": False, "online": True, "combined": True}


def test_official_only_views_say_so_on_the_online_scope(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url + "?reg=m-c:online#/players")
    page.wait_for_load_state("networkidle")
    note = page.locator('.tab-panel[data-panel="players"] .official-only-note').first
    assert note.is_visible()
    assert "official events only" in note.text_content()
    page.goto(site_url + "?reg=m-c:online#/teams")
    page.wait_for_load_state("networkidle")
    assert page.locator('.tab-panel[data-panel="top-teams"] .official-only-note').first.is_visible()


def test_events_lists_online_tournaments_separately_with_links_out(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url + "#/events")
    page.wait_for_load_state("networkidle")
    assert page.locator("#online-events-head").is_visible()
    links = page.locator("#online-events-table a[href*='play.limitlesstcg.com']")
    assert links.count() == 2
    assert links.first.get_attribute("target") == "_blank"
    # The official list keeps only official events.
    assert "Online Cup" not in page.locator("#events-table").text_content()
    assert not page.errors


def test_a_thin_new_regulation_opens_on_its_online_events(online_rollover_site_url, open_page):
    page = open_page(clock=DAY_AFTER_MC_ENDS)
    page.goto(online_rollover_site_url)
    page.wait_for_load_state("networkidle")
    assert page.locator("#regulation-scope").input_value() == "m-d"
    assert page.locator("#population-scope").input_value() == "online"
    banner = page.locator("#rollover-banner")
    assert banner.is_visible()
    text = banner.text_content()
    assert "Reg M-D started 2026-12-02" in text
    assert "Official results are thin so far" in text
    assert "showing online events (400 teams)" in text
    # No official M-D result yet, so nothing to switch to; and the rollover
    # banner already says why online events are showing.
    assert "Switch to" not in text
    assert not page.locator("#population-banner").is_visible()
    assert not page.errors


def test_official_only_tables_say_so_and_cite_the_official_sample(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url + "?reg=m-c:online#/events")
    page.wait_for_load_state("networkidle")
    # The official events table on the Online scope carries its note.
    note = page.locator('.tab-panel[data-panel="events"] .official-only-note').first
    assert note.is_visible()
    assert "official events only" in note.text_content()
    # The event window's choices sit under an "Official events" heading.
    page.goto(site_url + "?reg=m-c:online#/usage")
    page.wait_for_selector(
        "#usage-window-filter optgroup[label='Official events'] option", state="attached"
    )
    assert page.locator("#usage-window-filter optgroup[label='Official events'] option").count() > 0
    assert not page.errors


def test_the_banner_link_back_to_official_is_remembered(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url + "?reg=m-c:online")
    page.wait_for_load_state("networkidle")
    link = page.locator("#population-banner a[data-set-scope]")
    assert link.get_attribute("data-set-scope") == "m-c"
    with page.expect_navigation():
        link.click()
    page.wait_for_load_state("networkidle")
    assert page.locator("#population-scope").input_value() == "official"
    saved = page.evaluate("JSON.parse(localStorage.getItem('dashboard-regulation'))")
    assert saved["code"] == "m-c"


def test_the_online_rollover_has_no_online_latest_event_card(online_rollover_site_url, open_page):
    page = open_page(clock=DAY_AFTER_MC_ENDS)
    page.goto(online_rollover_site_url)
    page.wait_for_load_state("networkidle")
    # Online events have no event pages: no card links to an "LP-" id.
    assert page.locator("#overview-latest-event a[href*='LP-']").count() == 0
    # No official M-D result yet, so no way back to official M-D either.
    assert page.locator("#population-banner a[data-set-scope]").count() == 0
