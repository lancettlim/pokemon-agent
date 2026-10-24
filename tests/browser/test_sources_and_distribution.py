"""Sprint 17 (docs/upgrade-plan-2027q2.md, S3, S5/E5, laundry list #27,
#31, #33): "Watch on stream" links, upcoming online events, the embeddable
widget and Showdown replay bring rates."""

from __future__ import annotations

from dashboard_fixture import FIXTURE_VOD_URL

DURING_MC = "2026-10-20T12:00:00Z"


def test_a_final_with_a_video_links_to_it(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url + "#/event/EVT-LOU")
    page.wait_for_selector("#event-bracket .bracket-match")
    links = page.locator("#event-bracket .bracket-vod")
    # Only the final has a curated video.
    assert links.count() == 1
    link = links.first
    assert link.get_attribute("href") == FIXTURE_VOD_URL
    assert link.get_attribute("target") == "_blank"
    assert "noopener" in link.get_attribute("rel")
    assert "Watch on stream" in link.text_content()
    final = page.locator("#event-bracket .bracket-round").last
    assert final.locator(".bracket-vod").count() == 1
    assert not page.errors


SITE = "https://lancettlim.github.io/pokemon-agent/dashboard/"


def _open_embed(open_page, site_url, query="", **kwargs):
    page = open_page(clock=DURING_MC, **kwargs)
    page.goto(site_url + "embed.html" + query)
    page.wait_for_selector("#embed .embed-cite")
    return page


def test_the_embed_shows_the_regulations_top_12_with_its_citation(site_url, open_page):
    page = _open_embed(open_page, site_url, "?reg=m-c")
    tiles = page.locator(".embed-tile")
    # The Overview's board, tile for tile (the fixture's M-C has eight).
    expected = page.evaluate("window.EMBED_DATA.boards['m-c'].all.forms.map(t => t.k)")
    assert 0 < len(expected) <= 12
    assert tiles.count() == len(expected)
    assert tiles.first.locator("a").get_attribute("href").endswith("#/pokemon/" + expected[0])
    assert "Reg M-C" in page.locator(".embed-scope").text_content()
    cite = page.locator(".embed-cite").text_content()
    assert "official events" in cite and "teams from" in cite
    assert "unofficial fan project" in cite
    back = page.locator(".embed-cite a")
    assert back.get_attribute("href") == SITE + "?reg=m-c#/overview"
    assert back.get_attribute("target") == "_blank"
    first = tiles.first.locator("a")
    assert first.get_attribute("href").startswith(SITE + "?reg=m-c#/pokemon/")
    assert first.get_attribute("target") == "_blank"
    assert not page.errors


def test_the_embed_fits_a_narrow_column(site_url, open_page):
    page = _open_embed(open_page, site_url, "?reg=m-c", width=320, height=480)
    assert page.evaluate("document.documentElement.scrollWidth") <= 320
    # Four columns of at most three rows, inside the snippet's 480px.
    assert page.evaluate("document.documentElement.scrollHeight") <= 480
    assert not page.errors


def test_the_board_hands_out_its_embed_code(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url + "#/overview")
    page.wait_for_selector("[data-embed-toggle]")
    assert page.locator("#board-embed").is_hidden()
    page.locator("[data-embed-toggle]").click()
    code = page.locator("#board-embed .embed-code")
    assert code.is_visible()
    snippet = code.input_value()
    assert snippet.startswith("<iframe ")
    assert "embed.html?reg=m-c&amp;board=all&amp;group=forms" in snippet or (
        "embed.html?reg=m-c&board=all&group=forms" in snippet
    )
    assert page.locator("[data-embed-toggle]").get_attribute("aria-expanded") == "true"
    assert not page.errors


def test_the_ladder_view_shows_which_four_they_bring(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url + "#/usage/ladder")
    page.wait_for_selector("#ladder-bring-table tbody tr")
    section = page.locator("#ladder-bring-section")
    assert "Showdown ladder replays" in section.locator(".source-chip").text_content()
    note = page.locator("#ladder-bring-note").text_content()
    assert "1,000 rated Bo1 and Bo3 ladder battles" in note and "chose to upload" in note
    # Pelipper, on 10 complete sides, is under the 30-side floor.
    rows = page.locator("#ladder-bring-table tbody tr")
    assert rows.count() == 7
    kingambit = page.locator("#ladder-bring-table tbody tr", has_text="Kingambit")
    assert "89.6%" in kingambit.text_content()
    leads = page.locator("#ladder-lead-pairs li")
    assert leads.count() == 3
    assert "Incineroar" in leads.first.text_content() and "Rillaboom" in leads.first.text_content()
    assert "won 55.0%" in leads.first.text_content()
    assert not page.errors


def test_the_profile_carries_its_ladder_bring_line(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url + "#/pokemon/kingambit/counters")
    page.wait_for_selector("#profile-bring:not([hidden])")
    block = page.locator("#profile-bring")
    assert "Showdown ladder replays" in block.text_content()
    assert "89.6%" in block.locator(".bring-stats div").first.text_content()
    assert "Not tournament data" in block.text_content()
    # Under the floor: no line.
    page.goto(site_url + "#/pokemon/pelipper/counters")
    page.wait_for_function("document.querySelector('#profile-bring').hidden")
    assert not page.errors
