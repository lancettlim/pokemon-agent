"""Sprint 14 (docs/upgrade-plan-2027q2.md, S2): the Showdown ladder lens.

The fixture has Smogon statistics for M-C only (dashboard_fixture.
LADDER_SHARES): on the 1760+ Bo1 ladder Garchomp is played 8 pts above its
tournament share and Gholdengo 8 pts below; Kingambit has seven checks and
three spreads.
"""

from __future__ import annotations

DURING_MC = "2026-10-20T12:00:00Z"


def _open(open_page, site_url, route, selector, **kwargs):
    page = open_page(clock=DURING_MC, **kwargs)
    page.goto(site_url + route)
    page.wait_for_selector(selector)
    return page


def test_ladder_vs_tournament_plots_every_pokemon_and_lists_the_gaps(site_url, open_page):
    page = _open(open_page, site_url, "#/usage/ladder", "#ladder-scatter .dot")
    assert page.locator("#ladder-scatter .dot").count() == 8
    assert page.locator("#ladder-scatter .dot.is-even").count() == 2  # Incineroar, Pelipper
    note = page.locator("#ladder-note")
    assert "1,631,943 Bo1 ladder battles" in note.text_content()
    assert note.locator("a").get_attribute("href") == "https://www.smogon.com/stats/2026-09/"
    assert "September 2026" in note.text_content()
    lists = page.locator("#ladder-lists section")
    assert "Played more on the ladder" in lists.nth(0).text_content()
    assert lists.nth(0).locator("li .pokemon-link").first.text_content().strip() == "Garchomp"
    assert lists.nth(0).locator(".ladder-gap").first.text_content() == "+8.0 pts"
    assert lists.nth(1).locator("li .pokemon-link").first.text_content().strip() == "Gholdengo"
    # A dot opens the Pokémon's profile and names both shares.
    tip = page.locator('#ladder-scatter a[href$="/garchomp"]').get_attribute("data-tip")
    assert "ladder 28.0%" in tip and "official tournaments 20.0%" in tip
    assert not page.errors


def test_the_ladder_switches_say_when_a_file_isnt_published(site_url, open_page):
    page = _open(open_page, site_url, "#/usage/ladder", "#ladder-scatter .dot")
    page.locator('[data-ladder-variant="bo3"]').click()
    assert page.locator("#ladder-scatter .dot").count() == 5
    assert page.locator('[data-ladder-variant="bo3"]').get_attribute("aria-pressed") == "true"
    page.locator('[data-ladder-cutoff="0"]').click()
    assert "published no Bo3 all-ratings file" in page.locator("#ladder-note").text_content()
    assert page.locator("#ladder-scatter .dot").count() == 0


def test_phones_get_the_two_lists_without_the_scatter(site_url, open_page):
    page = _open(open_page, site_url, "#/usage/ladder", "#ladder-lists li", width=390, height=844)
    assert not page.locator("#ladder-scatter").is_visible()
    assert page.locator("#ladder-lists section").nth(1).is_visible()
    assert page.evaluate("document.documentElement.scrollWidth") <= 390


def test_profile_checks_and_counters_are_labelled_ladder(site_url, open_page):
    page = _open(open_page, site_url, "#/pokemon/kingambit/counters", "#profile-counters li")
    panel = page.locator('[data-subpanel="profile-counters"]')
    assert panel.locator(".source-chip").first.text_content() == "Showdown ladder, from battle logs"
    items = page.locator("#profile-counters li")
    assert items.count() == 6
    assert items.first.locator(".pokemon-link").text_content().strip() == "Garchomp"
    assert "KO'd or switched out" in items.first.locator(".counter-rate").get_attribute("data-tip")
    more = page.locator("#profile-counters-more")
    assert more.text_content() == "Show all 7"
    more.click()
    assert items.count() == 7
    assert more.text_content() == "Show fewer"
    assert not page.errors


def test_profile_spreads_are_ladder_only(site_url, open_page):
    page = _open(open_page, site_url, "#/pokemon/kingambit/spreads", "#profile-spreads li")
    panel = page.locator('[data-subpanel="profile-spreads"]')
    assert "tournament sheets don't publish spreads" in panel.locator(".source-chip").text_content()
    rows = page.locator("#profile-spreads li")
    assert rows.count() == 3
    assert rows.first.locator(".spread-points").text_content() == "Adamant32 HP / 32 Atk / 2 SpD"
    assert rows.first.locator(".spread-share").text_content() == "15.8%"


def test_a_pokemon_without_ladder_rows_says_so(site_url, open_page):
    page = _open(
        open_page, site_url, "#/pokemon/pelipper/spreads", "#profile-spreads-note:not(:empty)"
    )
    assert (
        "doesn't appear in Reg M-C's 1760+ Bo1 ladder statistics"
        in page.locator("#profile-spreads-note").text_content()
    )
    page.locator('[data-subtab="profile-counters"]').click()
    assert "met no opponent 100 times" in page.locator("#profile-counters-note").text_content()


def test_a_regulation_smogon_has_no_file_for_says_so(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url + "?reg=m-b#/usage/ladder")
    page.wait_for_selector("#ladder-note:not(:empty)")
    assert (
        "hasn't published ladder statistics for Reg M-B"
        in page.locator("#ladder-note").text_content()
    )
    page.goto(site_url + "?reg=m-b#/pokemon/kingambit/counters")
    page.wait_for_selector("#profile-counters-note:not(:empty)")
    assert (
        "no checks and counters for Reg M-B"
        in page.locator("#profile-counters-note").text_content()
    )


def test_all_regulations_shows_the_newest_ladder_and_says_which(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url + "?reg=all#/usage/ladder")
    page.wait_for_selector("#ladder-scatter .dot")
    assert "so this shows Reg M-C" in page.locator("#ladder-note").text_content()


def test_the_profile_header_fits_a_phone(site_url, open_page):
    # The stat bars need 260px beside a 128px hero: on phones the header
    # wraps instead of running past the panel's clipped edge.
    page = _open(
        open_page,
        site_url,
        "#/pokemon/kingambit",
        "#pokemon-profile-stats .stat-bars",
        width=360,
        height=780,
    )
    overflow = page.evaluate(
        """() => Array.from(document.querySelectorAll('#pokemon-profile-stats *'))
            .filter(el => el.getBoundingClientRect().right > window.innerWidth + 1).length"""
    )
    assert overflow == 0
