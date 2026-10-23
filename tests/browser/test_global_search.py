"""docs/upgrade-plan-2027q2.md, Q3: one search box for Pokémon, players and
events, opened by "/", Ctrl/⌘+K, the header button (1024px and up) or the
⋯ menu's Search below that."""

from __future__ import annotations

DURING_MC = "2026-10-20T12:00:00Z"


def _open_search(page, site_url, route=""):
    page.goto(site_url + route)
    page.wait_for_load_state("networkidle")
    page.keyboard.press("/")
    page.wait_for_selector("#search-sheet:not([hidden])")


def test_slash_finds_a_pokemon_and_enter_opens_it(site_url, open_page):
    page = open_page(clock=DURING_MC)
    _open_search(page, site_url)
    assert page.evaluate("document.activeElement.id") == "search-input"
    page.keyboard.type("garch")
    first = page.locator("#search-results [role='option']").first
    assert first.locator(".search-label").text_content() == "Garchomp"
    assert page.locator("#search-results .search-group").first.text_content() == "Pokémon"
    page.keyboard.press("Enter")
    page.wait_for_selector("#search-sheet[hidden]", state="attached")
    assert page.evaluate("location.hash") == "#/pokemon/garchomp"
    assert not page.errors


def test_players_and_events_are_found_once_loaded(site_url, open_page):
    page = open_page(clock=DURING_MC)
    _open_search(page, site_url)
    page.keyboard.type("louisville")
    page.wait_for_selector("#search-results [role='option']")
    option = page.locator("#search-results [role='option']").first
    assert "Louisville" in option.text_content()
    assert page.locator("#search-results .search-group").first.text_content() == "Events"
    option.click()
    assert page.evaluate("location.hash") == "#/event/EVT-LOU"

    page.keyboard.press("Control+k")
    page.wait_for_selector("#search-sheet:not([hidden])")
    page.keyboard.type("player 1")
    page.wait_for_selector("#search-results .search-group")
    groups = page.locator("#search-results .search-group").all_text_contents()
    assert "Players" in groups


def test_an_empty_box_lists_recent_picks(site_url, open_page):
    page = open_page(clock=DURING_MC)
    _open_search(page, site_url)
    page.keyboard.type("kingam")
    page.keyboard.press("Enter")
    page.keyboard.press("/")
    page.wait_for_selector("#search-sheet:not([hidden])")
    assert page.locator("#search-results .search-group").first.text_content() == "Recent"
    assert page.locator("#search-results .search-label").first.text_content() == "Kingambit"
    page.keyboard.press("Escape")
    assert page.locator("#search-sheet").is_hidden()


def test_phones_open_it_from_the_menu_as_a_full_screen_sheet(site_url, open_page):
    page = open_page(clock=DURING_MC, width=390, height=844)
    page.goto(site_url)
    page.wait_for_load_state("networkidle")
    assert not page.locator(".search-btn").is_visible()
    page.locator("#more-menu-btn").click()
    page.locator("#more-menu-panel [data-search-open]").click()
    page.wait_for_selector("#search-sheet:not([hidden])")
    box = page.locator(".search-panel").bounding_box()
    assert box["width"] == 390 and box["height"] == 844
    assert page.locator("#more-menu-panel").is_hidden()
    page.locator("[data-search-close]").click()
    assert page.locator("#search-sheet").is_hidden()


def test_desktop_has_a_header_button(site_url, open_page):
    page = open_page(clock=DURING_MC, width=1440, height=900)
    page.goto(site_url)
    page.wait_for_load_state("networkidle")
    page.locator(".search-btn").click()
    page.wait_for_selector("#search-sheet:not([hidden])")
    box = page.locator(".search-panel").bounding_box()
    assert box["width"] <= 640 and box["y"] >= 60


def test_names_in_another_language_and_english_both_match(site_url, open_page):
    page = open_page(clock=DURING_MC, storage={"dashboard-name-language": "ja"})
    _open_search(page, site_url)
    page.keyboard.type("ガブ")
    assert page.locator("#search-results .search-label").first.text_content() == "ガブリアス"
    page.locator("#search-input").fill("garch")
    assert page.locator("#search-results .search-label").first.text_content() == "ガブリアス"
