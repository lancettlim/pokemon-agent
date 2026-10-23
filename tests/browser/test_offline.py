"""docs/upgrade-plan-2027q2.md, Q5: offline at the venue. sw.js keeps the
page, its scripts and the shards a visitor opened, so the calculator and
the Builder still work when the convention Wi-Fi drops."""

from __future__ import annotations

DURING_MC = "2026-10-20T12:00:00Z"


def _visit_then_go_offline(open_page, site_url, routes):
    page = open_page(clock=DURING_MC, service_workers="allow")
    page.goto(site_url)
    page.wait_for_load_state("networkidle")
    page.evaluate("navigator.serviceWorker.ready.then(() => true)")
    # The worker takes control once installed; reload so it sees the shards.
    page.reload()
    page.wait_for_load_state("networkidle")
    for route in routes:
        page.goto(site_url + route)
        page.wait_for_load_state("networkidle")
    page.context.set_offline(True)
    return page


def test_the_site_reloads_offline_with_a_banner(site_url, open_page):
    page = _visit_then_go_offline(open_page, site_url, ["#/usage", "#/overview"])
    page.reload()
    page.wait_for_selector("#top-board .board-tile")
    banner = page.locator("#offline-banner")
    assert banner.is_visible()
    assert "offline" in banner.text_content()
    page.goto(site_url + "#/usage")
    page.wait_for_selector("#usage-table tbody tr")


def test_the_calculator_and_builder_work_offline(site_url, open_page):
    page = _visit_then_go_offline(
        open_page, site_url, ["#/matchup/rillaboom/sneasler", "#/builder"]
    )
    page.reload()
    page.goto(site_url + "#/matchup/rillaboom/sneasler")
    page.wait_for_selector("#matchup-attacker-select", state="attached")
    assert not page.locator(".tab-panel:not([hidden]) .data-load-error").count()
    page.goto(site_url + "#/builder")
    page.wait_for_selector('.tab-panel[data-panel="team-builder"]:not([hidden])')
    assert not page.locator(".tab-panel:not([hidden]) .data-load-error").count()


def test_coming_back_online_hides_the_banner(site_url, open_page):
    page = _visit_then_go_offline(open_page, site_url, [])
    page.wait_for_selector("#offline-banner:not([hidden])")
    page.context.set_offline(False)
    page.wait_for_selector("#offline-banner[hidden]", state="attached")
