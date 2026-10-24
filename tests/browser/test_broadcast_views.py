"""The 2027 Q2 broadcast-grade views (docs/upgrade-plan-2027q2.md)."""

from __future__ import annotations


def _boxes(page, selector):
    return page.evaluate(
        """(sel) => Array.from(document.querySelectorAll(sel)).map((el) => {
            const r = el.getBoundingClientRect();
            return {top: r.top, bottom: r.bottom, left: r.left};
        })""",
        selector,
    )


def test_overview_opens_on_the_top_12_board(site_url, open_page):
    """V2: the board leads the Overview, in team share, 6 + band + 6."""
    page = open_page()
    page.goto(site_url)
    page.wait_for_load_state("networkidle")
    order = page.evaluate(
        """() => Array.from(document.querySelectorAll('[data-panel="overview"] > *'))
            .filter((el) => !el.hidden && el.offsetHeight).map((el) => el.id || el.className)"""
    )
    assert order.index("top-board") < order.index("movers-panel")
    tiles = page.locator("#top-board .board-tile")
    assert tiles.count() == 8
    first = tiles.first
    assert first.locator(".board-value").inner_text() == "60.0%"
    assert first.get_attribute("href") == "#/pokemon/rillaboom"
    assert "on 60.0% of teams (60 of 100 teams)" in first.get_attribute("aria-label")
    band = page.locator("#top-board .board-band")
    assert "Top 12 Pokémon" in band.text_content()
    assert "Reg M-C" in band.text_content() and "710 teams" in band.text_content()
    # The dashboard shows official events only, so there is no Online board.
    assert band.locator(".phase-chip").inner_text().lower() == "all players"
    assert page.locator('[data-board-scope="online"]').count() == 0
    # Desktop: tiles 1-6 above the band, the rest below it.
    band_box = _boxes(page, "#top-board .board-band")[0]
    tile_boxes = _boxes(page, "#top-board .board-tile")
    assert all(b["bottom"] <= band_box["top"] for b in tile_boxes[:6])
    assert all(b["top"] >= band_box["bottom"] for b in tile_boxes[6:])
    assert not page.errors


def test_board_puts_its_band_on_top_with_three_columns_on_a_phone(site_url, open_page):
    """M3: band first, then 3 columns of tiles at least 104px wide."""
    page = open_page(360, 780, touch=True)
    page.goto(site_url)
    page.wait_for_load_state("networkidle")
    band_box = _boxes(page, "#top-board .board-band")[0]
    tile_boxes = _boxes(page, "#top-board .board-tile")
    assert all(b["top"] >= band_box["bottom"] for b in tile_boxes)
    assert len({round(b["left"]) for b in tile_boxes}) == 3
    widths = page.evaluate(
        "Array.from(document.querySelectorAll('#top-board .board-tile')).map(e => e.offsetWidth)"
    )
    assert min(widths) >= 104


def test_board_groups_by_species_and_remembers_it(site_url, open_page):
    """V2: the Species/Forms toggle re-renders and is remembered."""
    page = open_page()
    page.goto(site_url)
    page.wait_for_load_state("networkidle")
    forms = page.locator('[data-board-group="forms"]')
    species = page.locator('[data-board-group="species"]')
    assert forms.get_attribute("aria-pressed") == "true"
    species.click()
    assert page.locator('[data-board-group="species"]').get_attribute("aria-pressed") == "true"
    assert page.evaluate("localStorage.getItem('dashboard-board-grouping')") == "species"
    page.reload()
    page.wait_for_load_state("networkidle")
    assert page.locator('[data-board-group="species"]').get_attribute("aria-pressed") == "true"
    assert page.locator("#top-board .board-tile").count() == 8


def test_team_share_notice_is_dismissed_for_good(site_url, open_page):
    """V1's risk: a one-time note on the change of unit."""
    page = open_page()
    page.goto(site_url)
    page.wait_for_load_state("networkidle")
    notice = page.locator("#team-share-notice")
    assert notice.is_visible()
    assert "share of teams" in notice.inner_text()
    page.click("#team-share-notice-dismiss")
    assert notice.is_hidden()
    page.reload()
    page.wait_for_load_state("networkidle")
    assert page.locator("#team-share-notice").is_hidden()


def test_usage_leads_with_team_share_and_keeps_slot_share_in_the_tooltip(site_url, open_page):
    """V1: the headline is share of teams; the slot share is in the tip."""
    page = open_page()
    page.goto(site_url + "#/usage")
    page.wait_for_load_state("networkidle")
    cell = page.locator("#usage-table tbody tr").first.locator("td[data-label='Usage']")
    assert "60.0%" in cell.inner_text()
    assert cell.get_attribute("data-tip") == "60 of 100 teams · 10.0% of roster slots"
    assert "100 teams" in page.locator("#usage-table-note").inner_text()


def test_speed_tiers_speak_stat_points_not_evs(site_url, open_page):
    """Q2: Champions has Stat Points; the figures were right, the words weren't."""
    page = open_page()
    page.goto(site_url + "#/speed")
    page.wait_for_load_state("networkidle")
    page.locator('[data-panel="speed-tiers"] details.method summary').click()
    method = page.locator('[data-panel="speed-tiers"] details.method').inner_text()
    assert "32 Stat Points" in method and "Stat Alignment" in method
    assert "EV" not in method
    page.goto(site_url + "#/data/how-to-read")
    page.wait_for_function("document.getElementById('ds-glossary').textContent.length > 0")
    glossary = page.locator("#ds-glossary").inner_text()
    assert "Stat Points" in glossary and "Stat Alignment" in glossary


def test_team_cards_draw_the_team_strip_with_items_and_open_a_set(site_url, open_page):
    """V3: six square tiles with item badges; a tap opens the set."""
    page = open_page()
    page.goto(site_url + "#/event/EVT-LOU")
    page.wait_for_load_state("networkidle")
    card = page.locator("#event-top8 .team-card").first
    slots = card.locator(".team-strip-slot")
    assert slots.count() == 6
    assert card.locator(".strip-item").count() == 6
    # One row of six on desktop.
    tops = {
        round(box["top"])
        for box in _boxes(page, "#event-top8 .team-card:first-child .team-strip-slot")
    }
    assert len(tops) == 1
    slots.first.click()
    pop = page.locator(".strip-pop")
    assert pop.is_visible()
    text = pop.inner_text()
    assert "Ability" in text and "Item" in text
    assert pop.locator("a").first.get_attribute("href").startswith("#/pokemon/")
    page.keyboard.press("Escape")
    assert pop.is_hidden()
    assert not page.errors


def test_team_strip_keeps_one_row_of_six_on_a_360px_phone(site_url, open_page):
    """M3: tiles of at least 44px, in one row, inside a card."""
    page = open_page(360, 780, touch=True)
    page.goto(site_url + "#/event/EVT-LOU")
    page.wait_for_load_state("networkidle")
    boxes = page.evaluate(
        """() => Array.from(document.querySelectorAll(
            '#event-top8 .team-card:first-child .team-strip-slot')).map((el) => {
            const r = el.getBoundingClientRect();
            return {top: Math.round(r.top), width: r.width};
        })"""
    )
    assert len(boxes) == 6
    assert len({b["top"] for b in boxes}) == 1
    assert min(b["width"] for b in boxes) >= 44


def test_player_lines_and_phase_chips_say_who_and_what(site_url, open_page):
    """V4/V5: name · country in chips; each card says the phase it reached."""
    page = open_page()
    page.goto(site_url + "#/event/EVT-LOU")
    page.wait_for_load_state("networkidle")
    first = page.locator("#event-top8 .team-card").first
    assert first.locator(".phase-chip").inner_text().lower() == "champion"
    assert (
        page.locator("#event-top8 .team-card").nth(1).locator(".phase-chip").inner_text().lower()
        == "top 8"
    )
    line = first.locator(".sb-player")
    assert line.locator(".sb-name").text_content() == "Player 1"
    assert "US" in line.locator(".sb-cc").inner_text()
    header = page.locator("#event-header")
    assert header.locator(".sb-rec").count() == 1  # the winner's record chip
    assert "page-band" in header.get_attribute("class")


def test_board_tiles_use_the_type_emblem(site_url, open_page):
    """One type logo everywhere: the board draws the in-game emblem."""
    page = open_page()
    page.goto(site_url)
    page.wait_for_load_state("networkidle")
    badge = page.locator("#top-board .board-tile").first.locator("img.type-icon").first
    assert badge.get_attribute("title") == "grass"


def test_mega_panel_on_events_and_the_usage_megas_view(site_url, open_page):
    """E3: each Mega's share of teams and the teams-per-Mega-count split."""
    page = open_page()
    page.goto(site_url + "#/event/EVT-LOU")
    page.wait_for_load_state("networkidle")
    rows = page.locator("#event-mega-table .stat-card")
    assert rows.count() == 2
    assert "Garchompite" in rows.first.inner_text()
    assert "50.0%" in rows.first.inner_text()  # 180 of 360 teams
    counts = page.locator("#event-mega-count .mega-count-list li")
    assert counts.count() == 3
    assert "60.0%" in counts.nth(2).inner_text()
    page.goto("about:blank")
    page.goto(site_url + "#/usage/megas")
    page.wait_for_load_state("networkidle")
    assert page.locator("#usage-mega-table .stat-card").count() == 2
    assert "100 teams" in page.locator("#usage-mega-note").inner_text()
    assert not page.errors
