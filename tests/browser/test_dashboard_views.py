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


def test_event_page_lists_the_top_8_and_the_fields_outliers(site_url, open_page):
    """C1: header, top 8 with sets and copy, over/under-performers."""
    page = open_page()
    page.goto(site_url + "#/event/EVT-LOU")
    page.wait_for_load_state("networkidle")
    assert "Louisville" in page.locator("#event-header").inner_text()
    assert "360 teams" in page.locator("#event-header").inner_text()
    cards = page.locator("#event-top8 .team-card")
    assert cards.count() == 8
    first = cards.first.inner_text()
    assert first.startswith("1st") and "Player 1" in first
    assert cards.first.locator("[data-copy]").count() == 1
    assert page.locator("#event-over-table tbody tr").count() > 0
    assert page.locator("#event-under-table tbody tr").count() > 0
    # The Events tab is highlighted while an event page is open.
    selected = page.locator('.tab-btn[aria-selected="true"]')
    assert selected.get_attribute("data-tab") == "events"
    assert not page.errors


def test_an_unknown_event_says_so(site_url, open_page):
    page = open_page()
    page.goto(site_url + "#/event/NOPE")
    page.wait_for_load_state("networkidle")
    assert "No event with id" in page.locator("#event-header").inner_text()


def test_top_teams_lead_with_placement_and_filter_by_tier(site_url, open_page):
    """C2: "1st · 9–1" headline, placement-within-tier ranking, ?tier=."""
    page = open_page()
    page.goto(site_url + "#/teams")
    page.wait_for_load_state("networkidle")
    first = page.locator("#top-teams-grid .team-card").first
    assert first.locator(".team-card-headline").inner_text().startswith("1st")
    page.select_option("#top-teams-tier", "regional")
    page.wait_for_function("location.hash === '#/teams?tier=regional'")
    events = page.locator("#top-teams-grid .team-card-who").all_inner_texts()
    assert events and all("Regional" in text for text in events)
    page.select_option("#top-teams-sort", "win_rate")
    page.wait_for_function("location.hash === '#/teams?tier=regional&sort=win-rate'")


def test_overview_has_the_latest_event_and_starter_teams(site_url, open_page):
    """C1/P5: the Overview links the newest event and offers starter teams."""
    page = open_page()
    page.goto(site_url)
    page.wait_for_load_state("networkidle")
    latest = page.locator("#overview-latest-event")
    assert "Louisville" in latest.inner_text()
    starters = page.locator("#overview-starters .team-card")
    assert starters.count() == 3
    assert starters.first.locator("[data-copy]").count() == 1


def test_use_this_team_loads_the_real_sheet_into_the_builder(site_url, open_page):
    """C2/P4: Use this team loads the six Pokémon with their sets, undoably."""
    page = open_page()
    page.goto(site_url + "#/event/EVT-LOU")
    page.wait_for_load_state("networkidle")
    page.locator("#event-top8 .team-card").first.get_by_text("Use this team").click()
    page.wait_for_function("location.hash === '#/builder'")
    page.wait_for_function("!document.getElementById('team-builder-notice').hidden")
    assert "Loaded Player 1's team" in page.locator("#team-builder-notice").inner_text()
    assert page.locator("#team-builder-slots .team-slot:not(.empty)").count() == 6


def test_converged_lists_load_with_their_sets(site_url, open_page):
    page = open_page()
    page.goto(site_url + "#/builder/list/TL0")
    page.wait_for_load_state("networkidle")
    page.wait_for_function("!document.getElementById('team-builder-notice').hidden")
    assert page.locator("#team-builder-slots .team-slot:not(.empty)").count() == 6


def test_profile_hub_v2_sections(site_url, open_page):
    """P2: per-regulation trend, recently viewed, teammates, teams, pressure."""
    page = open_page()
    page.goto(site_url + "#/pokemon/sneasler")
    page.wait_for_load_state("networkidle")
    page.goto(site_url + "#/pokemon/garchomp")
    page.wait_for_load_state("networkidle")
    assert page.locator("#pokemon-profile-stats .trend-svg circle").count() == 2
    assert page.locator('#profile-recent a[href="#/pokemon/sneasler"]').count() == 1

    page.click('[data-panel="pokemon-profile"] .subtab-btn[data-route="cores"]')
    assert page.locator("#profile-pair-table tbody tr").count() > 0
    page.click('[data-panel="pokemon-profile"] .subtab-btn[data-route="teams"]')
    page.wait_for_function("location.hash === '#/pokemon/garchomp/teams'")
    assert page.locator("#profile-teams .team-card").count() > 0
    page.click('[data-panel="pokemon-profile"] .subtab-btn[data-route="pressure"]')
    summary = page.locator("#profile-pressure-summary").inner_text()
    # The fixture's damaging moves include Dragon and Fairy but no Ice.
    assert "hits Garchomp for" in summary and "dragon" in summary
    first = page.locator("#profile-pressure-table tbody tr").first.inner_text().lower()
    assert "dragon" in first  # the biggest pressure above neutral
    assert not page.errors


def test_calculator_presets_and_meta_mode(site_url, open_page):
    """P3: each side starts on its #1 set; "vs the meta" lists the top Pokémon."""
    page = open_page()
    page.goto(site_url + "#/matchup/gholdengo/incineroar")
    page.wait_for_load_state("networkidle")
    pressed = page.locator(
        '#matchup-toggle-row .toggle-chip[aria-pressed="true"]'
    ).all_inner_texts()
    assert "Choice Specs" in pressed  # Gholdengo's #1 set
    assert any("Intimidate" in t for t in pressed)  # Incineroar's #1 set
    assert "Choice Specs" in page.locator("#matchup-preset-note").inner_text()

    page.click('[data-calc-mode="meta"]')
    page.wait_for_function("location.hash === '#/matchup/gholdengo/meta'")
    rows = page.locator("#matchup-meta-table tbody tr")
    assert rows.count() == 8  # every fixture Pokémon; the top 12 in real data
    assert "%" in rows.first.inner_text()
    assert page.locator("#matchup-damage-result").is_hidden()
    assert not page.errors


def test_builder_share_link_saved_teams(site_url, open_page):
    """P4: a share link opens the team; teams save, load and delete."""
    page = open_page(permissions=["clipboard-read", "clipboard-write"])
    page.goto(site_url + "#/builder/garchomp.0,gholdengo.1")
    page.wait_for_load_state("networkidle")
    page.wait_for_function("!document.getElementById('team-builder-notice').hidden")
    assert page.locator("#team-builder-slots .team-slot:not(.empty)").count() == 2
    page.click("#team-builder-share")
    page.wait_for_function(
        "document.getElementById('team-builder-share').textContent === 'Link copied'"
    )
    link = page.evaluate("navigator.clipboard.readText()")
    assert "reg=m-c" in link and link.endswith("#/builder/garchomp.0,gholdengo.1")

    page.fill("#team-builder-save-name", "Scarf Chomp")
    page.click("#team-builder-save")
    saved = page.locator("#team-builder-saved li")
    assert saved.count() == 1 and "Scarf Chomp" in saved.first.inner_text()
    page.click("#team-builder-clear")
    assert page.locator("#team-builder-slots .team-slot:not(.empty)").count() == 0
    saved.first.get_by_text("Load").click()
    assert page.locator("#team-builder-slots .team-slot:not(.empty)").count() == 2
    page.locator("[data-saved-delete]").first.click()
    assert page.locator("#team-builder-saved li").count() == 0


def test_add_to_builder_keeps_the_rest_of_the_team(site_url, open_page):
    page = open_page()
    page.goto(site_url + "#/builder/pelipper.0")
    page.wait_for_load_state("networkidle")
    page.goto(site_url + "#/pokemon/garchomp")
    page.wait_for_load_state("networkidle")
    page.locator("#pokemon-profile-set").get_by_text("Add to Builder").click()
    page.wait_for_function("location.hash === '#/builder'")
    page.wait_for_function(
        "document.querySelectorAll('#team-builder-slots .team-slot:not(.empty)').length === 2"
    )


def test_usage_event_window_compares_with_earlier_events(site_url, open_page):
    """C4: "since <event>" / "last N events" with the change against before."""
    page = open_page()
    page.goto(site_url + "#/usage")
    page.wait_for_load_state("networkidle")
    page.select_option("#usage-window-filter", "last-1")
    page.wait_for_function("location.hash === '#/usage?window=last-1'")
    assert page.locator("#usage-table").is_hidden()
    rows = page.locator("#usage-window-table tbody tr")
    assert rows.count() == 8
    assert "pts" in page.locator("#usage-window-table").inner_text()
    assert "Louisville" in page.locator("#usage-table-note").inner_text()
    assert page.locator("#usage-tier-filter").is_disabled()


def test_tables_copy_with_a_citation(site_url, open_page):
    """C4: "Copy with citation" copies the rows and a source line."""
    page = open_page(permissions=["clipboard-read", "clipboard-write"])
    page.goto(site_url + "#/usage")
    page.wait_for_load_state("networkidle")
    page.locator("#usage-table .data-table-cite").click()
    page.wait_for_function(
        "document.querySelector('#usage-table .data-table-cite').textContent === 'Copied'"
    )
    text = page.evaluate("navigator.clipboard.readText()")
    lines = text.splitlines()
    assert lines[0].startswith("#\tPokémon")
    assert "Rillaboom" in lines[1]
    assert lines[-1].startswith("Source: Pokémon Champions Data Platform")
    assert "Reg M-C" in lines[-1] and "n = 710 teams" in lines[-1]


def test_what_changed_names_its_baseline_and_defaults_to_early_vs_recent(site_url, open_page):
    """C4 (finding 6): M-B is one event, so M-C opens on early vs recent."""
    page = open_page()
    page.goto(site_url)
    page.wait_for_load_state("networkidle")
    panel = page.locator("#movers-panel")
    assert "What changed within Reg M-C" in panel.text_content()
    assert page.locator('[data-movers="window"]').get_attribute("aria-pressed") == "true"
    assert "(1 event, 395 teams)" in page.locator('[data-movers="previous"]').inner_text()
    page.click('[data-movers="previous"]')
    assert "What changed in Reg M-C vs Reg M-B" in panel.text_content()


def test_player_search_opens_the_player_page(site_url, open_page):
    """C3: search by name, then the player's events, Pokémon and record
    against archetypes, in the selected regulation."""
    page = open_page()
    page.goto(site_url + "#/players")
    page.wait_for_load_state("networkidle")
    # No query: the regulation's top-8 finishers.
    assert page.locator("#player-search-table tbody tr").count() == 8
    assert "12 players on record" in page.locator("#player-search-note").inner_text()
    page.fill("#player-search", "player 1")
    assert page.locator("#player-search-table tbody tr").count() == 4  # 1, 10, 11, 12
    page.fill("#player-search", "nobody")
    assert "No player on record" in page.locator("#player-search-table").inner_text()
    page.fill("#player-search", "")
    page.locator("#player-search-table tbody tr").first.get_by_text("Player 1").click()
    page.wait_for_function("location.hash === '#/player/P000'")

    assert "Player 1" in page.locator("#player-header").inner_text()
    assert "best finish 1st" in page.locator("#player-header").inner_text()
    # Two M-C events on the page; the M-B one is a link away.
    cards = page.locator("#player-teams .team-card")
    assert cards.count() == 2
    assert "Player 1" not in cards.first.locator(".team-card-who").inner_text()
    assert cards.first.locator("[data-copy]").count() == 1
    note = page.locator("#player-events-note")
    assert "2 events in Reg M-C" in note.inner_text()
    assert note.locator("a").first.get_attribute("href").endswith("reg=m-b#/player/P000")
    assert page.locator("#player-pokemon-table tbody tr").count() > 0
    archetypes = page.locator("#player-archetype-table tbody tr")
    assert archetypes.count() == 2
    assert "3–1" in archetypes.first.inner_text()
    # The Players tab is highlighted while a player page is open.
    selected = page.locator('.tab-btn[aria-selected="true"]')
    assert selected.get_attribute("data-tab") == "players"
    assert not page.errors


def test_an_unknown_player_says_so(site_url, open_page):
    page = open_page()
    page.goto(site_url + "#/player/NOPE")
    page.wait_for_load_state("networkidle")
    assert "No player with id" in page.locator("#player-header").inner_text()
    assert not page.errors


def test_data_section_has_a_glossary_table_cards_and_a_dictionary(site_url, open_page):
    """U4/D2: How to read, Tables and Dictionary, all generated."""
    page = open_page()
    page.goto(site_url + "#/data/how-to-read")
    page.wait_for_load_state("networkidle")
    glossary = page.locator("#ds-glossary")
    assert glossary.locator("dt").count() >= 10
    assert "Wilson bound" in glossary.inner_text()

    page.click('[data-panel="data-sources"] .subtab-btn[data-route="tables"]')
    page.wait_for_function("location.hash === '#/data/tables'")
    assert "Dataset 9.9.0, published 2026-10-15" in page.locator("#ds-tables-lead").inner_text()
    release = page.locator("#ds-release-cards .data-card")
    assert release.count() == 2
    link = release.first.locator("a")
    assert link.inner_text() == "Download the 9.9.0 package (zip)"
    assert link.get_attribute("href").endswith("pokemon-champions-data-9.9.0.zip")
    # Descriptions are for readers: no maintainer pointers into the repo.
    assert "schema.json" not in page.locator("#ds-release-cards").inner_text()
    marts = page.locator("#ds-mart-cards .data-card")
    assert marts.count() > 10
    assert "data/" in page.locator("#ds-mart-cards").inner_text()

    page.click('[data-panel="data-sources"] .subtab-btn[data-route="dictionary"]')
    entry = page.locator("#dict-tournament_team_results")
    entry.locator("summary").click()
    fields = entry.locator("tbody tr").all_inner_texts()
    assert any(row.startswith("placement") for row in fields)
    # Display names the shards drop are not listed as fields.
    assert not any(row.startswith("pokemon_name") for row in fields)
    assert not page.errors


def test_glossary_terms_explain_themselves_where_they_appear(site_url, open_page):
    """U4: jargon is a .term with its definition on hover and focus."""
    page = open_page()
    page.goto(site_url + "#/tiers")
    page.wait_for_load_state("networkidle")
    page.locator("details.method:has(#tiers-method) summary").click()
    page.locator('#tiers-method .term:has-text("Wilson lower bound")').hover()
    bubble = page.locator("#tip-bubble")
    assert bubble.is_visible() and "95% confidence interval" in bubble.inner_text()

    page.goto(site_url + "#/usage")
    page.wait_for_selector("#usage-table th .term")

    page.goto(site_url + "#/pokemon/garchomp")
    page.wait_for_load_state("networkidle")
    hhi = page.locator('#profile-item-concentration .term:has-text("HHI")').first
    hhi.focus()
    assert "Herfindahl" in page.locator("#tip-bubble").inner_text()

    page.goto(site_url)
    page.wait_for_load_state("networkidle")
    assert page.locator('#movers-panel .term:has-text("pts")').count() == 1
    assert not page.errors


def test_a_tap_shows_a_shares_denominator(site_url, open_page):
    """U4: every share's "N of M" shows on tap, not only on hover."""
    page = open_page(390, 844, touch=True)
    page.goto(site_url + "#/pokemon/garchomp")
    page.wait_for_load_state("networkidle")
    cell = page.locator("#profile-item-table td[data-tip]").first
    cell.tap()
    bubble = page.locator("#tip-bubble")
    assert bubble.is_visible() and " of " in bubble.inner_text()
    # A glossary term opens on tap too, and a second tap closes it.
    term = page.locator('#profile-item-concentration .term:has-text("HHI")')
    term.tap()
    assert bubble.is_visible() and "Herfindahl" in bubble.inner_text()
    term.tap()
    assert bubble.is_hidden()
    cell.tap()
    # Changing view closes it.
    page.goto(site_url + "#/usage")
    page.wait_for_load_state("networkidle")
    assert bubble.is_hidden()
