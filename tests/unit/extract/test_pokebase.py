import csv
import json

import requests

from pipelines.extract import http as extract_http
from pipelines.extract import pokebase


class _FakeResponse:
    def __init__(self, text: str, *, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            error = requests.exceptions.HTTPError(f"{self.status_code} error")
            error.response = self
            raise error


class _FakeSession:
    def __init__(self, html: str, *, fail_count: int = 0, fail_status_code: int = 500) -> None:
        self._html = html
        self._fail_count = fail_count
        self._fail_status_code = fail_status_code
        self.requested_urls: list[str] = []

    def get(self, url: str, timeout: int):
        self.requested_urls.append(url)
        if len(self.requested_urls) <= self._fail_count:
            return _FakeResponse("", status_code=self._fail_status_code)
        return _FakeResponse(self._html)


POKEMON_DOCS = [
    {
        "id": "abc123",
        "name": "Venusaur",
        "slug": "venusaur",
        "nationalNumber": 3,
        "isMega": False,
        "regulationSets": [
            {"name": "M-A", "slug": "m-a", "id": "reg-a"},
            {"name": "M-B", "slug": "m-b", "id": "reg-b"},
        ],
    },
    {
        "id": "def456",
        "name": "Mega Venusaur",
        "slug": "venusaur-mega",
        "nationalNumber": 3,
        "isMega": True,
        "regulationSets": [{"name": "M-A", "slug": "m-a", "id": "reg-a"}],
    },
    {
        "id": "ghi789",
        "name": "Charmander",
        "slug": "charmander",
        "nationalNumber": 4,
        "isMega": False,
    },
]


def _html_with_flight_payload(pokemon_docs: list[dict]) -> str:
    """Build a synthetic page matching PokéBase's real structure: the
    pokemon list embedded as a JSON-string-escaped payload inside a
    Next.js Flight `self.__next_f.push(...)` script chunk."""
    inner_json = json.dumps(
        {
            "data": {
                "docs": pokemon_docs,
                "hasNextPage": False,
                "totalDocs": len(pokemon_docs),
            },
            "regulationSetOptions": [{"value": "m-a", "label": "M-A"}],
        },
        separators=(",", ":"),
    )
    escaped_inner_json = json.dumps(inner_json)
    return (
        "<html><body>"
        f'<script>self.__next_f.push([1,"6:{escaped_inner_json[1:-1]}"])</script>'
        "</body></html>"
    )


def test_extract_writes_one_row_per_pokemon_regulation_pair(tmp_path):
    session = _FakeSession(_html_with_flight_payload(POKEMON_DOCS))
    output_path = tmp_path / "pokebase.csv"

    pokebase.extract(output_path, dataset_version="0.1.0", session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert session.requested_urls == [pokebase.PAGE_URL]
    # Venusaur (2 regulations) + Mega Venusaur (1) + Charmander (0, skipped) = 3
    assert len(rows) == 3

    venusaur_rows = [r for r in rows if r["form_name"] == "venusaur"]
    assert {r["regulation_code"] for r in venusaur_rows} == {"m-a", "m-b"}
    row = venusaur_rows[0]
    assert row["pokemon_id"] == "3"
    assert row["pokemon_name"] == "Venusaur"
    assert row["is_legal"] == "True"
    assert row["source_name"] == "PokéBase"
    assert row["source_url"] == f"{pokebase.PAGE_URL}/venusaur"
    assert row["dataset_version"] == "0.1.0"
    assert row["extracted_at_utc"]


def test_extract_skips_pokemon_with_no_regulation_sets(tmp_path):
    session = _FakeSession(_html_with_flight_payload(POKEMON_DOCS))
    output_path = tmp_path / "pokebase.csv"

    pokebase.extract(output_path, session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert all(row["form_name"] != "charmander" for row in rows)


def test_extract_uses_national_number_for_mega_forms(tmp_path):
    session = _FakeSession(_html_with_flight_payload(POKEMON_DOCS))
    output_path = tmp_path / "pokebase.csv"

    pokebase.extract(output_path, session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    mega_row = next(row for row in rows if row["form_name"] == "venusaur-mega")
    assert mega_row["pokemon_id"] == "3"
    assert mega_row["pokemon_name"] == "Mega Venusaur"
    assert mega_row["regulation_code"] == "m-a"


def test_extract_defaults_dataset_version_when_not_provided(tmp_path):
    session = _FakeSession(_html_with_flight_payload(POKEMON_DOCS))
    output_path = tmp_path / "pokebase.csv"

    pokebase.extract(output_path, session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))

    assert row["dataset_version"] == pokebase.DEFAULT_DATASET_VERSION


def test_extract_retries_transient_error_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_http.time, "sleep", lambda seconds: None)
    session = _FakeSession(_html_with_flight_payload(POKEMON_DOCS), fail_count=2)
    output_path = tmp_path / "pokebase.csv"

    pokebase.extract(output_path, session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 3
    assert len(session.requested_urls) == 3


def _html_with_regulation_ordered_payload(pokemon: list[dict]) -> str:
    """The page shape PokéBase switched to by 2026-10: the list sits under
    data.pokemon, entries carry `dex` and `addedIn`, and a separate
    `regulations` array gives release order."""
    inner_json = json.dumps(
        {
            "data": {"pokemon": pokemon},
            "regulations": [
                {"slug": "m-a", "name": "M-A"},
                {"slug": "m-b", "name": "M-B"},
                {"slug": "m-c", "name": "M-C"},
            ],
        },
        separators=(",", ":"),
    )
    escaped_inner_json = json.dumps(inner_json)
    return (
        "<html><body>"
        f'<script>self.__next_f.push([1,"6:{escaped_inner_json[1:-1]}"])</script>'
        "</body></html>"
    )


def test_regulation_ordered_shape_is_legal_from_added_in_onward(tmp_path):
    pokemon = [
        {"id": "v1", "name": "Venusaur", "slug": "venusaur", "dex": 3, "addedIn": "m-a"},
        {"id": "a1", "name": "Mega Absol Z", "slug": "absol-mega-z", "dex": 359, "addedIn": "m-c"},
        {"id": "x1", "name": "Unreleased", "slug": "unreleased", "dex": 9999},
    ]
    session = _FakeSession(_html_with_regulation_ordered_payload(pokemon))
    output_path = tmp_path / "pokebase.csv"

    pokebase.extract(output_path, dataset_version="0.1.0", session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    by_form = {}
    for row in rows:
        by_form.setdefault(row["form_name"], []).append(row["regulation_code"])
    assert by_form == {"venusaur": ["m-a", "m-b", "m-c"], "absol-mega-z": ["m-c"]}
    absol = next(r for r in rows if r["form_name"] == "absol-mega-z")
    assert absol["pokemon_id"] == "359"
    assert absol["source_record_id"] == "a1:m-c"
