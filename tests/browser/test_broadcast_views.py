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
    assert band.locator(".phase-chip").inner_text().lower() == "all players"
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
