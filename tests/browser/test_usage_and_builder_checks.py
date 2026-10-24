"""docs/upgrade-plan-2027q2.md, laundry list #19 and #22: the Usage
table's rank change, and the Team Builder's item and species clauses."""

from __future__ import annotations

import json

DURING_MC = "2026-10-20T12:00:00Z"
TEAM_KEY = "pokemonChampionsTeamBuilder"


def test_usage_shows_each_pokemons_rank_change_since_the_last_event(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url + "#/usage")
    page.wait_for_selector("#usage-table tbody tr")
    headers = [h.strip() for h in page.locator("#usage-table thead th").all_text_contents()]
    assert "Rank" in headers
    cell = page.locator("#usage-table tbody tr").first.locator("td").nth(headers.index("Rank"))
    assert cell.locator(".badge").count() == 1
    assert "before Louisville" in cell.get_attribute("data-tip")


def test_an_event_window_compares_ranks_with_the_events_before_it(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url + "#/usage?window=last-1")
    page.wait_for_selector("#usage-window-table tbody tr")
    headers = [h.strip() for h in page.locator("#usage-window-table thead th").all_text_contents()]
    cell = (
        page.locator("#usage-window-table tbody tr").first.locator("td").nth(headers.index("Rank"))
    )
    assert "before these events" in cell.get_attribute("data-tip")




def _builder(open_page, site_url, slots, init_script=None):
    page = open_page(clock=DURING_MC, storage={TEAM_KEY: json.dumps(slots)})
    if init_script:
        page.add_init_script(init_script)
    page.goto(site_url + "#/builder")
    page.wait_for_selector("#team-builder-slots")
    return page


def test_two_pokemon_holding_one_item_break_the_item_clause(site_url, open_page):
    slots = [
        {"key": "incineroar", "item": "Sitrus Berry", "ability": None, "nature": None, "moves": []},
        {"key": "rillaboom", "item": "Sitrus Berry", "ability": None, "nature": None, "moves": []},
        {"key": "garchomp", "item": "Life Orb", "ability": None, "nature": None, "moves": []},
    ]
    page = _builder(open_page, site_url, slots)
    warnings = page.locator("#team-builder-warnings")
    assert warnings.is_visible()
    text = warnings.text_content()
    assert "Item clause: Incineroar and Rillaboom both hold Sitrus Berry" in text
    assert "Life Orb" not in text


def test_a_species_and_its_form_break_the_species_clause(site_url, open_page):
    # The fixture's Pokémon have no forms, so one is made a form of another.
    patch = """
      Object.defineProperty(window, "DASHBOARD_DATA", {
        configurable: true,
        set(value) { value.form_species = {garchomp: "kingambit"}; this._data = value; },
        get() { return this._data; },
      });
    """
    slots = [
        {"key": "garchomp", "item": "Life Orb", "ability": None, "nature": None, "moves": []},
        {"key": "kingambit", "item": "Black Glasses", "ability": None, "nature": None, "moves": []},
    ]
    page = _builder(open_page, site_url, slots, patch)
    assert (
        "Species clause: Garchomp and Kingambit are the same species"
        in page.locator("#team-builder-warnings").text_content()
    )


def test_a_legal_team_has_no_warnings(site_url, open_page):
    slots = [
        {"key": "incineroar", "item": "Sitrus Berry", "ability": None, "nature": None, "moves": []},
        {"key": "rillaboom", "item": "Miracle Seed", "ability": None, "nature": None, "moves": []},
    ]
    page = _builder(open_page, site_url, slots)
    assert page.locator("#team-builder-warnings").is_hidden()


def test_a_saved_team_says_which_pokemon_the_regulation_dropped(site_url, open_page):
    slots = [
        {"key": "incineroar", "item": "Sitrus Berry", "ability": None, "nature": None, "moves": []},
        {"key": "bulbasaur", "item": "Leftovers", "ability": None, "nature": None, "moves": []},
    ]
    page = _builder(open_page, site_url, slots)
    notice = page.locator("#team-builder-notice")
    assert notice.is_visible()
    assert (
        "1 Pokémon from your saved team isn't legal in Reg M-C and was removed"
        in notice.text_content()
    )
