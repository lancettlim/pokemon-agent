import csv

import requests

from pipelines.extract import http as extract_http
from pipelines.extract import rk9

# Markup shapes below are trimmed from real rk9.gg responses (NAIC 2026,
# event NA02wgUPFDXKmQmqILwS), keeping the class lists and cell-id scheme
# byte-for-byte so the parser is exercised against what the site emits --
# including the irregular internal whitespace in the class attributes.
_SHELL = """
<ul class="nav nav-pills" role="tablist">
<li class="nav-item"><a class="nav-link active" id="P2-tab" data-toggle="tab" href="#P2"
 role="tab" aria-controls="P2" aria-selected="false">Masters in Round 3</a></li>
<li class="nav-item"><a class="nav-link " id="P9-tab" data-toggle="tab" href="#P9"
 role="tab" aria-controls="P9" aria-selected="true">Senior in Round 1</a></li>
</ul>
"""


def _match(index: int, *, p1: str, p2: str | None, winner: int | None, table: int | None) -> str:
    def player_cell(slot: int, text: str, is_winner: bool) -> str:
        result = "winner" if is_winner else ("loser" if winner is not None else "")
        return (
            f'<div id="cell-2-3-{index}-{slot}" class="col-5 text-center player player{slot}'
            f' {result}   "><span class="name">{text}<br></span> (1-1-0) 3 pts <br></div>'
        )

    cells = player_cell(1, p1, winner == 1)
    table_cell = (
        f'<div id="cell-2-3-{index}-3" class="col-2 text-center  "> Table<br>'
        f'<span class="tablenumber "> {table} </span><br></div>'
        if table is not None
        else f'<div id="cell-2-3-{index}-3" class="col-2 text-center  "></div>'
    )
    cells += table_cell
    if p2 is None:
        cells += (
            f'<div id="cell-2-3-{index}-2" class="col-5 text-center player player2     "></div>'
        )
    else:
        cells += player_cell(2, p2, winner == 2)
    return f'<div class="row row-cols-3 match no-gutter complete">{cells}</div>'


_ROUND = "".join(
    [
        _match(0, p1="Zie<br> Hebert [US]", p2="Jérémy<br> Côté [CA]", winner=1, table=1),
        _match(1, p1="Colleen<br> Viets [US]", p2=None, winner=1, table=None),
        _match(2, p1="Ada<br> Lovelace [GB]", p2="Alan<br> Turing [GB]", winner=None, table=2),
        _match(3, p1="Solo<br> Player", p2="Other<br> Player [JP]", winner=2, table=3),
    ]
)


class _FakeResponse:
    def __init__(self, *, text: str = "", json_data=None, status_code: int = 200):
        self.text = text
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            error = requests.exceptions.HTTPError(f"{self.status_code} error")
            error.response = self
            raise error

    def json(self):
        return self._json_data


class _FakeSession:
    """Serves the MunchStats index as JSON and every rk9.gg URL as markup:
    the bare /pairings/<id> shell, or a per-round fragment when the request
    carries ?pod=&rnd=."""

    def __init__(self, *, index=None, fail_count: int = 0, fail_status_code: int = 500):
        self._index = index if index is not None else _INDEX
        self._fail_count = fail_count
        self._fail_status_code = fail_status_code
        self.requested_urls: list[str] = []

    def get(self, url: str, params: dict | None = None, timeout: int = 30):
        self.requested_urls.append(url)
        if len(self.requested_urls) <= self._fail_count:
            return _FakeResponse(status_code=self._fail_status_code)
        if url == rk9.MUNCHSTATS_INDEX_URL:
            return _FakeResponse(json_data=self._index)
        if "?" in url:
            return _FakeResponse(text=_ROUND)
        return _FakeResponse(text=_SHELL)


_INDEX = [
    {"id": "CHAMPS1", "format": "gen9championsvgc2026regma"},
    {"id": "STANDARD1", "format": "gen9vgc2026regi"},
    {"id": "NOFORMAT", "format": None},
]


def _read(path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_parse_pods_reads_division_and_highest_round():
    assert rk9._parse_pods(_SHELL) == [("2", "Masters", 3), ("9", "Senior", 1)]


def test_parse_round_classifies_every_outcome_shape():
    matches = rk9._parse_round(_ROUND)
    assert [m["outcome"] for m in matches] == ["player1_win", "bye", "tie", "player2_win"]


def test_parse_round_splits_name_country_and_record():
    first = rk9._parse_round(_ROUND)[0]
    assert first["player1"]["name"] == "Zie Hebert"
    assert first["player1"]["country"] == "US"
    # Non-ASCII names must survive unescaping and the <br> inside the span.
    assert first["player2"]["name"] == "Jérémy Côté"
    assert first["player2"]["country"] == "CA"
    assert (first["player1"]["wins"], first["player1"]["losses"], first["player1"]["ties"]) == (
        "1",
        "1",
        "0",
    )
    assert first["table_number"] == "1"


def test_parse_round_keeps_a_player_with_no_reported_country():
    solo = rk9._parse_round(_ROUND)[3]
    assert solo["player1"]["name"] == "Solo Player"
    assert solo["player1"]["country"] == ""


def test_bye_keeps_the_player_and_blanks_the_opponent(tmp_path):
    output_path = tmp_path / "rk9.csv"
    rk9.extract(output_path, session=_FakeSession(), dataset_version="9.9.9")
    bye = next(row for row in _read(output_path) if row["outcome"] == "bye")
    assert bye["player1_name"] == "Colleen Viets"
    assert bye["player2_name"] == ""
    assert bye["table_number"] == ""
    # A bye has no table, so the record id falls back to the player instead
    # of colliding with every other bye in the same round.
    assert bye["source_record_id"].endswith(":bye:Colleen Viets")


def test_extract_defaults_to_champions_format_events_only(tmp_path):
    output_path = tmp_path / "rk9.csv"
    session = _FakeSession()
    rk9.extract(output_path, session=session, dataset_version="9.9.9")
    assert {row["event_id"] for row in _read(output_path)} == {"CHAMPS1"}
    assert not any("STANDARD1" in url for url in session.requested_urls)


def test_extract_default_covers_every_registered_regulation(tmp_path):
    # Regression: the filter used to be the single Reg M-A format, which
    # silently dropped Worlds (M-B) and every M-C event.
    index = [
        {"id": "REGMA", "format": "gen9championsvgc2026regma"},
        {"id": "REGMB", "format": "gen9championsvgc2026regmb"},
        {"id": "REGMC", "format": "gen9championsvgc2026regmc"},
        {"id": "STANDARD1", "format": "gen9vgc2026regi"},
    ]
    output_path = tmp_path / "rk9.csv"
    rk9.extract(output_path, session=_FakeSession(index=index), dataset_version="9.9.9")
    assert {row["event_id"] for row in _read(output_path)} == {"REGMA", "REGMB", "REGMC"}


def test_extract_format_filter_none_takes_every_indexed_event(tmp_path):
    output_path = tmp_path / "rk9.csv"
    rk9.extract(output_path, session=_FakeSession(), dataset_version="9.9.9", format_filter=None)
    assert {row["event_id"] for row in _read(output_path)} == {
        "CHAMPS1",
        "STANDARD1",
        "NOFORMAT",
    }


def test_extract_covers_every_round_of_every_pod(tmp_path):
    output_path = tmp_path / "rk9.csv"
    rk9.extract(output_path, session=_FakeSession(), dataset_version="9.9.9")
    rows = _read(output_path)
    # Masters reached round 3 and Senior round 1, so rounds are enumerated
    # from the tab strip (1..N) rather than from lazy-load attributes --
    # the active round has no hx-get of its own.
    assert {(row["division"], row["round_number"]) for row in rows} == {
        ("Masters", "1"),
        ("Masters", "2"),
        ("Masters", "3"),
        ("Senior", "1"),
    }


def test_extract_writes_full_provenance(tmp_path):
    output_path = tmp_path / "rk9.csv"
    rk9.extract(output_path, session=_FakeSession(), dataset_version="9.9.9")
    row = _read(output_path)[0]
    assert row["source_name"] == rk9.SOURCE_NAME
    assert row["source_url"] == "https://rk9.gg/pairings/CHAMPS1?pod=2&rnd=1"
    assert row["dataset_version"] == "9.9.9"
    assert row["extracted_at_utc"]


def test_extract_reuses_cached_event_instead_of_refetching(tmp_path):
    previous = tmp_path / "previous.csv"
    rk9.extract(previous, session=_FakeSession(), dataset_version="0.0.1")

    session = _FakeSession()
    output_path = tmp_path / "rk9.csv"
    rk9.extract(
        output_path,
        session=session,
        dataset_version="9.9.9",
        previous_snapshot_path=previous,
    )

    # Every field except the two re-stamped provenance columns is preserved
    # exactly, so caching reuses rows rather than silently dropping them.
    stable = [k for k in rk9.FIELDNAMES if k not in ("extracted_at_utc", "dataset_version")]
    assert [{k: row[k] for k in stable} for row in _read(output_path)] == [
        {k: row[k] for k in stable} for row in _read(previous)
    ]
    # Only the index was fetched; no pairings request was made at all.
    assert session.requested_urls == [rk9.MUNCHSTATS_INDEX_URL]


def test_extract_restamps_reused_rows_with_the_current_run(tmp_path):
    previous = tmp_path / "previous.csv"
    rk9.extract(previous, session=_FakeSession(), dataset_version="0.0.1")
    output_path = tmp_path / "rk9.csv"
    rk9.extract(
        output_path,
        session=_FakeSession(),
        dataset_version="9.9.9",
        previous_snapshot_path=previous,
    )
    assert {row["dataset_version"] for row in _read(output_path)} == {"9.9.9"}


def test_extract_retries_transient_failure_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_http.time, "sleep", lambda _seconds: None)
    output_path = tmp_path / "rk9.csv"
    rk9.extract(output_path, session=_FakeSession(fail_count=1), dataset_version="9.9.9")
    assert _read(output_path)


def test_a_live_event_is_fetched_again_despite_the_cache(tmp_path):
    # docs/upgrade-plan-2027q2.md, E4: an event still running has cached
    # pairings that stop at whatever round was live, so it is re-fetched.
    previous = tmp_path / "previous.csv"
    rk9.extract(previous, session=_FakeSession(), dataset_version="0.0.1")
    cached_events = {row["event_id"] for row in _read(previous)}
    session = _FakeSession()
    rk9.extract(
        tmp_path / "rk9.csv",
        session=session,
        dataset_version="9.9.9",
        previous_snapshot_path=previous,
        refresh_event_ids=cached_events,
    )
    assert len(session.requested_urls) > 1
