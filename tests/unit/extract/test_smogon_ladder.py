import csv
from datetime import date

import requests

from pipelines.extract import smogon_ladder
from pipelines.regulations import Regulation

_REGULATIONS = [
    Regulation("m-b", "B", "gen9championsvgc2026regmb", "m-b", date(2026, 6, 17), date(2026, 9, 9)),
    Regulation("m-c", "C", "gen9championsvgc2026regmc", "m-c", date(2026, 9, 9), date(2026, 12, 2)),
]

_MONTHS_PAGE = """<html><body><pre>
<a href="../">../</a>
<a href="2026-06/">2026-06/</a>
<a href="2026-07/">2026-07/</a>
<a href="2026-08/">2026-08/</a>
<a href="2026-09/">2026-09/</a>
</pre></body></html>"""


def _files_page(names):
    return (
        "<pre>"
        + "".join(f'<a href="{n}">{n}</a>    01-Oct-2026 14:40   3490796\n' for n in names)
        + "</pre>"
    )


_LISTINGS = {
    "2026-06": ["gen9championsvgc2026regmb-1760.json", "gen9championsou-1760.json"],
    "2026-07": ["gen9championsvgc2026regmb-1760.json"],
    "2026-08": [
        "gen9championsvgc2026regmb-0.json",
        "gen9championsvgc2026regmb-1760.json",
        "gen9championsvgc2026regmbbo3-1760.json",
    ],
    "2026-09": [
        "gen9championsvgc2026regmb-1760.json",
        "gen9championsvgc2026regmc-0.json",
        "gen9championsvgc2026regmc-1760.json",
    ],
}

# Shape trimmed from a real chaos file (2026-09, Reg M-C).
_CHAOS = {
    "info": {"metagame": "gen9championsvgc2026regmc", "cutoff": 0, "number of battles": 1631943},
    "data": {
        "Kingambit": {
            "Raw count": 412345,
            "usage": 0.2527,
            "Spreads": {
                "Adamant:32/32/0/0/2/0": 30.0,
                "Adamant:2/32/0/0/0/32": 10.0,
                "Other": 60.0,
            },
            "Checks and Counters": {
                "Torkoal": {"n": 6624.0, "p": 0.5996, "d": 0.0060},
                "Sneasler": {"n": 39065.0, "p": 0.5028, "d": 0.0025},
                # High rate, too few encounters: dropped.
                "Mudsdale": {"n": 40.0, "p": 0.9, "d": 0.05},
                # Fewer encounters push a high rate down Smogon's p - 4d.
                "Grapploct": {"n": 120.0, "p": 0.62, "d": 0.045},
            },
        },
        "Farfetch'd": {"Raw count": 12, "usage": 0.00001, "Spreads": {}, "Checks and Counters": {}},
    },
}


class _FakeResponse:
    def __init__(self, *, text="", payload=None, status_code=200):
        self.text = text
        self._payload = payload
        self.status_code = status_code
        self.headers = {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.exceptions.HTTPError(f"{self.status_code} error")
            error.response = self
            raise error


class _FakeSession:
    def __init__(self):
        self.requested: list[str] = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.requested.append(url)
        if url == f"{smogon_ladder.BASE_URL}/":
            return _FakeResponse(text=_MONTHS_PAGE)
        for month, names in _LISTINGS.items():
            if url == f"{smogon_ladder.BASE_URL}/{month}/chaos/":
                return _FakeResponse(text=_files_page(names))
            if url.startswith(f"{smogon_ladder.BASE_URL}/{month}/chaos/") and url.endswith(".json"):
                return _FakeResponse(payload=_CHAOS)
        return _FakeResponse(status_code=404)


def _read(path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_each_regulation_takes_its_newest_mostly_in_force_month():
    # M-B ended on 9 September, so September's file is mostly M-C-era play
    # and August is its month. M-C began on the 9th: 22 of 30 days.
    plan = smogon_ladder.plan_files(_FakeSession(), _REGULATIONS)

    by_regulation = {}
    for month, regulation, variant, cutoff in plan:
        by_regulation.setdefault(regulation.regulation_code, set()).add((month, variant, cutoff))
    assert by_regulation["m-b"] == {
        ("2026-08", "bo1", 1760),
        ("2026-08", "bo1", 0),
        ("2026-08", "bo3", 1760),
    }
    assert by_regulation["m-c"] == {("2026-09", "bo1", 1760), ("2026-09", "bo1", 0)}


def test_a_new_regulations_first_partial_month_still_counts():
    m_d = Regulation(
        "m-d", "D", "gen9championsvgc2026regmd", "m-d", date(2026, 12, 20), date(2027, 3, 1)
    )

    assert smogon_ladder.pick_month(m_d, ["2026-12"]) == "2026-12"
    assert smogon_ladder.pick_month(m_d, ["2026-12", "2027-01"]) == "2027-01"
    assert smogon_ladder.pick_month(m_d, ["2026-11"]) is None


def test_only_months_a_regulation_was_in_force_are_listed():
    session = _FakeSession()

    smogon_ladder.plan_files(session, _REGULATIONS[1:])

    assert f"{smogon_ladder.BASE_URL}/2026-08/chaos/" not in session.requested
    assert f"{smogon_ladder.BASE_URL}/2026-09/chaos/" in session.requested


def test_parse_file_ranks_counters_by_smogons_score_and_drops_thin_pairs():
    usage, counters, spreads = smogon_ladder.parse_file(
        _CHAOS,
        month="2026-09",
        regulation=_REGULATIONS[1],
        variant="bo1",
        cutoff=0,
        extracted_at_utc="2026-10-23T00:00:00+00:00",
        dataset_version="0.0.0-dev",
    )

    kingambit = next(r for r in usage if r["pokemon_name"] == "Kingambit")
    assert kingambit["usage"] == 0.2527
    assert kingambit["battles"] == 1631943
    assert (
        kingambit["source_url"]
        == f"{smogon_ladder.BASE_URL}/2026-09/chaos/gen9championsvgc2026regmc-0.json"
    )
    assert kingambit["source_record_id"] == "2026-09/gen9championsvgc2026regmc-0.json:Kingambit"
    # Torkoal 0.5996 - 4(0.006) = 0.576 > Sneasler 0.4928 > Grapploct 0.44.
    assert [r["counter_name"] for r in counters] == ["Torkoal", "Sneasler", "Grapploct"]
    assert counters[0]["encounters"] == 6624.0
    # A malformed spread ("Other") is skipped; shares are of the whole.
    assert [(r["nature"], r["sp_hp"], r["sp_spe"], r["share"]) for r in spreads] == [
        ("Adamant", 32, 0, 0.3),
        ("Adamant", 2, 32, 0.1),
    ]
    assert all(r["regulation_code"] == "m-c" for r in usage + counters + spreads)


def test_extract_writes_three_tables_and_reuses_a_held_month(tmp_path):
    first = [tmp_path / "1" / f"{name}.csv" for name in ("usage", "counters", "spreads")]
    session = _FakeSession()
    smogon_ladder.extract(
        *first,
        session=session,
        regulations=_REGULATIONS,
        extracted_at_utc="2026-10-22T00:00:00+00:00",
    )
    downloads = [u for u in session.requested if u.endswith(".json")]
    assert len(downloads) == 5
    assert {r["regulation_code"] for r in _read(first[0])} == {"m-b", "m-c"}
    assert _read(first[1]) and _read(first[2])

    second = [tmp_path / "2" / f"{name}.csv" for name in ("usage", "counters", "spreads")]
    session = _FakeSession()
    smogon_ladder.extract(
        *second,
        session=session,
        regulations=_REGULATIONS,
        previous_paths=tuple(first),
        extracted_at_utc="2026-10-23T00:00:00+00:00",
        dataset_version="0.4.0",
    )

    assert [u for u in session.requested if u.endswith(".json")] == []
    rows = _read(second[0])
    assert len(rows) == len(_read(first[0]))
    assert {r["extracted_at_utc"] for r in rows} == {"2026-10-23T00:00:00+00:00"}
    assert {r["dataset_version"] for r in _read(second[1])} == {"0.4.0"}
    assert len(_read(second[2])) == len(_read(first[2]))


def test_a_file_missing_from_the_previous_snapshot_is_downloaded(tmp_path):
    previous = []
    for fieldnames in (
        smogon_ladder.FIELDNAMES,
        smogon_ladder.COUNTER_FIELDNAMES,
        smogon_ladder.SPREAD_FIELDNAMES,
    ):
        path = tmp_path / f"previous-{len(previous)}.csv"
        path.write_text(",".join(fieldnames) + "\n", encoding="utf-8")
        previous.append(path)
    paths = [tmp_path / f"{name}.csv" for name in ("usage", "counters", "spreads")]
    session = _FakeSession()

    smogon_ladder.extract(
        *paths,
        session=session,
        regulations=_REGULATIONS[1:],
        previous_paths=tuple(previous),
    )

    assert len([u for u in session.requested if u.endswith(".json")]) == 2


def test_without_every_previous_table_nothing_is_reused(tmp_path):
    # A held month can rightly have no counter rows, so a missing counters
    # snapshot can't be told apart from an empty one: download everything.
    first = [tmp_path / "1" / f"{name}.csv" for name in ("usage", "counters", "spreads")]
    smogon_ladder.extract(*first, session=_FakeSession(), regulations=_REGULATIONS[1:])
    second = [tmp_path / "2" / f"{name}.csv" for name in ("usage", "counters", "spreads")]
    session = _FakeSession()

    smogon_ladder.extract(
        *second,
        session=session,
        regulations=_REGULATIONS[1:],
        previous_paths=(first[0], None, first[2]),
    )

    assert len([u for u in session.requested if u.endswith(".json")]) == 2
    assert len(_read(second[1])) == len(_read(first[1]))
