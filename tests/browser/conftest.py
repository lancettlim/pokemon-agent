"""Browser tests for the static dashboard (docs/upgrade-plan-2027q1.md, U8).

The dashboard is built from the synthetic marts in dashboard_fixture.py,
served over HTTP (the page fetches its mart shards, which a browser refuses
over file://), and driven in headless Chromium. Every test here is skipped
when no Chromium can be launched, so `make test` still passes on a machine
that never ran `make setup`'s `playwright install`.
"""

from __future__ import annotations

import functools
import http.server
import os
import threading
from datetime import date
from pathlib import Path

import pytest
from dashboard_fixture import (
    ONLINE_SCOPES,
    write_fixture_archetype_matchups,
    write_fixture_event_phase_marts,
    write_fixture_ladder_marts,
    write_fixture_manifest,
    write_fixture_marts,
    write_fixture_mega_marts,
    write_fixture_name_marts,
    write_fixture_share_cards,
)

from pipelines.dashboard import build
from pipelines.regulations import Regulation, load_regulations

# Same preference as pipelines/render/team_card.py: an environment's
# pre-installed Chromium can trail the playwright package's own revision.
_PREINSTALLED_CHROMIUM = "/opt/pw-browsers/chromium"

# The fixture build's date. Rollover tests set the browser clock instead.
BUILD_DAY = date(2026, 10, 19)


def _build_site(
    root: Path,
    regulations: list[Regulation] | None = None,
    online_scopes: tuple[str, ...] = ONLINE_SCOPES,
) -> Path:
    marts_dir = root / "marts"
    normalized_dir = root / "normalized"
    write_fixture_marts(marts_dir, normalized_dir, online_scopes)
    write_fixture_mega_marts(marts_dir)
    write_fixture_event_phase_marts(marts_dir)
    write_fixture_ladder_marts(marts_dir)
    write_fixture_name_marts(marts_dir)
    write_fixture_archetype_matchups(marts_dir)
    write_fixture_manifest(root / "manifests")
    output_dir = root / "site"
    write_fixture_share_cards(output_dir)
    build.build(
        marts_dir=marts_dir,
        normalized_dir=normalized_dir,
        output_dir=output_dir,
        asset_cache_dir=root / "no-assets",
        artwork_cache_dir=root / "no-artwork",
        reference_teams_dir=root / "no-reference-teams",
        fetch_icons=False,
        regulations=regulations,
        today=BUILD_DAY,
        manifests_dir=root / "manifests",
    )
    return output_dir


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        pass


@pytest.fixture(scope="session")
def serve():
    servers = []

    def start(directory: Path) -> str:
        handler = functools.partial(_QuietHandler, directory=str(directory))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}/"

    yield start
    for server in servers:
        server.shutdown()


@pytest.fixture(scope="session")
def site_url(tmp_path_factory, serve) -> str:
    return serve(_build_site(tmp_path_factory.mktemp("dashboard")))


def regulations_with_next_set() -> list[Regulation]:
    """The real registry plus a fixture M-D starting the day M-C ends, for
    the U3 rollover cases: the new set is in force but nothing has been
    played under it."""
    registry = load_regulations()
    last = registry[-1]
    return registry + [
        Regulation(
            regulation_code="m-d",
            regulation_name="Regulation Set M-D",
            munchstats_format="fixture-regmd",
            limitless_format="m-d",
            start_date=last.end_date,
            end_date=date(last.end_date.year + 1, 3, 3),
        )
    ]


@pytest.fixture(scope="session")
def rollover_site_url(tmp_path_factory, serve) -> str:
    return serve(
        _build_site(tmp_path_factory.mktemp("dashboard-rollover"), regulations_with_next_set())
    )


@pytest.fixture(scope="session")
def online_rollover_site_url(tmp_path_factory, serve) -> str:
    """The rollover registry, with online events already played under M-D
    (docs/upgrade-plan-2027q2.md, S1): official M-D has nothing yet, online
    M-D has enough to open on."""
    return serve(
        _build_site(
            tmp_path_factory.mktemp("dashboard-online-rollover"),
            regulations_with_next_set(),
            online_scopes=("m-d:online", "all:online"),
        )
    )


@pytest.fixture(scope="session")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    launch_kwargs = {}
    if os.path.exists(_PREINSTALLED_CHROMIUM):
        launch_kwargs["executable_path"] = _PREINSTALLED_CHROMIUM
    manager = sync_api.sync_playwright().start()
    try:
        chromium = manager.chromium.launch(**launch_kwargs)
    except Exception as exc:  # noqa: BLE001 - any launch failure means "no browser here"
        manager.stop()
        pytest.skip(f"Chromium is not available: {exc}")
    yield chromium
    chromium.close()
    manager.stop()


class PageErrors(list):
    """Console errors and uncaught exceptions a page raised."""


@pytest.fixture
def open_page(browser):
    contexts = []

    def make(
        width: int = 1440,
        height: int = 900,
        clock: str | None = None,
        storage=None,
        permissions=None,
        touch: bool = False,
        service_workers: str = "block",
        timezone_id: str | None = None,
        locale: str | None = None,
    ):
        # sw.js (Q5) would answer requests page.route() means to intercept,
        # so workers are blocked unless a test is about them.
        options = {"timezone_id": timezone_id, "locale": locale}
        context = browser.new_context(
            viewport={"width": width, "height": height},
            permissions=permissions or [],
            has_touch=touch,
            service_workers=service_workers,
            **{key: value for key, value in options.items() if value},
        )
        contexts.append(context)
        if storage:
            script = "".join(
                f"localStorage.setItem({key!r}, {value!r});" for key, value in storage.items()
            )
            context.add_init_script(f"try {{ {script} }} catch (e) {{}}")
        page = context.new_page()
        if clock:
            page.clock.set_fixed_time(clock)
        errors = PageErrors()
        page.on(
            "console",
            lambda message: (
                errors.append(f"console.{message.type}: {message.text}")
                if message.type == "error"
                else None
            ),
        )
        page.on("pageerror", lambda error: errors.append(f"pageerror: {error}"))
        page.errors = errors
        return page

    yield make
    for context in contexts:
        context.close()
