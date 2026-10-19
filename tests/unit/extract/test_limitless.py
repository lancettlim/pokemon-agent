import csv

import requests

from pipelines.extract import http as extract_http
from pipelines.extract import limitless

# Markup below is trimmed from real limitlessvgc.com responses, keeping the
# data- attributes and class names byte-for-byte.
_TOURNAMENTS = """
<table class="data-table striped">
<tr><th>Date</th></tr>
<tr data-date="2026-06-11" data-country="US"
    data-name="NAIC 2026, New Orleans" data-format="m-a"
    data-players="1096" data-winner="IT-Francesco Pio Pero">
    <td><a href="/tournaments/436">NAIC 2026, New Orleans</a></td>
</tr>
<tr data-date="2026-05-02" data-country="JP"
    data-name="Standard VGC Event" data-format="reg-i"
    data-players="200" data-winner="JP-Someone Else">
    <td><a href="/tournaments/400">Standard VGC Event</a></td>
</tr>
</table>
"""

_STANDINGS = """
<div class="rk9gg">
  <a href="https://rk9.gg/pairings/NA02wgUPFDXKmQmqILwS" class="external">Pairings</a>
  <a href="https://rk9.gg/roster/NA02wgUPFDXKmQmqILwS" class="external">Roster</a>
</div>
<tr data-rank="1" data-name="Francesco Pio Pero" data-country="IT" >
  <td><a href="/players/1507">Francesco Pio Pero</a></td>
  <td><a href="/teams/6582"><i class="far fa-lg fa-list-alt"></i></a></td>
</tr>
<tr data-rank="2" data-name="Shared Team Player" data-country="ES" >
  <td><a href="/players/1508">Shared Team Player</a></td>
  <td><a href="/teams/6582"><i class="far fa-lg fa-list-alt"></i></a></td>
</tr>
<tr data-rank="3" data-name="No List Player" data-country="US" >
  <td><a href="/players/1509">No List Player</a></td>
  <td></td>
</tr>
"""


def _pkmn(slug: str, name: str, item_html: str, ability: str, nature_html: str, moves) -> str:
    move_items = "".join(f"<li>{move}</li>" for move in moves)
    return (
        f'<div class="pkmn" data-id="{slug}">'
        f'<div class="name"><a href="/pokemon/{slug}">{name}</a></div>'
        f'<div class="main"><div class="image"></div><div>'
        f'<div class="details">{item_html}'
        f'<div class="ability">Ability: {ability}</div>{nature_html}</div>'
        f'<ul class="moves">{move_items}</ul></div></div></div>'
    )


_TEAM = (
    '<div class="teamlist"><div class="teamlist-pokemon">'
    + _pkmn(
        "charizard",
        "Charizard",
        '<div class="item">Charizardite Y</div>',
        "Blaze",
        '<div class="nature">Modest Nature</div>',
        ["Heat Wave", "Solar Beam"],
    )
    # Limitless renders a bare "Held Item:" label for a Pokémon holding
    # nothing at all -- a real build choice (Acrobatics), not missing data.
    + _pkmn(
        "talonflame",
        "Talonflame",
        '<div class="item">Held Item:</div>',
        "Gale Wings",
        '<div class="nature">Adamant Nature</div>',
        ["Acrobatics"],
    )
    # A published list can omit the nature block entirely.
    + _pkmn(
        "kingambit",
        "Kingambit",
        '<div class="item">Chople Berry</div>',
        "Defiant",
        "",
        ["Sucker Punch"],
    )
    + "</div></div>"
)


class _FakeResponse:
    def __init__(self, *, text: str = "", status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            error = requests.exceptions.HTTPError(f"{self.status_code} error")
            error.response = self
            raise error


class _FakeSession:
    def __init__(self, *, fail_count: int = 0, fail_status_code: int = 500):
        self._fail_count = fail_count
        self._fail_status_code = fail_status_code
        self.requested_urls: list[str] = []

    def get(self, url: str, params: dict | None = None, timeout: int = 30):
        self.requested_urls.append(url)
        if len(self.requested_urls) <= self._fail_count:
            return _FakeResponse(status_code=self._fail_status_code)
        if url == limitless.TOURNAMENTS_URL:
            return _FakeResponse(text=_TOURNAMENTS)
        if "/teams/" in url:
            return _FakeResponse(text=_TEAM)
        return _FakeResponse(text=_STANDINGS)


def _read(path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_parse_tournaments_reads_data_attributes():
    tournaments = limitless._parse_tournaments(_TOURNAMENTS)
    assert [t["tournament_id"] for t in tournaments] == ["436", "400"]
    assert tournaments[0]["regulation_set"] == "m-a"
    assert tournaments[0]["tournament_date"] == "2026-06-11"
    assert tournaments[0]["tournament_name"] == "NAIC 2026, New Orleans"


def test_parse_standings_keeps_a_player_with_no_published_list():
    standings = limitless._parse_standings(_STANDINGS)
    assert [entry["limitless_team_id"] for entry in standings] == ["6582", "6582", ""]
    assert standings[0]["player_country"] == "IT"
    assert standings[0]["limitless_player_id"] == "1507"


def test_parse_team_list_reads_build_details():
    slots = limitless._parse_team_list(_TEAM)
    assert [slot["pokemon_slug"] for slot in slots] == ["charizard", "talonflame", "kingambit"]
    assert slots[0]["item_name"] == "Charizardite Y"
    assert slots[0]["ability"] == "Blaze"
    assert slots[0]["nature"] == "Modest"
    assert slots[0]["moves"] == "Heat Wave|Solar Beam"


def test_held_item_placeholder_becomes_empty_not_a_literal_label():
    slots = limitless._parse_team_list(_TEAM)
    talonflame = slots[1]
    assert talonflame["item_name"] == ""
    # The rest of the slot must still parse -- it's a real build, not a
    # broken row.
    assert talonflame["ability"] == "Gale Wings"
    assert talonflame["moves"] == "Acrobatics"


def test_missing_nature_block_is_blank_not_guessed():
    assert limitless._parse_team_list(_TEAM)[2]["nature"] == ""


def test_extract_defaults_to_champions_format_only(tmp_path):
    output_path = tmp_path / "limitless.csv"
    session = _FakeSession()
    limitless.extract(output_path, session=session, dataset_version="9.9.9")
    assert {row["tournament_id"] for row in _read(output_path)} == {"436"}
    assert not any(url.endswith("/tournaments/400") for url in session.requested_urls)


def test_extract_captures_the_rk9_event_id_join_key(tmp_path):
    output_path = tmp_path / "limitless.csv"
    limitless.extract(output_path, session=_FakeSession(), dataset_version="9.9.9")
    assert {row["rk9_event_id"] for row in _read(output_path)} == {"NA02wgUPFDXKmQmqILwS"}


def test_extract_fetches_each_shared_team_once(tmp_path):
    output_path = tmp_path / "limitless.csv"
    session = _FakeSession()
    limitless.extract(output_path, session=session, dataset_version="9.9.9")
    team_requests = [url for url in session.requested_urls if "/teams/" in url]
    # Two players share team 6582; it must be downloaded once, not twice.
    assert team_requests == ["https://limitlessvgc.com/teams/6582"]
    # ...but both players still get their own rows.
    assert {row["player_name"] for row in _read(output_path)} == {
        "Francesco Pio Pero",
        "Shared Team Player",
    }


def test_extract_skips_players_without_a_published_list(tmp_path):
    output_path = tmp_path / "limitless.csv"
    limitless.extract(output_path, session=_FakeSession(), dataset_version="9.9.9")
    assert "No List Player" not in {row["player_name"] for row in _read(output_path)}


def test_extract_writes_full_provenance(tmp_path):
    output_path = tmp_path / "limitless.csv"
    limitless.extract(output_path, session=_FakeSession(), dataset_version="9.9.9")
    row = _read(output_path)[0]
    assert row["source_name"] == limitless.SOURCE_NAME
    assert row["source_url"] == "https://limitlessvgc.com/teams/6582"
    assert row["source_record_id"] == "436:6582:1507:1"
    assert row["dataset_version"] == "9.9.9"
    assert row["extracted_at_utc"]


def test_extract_default_covers_every_registered_regulation(tmp_path, monkeypatch):
    # Regression: the filter used to be the single slug "m-a", which
    # silently dropped Worlds (m-b) and every m-c event.
    listing = _TOURNAMENTS.replace('data-format="reg-i"', 'data-format="m-c"')
    monkeypatch.setattr(
        limitless,
        "_fetch_text",
        lambda _http, url: (
            listing
            if url == limitless.TOURNAMENTS_URL
            else _TEAM
            if "/teams/" in url
            else _STANDINGS
        ),
    )
    output_path = tmp_path / "limitless.csv"
    limitless.extract(output_path, session=_FakeSession(), dataset_version="9.9.9")
    assert {row["regulation_set"] for row in _read(output_path)} == {"m-a", "m-c"}


def test_extract_format_filter_none_takes_every_tournament(tmp_path):
    output_path = tmp_path / "limitless.csv"
    limitless.extract(
        output_path, session=_FakeSession(), dataset_version="9.9.9", format_filter=None
    )
    assert {row["tournament_id"] for row in _read(output_path)} == {"436", "400"}


def test_extract_retries_transient_failure_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_http.time, "sleep", lambda _seconds: None)
    output_path = tmp_path / "limitless.csv"
    limitless.extract(output_path, session=_FakeSession(fail_count=1), dataset_version="9.9.9")
    assert _read(output_path)
