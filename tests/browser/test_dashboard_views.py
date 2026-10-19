"""Behaviour of individual dashboard views (docs/upgrade-plan-2027q1.md)."""

from __future__ import annotations


def _clipboard(page) -> str:
    return page.evaluate("navigator.clipboard.readText()")


def test_profile_shows_real_sets_and_copies_one_for_showdown(site_url, open_page):
    """P1: the set card lists real sets as tabs and copies the chosen one."""
    page = open_page(permissions=["clipboard-read", "clipboard-write"])
    page.goto(site_url + "#/pokemon/garchomp")
    page.wait_for_load_state("networkidle")
    card = page.locator("#pokemon-profile-set .set-card")
    assert card.locator(".set-tab").count() == 2
    assert "Choice Scarf" in card.inner_text()
    card.locator(".set-actions [data-copy]").click()
    page.wait_for_function(
        "document.querySelector('.set-actions [data-copy]').textContent === 'Copied'"
    )
    text = _clipboard(page)
    assert text.splitlines()[0] == "Garchomp @ Choice Scarf"
    assert "Ability: Rough Skin" in text
    assert "Adamant Nature" in text
    assert sum(1 for line in text.splitlines() if line.startswith("- ")) == 4

    # The second set and the looser "core" grouping are one click away.
    card.locator('.set-tab[data-set-index="1"]').click()
    assert "Sitrus Berry" in page.locator("#pokemon-profile-set").inner_text()
    page.locator('[data-set-level="core"]').click()
    assert "+ 1 flex move" in page.locator("#pokemon-profile-set").inner_text()


def test_tables_sort_and_open_the_pokemon_a_row_describes(site_url, open_page):
    """U5: header clicks sort; a row click routes to that Pokémon."""
    page = open_page()
    page.goto(site_url + "#/usage")
    page.wait_for_load_state("networkidle")
    first = page.locator("#usage-table tbody tr").first
    assert "Rillaboom" in first.inner_text()
    page.locator('#usage-table th[data-sort-key="usage_rank"]').click()
    assert "Pelipper" in page.locator("#usage-table tbody tr").first.inner_text()
    page.locator("#usage-table tbody tr").first.locator("td").last.click()
    page.wait_for_function("location.hash === '#/pokemon/pelipper'")


def test_type_popover_filters_and_reports_the_selection(site_url, open_page):
    """U6: one "Type" button opens the 18-type picker."""
    page = open_page()
    page.goto(site_url + "#/usage")
    page.wait_for_load_state("networkidle")
    toggle = page.locator("#usage-type-filter .type-popover-btn")
    assert toggle.inner_text().startswith("Any type")
    toggle.click()
    page.locator('#usage-type-filter .type-filter-chip[aria-label="dragon"]').click()
    assert "1 selected" in toggle.inner_text()
    names = page.locator("#usage-table tbody tr").all_inner_texts()
    assert len(names) == 1 and "Garchomp" in names[0]
    page.keyboard.press("Escape")
    assert page.locator("#usage-type-filter .type-popover-panel").is_hidden()


def test_pokepaste_import_lives_in_the_builder(site_url, open_page):
    """U7: importing a team is part of building one."""
    page = open_page()
    page.goto(site_url + "#/builder")
    page.wait_for_load_state("networkidle")
    page.locator("#import-team summary").click()
    page.fill(
        "#pokepaste-input", "Garchomp @ Choice Scarf\nAbility: Rough Skin\n- Earthquake\n\nPelipper"
    )
    page.click("#pokepaste-load")
    assert "Loaded 2 Pokémon" in page.locator("#pokepaste-status").inner_text()
    assert page.locator("#team-builder-slots .team-slot:not(.empty)").count() == 2
    page.goto(site_url + "#/teams")
    page.wait_for_load_state("networkidle")
    assert page.locator('[data-panel="top-teams"] #pokepaste-input').count() == 0


def test_phone_tab_rows_scroll_with_edge_cues(site_url, open_page):
    """U7: a clipped tab row says so with an edge fade."""
    page = open_page(390, 844)
    page.goto(site_url + "#/overview")
    page.wait_for_load_state("networkidle")
    row = page.locator("nav.tabs")
    assert "can-scroll-right" in row.get_attribute("class")
