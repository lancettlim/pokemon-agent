"""Sprint 13 (docs/upgrade-plan-2027q2.md): the top-cut bracket and paths
(E2), Day 2 conversion (E1), the Top 12 card's share controls (V8, M4).

The fixture gives EVT-LOU an eight-player bracket (1v8, 4v5, 3v6, 2v7, the
better seed winning) and Day 2 as each event's first six teams.
"""

from __future__ import annotations

DURING_MC = "2026-10-20T12:00:00Z"
EVENT = "#/event/EVT-LOU"


def _open_event(open_page, site_url, **kwargs):
    page = open_page(clock=DURING_MC, **kwargs)
    page.goto(site_url + EVENT)
    page.wait_for_selector("#event-bracket .bracket-match")
    return page


def test_the_bracket_shows_every_round_in_columns_on_desktop(site_url, open_page):
    page = _open_event(open_page, site_url)
    assert page.locator("#event-bracket-chip").inner_text().lower() == "8 players"
    assert "Team vs team" in page.locator("#event-bracket-note").text_content()
    rounds = page.locator("#event-bracket .bracket-round")
    assert rounds.count() == 3
    assert all(rounds.nth(i).is_visible() for i in range(3))
    assert not page.locator("#event-bracket .bracket-tabs").is_visible()
    # Bracket order: the final's two semifinals' feeders sit together, so
    # the quarterfinals read 1v8, 4v5, 3v6, 2v7.
    first_round = page.locator("#event-bracket .bracket-round").first
    names = first_round.locator(".bracket-side .sb-name").all_text_contents()
    assert names[:4] == ["Player 1", "Player 8", "Player 4", "Player 5"]
    # The winner's side carries the W.
    assert (
        first_round.locator(".bracket-side.is-winner .sb-name").first.text_content() == "Player 1"
    )
    assert not page.errors


def test_phones_get_round_tabs(site_url, open_page):
    page = _open_event(open_page, site_url, width=360, height=780)
    tabs = page.locator("#event-bracket .bracket-tabs [data-bracket-round]")
    assert tabs.count() == 3
    visible = [
        r for r in range(3) if page.locator("#event-bracket .bracket-round").nth(r).is_visible()
    ]
    assert visible == [0]
    tabs.nth(2).click()
    final = page.locator("#event-bracket .bracket-round").nth(2)
    assert final.is_visible()
    assert final.locator(".bracket-match").count() == 1
    assert page.evaluate("document.documentElement.scrollWidth") <= 360


def test_a_player_opens_their_path(site_url, open_page):
    page = _open_event(open_page, site_url)
    page.locator("#event-bracket [data-path-team='EVT-LOU-T01']").first.click()
    panel = page.locator("#event-path")
    assert panel.is_visible()
    text = panel.text_content()
    assert "Player 1's path" in text
    assert "Team vs team" in text
    rounds = panel.locator(".path-list li")
    # Two Swiss rounds and three top-cut rounds, in order.
    assert rounds.count() == 5
    assert [c.lower() for c in panel.locator(".path-list .phase-chip").all_inner_texts()] == [
        "day 1",
        "day 2",
        "top cut",
        "top cut",
        "top cut",
    ]
    panel.locator("[data-path-close]").click()
    assert not panel.is_visible()


def test_day2_conversion_holds_back_small_fields(site_url, open_page):
    page = _open_event(open_page, site_url)
    note = page.locator("#event-conversion-note")
    assert note.is_visible()
    assert "6 of 12 teams reached Day 2" in note.text_content()
    assert "held back" in note.text_content()
    cells = page.locator("#event-conversion-table tbody tr").first.locator("td")
    assert cells.count() >= 4
    # A 12-team field is far under the floor: shares, but no ratio.
    assert "—" in page.locator("#event-conversion-table tbody").inner_text()


def test_the_board_has_a_day2_switch_with_conversion(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url)
    page.wait_for_load_state("networkidle")
    page.locator('[data-board-scope="day2"]').click()
    chip = page.locator("#top-board .board-band-scope .phase-chip")
    assert chip.inner_text().lower() == "day 2"
    title = page.locator("#top-board .board-tile").first.get_attribute("title")
    assert "Day 2 conversion" in title


def test_the_board_card_downloads_and_shares(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.add_init_script(
        """
        window.__shared = null;
        navigator.canShare = () => true;
        navigator.share = (data) => { window.__shared = data; return Promise.resolve(); };
        """
    )
    page.goto(site_url)
    page.wait_for_load_state("networkidle")
    download = page.locator("#top-board a[download]")
    assert download.get_attribute("href").endswith("top12-regulation-m-c-all-landscape.png")
    page.locator("#top-board [data-share-files]").click()
    page.wait_for_function("window.__shared !== null")
    shared = page.evaluate(
        "({n: window.__shared.files.length, names: window.__shared.files.map(f => f.name),"
        " title: window.__shared.title})"
    )
    assert shared["n"] == 2
    assert shared["names"] == [
        "top12-regulation-m-c-all-portrait.png",
        "top12-regulation-m-c-all-story.png",
    ]
    assert "Top 12 Pokémon" in shared["title"]
    # The Day 2 board shares the Day 2 card.
    page.locator('[data-board-scope="day2"]').click()
    assert (
        page.locator("#top-board a[download]")
        .get_attribute("href")
        .endswith("top12-regulation-m-c-day2-landscape.png")
    )


def test_event_pages_offer_their_cards(site_url, open_page):
    page = _open_event(open_page, site_url)
    links = page.locator("#event-header .event-cards a[download]")
    assert links.count() == 2
    hrefs = [links.nth(i).get_attribute("href") for i in range(2)]
    assert hrefs[0].endswith("top12-event-EVT-LOU-all-landscape.png")
    assert hrefs[1].endswith("top12-event-EVT-LOU-day2-landscape.png")


def test_copying_on_a_touch_screen_confirms_with_a_toast(site_url, open_page):
    page = open_page(
        clock=DURING_MC,
        width=390,
        height=844,
        touch=True,
        permissions=["clipboard-read", "clipboard-write"],
    )
    page.add_init_script(
        "window.matchMedia = (q) => ({matches: q === '(hover: none)', media: q,"
        " addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}});"
    )
    page.goto(site_url + EVENT)
    page.wait_for_selector("#event-top8 [data-copy]")
    page.locator("#event-top8 [data-copy]").first.click()
    toast = page.locator("#toast")
    toast.wait_for(state="visible")
    assert "Copied" in toast.inner_text()
