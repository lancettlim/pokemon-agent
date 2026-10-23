import csv
from datetime import date

import pytest
import requests

from pipelines.extract import http as extract_http
from pipelines.extract import limitless_play
from pipelines.regulations import Regulation

# Shapes trimmed from real play.limitlesstcg.com/api responses.
_REGULATIONS = [
    Regulation("m-b", "B", "fb", "m-b", date(2026, 6, 17), date(2026, 9, 9), "M-B"),
    Regulation("m-c", "C", "fc", "m-c", date(2026, 9, 9), date(2026, 12, 2), "M-C"),
]

_LISTING = [
    {
        "id": "t-new",
        "name": "Weekly Cup #12",
        "date": "2026-10-18T18:00:00.000Z",
        "format": "M-C",
        "players": 64,
        "organizerId": 7,
    },
    {
        "id": "t-small",
        "name": "Tiny Cup",
        "date": "2026-10-17T18:00:00.000Z",
        "format": "M-C",
        "players": 9,
        "organizerId": 7,
    },
    {
        "id": "t-mono",
        "name": "Monotype Madness",
        "date": "2026-10-16T18:00:00.000Z",
        "format": "M-C",
        "players": 40,
        "organizerId": 8,
    },
    {
        "id": "t-other",
        "name": "Reg I Classic",
        "date": "2026-10-15T18:00:00.000Z",
        "format": "SVI",
        "players": 80,
        "organizerId": 9,
    },
    {
        "id": "t-old",
        "name": "Last Reg Cup",
        "date": "2026-09-01T18:00:00.000Z",
        "format": "M-B",
        "players": 50,
        "organizerId": 7,
    },
]

_STANDINGS = [
    {
        "player": "ash_k",
        "name": "Ash K",
        "country": "US",
        "placing": 1,
        "record": {"wins": 6, "losses": 1, "ties": 0},
        "drop": None,
        "decklist": [
            {
                "id": "charizard",
                "name": "Charizard",
                "item": "Charizardite Y",
                "ability": "Blaze",
                "nature": "Modest",
                "attacks": ["Heat Wave", "Protect"],
            },
            {
                "id": "incineroar",
                "name": "Incineroar",
                "item": "Sitrus Berry",
                "ability": "Intimidate",
                "nature": "Careful",
                "attacks": ["Fake Out"],
            },
        ],
    },
    # The organiser didn't publish this list: no rows, but the pairing stays.
    {
        "player": "no_list",
        "name": "No List",
        "placing": 2,
        "record": {"wins": 5, "losses": 2},
        "drop": 4,
    },
]

_PAIRINGS = [
    {
        "round": 1,
        "phase": 1,
        "table": 1,
        "player1": "ash_k",
        "player2": "no_list",
        "winner": "ash_k",
    },
    {"round": 1, "phase": 1, "table": 2, "player1": "bye_guy", "winner": "bye_guy"},
    {"round": 2, "phase": 1, "table": 1, "player1": "ash_k", "player2": "x", "winner": 0},
]


class _FakeResponse:
    def __init__(
        self, payload=None, status_code: int = 200, headers: dict | None = None, text: str = ""
    ):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            error = requests.exceptions.HTTPError(f"{self.status_code} error")
            error.response = self
            raise error


class _FakeSession:
    def __init__(self, *, rate_limited: int = 0):
        self.requested: list[str] = []
        self._rate_limited = rate_limited

    def get(self, url, params=None, headers=None, timeout=None):
        self.requested.append(url)
        if self._rate_limited:
            self._rate_limited -= 1
            return _FakeResponse(status_code=429, headers={"Retry-After": "7"})
        if url.endswith("/tournaments"):
            return _FakeResponse(_LISTING if (params or {}).get("page") == 1 else [])
        if url.endswith("/standings"):
            return _FakeResponse(_STANDINGS)
        if url.endswith("/pairings"):
            return _FakeResponse(_PAIRINGS)
        return _FakeResponse(status_code=404)


class _FakeClock:
    def __init__(self):
        self.now = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _limiter(limit: int = 50):
    fake = _FakeClock()
    return limitless_play.RateLimiter(limit, 300.0, clock=fake.clock, sleep=fake.sleep), fake


def _read(path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_rate_limiter_waits_out_the_window_once_full():
    limiter, fake = _limiter(limit=2)
    limiter.wait()
    fake.now = 10.0
    limiter.wait()
    assert fake.slept == []
    fake.now = 20.0
    limiter.wait()
    # The third call waits until the first leaves the 300s window.
    assert fake.slept == [300.0 - 20.0 + 0.05]
    assert len(limiter.calls) == 2


def test_qualifies_needs_a_registered_format_enough_players_and_no_monotype():
    formats = limitless_play.format_regulations(_REGULATIONS)
    verdicts = {t["id"]: limitless_play.qualifies(t, formats, min_players=16) for t in _LISTING}
    assert verdicts == {
        "t-new": True,
        "t-small": False,
        "t-mono": False,
        "t-other": False,
        "t-old": True,
    }


def test_format_match_is_case_insensitive():
    formats = limitless_play.format_regulations(_REGULATIONS)
    assert limitless_play.qualifies({**_LISTING[0], "format": "m-c"}, formats, min_players=16)


def test_extract_keeps_the_regulation_in_force_and_writes_provenance(tmp_path):
    output = tmp_path / "limitless_play.csv"
    limiter, _ = _limiter()
    covered = limitless_play.extract(
        output,
        dataset_version="9.9.9",
        session=_FakeSession(),
        regulations=_REGULATIONS,
        today=date(2026, 10, 21),
        limiter=limiter,
    )
    rows = _read(output)
    # The lookback is M-C's start, so the M-B cup is out; the unpublished
    # list contributes no rows.
    assert [t["id"] for t in covered] == ["t-new"]
    assert [r["pokemon_slug"] for r in rows] == ["charizard", "incineroar"]
    first = rows[0]
    assert first["player_handle"] == "ash_k"
    assert first["tournament_date"] == "2026-10-18"
    assert first["moves"] == "Heat Wave|Protect"
    assert first["dropped"] == "false"
    assert first["source_name"] == "Limitless Online"
    assert first["source_url"] == "https://play.limitlesstcg.com/tournament/t-new/standings"
    assert first["source_record_id"] == "t-new:ash_k:1"
    assert first["dataset_version"] == "9.9.9"
    assert first["extracted_at_utc"]


def _run(path, session, today, fetched, previous=None, regulations=_REGULATIONS):
    limiter, _ = _limiter()
    return limitless_play.extract(
        path,
        session=session,
        previous_snapshot_path=previous,
        regulations=regulations,
        today=today,
        limiter=limiter,
        extracted_at_utc=fetched,
    )


def test_extract_reuses_a_copy_fetched_once_the_tournament_settled(tmp_path):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    _run(first, _FakeSession(), date(2026, 10, 21), "2026-10-21T06:00:00+00:00")
    session = _FakeSession()
    _run(second, session, date(2026, 10, 25), "2026-10-25T06:00:00+00:00", previous=first)
    # Fetched three days after the cup: final, so reused, not re-fetched.
    assert not any(url.endswith("/standings") for url in session.requested)
    rows = _read(second)
    assert len(rows) == 2
    # Reuse restamps extracted_at_utc but keeps when the rows were fetched.
    assert rows[0]["extracted_at_utc"] == "2026-10-25T06:00:00+00:00"
    assert rows[0]["fetched_at_utc"] == "2026-10-21T06:00:00+00:00"


def test_a_copy_fetched_mid_event_is_fetched_again_however_old(tmp_path):
    first = tmp_path / "first.csv"
    _run(first, _FakeSession(), date(2026, 10, 18), "2026-10-18T20:00:00+00:00")
    session = _FakeSession()
    _run(
        tmp_path / "second.csv",
        session,
        date(2026, 11, 30),
        "2026-11-30T06:00:00+00:00",
        previous=first,
    )
    # The cup ran on the 18th and was fetched that evening: that copy may
    # be partial, so it is fetched again even six weeks later, by id.
    assert any(url.endswith("/t-new/standings") for url in session.requested)


def test_extract_refetches_a_tournament_still_settling(tmp_path):
    first = tmp_path / "first.csv"
    _run(first, _FakeSession(), date(2026, 10, 19), "2026-10-19T06:00:00+00:00")
    session = _FakeSession()
    _run(
        tmp_path / "second.csv",
        session,
        date(2026, 10, 19),
        "2026-10-19T18:00:00+00:00",
        previous=first,
    )
    assert any(url.endswith("/t-new/standings") for url in session.requested)


def test_the_lookback_keeps_the_outgoing_regulations_last_days(tmp_path):
    # A rollover the day after the cup: M-C is in force, but the cup (the
    # outgoing set's last weekend) is still inside the lookback.
    regulations = [
        Regulation("m-b", "B", "fb", "m-b", date(2026, 6, 17), date(2026, 10, 19), "M-B"),
        Regulation("m-c", "C", "fc", "m-c", date(2026, 10, 19), date(2026, 12, 2), "M-C"),
    ]
    covered = _run(
        tmp_path / "out.csv",
        _FakeSession(),
        date(2026, 10, 20),
        "2026-10-20T06:00:00+00:00",
        regulations=regulations,
    )
    assert "t-new" in [t["id"] for t in covered]


def test_pairings_record_winners_ties_and_byes(tmp_path):
    output = tmp_path / "pairings.csv"
    limiter, _ = _limiter()
    limitless_play.extract_pairings(
        output,
        [{"id": "t-new", "date": "2026-10-18"}],
        session=_FakeSession(),
        limiter=limiter,
        extracted_at_utc="2026-10-21T06:00:00+00:00",
    )
    rows = _read(output)
    assert [(r["player1_handle"], r["player2_handle"], r["winner_handle"]) for r in rows] == [
        ("ash_k", "no_list", "ash_k"),
        ("bye_guy", "", "bye_guy"),
        ("ash_k", "x", "0"),
    ]
    assert rows[0]["source_url"] == "https://play.limitlesstcg.com/tournament/t-new/pairings"
    assert rows[0]["fetched_at_utc"] == rows[0]["extracted_at_utc"] == "2026-10-21T06:00:00+00:00"


def test_a_rate_limited_call_waits_and_retries_as_one_request():
    limiter, fake = _limiter()
    session = _FakeSession(rate_limited=1)
    with extract_http.track_requests() as stats:
        payload = limitless_play._get_json(session, "/tournaments/t-new/pairings", limiter=limiter)
    assert payload == _PAIRINGS
    assert 7.0 in fake.slept
    assert len(session.requested) == 2
    # Waited out, then answered: one logical request, not a failure.
    assert (stats.attempted, stats.succeeded, stats.failed_urls) == (1, 1, [])


# Two rows trimmed from the real upcoming page (2026-10-23, format M-C).
_UPCOMING_PAGE = """<table class="striped upcoming-tournaments"><tr><th>Date</th></tr>
<tr data-platform="SWITCH" data-date="2026-10-23T12:00:00.000Z" data-name="Malaysia Poke Ball League #12" data-organizer="Malaysia Poke Ball League" data-format="1" data-players="22" data-registration="2"><td class="date"><a class="time" href="/tournament/6ac9a5df8a8383117e3e85d6/details" data-time="1792756800000"></a></td><td class="organizer"><a href="/organizer/2849">Malaysia Poke Ball League</a></td><td class="registrations"><a href="/tournament/6ac9a5df8a8383117e3e85d6/registrations">22 / 32<span class="hide-md"> Registrations</span></a></td><td class="registration-link"><a class="register open" href="/tournament/6ac9a5df8a8383117e3e85d6/register">register</a></td></tr>
<tr data-platform="SIM" data-date="2026-10-28T18:00:00.000Z" data-name="Alpensee Tour (Reg M-C) #81 &amp; Friends" data-organizer="Alpensee eSports e.V." data-format="1" data-players="0" data-registration="1"><td class="date"><a class="time" href="/tournament/6abaa2a5880ed327106dea23/details"></a></td><td class="organizer"><a href="/organizer/2812">Alpensee eSports e.V.</a></td><td class="registrations"><a href="/tournament/6abaa2a5880ed327106dea23/registrations">0<span class="hide-md"> Registrations</span></a></td><td class="registration-link"><span class="register closed" title="Registration not open">not open</span></td></tr>
</table>"""


class _UpcomingSession:
    def __init__(self, page=_UPCOMING_PAGE):
        self.requested: list[str] = []
        self.page = page

    def get(self, url, params=None, headers=None, timeout=None):
        self.requested.append(url)
        return (
            _FakeResponse(text=self.page)
            if "/tournaments/upcoming" in url
            else _FakeResponse(status_code=404)
        )


def test_parse_upcoming_reads_the_rows_data_attributes_and_links():
    rows = limitless_play.parse_upcoming(
        _UPCOMING_PAGE,
        _REGULATIONS[1],
        extracted_at_utc="2026-10-23T06:00:00+00:00",
        dataset_version="0.0.0-dev",
    )

    first, second = rows
    assert first["tournament_id"] == "6ac9a5df8a8383117e3e85d6"
    assert first["starts_at_utc"] == "2026-10-23T12:00:00.000Z"
    assert (first["platform"], first["organizer_id"]) == ("SWITCH", "2849")
    assert (first["registrations"], first["player_cap"], first["registration_open"]) == (
        22,
        32,
        True,
    )
    assert first["regulation_code"] == "m-c" and first["tournament_format"] == "M-C"
    assert (
        first["source_url"]
        == f"{limitless_play.BASE_URL}/tournament/{first['tournament_id']}/details"
    )
    # Entities unescaped; no cap; registration not open yet.
    assert second["tournament_name"] == "Alpensee Tour (Reg M-C) #81 & Friends"
    assert (second["platform"], second["player_cap"], second["registration_open"]) == (
        "SIM",
        "",
        False,
    )


def test_a_page_without_the_table_fails_rather_than_listing_nothing():
    with pytest.raises(ValueError, match="upcoming-tournaments"):
        limitless_play.parse_upcoming(
            "<html>maintenance</html>",
            _REGULATIONS[1],
            extracted_at_utc="2026-10-23T06:00:00+00:00",
            dataset_version="0.0.0-dev",
        )


def test_upcoming_lists_the_regulation_in_force_and_one_starting_soon():
    m_d = Regulation("m-d", "D", "fd", "m-d", date(2026, 12, 2), date(2027, 3, 1), "M-D")
    regulations = [*_REGULATIONS, m_d]

    assert limitless_play.upcoming_regulations(regulations, date(2026, 10, 23)) == [_REGULATIONS[1]]
    assert limitless_play.upcoming_regulations(regulations, date(2026, 11, 15)) == [
        _REGULATIONS[1],
        m_d,
    ]


def test_extract_upcoming_writes_one_request_per_regulation(tmp_path):
    session = _UpcomingSession()
    limiter, _ = _limiter()
    path = tmp_path / "upcoming.csv"

    count = limitless_play.extract_upcoming(
        path,
        session=session,
        regulations=_REGULATIONS,
        today=date(2026, 10, 23),
        limiter=limiter,
        extracted_at_utc="2026-10-23T06:00:00+00:00",
    )

    assert count == 2
    assert session.requested == [
        f"{limitless_play.BASE_URL}/tournaments/upcoming?game=VGC&format=M-C"
    ]
    rows = _read(path)
    assert [r["tournament_id"] for r in rows] == [
        "6ac9a5df8a8383117e3e85d6",
        "6abaa2a5880ed327106dea23",
    ]
    assert list(rows[0]) == limitless_play.UPCOMING_FIELDNAMES
