"""Sprint 16 (docs/upgrade-plan-2027q2.md, laundry list #21, #23, #24, #30,
#34): the team sheet image, ladder checks in the threat screen, the speed
line, archetype matchups and the compare tray."""

from __future__ import annotations

import json

DURING_MC = "2026-10-20T12:00:00Z"
TEAM_KEY = "pokemonChampionsTeamBuilder"


def _team(*pairs):
    return json.dumps(
        [
            {
                "key": k,
                "item": i,
                "ability": "Intimidate",
                "nature": None,
                "moves": ["Protect", "Fake Out"],
            }
            for k, i in pairs
        ]
    )


def test_the_builder_saves_an_open_team_sheet_image(site_url, open_page):
    page = open_page(
        clock=DURING_MC,
        storage={TEAM_KEY: _team(("incineroar", "Sitrus Berry"), ("garchomp", "Life Orb"))},
    )
    page.goto(site_url + "#/builder")
    page.wait_for_selector("#team-builder-sheet:not([disabled])")
    with page.expect_download() as download_info:
        page.locator("#team-builder-sheet").click()
    download = download_info.value
    assert download.suggested_filename == "team-sheet.png"
    data = open(download.path(), "rb").read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    # 1200x760: the IHDR chunk's width and height.
    assert int.from_bytes(data[16:20], "big") == 1200
    assert int.from_bytes(data[20:24], "big") == 760
    assert not page.errors


def test_the_threat_screen_names_ladder_checks_on_your_team(site_url, open_page):
    # The fixture's ladder lists Garchomp as Kingambit's strongest check.
    page = open_page(
        clock=DURING_MC,
        storage={TEAM_KEY: _team(("garchomp", "Life Orb"), ("pelipper", "Damp Rock"))},
    )
    page.goto(site_url + "#/builder")
    page.wait_for_selector("#team-analysis-threat-table tbody tr")
    row = page.locator("#team-analysis-threat-table tbody tr", has_text="Kingambit")
    cell = row.locator("td").nth(3)
    assert "Garchomp" in cell.text_content()
    assert "KO'd or switched out" in cell.get_attribute("data-tip")


def test_the_speed_line_places_your_team_and_flips_under_trick_room(site_url, open_page):
    page = open_page(clock=DURING_MC, storage={TEAM_KEY: _team(("kingambit", "Black Glasses"))})
    page.goto(site_url + "#/speed")
    page.wait_for_selector("#speed-line .speed-line-dot")
    assert page.locator("#speed-line .speed-line-dot.is-yours").count() == 1
    first = (
        page.locator("#speed-line-list li").first.locator(".pokemon-link").text_content().strip()
    )
    page.locator('[data-speed-trick-room="on"]').click()
    after = (
        page.locator("#speed-line-list li").first.locator(".pokemon-link").text_content().strip()
    )
    assert first != after
    assert "Trick Room" in page.locator("#speed-line-note").text_content()
    assert page.locator("#speed-line .speed-line-first").text_content().startswith("←")


def test_tailwind_doubles_your_side(site_url, open_page):
    page = open_page(clock=DURING_MC, storage={TEAM_KEY: _team(("kingambit", "Black Glasses"))})
    page.goto(site_url + "#/speed")
    page.wait_for_selector("#speed-line-list li", state="attached")
    mine = page.locator("#speed-line-list li", has=page.locator(".speed-side-chip"))
    before = int(mine.locator(".speed-value").text_content())
    page.locator('[data-speed-tailwind="on"]').click()
    assert int(mine.locator(".speed-value").text_content()) == before * 2


def test_without_a_team_tailwind_is_off_and_the_note_says_why(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url + "#/speed")
    page.wait_for_selector("#speed-line-list li", state="attached")
    assert page.locator('[data-speed-tailwind="on"]').is_disabled()
    assert "Add a team in the Builder" in page.locator("#speed-line-note").text_content()


def test_archetype_matchups_heatmap_and_phone_list(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url + "#/archetypes")
    page.wait_for_selector("#archetype-heatmap tbody tr")
    assert page.locator("#archetype-heatmap tbody tr").count() == 3
    first_row = page.locator("#archetype-heatmap tbody tr").first.locator("td")
    assert first_row.nth(1).text_content() == "75"
    assert "30–10" in first_row.nth(1).get_attribute("data-tip")
    assert "is-thin" in first_row.nth(2).get_attribute("class")
    assert "Team vs team" in page.locator(".archetype-matchups").text_content()

    phone = open_page(clock=DURING_MC, width=390, height=844)
    phone.goto(site_url + "#/archetypes")
    phone.wait_for_selector("#archetype-matchup-list li")
    assert not phone.locator(".archetype-heatmap-wrap").is_visible()
    assert "75.0%" in phone.locator("#archetype-matchup-list").text_content()
    assert phone.evaluate("document.documentElement.scrollWidth") <= 390


def test_pins_follow_the_visitor_and_open_a_comparison(site_url, open_page):
    page = open_page(clock=DURING_MC)
    for key in ("kingambit", "garchomp", "incineroar"):
        page.goto(site_url + "#/pokemon/" + key)
        page.wait_for_selector("#profile-pin")
        page.locator("#profile-pin").click()
        assert page.locator("#profile-pin").get_attribute("aria-pressed") == "true"
    tray = page.locator("#compare-tray")
    assert tray.is_visible()
    assert tray.locator(".compare-tray-list li").count() == 3
    page.goto(site_url + "#/usage")
    assert tray.is_visible()
    tray.locator("a.btn-primary").click()
    page.wait_for_selector(".compare-columns-3")
    assert page.evaluate("location.hash") == "#/compare/kingambit,garchomp,incineroar"
    assert page.locator("#compare-results thead th").count() == 4
    # Unpinning from the tray.
    tray.locator("[data-tray-remove='garchomp']").click()
    assert tray.locator(".compare-tray-list li").count() == 2
    tray.locator("[data-tray-clear]").click()
    assert tray.is_hidden()


def test_compare_takes_up_to_four_and_drops_a_removed_column(site_url, open_page):
    page = open_page(clock=DURING_MC)
    page.goto(site_url + "#/compare/kingambit,garchomp,incineroar,rillaboom")
    page.wait_for_selector(".compare-columns-4")
    assert page.locator("#compare-add").is_hidden()
    page.locator(".compare-extra-field .compare-remove").first.click()
    page.wait_for_selector(".compare-columns-3")
    assert page.evaluate("location.hash") == "#/compare/kingambit,garchomp,rillaboom"
    assert page.locator("#compare-add").is_visible()
