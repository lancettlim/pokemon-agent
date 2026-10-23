"""RK9.gg tournament pairings extraction.

Contract: data/staging/rk9_pairings.schema.json
Spec reference: docs/dataset-spec.md, "Source-specific extraction contracts > RK9.gg"

Supplies the match-level head-to-head data backlog.md #27 recorded as
having "no signal to derive from" -- MunchStats reports each team's
aggregate win/loss record but never who they played. RK9 is the tournament
software the events themselves run on (MunchStats scrapes it too, for
rosters), and it publishes round-by-round pairings:

  - `GET /pairings/{event_id}` returns the pairings shell. Its division tab
    strip (`<a id="P{pod}-tab" ...>Masters in Round 17</a>`) names every
    pod, its human division label, and the highest round reached.
  - `GET /pairings/{event_id}?pod={pod}&rnd={n}` returns one round's
    pairings as an HTML fragment (htmx lazy-loads these client-side; a
    plain GET works exactly as well, no browser automation needed).

Rounds are enumerated from the tab strip rather than from the fragments'
own `hx-get` attributes: the *currently active* round is rendered inline
into the shell instead of being lazy-loaded, so it has no `hx-get` of its
own and reading only those would silently drop the final round of every
event (verified against NAIC 2026, whose round 17 -- the finals -- appears
in no `hx-get`).

`event_id` needs no mapping seed or ID reconciliation: MunchStats scrapes
RK9 and reuses RK9's own event IDs verbatim, so the `event_id` already in
`tournament_event` (e.g. "NA02wgUPFDXKmQmqILwS") *is* the RK9 pairings key.
The event list therefore comes from MunchStats' tournaments_index.json --
the same document munchstats.py already reads -- rather than from a
separate RK9 crawl.

Scoped to Champions-format events (`format_filter`, default: every
`munchstats_format` in dbt/seeds/champions_regulations.csv, via
pipelines/regulations.py). MunchStats indexes 60 events, most of them
standard VGC or same-venue TCG, which are out of this dataset's scope
(docs/prd.md) -- extracting all of them would mean ~1,300 requests per run
against a host whose posture is unverified (below) to produce rows nothing
downstream consumes.

Pairing rows are parsed by cell rather than by scraping the match container
loosely: every cell carries a fully-determined
`id="cell-{pod}-{round}-{index}-{slot}"`, where slot 1/2 are the two
players and slot 3 is the table number. A cell's class list carries the
result (`winner`/`loser`, plus `dropped` for a player who dropped out).
Outcome is derived structurally, so a shape this extractor has not seen
degrades honestly instead of being guessed at:

  - player 2's cell empty                -> "bye"
  - `winner` on player 1 / player 2      -> "player1_win" / "player2_win"
  - both cells present, neither a winner -> "tie"

Known risk, same posture as bulbagarden.py: RK9's rate-limiting/ToS stance
for sustained scheduled access has not been independently verified beyond
confirming that plain GETs work. Request volume is deliberately kept low --
one shell request plus one per (pod, round) for Champions events only, and
a concluded event's pairings are reused from the previous snapshot rather
than re-fetched (see `previous_snapshot_path`).
"""

from __future__ import annotations

import csv
import html
import re
from collections.abc import Collection, Iterable
from datetime import UTC, datetime
from pathlib import Path

import requests

from pipelines.extract.http import get_with_retry
from pipelines.regulations import munchstats_formats

SOURCE_NAME = "RK9.gg"
BASE_URL = "https://rk9.gg"
MUNCHSTATS_INDEX_URL = (
    "https://raw.githubusercontent.com/PizzaTimeJoshua/munchstats/main"
    "/stats/tournaments/tournaments_index.json"
)
DEFAULT_DATASET_VERSION = "0.0.0-dev"

# Every Champions format as MunchStats labels it in tournaments_index.json,
# one per registered regulation set. This used to be the single Reg M-A
# value, which silently dropped Worlds (M-B) and every M-C event.
CHAMPIONS_FORMATS = munchstats_formats()

# <a class="nav-link active" id="P2-tab" ... >Masters in Round 17</a>
_POD_TAB_PATTERN = re.compile(
    r'id="P(\d+)-tab"[^>]*>\s*([A-Za-z]+)\s+in\s+Round\s+(\d+)\s*<',
    re.IGNORECASE,
)

# One match container; cells are parsed out of the captured block below.
_MATCH_SPLIT_PATTERN = re.compile(r'<div class="row row-cols-3 match([^"]*)"\s*>')

# <div id="cell-2-5-0-1" class="col-5 text-center player player1 winner  ">...</div>
# Player and table cells alike contain no nested <div>, so a non-greedy
# match to the first closing tag is exact rather than merely close enough.
_CELL_PATTERN = re.compile(
    r'<div id="cell-(\d+)-(\d+)-(\d+)-(\d+)" class="([^"]*)"\s*>(.*?)</div>',
    re.DOTALL,
)

_NAME_PATTERN = re.compile(r'<span class="name">(.*?)</span>', re.DOTALL)
_TABLE_PATTERN = re.compile(r'<span class="tablenumber\s*">\s*(\d+)\s*</span>')
_RECORD_PATTERN = re.compile(r"\((\d+)-(\d+)-(\d+)\)")
_COUNTRY_PATTERN = re.compile(r"^(.*?)\s*\[([A-Za-z]{2})\]$")
_TAG_PATTERN = re.compile(r"<[^>]+>")

FIELDNAMES = [
    "event_id",
    "pod_id",
    "division",
    "round_number",
    "table_number",
    "player1_name",
    "player1_country",
    "player1_wins",
    "player1_losses",
    "player1_ties",
    "player2_name",
    "player2_country",
    "player2_wins",
    "player2_losses",
    "player2_ties",
    "outcome",
    "is_complete",
    "source_name",
    "source_url",
    "source_record_id",
    "extracted_at_utc",
    "dataset_version",
]


def _pairings_url(event_id: str) -> str:
    return f"{BASE_URL}/pairings/{event_id}"


def _round_url(event_id: str, pod_id: str, round_number: int) -> str:
    return f"{_pairings_url(event_id)}?pod={pod_id}&rnd={round_number}"


def _fetch_text(session: requests.Session, url: str) -> str:
    return get_with_retry(session, url, timeout=30).text


def _fetch_json(session: requests.Session, url: str):
    return get_with_retry(session, url, timeout=30).json()


def _strip_tags(fragment: str) -> str:
    """Collapse a cell's inner HTML to plain text. Names carry a <br> between
    given and family name ("Colleen<br> Viets [US]<br>"), so tags become
    spaces rather than being deleted outright."""
    return " ".join(html.unescape(_TAG_PATTERN.sub(" ", fragment)).split())


def _parse_pods(shell_html: str) -> list[tuple[str, str, int]]:
    """Return (pod_id, division, highest_round) per division tab."""
    return [
        (pod_id, division, int(highest_round))
        for pod_id, division, highest_round in _POD_TAB_PATTERN.findall(shell_html)
    ]


def _split_name_and_country(text: str) -> tuple[str, str]:
    """ "Colleen Viets [US]" -> ("Colleen Viets", "US"). A player with no
    reported country keeps their full name and an empty country rather than
    having a trailing bracket guessed at."""
    match = _COUNTRY_PATTERN.match(text)
    if match:
        return match.group(1).strip(), match.group(2).upper()
    return text.strip(), ""


def _parse_player_cell(class_list: str, inner_html: str) -> dict | None:
    """Parse one player cell into name/country/record/result. Returns None
    for an empty cell -- the marker of a bye, which the caller classifies."""
    name_match = _NAME_PATTERN.search(inner_html)
    if name_match is None:
        return None
    name, country = _split_name_and_country(_strip_tags(name_match.group(1)))
    if not name:
        return None
    record = _RECORD_PATTERN.search(_strip_tags(inner_html))
    classes = class_list.split()
    return {
        "name": name,
        "country": country,
        "wins": record.group(1) if record else "",
        "losses": record.group(2) if record else "",
        "ties": record.group(3) if record else "",
        "is_winner": "winner" in classes,
    }


def _outcome(player1: dict | None, player2: dict | None) -> str | None:
    """Derive the match result from the two parsed cells. Returns None for a
    shape with no players at all, which is not a match and is skipped."""
    if player1 is None and player2 is None:
        return None
    if player2 is None or player1 is None:
        return "bye"
    if player1["is_winner"] and not player2["is_winner"]:
        return "player1_win"
    if player2["is_winner"] and not player1["is_winner"]:
        return "player2_win"
    # Neither side flagged a winner: a real tie. Both flagged would be
    # contradictory markup; treat it the same rather than inventing a winner.
    return "tie"


def _parse_round(fragment: str) -> list[dict]:
    """Parse one round fragment into per-match dicts (still pod/round-free;
    the caller stamps those from the request it made)."""
    matches: list[dict] = []
    blocks = _MATCH_SPLIT_PATTERN.split(fragment)
    # split() yields [preamble, class_1, body_1, class_2, body_2, ...]
    for index in range(1, len(blocks) - 1, 2):
        container_classes = blocks[index]
        body = blocks[index + 1]
        cells = {
            int(slot): (classes, inner)
            for _, _, _, slot, classes, inner in _CELL_PATTERN.findall(body)
        }
        player1 = _parse_player_cell(*cells[1]) if 1 in cells else None
        player2 = _parse_player_cell(*cells[2]) if 2 in cells else None
        outcome = _outcome(player1, player2)
        if outcome is None:
            continue
        table_match = _TABLE_PATTERN.search(cells[3][1]) if 3 in cells else None
        matches.append(
            {
                "table_number": table_match.group(1) if table_match else "",
                "player1": player1,
                "player2": player2,
                "outcome": outcome,
                "is_complete": "complete" in container_classes.split(),
            }
        )
    return matches


def _row_from_match(
    match: dict,
    *,
    event_id: str,
    pod_id: str,
    division: str,
    round_number: int,
    extracted_at_utc: str,
    dataset_version: str,
) -> dict:
    empty = {"name": "", "country": "", "wins": "", "losses": "", "ties": ""}
    player1 = match["player1"] or empty
    player2 = match["player2"] or empty
    table_number = match["table_number"]
    return {
        "event_id": event_id,
        "pod_id": pod_id,
        "division": division,
        "round_number": round_number,
        "table_number": table_number,
        "player1_name": player1["name"],
        "player1_country": player1["country"],
        "player1_wins": player1["wins"],
        "player1_losses": player1["losses"],
        "player1_ties": player1["ties"],
        "player2_name": player2["name"],
        "player2_country": player2["country"],
        "player2_wins": player2["wins"],
        "player2_losses": player2["losses"],
        "player2_ties": player2["ties"],
        "outcome": match["outcome"],
        "is_complete": str(match["is_complete"]).lower(),
        "source_name": SOURCE_NAME,
        "source_url": _round_url(event_id, pod_id, round_number),
        # A bye has no table number, so table alone is not unique within a
        # round; the player-1 name disambiguates those rows.
        "source_record_id": (
            f"{event_id}:{pod_id}:{round_number}:{table_number or 'bye'}:{player1['name']}"
        ),
        "extracted_at_utc": extracted_at_utc,
        "dataset_version": dataset_version,
    }


def _load_cached_rows_by_event(previous_snapshot_path: Path | None) -> dict[str, list[dict]]:
    """Group the prior dated snapshot's rows by event_id. A concluded
    tournament's pairings never change once uploaded, so a cached event can
    be reused wholesale instead of re-fetching every round."""
    if previous_snapshot_path is None or not previous_snapshot_path.exists():
        return {}
    cached: dict[str, list[dict]] = {}
    with previous_snapshot_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            cached.setdefault(row["event_id"], []).append(row)
    return cached


def _rows_for_event(
    session: requests.Session,
    event_id: str,
    *,
    extracted_at_utc: str,
    dataset_version: str,
) -> list[dict]:
    shell = _fetch_text(session, _pairings_url(event_id))
    rows: list[dict] = []
    for pod_id, division, highest_round in _parse_pods(shell):
        for round_number in range(1, highest_round + 1):
            fragment = _fetch_text(session, _round_url(event_id, pod_id, round_number))
            for match in _parse_round(fragment):
                rows.append(
                    _row_from_match(
                        match,
                        event_id=event_id,
                        pod_id=pod_id,
                        division=division,
                        round_number=round_number,
                        extracted_at_utc=extracted_at_utc,
                        dataset_version=dataset_version,
                    )
                )
    return rows


def extract(
    output_path: Path,
    event_ids: Iterable[str] | None = None,
    *,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    session: requests.Session | None = None,
    previous_snapshot_path: Path | None = None,
    format_filter: Collection[str] | None = CHAMPIONS_FORMATS,
    refresh_event_ids: Collection[str] = (),
) -> None:
    """Fetch RK9 round-by-round pairings and write one row per match to
    output_path as CSV matching data/staging/rk9_pairings.schema.json,
    including provenance fields.

    `event_ids` defaults to the Champions-format events in MunchStats'
    tournaments_index.json (whose IDs are RK9's own; see the module
    docstring). Pass an explicit iterable to scope the run, or
    `format_filter=None` to take every indexed event.

    `previous_snapshot_path`, if given, enables incremental extraction the
    same way munchstats.py does: an event already present in that snapshot
    is reused from it rather than re-fetched, since pairings for a
    concluded event are immutable. Reused rows are re-stamped with this
    run's extracted_at_utc/dataset_version, matching the convention
    munchstats.py and bulbagarden.py already set for skipped work.
    `refresh_event_ids` are fetched again regardless: events still running
    (docs/upgrade-plan-2027q2.md, E4), whose cached pairings stop at
    whatever round was live when they were cached.
    """
    http = session if session is not None else requests.Session()
    if event_ids is None:
        index = _fetch_json(http, MUNCHSTATS_INDEX_URL)
        event_ids = [
            entry["id"]
            for entry in index
            if format_filter is None or entry.get("format") in format_filter
        ]
    extracted_at_utc = datetime.now(UTC).isoformat()
    cached_rows_by_event = _load_cached_rows_by_event(previous_snapshot_path)

    rows: list[dict] = []
    for event_id in event_ids:
        cached_rows = cached_rows_by_event.get(event_id)
        if cached_rows and event_id not in refresh_event_ids:
            rows.extend(
                {
                    **row,
                    "extracted_at_utc": extracted_at_utc,
                    "dataset_version": dataset_version,
                }
                for row in cached_rows
            )
            continue
        rows.extend(
            _rows_for_event(
                http,
                event_id,
                extracted_at_utc=extracted_at_utc,
                dataset_version=dataset_version,
            )
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
