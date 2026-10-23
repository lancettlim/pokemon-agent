"""docs/upgrade-plan-2027q2.md, Q4: Pokémon names in another language.

The fixture has every Pokémon in Japanese and two in German
(dashboard_fixture.LOCALISED_NAMES).
"""

from __future__ import annotations

DURING_MC = "2026-10-20T12:00:00Z"
STORAGE_KEY = "dashboard-name-language"


def test_the_switch_reloads_the_page_in_the_chosen_language(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url)
    page.wait_for_selector("#top-board .board-tile")
    assert "Rillaboom" in page.locator("#top-board").text_content()
    page.locator("#more-menu-btn").click()
    with page.expect_navigation():
        page.locator("#name-language").select_option("ja")
    page.wait_for_selector("#top-board .board-tile")
    board = page.locator("#top-board").text_content()
    assert "ゴリランダー" in board and "Rillaboom" not in board
    assert page.locator("#name-language").input_value() == "ja"
    assert not page.errors


def test_marts_loaded_later_take_the_names_too(site_url, open_page):
    page = open_page(clock=DURING_MC, storage={STORAGE_KEY: "ja"})
    page.goto(site_url + "#/usage")
    page.wait_for_selector("#usage-table tbody tr")
    names = page.locator("#usage-table tbody .pokemon-link").all_text_contents()
    assert "ガオガエン" in [n.strip() for n in names]
    # Numbers and copy stay in English.
    assert "Pokémon" in page.locator("#usage-table thead").text_content()


def test_english_names_still_find_a_pokemon(site_url, open_page):
    page = open_page(clock=DURING_MC, storage={STORAGE_KEY: "ja"})
    page.goto(site_url + "#/pokemon/garchomp")
    page.wait_for_selector(".profile-controls .combo-input")
    combo = page.locator(".profile-controls .combo-input")
    combo.fill("incin")
    option = page.locator(".profile-controls .combo-list li").first
    assert option.text_content().strip() == "ガオガエン"


def test_a_name_missing_in_the_language_stays_english(site_url, open_page):
    page = open_page(clock=DURING_MC, storage={STORAGE_KEY: "de"})
    page.goto(site_url + "#/usage")
    page.wait_for_selector("#usage-table tbody tr")
    names = [
        n.strip() for n in page.locator("#usage-table tbody .pokemon-link").all_text_contents()
    ]
    assert "Fuegro" in names and "Rillaboom" in names


def test_portuguese_uses_the_english_names(site_url, open_page):
    page = open_page(clock=DURING_MC, storage={STORAGE_KEY: "pt"})
    page.goto(site_url)
    page.wait_for_selector("#top-board .board-tile")
    assert "Rillaboom" in page.locator("#top-board").text_content()
    page.locator("#more-menu-btn").click()
    assert page.locator("#name-language").input_value() == "pt"
