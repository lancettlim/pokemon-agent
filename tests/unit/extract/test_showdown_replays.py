import csv
from datetime import UTC, date, datetime

import requests

from pipelines.extract import showdown_replays
from pipelines.regulations import Regulation

_MC = Regulation(
    "m-c", "C", "gen9championsvgc2026regmc", "m-c", date(2026, 9, 9), date(2026, 12, 2), "M-C"
)
_MB = Regulation(
    "m-b", "B", "gen9championsvgc2026regmb", "m-b", date(2026, 6, 17), date(2026, 9, 9), "M-B"
)
_NOW = datetime(2026, 10, 23, 8, 0, tzinfo=UTC)


def _log(*, rated=True, winner="Alice", extra=(), p1_team=None, p2_team=None, start=True):
    """A doubles log trimmed from a real Reg M-C replay's shape."""
    p1_team = p1_team or [
        "Pelipper",
        "Golisopod",
        "Salamence",
        "Basculegion",
        "Sneasler",
        "Indeedee",
    ]
    p2_team = p2_team or [
        "Gallade",
        "Gholdengo",
        "Indeedee-F",
        "Hydreigon",
        "Alcremie",
        "Rotom-Heat",
    ]
    lines = ["|player|p1|Alice|169|1169", "|player|p2|Bob B|102|1069", "|gametype|doubles"]
    if rated:
        lines.append("|rated|")
    lines += [f"|poke|p1|{name}, L50, M|" for name in p1_team]
    lines += [f"|poke|p2|{name}, L50, F|" for name in p2_team]
    lines += ["|teampreview|4", "|teamsize|p1|4", "|teamsize|p2|4"]
    if start:
        lines += [
            "|start",
            "|switch|p1a: Sneasler|Sneasler, L50, M|100/100",
            "|switch|p1b: Salamence|Salamence, L50, M|100/100",
            "|switch|p2a: Hydreigon|Hydreigon, L50, F|100/100",
            "|switch|p2b: Indeedee|Indeedee-F, L50, F|100/100",
            "|turn|1",
            "|detailschange|p1b: Salamence|Salamence-Mega, L50, M",
            "|-mega|p1b: Salamence|Salamence|Salamencite",
            "|faint|p1a: Sneasler",
            "|switch|p1a: Basculegion|Basculegion, L50, M|100/100",
            "|turn|2",
            "|switch|p1b: Pelipper|Pelipper, L50, M|100/100",
            "|switch|p2a: Gholdengo|Gholdengo, L50|100/100",
            "|turn|3",
            *extra,
        ]
    if winner:
        lines.append(f"|win|{winner}")
    return "\n".join(lines)


def test_parse_log_reads_preview_brought_leads_megas_and_the_winner():
    parsed = showdown_replays.parse_log(_log(winner="bob b"))

    assert parsed["rated"] and parsed["turns"] == 3
    p1, p2 = parsed["sides"]["p1"], parsed["sides"]["p2"]
    assert p1["team"] == "Pelipper|Golisopod|Salamence|Basculegion|Sneasler|Indeedee"
    assert p1["brought"] == "Sneasler|Salamence|Basculegion|Pelipper"
    assert p1["leads"] == "Sneasler|Salamence"
    assert p1["mega_evolved"] == "Salamence"
    assert p2["brought"] == "Hydreigon|Indeedee-F|Gholdengo"
    # The win line's name matched case- and space-insensitively.
    assert (p1["result"], p2["result"]) == ("loss", "win")


def test_an_illusion_that_ends_credits_the_pokemon_really_sent_in():
    team = ["Zoroark-Hisui", "Kingambit", "Sneasler", "Incineroar", "Rillaboom", "Pelipper"]
    log = (
        _log(
            p1_team=team,
            extra=[
                # Shown as Kingambit, revealed as Zoroark-Hisui.
                "|switch|p1a: Kingambit|Kingambit, L50, M|100/100",
                "|replace|p1a: Zoroark|Zoroark-Hisui, L50, M",
            ],
        )
        .replace("|switch|p1a: Sneasler|Sneasler", "|switch|p1a: Sneasler|Sneasler")
        .replace("Salamence", "Incineroar")
        .replace("|switch|p1a: Basculegion|Basculegion, L50, M|100/100", "")
        .replace("|switch|p1b: Pelipper|Pelipper, L50, M|100/100", "")
    )

    p1 = showdown_replays.parse_log(log)["sides"]["p1"]

    assert p1["brought"].split("|") == ["Sneasler", "Incineroar", "Zoroark-Hisui"]


def test_a_form_hidden_at_preview_takes_the_form_sent_in():
    team = ["Urshifu-*", "Kingambit", "Sneasler", "Incineroar", "Rillaboom", "Pelipper"]
    log = _log(p1_team=team, extra=["|switch|p1a: Urshifu|Urshifu-Rapid-Strike, L50, M|100/100"])

    p1 = showdown_replays.parse_log(
        log.replace("Salamence", "Incineroar")
        .replace("|switch|p1a: Basculegion|Basculegion, L50, M|100/100", "")
        .replace("|switch|p1b: Pelipper|Pelipper, L50, M|100/100", "")
    )["sides"]["p1"]

    assert p1["team"].split("|")[0] == "Urshifu-Rapid-Strike"
    assert "Urshifu-Rapid-Strike" in p1["brought"]


def test_a_forms_mega_matches_its_preview_entry():
    team = ["Floette-Eternal", "Kingambit", "Sneasler", "Incineroar", "Rillaboom", "Pelipper"]
    assert showdown_replays._match("Floette-Mega", team) == 0
    assert showdown_replays._match("Raichu-Mega-Y", ["Raichu", "Sneasler"]) == 0
    assert showdown_replays._match("Ditto", team) is None


def test_unreadable_unstarted_and_unrated_battles_are_dropped():
    assert showdown_replays.parse_log(_log(start=False)) is None
    assert showdown_replays.parse_log(_log(winner=None)) is None
    # A Pokémon on the field that wasn't at preview.
    assert showdown_replays.parse_log(_log(extra=["|switch|p2b: Ditto|Ditto, L50|100/100"])) is None
    replay = {"id": "x-1", "uploadtime": 1792739682, "log": _log(rated=False), "rating": 0}
    assert (
        showdown_replays.battle_rows(replay, _MC, "bo1", extracted_at_utc="t", dataset_version="v")
        == []
    )


def test_battle_rows_carry_provenance_and_no_player_names():
    replay = {
        "id": "gen9championsvgc2026regmc-1",
        "uploadtime": 1792739682,
        "log": _log(),
        "rating": 1107,
    }

    rows = showdown_replays.battle_rows(
        replay, _MC, "bo1", extracted_at_utc="2026-10-23T08:00:00+00:00", dataset_version="0.4.0"
    )

    assert [r["side"] for r in rows] == ["p1", "p2"]
    assert rows[0]["source_url"] == f"{showdown_replays.BASE_URL}/gen9championsvgc2026regmc-1"
    assert rows[0]["source_record_id"] == "gen9championsvgc2026regmc-1:p1"
    assert rows[0]["uploaded_at_utc"] == "2026-10-23T07:14:42Z"
    assert rows[0]["format_id"] == "gen9championsvgc2026regmc"
    assert list(rows[0]) == showdown_replays.FIELDNAMES
    text = " ".join(str(v) for row in rows for v in row.values())
    assert "Alice" not in text and "Bob" not in text


class _Pacer:
    def __init__(self):
        self.calls = 0

    def wait(self):
        self.calls += 1


class _FakeResponse:
    def __init__(self, payload, status_code=200):
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
    """Search pages over `uploads` (id -> uploadtime), newest first, 51 a
    page, `before` exclusive; every replay is a readable rated battle."""

    def __init__(self, uploads):
        self.uploads = sorted(uploads.items(), key=lambda kv: -kv[1])
        self.searches: list[dict] = []
        self.fetched: list[str] = []

    def get(self, url, params=None, headers=None, timeout=None):
        if url.endswith("/search.json"):
            self.searches.append(dict(params))
            before = params.get("before")
            page = [
                {"id": rid, "uploadtime": t, "rating": 1300, "private": 0, "password": None}
                for rid, t in self.uploads
                if rid.rsplit("-", 1)[0] == params["format"] and (before is None or t < before)
            ][:51]
            return _FakeResponse(page)
        replay_id = url.rsplit("/", 1)[1].removesuffix(".json")
        self.fetched.append(replay_id)
        uploadtime = dict(self.uploads)[replay_id]
        return _FakeResponse(
            {"id": replay_id, "uploadtime": uploadtime, "rating": 1300, "log": _log()}
        )


def _uploads(prefix, start, count, step=600):
    return {f"{prefix}-{i}": start - i * step for i in range(count)}


def test_sampling_takes_the_newest_then_continues_from_the_oldest_held():
    # 100 uploads on 22 October; the run before held the 10 newest after #20.
    uploads = _uploads("gen9championsvgc2026regmc", 1792713600, 100)
    held_ids = [f"gen9championsvgc2026regmc-{i}" for i in range(20, 30)]
    held = {
        rid: [
            {
                "uploaded_at_utc": datetime.fromtimestamp(uploads[rid], UTC).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
            }
        ]
        for rid in held_ids
    }
    session = _FakeSession(uploads)

    rows = showdown_replays.sample_format(
        session,
        _MC,
        "bo1",
        held,
        now_epoch=int(_NOW.timestamp()),
        pacer=_Pacer(),
        extracted_at_utc="t",
        dataset_version="v",
        budget=30,
    )

    # The 20 newer than anything held, then 10 from below the oldest held.
    fetched = [int(rid.rsplit("-", 1)[1]) for rid in session.fetched]
    assert fetched == list(range(20)) + list(range(30, 40))
    assert len(rows) == 60
    assert session.searches[1]["before"] == uploads["gen9championsvgc2026regmc-29"]


def test_sampling_stays_inside_the_regulations_window():
    # M-B ended 9 September: its newest replays are searched from there, and
    # uploads from before 17 June end the walk.
    end = int(datetime(2026, 9, 9, tzinfo=UTC).timestamp())
    start = int(datetime(2026, 6, 17, tzinfo=UTC).timestamp())
    uploads = {
        "gen9championsvgc2026regmb-late": end + 100,
        "gen9championsvgc2026regmb-in": end - 100,
        "gen9championsvgc2026regmb-early": start - 100,
    }
    session = _FakeSession(uploads)

    showdown_replays.sample_format(
        session,
        _MB,
        "bo1",
        {},
        now_epoch=int(_NOW.timestamp()),
        pacer=_Pacer(),
        extracted_at_utc="t",
        dataset_version="v",
    )

    assert session.searches[0] == {"format": "gen9championsvgc2026regmb", "before": end}
    assert session.fetched == ["gen9championsvgc2026regmb-in"]


def _read(path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_extract_reuses_held_battles_and_caps_each_format(tmp_path, monkeypatch):
    monkeypatch.setattr(showdown_replays, "MAX_HELD_PER_FORMAT", 25)
    uploads = _uploads("gen9championsvgc2026regmc", 1792713600, 40)
    first = tmp_path / "1.csv"
    showdown_replays.extract(
        first, session=_FakeSession(uploads), regulations=[_MC], pacer=_Pacer(), now=_NOW, budget=10
    )
    assert len({r["replay_id"] for r in _read(first)}) == 10

    session = _FakeSession(uploads)
    second = tmp_path / "2.csv"
    new = showdown_replays.extract(
        second,
        session=session,
        previous_snapshot_path=first,
        regulations=[_MC],
        pacer=_Pacer(),
        now=_NOW,
        budget=20,
        dataset_version="0.4.0",
    )

    assert new == 20
    assert not set(session.fetched) & {r["replay_id"] for r in _read(first)}
    rows = _read(second)
    # 30 battles, capped to the newest 25, two sides each.
    assert len(rows) == 50
    assert {r["dataset_version"] for r in rows} == {"0.4.0"}
    kept = {int(r["replay_id"].rsplit("-", 1)[1]) for r in rows}
    assert kept == set(range(25))


def test_the_pacer_spaces_requests():
    now = [0.0]
    slept = []

    def sleep(seconds):
        slept.append(seconds)
        now[0] += seconds

    pacer = showdown_replays.Pacer(1.0, clock=lambda: now[0], sleep=sleep)
    pacer.wait()
    now[0] += 0.25
    pacer.wait()
    assert slept == [0.75]
