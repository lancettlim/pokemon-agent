"""Pokémon Showdown ladder replays (replay.pokemonshowdown.com).

Contract: data/staging/showdown_replays.schema.json (one row per battle
side).
Spec reference: docs/dataset-spec.md, "Added sources > Showdown replays";
docs/upgrade-plan-2027q2.md, S3 and laundry list #27; docs/roadmap.md,
Phase 4.

Tournament data is team vs team: no source says which four of a team's six
were brought to a game. Showdown's replays do, for the ladder: a replay's
log names the six each side showed at team preview (`|poke|`), every
Pokémon that entered the battle (`|switch|`, `|drag|`, `|replace|`), the
two that led, any Mega Evolution (`|detailschange|`) and the winner
(`|win|`). That is the "which four did they bring" signal, for the Showdown
ladder population only: official events are played on the game itself, so
no replay belongs to one, and nothing here joins RK9 or MunchStats.

  - `GET /search.json?format=<id>[&before=<uploadtime>]` lists the newest
    51 public replays of a format, newest first, with id, upload time and
    rating; `before` pages back.
  - `GET /<id>.json` is one replay, its log included.

The format id comes from the regulation registry (`munchstats_format`,
"gen9championsvgc2026regmc", plus "bo3" for the Bo3 ladder), so nothing
here hardcodes a regulation. Only rated battles (the log's `|rated|`) are
kept, uploaded while the regulation was in force.

Volume: about 2,700 Reg M-C ladder replays are uploaded a day (about 2,000
Bo1 and 800 Bo3 in October 2026), and each is one request. This samples rather than mirrors: each run fetches at most
MAX_NEW_PER_FORMAT new replays per format, at most one request per
REQUEST_INTERVAL seconds, the newest first and then further back from the
oldest one held, and keeps at most MAX_HELD_PER_FORMAT battles per format
(the newest). A replay already held is never fetched again.

Privacy: player names are read only to tell which side won and are never
written. A row carries the replay id (its source_url, as provenance
requires) and the side, nothing else about the players, and the dashboard
shows aggregates only (CLAUDE.md, "Populations").

Brought means "entered the battle": a Pokémon brought but never sent in
looks the same as one left at home. Only a side that revealed all
`teamsize` Pokémon says exactly which were brought, so the marts read bring
and win-when-brought figures from complete battles (both sides revealed
all four) and lead figures from every battle (int_ladder_battle).

Megas show at team preview as their base Pokémon (the stone is hidden in
Bo1), so every Pokémon here is the preview's name: a Mega counts with its
base. Bo3 logs also carry open team sheets (`|showteam|`); they aren't
read, so Bo1 and Bo3 rows mean the same thing.

Credit: Pokémon Showdown (pokemonshowdown.com), and the players who chose
to upload their battles.
"""

from __future__ import annotations

import csv
import re
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path

import requests

from pipelines.extract.http import get_with_retry
from pipelines.regulations import Regulation, load_regulations

SOURCE_NAME = "Pokémon Showdown replays"
BASE_URL = "https://replay.pokemonshowdown.com"
DEFAULT_DATASET_VERSION = "0.0.0-dev"
VARIANTS = ("bo1", "bo3")
# Per format and run: new replays fetched, and search pages read to find
# them. A run's worst case is about 2 x 3 x 150 requests at one a second.
MAX_NEW_PER_FORMAT = 150
MAX_SEARCH_PAGES = 30
# Battles kept per format, the newest.
MAX_HELD_PER_FORMAT = 5000
REQUEST_INTERVAL = 1.0

FIELDNAMES = [
    "replay_id",
    "format_id",
    "regulation_code",
    "variant",
    "uploaded_at_utc",
    "rating",
    "turns",
    "side",
    "result",
    "team_size",
    "team",
    "brought",
    "leads",
    "mega_evolved",
    "source_name",
    "source_url",
    "source_record_id",
    "extracted_at_utc",
    "dataset_version",
]

_SIDES = ("p1", "p2")
_MEGA_SUFFIX = re.compile(r"-Mega(-[A-Z])?$")


class Pacer:
    """At most one call per `interval` seconds; clock and sleep injectable
    so tests don't wait."""

    def __init__(
        self,
        interval: float = REQUEST_INTERVAL,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.interval = interval
        self.clock = clock
        self.sleep = sleep
        self._last: float | None = None

    def wait(self) -> None:
        now = self.clock()
        if self._last is not None and now - self._last < self.interval:
            self.sleep(self.interval - (now - self._last))
            now = self.clock()
        self._last = now


def format_id(regulation: Regulation, variant: str) -> str:
    return regulation.munchstats_format + ("bo3" if variant == "bo3" else "")


def replay_url(replay_id: str) -> str:
    return f"{BASE_URL}/{replay_id}"


def _to_id(name: str) -> str:
    """Showdown's own name normalisation: lowercase letters and digits."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _species(details: str) -> str:
    """'Indeedee-F, L50, F' -> 'Indeedee-F'."""
    return details.split(",", 1)[0].strip()


def _match(species: str, team: list[str]) -> int | None:
    """The preview slot a Pokémon on the field is: the same name, a form
    the preview hid ("Urshifu-*"), or a form it changed into in battle
    ("Salamence-Mega" from "Salamence")."""
    if species in team:
        return team.index(species)
    for index, name in enumerate(team):
        base = name[:-2] if name.endswith("-*") else name
        if species == base or species.startswith(base + "-"):
            return index
    # A form's Mega drops the form from its name: "Floette-Mega" is the
    # preview's "Floette-Eternal". The species clause makes it unique.
    mega = _MEGA_SUFFIX.sub("", species)
    if mega != species:
        candidates = [
            index for index, name in enumerate(team) if name == mega or name.startswith(mega + "-")
        ]
        if len(candidates) == 1:
            return candidates[0]
    return None


class _Side:
    def __init__(self) -> None:
        self.player = ""
        self.team: list[str] = []
        self.team_size: int | None = None
        self.appearances: dict[int, int] = {}
        self.order: list[int] = []
        self.leads: list[int] = []
        self.occupant: dict[str, int] = {}
        self.lead_slots: set[str] = set()
        self.megas: list[int] = []
        self.resolved: dict[int, str] = {}

    def enter(self, slot: str, index: int, *, lead: bool) -> None:
        self.appearances[index] = self.appearances.get(index, 0) + 1
        if index not in self.order:
            self.order.append(index)
        self.occupant[slot] = index
        if lead:
            self.leads.append(index)
            self.lead_slots.add(slot)
        else:
            self.lead_slots.discard(slot)

    def replace(self, slot: str, index: int) -> None:
        """Illusion ended: the Pokémon in `slot` was `index` all along."""
        shown = self.occupant.get(slot)
        if shown is not None and shown != index:
            self.appearances[shown] -= 1
            if not self.appearances[shown]:
                self.order.remove(shown)
            if slot in self.lead_slots and shown in self.leads:
                self.leads[self.leads.index(shown)] = index
        self.appearances[index] = self.appearances.get(index, 0) + 1
        if index not in self.order:
            self.order.append(index)
        self.occupant[slot] = index

    def name(self, index: int) -> str:
        return self.resolved.get(index) or self.team[index].removesuffix("-*")

    def brought(self) -> list[int]:
        return [index for index in self.order if self.appearances.get(index)]


def parse_log(log: str) -> dict | None:
    """A replay log -> {"rated", "turns", "sides": {p1: row fields, p2: ...}}, or
    None when the battle never started, has no result, or the log can't be
    read consistently (a Pokémon on the field that wasn't at preview, more
    brought than the team size)."""
    sides = {side: _Side() for side in _SIDES}
    rated = started = in_turns = False
    turns = 0
    winner_name: str | None = None
    tie = False
    for line in log.split("\n"):
        parts = line.split("|")
        if len(parts) < 2:
            continue
        kind = parts[1]
        if kind == "player" and len(parts) > 3 and parts[2] in sides and parts[3]:
            sides[parts[2]].player = parts[3]
        elif kind == "poke" and len(parts) > 3 and parts[2] in sides:
            sides[parts[2]].team.append(_species(parts[3]))
        elif kind == "teamsize" and len(parts) > 3 and parts[2] in sides and parts[3].isdigit():
            sides[parts[2]].team_size = int(parts[3])
        elif kind == "rated":
            rated = True
        elif kind == "start":
            started = True
        elif kind == "turn" and len(parts) > 2 and parts[2].isdigit():
            in_turns = True
            turns = max(turns, int(parts[2]))
        elif kind in ("switch", "drag", "replace") and len(parts) > 3 and started:
            slot = parts[2].split(":", 1)[0]
            side = sides.get(slot[:2])
            if side is None:
                continue
            species = _species(parts[3])
            index = _match(species, side.team)
            if index is None:
                return None
            if side.team[index].endswith("-*"):
                side.resolved[index] = species
            if kind == "replace":
                side.replace(slot, index)
            else:
                side.enter(slot, index, lead=not in_turns)
        elif kind == "detailschange" and len(parts) > 3:
            slot = parts[2].split(":", 1)[0]
            side = sides.get(slot[:2])
            species = _species(parts[3])
            if side is not None and "-Mega" in species:
                index = _match(species, side.team)
                if index is not None and index not in side.megas:
                    side.megas.append(index)
        elif kind == "win" and len(parts) > 2:
            winner_name = parts[2]
        elif kind == "tie":
            tie = True
    if not started or (winner_name is None and not tie):
        return None
    winner = None
    if winner_name is not None:
        matches = [s for s in _SIDES if _to_id(sides[s].player) == _to_id(winner_name)]
        if len(matches) != 1:
            return None
        winner = matches[0]
    out = {}
    for key, side in sides.items():
        brought = side.brought()
        if not side.team or not side.leads or (side.team_size and len(brought) > side.team_size):
            return None
        out[key] = {
            "result": "tie" if tie else ("win" if key == winner else "loss"),
            "team_size": side.team_size or "",
            "team": "|".join(side.name(i) for i in range(len(side.team))),
            "brought": "|".join(side.name(i) for i in brought),
            "leads": "|".join(side.name(i) for i in side.leads),
            "mega_evolved": "|".join(side.name(i) for i in side.megas),
        }
    return {"rated": rated, "turns": turns, "sides": out}


def battle_rows(
    replay: dict,
    regulation: Regulation,
    variant: str,
    *,
    extracted_at_utc: str,
    dataset_version: str,
) -> list[dict]:
    """One replay's two side rows, or [] for an unrated or unreadable one."""
    parsed = parse_log(replay.get("log") or "")
    if parsed is None or not parsed["rated"]:
        return []
    replay_id = replay["id"]
    uploaded = datetime.fromtimestamp(int(replay["uploadtime"]), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return [
        {
            "replay_id": replay_id,
            "format_id": replay.get("formatid") or format_id(regulation, variant),
            "regulation_code": regulation.regulation_code,
            "variant": variant,
            "uploaded_at_utc": uploaded,
            "rating": replay.get("rating") or "",
            "turns": parsed["turns"],
            "side": side,
            **parsed["sides"][side],
            "source_name": SOURCE_NAME,
            "source_url": replay_url(replay_id),
            "source_record_id": f"{replay_id}:{side}",
            "extracted_at_utc": extracted_at_utc,
            "dataset_version": dataset_version,
        }
        for side in _SIDES
    ]


def _epoch(day) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())


def _get_json(session: requests.Session, url: str, pacer: Pacer, params: dict | None = None):
    pacer.wait()
    return get_with_retry(session, url, params=params, timeout=60).json()


def _search(session, fid: str, before: int | None, pacer: Pacer) -> list[dict]:
    params = {"format": fid}
    if before is not None:
        params["before"] = before
    return _get_json(session, f"{BASE_URL}/search.json", pacer, params) or []


def sample_format(
    session: requests.Session,
    regulation: Regulation,
    variant: str,
    held: dict[str, list[dict]],
    *,
    now_epoch: int,
    pacer: Pacer,
    extracted_at_utc: str,
    dataset_version: str,
    budget: int = MAX_NEW_PER_FORMAT,
) -> list[dict]:
    """New side rows for one format: the newest replays down to the newest
    one held, then on back from the oldest held, until `budget` replays
    have been fetched or the regulation's start is reached."""
    fid = format_id(regulation, variant)
    start, end = _epoch(regulation.start_date), _epoch(regulation.end_date)
    oldest_held = min(
        (int(_uploaded_epoch(rows[0])) for rows in held.values() if rows), default=None
    )
    cursor = None if end > now_epoch else end
    jumped = oldest_held is None
    fetched = 0
    rows: list[dict] = []
    seen: set[str] = set()
    for _page in range(MAX_SEARCH_PAGES):
        results = _search(session, fid, cursor, pacer)
        if not results:
            break
        next_cursor = int(results[-1]["uploadtime"])
        for result in results:
            replay_id = result.get("id")
            uploaded = int(result.get("uploadtime") or 0)
            if not replay_id or replay_id in seen:
                continue
            seen.add(replay_id)
            if uploaded < start:
                return rows
            if uploaded >= end:
                continue
            if replay_id in held:
                if not jumped:
                    # Caught up with the newest held: carry on from the
                    # oldest held instead of re-reading the held run.
                    jumped = True
                    next_cursor = oldest_held
                    break
                continue
            if result.get("private") or result.get("password"):
                continue
            replay = _get_json(session, f"{BASE_URL}/{replay_id}.json", pacer)
            fetched += 1
            rows.extend(
                battle_rows(
                    replay,
                    regulation,
                    variant,
                    extracted_at_utc=extracted_at_utc,
                    dataset_version=dataset_version,
                )
            )
            if fetched >= budget:
                return rows
        if len(results) < 51 and next_cursor != oldest_held:
            break
        cursor = next_cursor
    return rows


def _uploaded_epoch(row: dict) -> float:
    return (
        datetime.strptime(row["uploaded_at_utc"], "%Y-%m-%dT%H:%M:%SZ")
        .replace(tzinfo=UTC)
        .timestamp()
    )


def _load(path: Path | None) -> dict[str, dict[str, list[dict]]]:
    """A previous snapshot's rows: format id -> replay id -> side rows."""
    held: dict[str, dict[str, list[dict]]] = {}
    if path is None or not path.exists():
        return held
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            held.setdefault(row["format_id"], {}).setdefault(row["replay_id"], []).append(row)
    return held


def _write(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def extract(
    output_path: Path,
    *,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    session: requests.Session | None = None,
    previous_snapshot_path: Path | None = None,
    regulations: list[Regulation] | None = None,
    pacer: Pacer | None = None,
    now: datetime | None = None,
    budget: int = MAX_NEW_PER_FORMAT,
) -> int:
    """Write every held battle plus this run's sample, newest regulation
    first, each format capped at MAX_HELD_PER_FORMAT battles. Returns the
    number of new battles."""
    http = session if session is not None else requests.Session()
    regulations = load_regulations() if regulations is None else regulations
    pacer = pacer or Pacer()
    now = now or datetime.now(UTC)
    extracted_at_utc = now.isoformat()
    previous = _load(previous_snapshot_path)
    out: list[dict] = []
    new_battles = 0
    for regulation in sorted(regulations, key=lambda r: r.start_date, reverse=True):
        for variant in VARIANTS:
            fid = format_id(regulation, variant)
            held = previous.get(fid, {})
            fresh = sample_format(
                http,
                regulation,
                variant,
                held,
                now_epoch=int(now.timestamp()),
                pacer=pacer,
                extracted_at_utc=extracted_at_utc,
                dataset_version=dataset_version,
                budget=budget,
            )
            battles: dict[str, list[dict]] = {
                replay_id: [
                    {
                        **row,
                        "extracted_at_utc": extracted_at_utc,
                        "dataset_version": dataset_version,
                    }
                    for row in rows
                ]
                for replay_id, rows in held.items()
            }
            for row in fresh:
                if row["replay_id"] not in battles:
                    new_battles += row["side"] == "p1"
                battles.setdefault(row["replay_id"], [])
                if row["side"] not in {r["side"] for r in battles[row["replay_id"]]}:
                    battles[row["replay_id"]].append(row)
            newest = sorted(
                battles.values(), key=lambda rows: rows[0]["uploaded_at_utc"], reverse=True
            )[:MAX_HELD_PER_FORMAT]
            for rows in newest:
                out.extend(sorted(rows, key=lambda r: r["side"]))
    _write(output_path, out)
    return new_battles
