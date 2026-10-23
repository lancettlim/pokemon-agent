import csv

import requests

from pipelines.extract import http as extract_http
from pipelines.extract import munchstats


class _FakeResponse:
    def __init__(self, payload, *, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            error = requests.exceptions.HTTPError(f"{self.status_code} error")
            error.response = self
            raise error

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(
        self,
        payloads_by_url: dict[str, object],
        *,
        fail_urls: dict[str, int] | None = None,
        fail_status_code: int = 500,
    ) -> None:
        self._payloads_by_url = payloads_by_url
        self._fail_urls = dict(fail_urls or {})
        self._fail_status_code = fail_status_code
        self.requested_urls: list[str] = []

    def get(self, url: str, timeout: int):
        self.requested_urls.append(url)
        remaining_failures = self._fail_urls.get(url, 0)
        if remaining_failures > 0:
            self._fail_urls[url] = remaining_failures - 1
            return _FakeResponse(None, status_code=self._fail_status_code)
        return _FakeResponse(self._payloads_by_url[url])


TOURNAMENT_ID = "MB02w71HQZzTvTOYLtXb"
DIR_URL = munchstats._tournament_dir_url(TOURNAMENT_ID)

METADATA = {
    "id": TOURNAMENT_ID,
    "name": "2026 Melbourne Pokémon VGC Regional Championships",
    "date": "2026-05-23",
    "type": "Regional",
    "format": "gen9vgc2026regi",
    "teams_scraped": 2,
}

PLAYERS = [
    {
        "name": "Nicholas Kan",
        "country": "AU",
        "placement": 1,
        "team": [
            {
                "pokemon": "Miraidon",
                "item": "Choice Specs",
                "ability": "Hadron Engine",
                "tera_type": "Fairy",
                "nature": "Modest",
                "moves": ["Electro Drift", "Draco Meteor", "Protect", "Dazzling Gleam"],
            },
            {"pokemon": "Ursaluna", "item": "Flame Orb"},
        ],
        "day_reached": "top8",
        "team_link": f"/teamlist/public/{TOURNAMENT_ID}/YV8VbSG82iS8rMz0hhwb",
        "record": {"wins": 14, "losses": 2},
    },
    {
        "name": "No Link Player",
        "country": "US",
        "placement": 2,
        "team": [{"pokemon": "Incineroar", "item": "Assault Vest"}],
        "team_link": "",
    },
]


def _session_for_one_tournament():
    return _FakeSession(
        {
            munchstats.TOURNAMENTS_INDEX_URL: [{"id": TOURNAMENT_ID}],
            f"{DIR_URL}/metadata.json": METADATA,
            f"{DIR_URL}/players.json": PLAYERS,
        }
    )


def test_extract_flattens_team_into_one_row_per_slot(tmp_path):
    session = _session_for_one_tournament()
    output_path = tmp_path / "munchstats.csv"

    munchstats.extract(output_path, [TOURNAMENT_ID], dataset_version="0.1.0", session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 3  # 2 slots for player 1, 1 slot for player 2

    row = rows[0]
    assert row["event_id"] == TOURNAMENT_ID
    assert row["event_name"] == METADATA["name"]
    assert row["event_date"] == METADATA["date"]
    assert row["event_tier"] == "Regional"
    assert row["team_id"] == "YV8VbSG82iS8rMz0hhwb"
    assert row["player_name"] == "Nicholas Kan"
    assert row["player_country"] == "AU"
    assert row["placement"] == "1"
    assert row["record_wins"] == "14"
    assert row["record_losses"] == "2"
    assert row["slot_number"] == "1"
    assert row["pokemon_name"] == "Miraidon"
    assert row["form_name"] == ""
    assert row["item_name"] == "Choice Specs"
    assert row["ability"] == "Hadron Engine"
    assert row["tera_type"] == "Fairy"
    assert row["nature"] == "Modest"
    assert row["moves"] == "Electro Drift|Draco Meteor|Protect|Dazzling Gleam"
    assert row["source_name"] == "MunchStats"
    assert row["source_url"] == f"{DIR_URL}/players.json"
    assert row["source_record_id"] == f"{TOURNAMENT_ID}:YV8VbSG82iS8rMz0hhwb:1"
    assert row["dataset_version"] == "0.1.0"
    assert row["extracted_at_utc"]

    assert rows[1]["slot_number"] == "2"
    assert rows[1]["pokemon_name"] == "Ursaluna"
    assert rows[1]["team_id"] == "YV8VbSG82iS8rMz0hhwb"
    assert rows[1]["ability"] == ""
    assert rows[1]["nature"] == ""
    assert rows[1]["moves"] == ""

    fallback_player_row = rows[2]
    assert fallback_player_row["pokemon_name"] == "Incineroar"
    assert fallback_player_row["record_wins"] == ""
    assert fallback_player_row["record_losses"] == ""


def test_extract_falls_back_to_synthetic_team_id_without_team_link(tmp_path):
    session = _session_for_one_tournament()
    output_path = tmp_path / "munchstats.csv"

    munchstats.extract(output_path, [TOURNAMENT_ID], session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    fallback_row = next(row for row in rows if row["pokemon_name"] == "Incineroar")
    assert fallback_row["team_id"] == f"{TOURNAMENT_ID}:No Link Player"


def test_extract_derives_stable_player_id_from_name_and_country(tmp_path):
    session = _session_for_one_tournament()
    output_path = tmp_path / "munchstats.csv"

    munchstats.extract(output_path, [TOURNAMENT_ID], session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    player_ids = {row["pokemon_name"]: row["player_id"] for row in rows}
    assert player_ids["Miraidon"] == player_ids["Ursaluna"]
    assert player_ids["Miraidon"] != player_ids["Incineroar"]


def test_extract_defaults_to_full_tournaments_index(tmp_path):
    session = _session_for_one_tournament()
    output_path = tmp_path / "munchstats.csv"

    munchstats.extract(output_path, session=session)

    assert munchstats.TOURNAMENTS_INDEX_URL in session.requested_urls
    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 3


def test_extract_skips_players_fetch_for_zero_teams_scraped_tournament(tmp_path):
    # A same-venue TCG tournament: metadata.json reports teams_scraped: 0,
    # so players.json is never fetched (its absence from the payload map
    # would otherwise raise KeyError) and it contributes zero rows.
    tcg_metadata = {**METADATA, "name": "2026 Melbourne Pokémon TCG Regional Championships"}
    del tcg_metadata["teams_scraped"]
    tcg_metadata["teams_scraped"] = 0
    session = _FakeSession(
        {
            munchstats.TOURNAMENTS_INDEX_URL: [{"id": TOURNAMENT_ID}],
            f"{DIR_URL}/metadata.json": tcg_metadata,
        }
    )
    output_path = tmp_path / "munchstats.csv"

    munchstats.extract(output_path, [TOURNAMENT_ID], session=session)

    assert f"{DIR_URL}/players.json" not in session.requested_urls
    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows == []


def test_extract_skips_players_fetch_even_with_no_previous_snapshot(tmp_path):
    """The teams_scraped: 0 short-circuit isn't cache-dependent -- it must
    also fire on a completely fresh extraction with nothing cached yet."""
    tcg_metadata = {**METADATA, "teams_scraped": 0}
    session = _FakeSession(
        {
            munchstats.TOURNAMENTS_INDEX_URL: [{"id": TOURNAMENT_ID}],
            f"{DIR_URL}/metadata.json": tcg_metadata,
        }
    )
    output_path = tmp_path / "munchstats.csv"

    munchstats.extract(
        output_path,
        [TOURNAMENT_ID],
        session=session,
        previous_snapshot_path=tmp_path / "does-not-exist.csv",
    )

    assert f"{DIR_URL}/players.json" not in session.requested_urls


def _write_previous_snapshot(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=munchstats.FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _cached_row(**overrides):
    row = {name: "" for name in munchstats.FIELDNAMES}
    row.update(
        {
            "event_id": TOURNAMENT_ID,
            "event_name": METADATA["name"],
            "event_date": METADATA["date"],
            "event_tier": METADATA["type"],
            "event_format": METADATA["format"],
            "team_id": "cached-team",
            "player_id": "cached-player",
            "player_name": "Cached Player",
            "slot_number": "1",
            "pokemon_name": "Cached Mon",
            "source_name": munchstats.SOURCE_NAME,
            "source_url": f"{DIR_URL}/players.json",
            "source_record_id": f"{TOURNAMENT_ID}:cached-team:1",
            "extracted_at_utc": "2026-01-01T00:00:00+00:00",
            "dataset_version": "0.0.1",
        }
    )
    row.update(overrides)
    return row


def test_extract_reuses_cached_rows_when_metadata_signature_unchanged(tmp_path):
    # players.json is deliberately absent from the payload map: if the
    # extractor tries to fetch it despite the metadata signature matching,
    # the fake session raises KeyError and fails the test.
    session = _FakeSession(
        {
            munchstats.TOURNAMENTS_INDEX_URL: [{"id": TOURNAMENT_ID}],
            f"{DIR_URL}/metadata.json": METADATA,
        }
    )
    previous_path = tmp_path / "previous.csv"
    _write_previous_snapshot(previous_path, [_cached_row()])
    output_path = tmp_path / "munchstats.csv"

    munchstats.extract(
        output_path,
        [TOURNAMENT_ID],
        dataset_version="0.2.0",
        session=session,
        previous_snapshot_path=previous_path,
    )

    assert f"{DIR_URL}/players.json" not in session.requested_urls
    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["pokemon_name"] == "Cached Mon"
    assert rows[0]["team_id"] == "cached-team"
    # Reused rows are still re-stamped with this run's provenance fields.
    assert rows[0]["dataset_version"] == "0.2.0"
    assert rows[0]["extracted_at_utc"] != "2026-01-01T00:00:00+00:00"


def test_extract_refetches_a_snapshot_cached_before_event_format_existed(tmp_path):
    """A snapshot written before event_format was captured has no such
    column. Those rows must NOT be reused as-is -- that would silently
    carry a blank format forward, and every Champions-scoped mart keys off
    it. The signature comparison treats the missing column as "" so it
    can't match the real format, forcing a re-fetch that backfills it."""
    session = _FakeSession(
        {
            munchstats.TOURNAMENTS_INDEX_URL: [{"id": TOURNAMENT_ID}],
            f"{DIR_URL}/metadata.json": METADATA,
            f"{DIR_URL}/players.json": PLAYERS,
        }
    )
    previous_path = tmp_path / "previous.csv"
    stale_row = _cached_row()
    stale_row.pop("event_format")
    with previous_path.open("w", newline="", encoding="utf-8") as fh:
        fieldnames = [n for n in munchstats.FIELDNAMES if n != "event_format"]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(stale_row)
    output_path = tmp_path / "munchstats.csv"

    munchstats.extract(
        output_path,
        [TOURNAMENT_ID],
        dataset_version="0.3.0",
        session=session,
        previous_snapshot_path=previous_path,
    )

    assert f"{DIR_URL}/players.json" in session.requested_urls
    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows, "re-fetch must produce real rows, not an empty file"
    assert {row["event_format"] for row in rows} == {METADATA["format"]}
    assert "Cached Mon" not in {row["pokemon_name"] for row in rows}


def test_extract_refetches_when_metadata_signature_changed(tmp_path):
    session = _session_for_one_tournament()
    previous_path = tmp_path / "previous.csv"
    _write_previous_snapshot(previous_path, [_cached_row(event_date="2020-01-01")])
    output_path = tmp_path / "munchstats.csv"

    munchstats.extract(
        output_path,
        [TOURNAMENT_ID],
        session=session,
        previous_snapshot_path=previous_path,
    )

    assert f"{DIR_URL}/players.json" in session.requested_urls
    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 3
    assert rows[0]["pokemon_name"] == "Miraidon"


def test_extract_ignores_missing_previous_snapshot_path(tmp_path):
    session = _session_for_one_tournament()
    output_path = tmp_path / "munchstats.csv"
    missing_path = tmp_path / "does-not-exist.csv"

    munchstats.extract(
        output_path,
        [TOURNAMENT_ID],
        session=session,
        previous_snapshot_path=missing_path,
    )

    assert f"{DIR_URL}/players.json" in session.requested_urls
    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 3


def test_extract_retries_transient_error_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_http.time, "sleep", lambda seconds: None)
    session = _FakeSession(
        {
            munchstats.TOURNAMENTS_INDEX_URL: [{"id": TOURNAMENT_ID}],
            f"{DIR_URL}/metadata.json": METADATA,
            f"{DIR_URL}/players.json": PLAYERS,
        },
        fail_urls={f"{DIR_URL}/metadata.json": 2},
    )
    output_path = tmp_path / "munchstats.csv"

    munchstats.extract(output_path, [TOURNAMENT_ID], session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 3


def test_an_event_counts_as_live_from_the_day_before_to_three_days_after():
    # docs/upgrade-plan-2027q2.md, E4.
    from datetime import date

    event = "2026-12-05"
    assert not munchstats.is_live(event, date(2026, 12, 3))
    assert munchstats.is_live(event, date(2026, 12, 4))
    assert munchstats.is_live(event, date(2026, 12, 8))
    assert not munchstats.is_live(event, date(2026, 12, 9))
    assert not munchstats.is_live("", date(2026, 12, 5))
    assert not munchstats.is_live("not a date", date(2026, 12, 5))
