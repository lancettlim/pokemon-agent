"""MunchStats extraction.

Contract: data/staging/munchstats.schema.json
Spec reference: docs/dataset-spec.md, "Source-specific extraction contracts > MunchStats"

Pulls structured JSON from the MunchStats repo (github.com/PizzaTimeJoshua/munchstats)
via raw.githubusercontent.com and flattens nested team arrays into one row
per team member, per docs/data-sources.md's "How to extract" notes.

Repo layout (see the repo's README "Data Files" section):
  stats/tournaments/tournaments_index.json      one entry per scraped tournament
  stats/tournaments/{tournament_id}/metadata.json   event name/date/location/type
  stats/tournaments/{tournament_id}/players.json    list of {name, country,
      placement, team: [{pokemon, item, ability, tera_type, nature, moves}, ...],
      day_reached, team_link, record}

MunchStats doesn't expose an opaque per-player ID or a separately reported
form label (forms like "Urshifu-Rapid-Strike" are embedded in `pokemon`
name) — both are known risks called out in the schema contract. `player_id`
is derived from a hash of the player's name and country; `form_name` is
left blank pending normalization. `player_name` and `player_country` (a
two-letter code, e.g. "IT", "ES") are captured as their own columns
alongside `player_id` — real, sourced fields, not fabricated.

`metadata.json`'s `type` (tournament tier, e.g. "International"/"Regional"),
`players.json`'s `record` (win/loss count), and team-member `item`/
`ability`/`tera_type`/`nature`/`moves` are captured too, duplicated onto
every roster-slot row like `placement` already is; `moves` is a
pipe-delimited string since a roster slot can carry more than one.

Incremental extraction (backlog.md #44): a concluded tournament's
`players.json` (the bulk of every run's ~106k rows) never changes once
published, so re-downloading every tournament's full roster data on every
scheduled run is pure waste. `extract`'s `previous_snapshot_path` lets the
caller pass the most recent prior dated snapshot (see
`pipelines.cli._latest_snapshot_path`); for each tournament, the cheap
`metadata.json` is still always re-fetched (so a genuine change is never
missed), and the heavier `players.json` fetch is skipped in favor of the
cached rows only when that tournament's `(name, date, type)` signature is
unchanged from what's already cached -- mirroring
`pipelines/extract/bulbagarden.py`'s sha1-based `skip_existing` pattern
(fetch a cheap signal first, skip the expensive download only when it
still matches). Reused rows are still re-stamped with this run's
`extracted_at_utc`/`dataset_version`, the same "every row reflects this
extraction run" convention `bulbagarden.py`'s `extract()` already
establishes for its own skipped-download rows.

`tournaments_index.json` in production actually lists both Pokémon VGC
events and same-venue Pokémon TCG events side by side (discovered while
verifying this against the real live source, not anticipated up front) --
a TCG tournament's `players.json` reports players but every player's
`team` is empty, since TCG doesn't have a "Pokémon team" in this dataset's
sense, so it always contributes zero roster rows. Those TCG tournaments
can never satisfy the cache-hit check above (a zero-row tournament is
never actually written to the CSV, so it's never present in
`cached_rows_by_tournament` to compare against), which would otherwise
mean re-fetching their `players.json` on *every* run forever regardless of
caching. `metadata.json`'s own `teams_scraped` count avoids that
unconditionally, with no cache needed at all: `teams_scraped: 0` means
skip straight to an empty row list without ever fetching `players.json`,
on the very first extraction as much as the hundredth.
"""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import requests

from pipelines.extract.http import get_with_retry

SOURCE_NAME = "MunchStats"
RAW_BASE_URL = "https://raw.githubusercontent.com/PizzaTimeJoshua/munchstats/main"
TOURNAMENTS_INDEX_URL = f"{RAW_BASE_URL}/stats/tournaments/tournaments_index.json"
DEFAULT_DATASET_VERSION = "0.0.0-dev"

FIELDNAMES = [
    "event_id",
    "event_name",
    "event_date",
    "event_tier",
    "event_format",
    "team_id",
    "player_id",
    "player_name",
    "player_country",
    "placement",
    "record_wins",
    "record_losses",
    "slot_number",
    "pokemon_name",
    "form_name",
    "item_name",
    "ability",
    "tera_type",
    "nature",
    "moves",
    "source_name",
    "source_url",
    "source_record_id",
    "extracted_at_utc",
    "dataset_version",
]


def _tournament_dir_url(tournament_id: str) -> str:
    return f"{RAW_BASE_URL}/stats/tournaments/{tournament_id}"


def _fetch_json(session: requests.Session, url: str):
    response = get_with_retry(session, url, timeout=30)
    return response.json()


def _team_id(player: dict, tournament_id: str) -> str:
    team_link = player.get("team_link") or ""
    if team_link:
        return team_link.rstrip("/").rsplit("/", 1)[-1]
    return f"{tournament_id}:{player['name']}"


def _player_id(player: dict) -> str:
    basis = f"{player['name']}|{player.get('country', '')}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def _load_cached_rows_by_tournament(previous_snapshot_path: Path | None) -> dict[str, list[dict]]:
    """Group the prior dated snapshot's rows by event_id (tournament_id),
    so a tournament whose metadata hasn't changed can reuse its cached
    roster rows instead of re-fetching players.json."""
    if previous_snapshot_path is None or not previous_snapshot_path.exists():
        return {}
    cached: dict[str, list[dict]] = {}
    with previous_snapshot_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            cached.setdefault(row["event_id"], []).append(row)
    return cached


# Days after an event's (start) date during which its rosters and pairings
# are still re-fetched every run: a Regional runs Friday to Sunday, and the
# sources finish publishing a day or so after.
LIVE_DAYS = 3


def is_live(event_date: str | None, today: date | None = None) -> bool:
    """Whether an event dated `event_date` (ISO) is running or just over:
    from the day before it to LIVE_DAYS after."""
    if not event_date:
        return False
    try:
        day = date.fromisoformat(str(event_date)[:10])
    except ValueError:
        return False
    today = today or datetime.now(UTC).date()
    return day - timedelta(days=1) <= today <= day + timedelta(days=LIVE_DAYS)


def _metadata_signature(metadata: dict) -> tuple[str, str, str, str]:
    return (
        metadata["name"],
        metadata["date"],
        metadata.get("type", ""),
        metadata.get("format", ""),
    )


def _cached_metadata_signature(cached_rows: list[dict]) -> tuple[str, str, str, str] | None:
    """The cached counterpart of _metadata_signature. `event_format` is read
    with a default because a snapshot written before that column existed
    simply has no such key: such a row yields "" here, which cannot match a
    real format, so the tournament is re-fetched and backfilled rather than
    being reused with a silently blank format."""
    if not cached_rows:
        return None
    first = cached_rows[0]
    return (
        first.get("event_name", ""),
        first.get("event_date", ""),
        first.get("event_tier", ""),
        first.get("event_format", ""),
    )


def _rows_for_tournament(
    session: requests.Session,
    tournament_id: str,
    *,
    extracted_at_utc: str,
    dataset_version: str,
    cached_rows_by_tournament: dict[str, list[dict]],
) -> list[dict]:
    metadata = _fetch_json(session, f"{_tournament_dir_url(tournament_id)}/metadata.json")
    # metadata.json's own `teams_scraped` count tells us upfront, with no
    # players.json fetch at all, whether this tournament has any roster
    # data to contribute. MunchStats' index carries both VGC events (which
    # populate `team`) and same-venue TCG events (teams_scraped: 0 --
    # TCG has no "Pokémon team" in this dataset's sense, so every player's
    # `team` list is always empty) under the same index/metadata/players.json
    # shape; a TCG tournament's metadata never changes once published any
    # more than a VGC one's does, so this check is unconditional -- it
    # saves the always-wasted fetch on every run, not just a cached one.
    if metadata.get("teams_scraped", 0) == 0:
        return []

    cached_rows = cached_rows_by_tournament.get(tournament_id)
    # A tournament still running (or just finished) keeps adding teams under
    # the same metadata, so within LIVE_DAYS of its date it is fetched again
    # every run (docs/upgrade-plan-2027q2.md, E4) rather than reused.
    if (
        cached_rows
        and not is_live(metadata.get("date"))
        and _cached_metadata_signature(cached_rows) == _metadata_signature(metadata)
    ):
        return [
            {**row, "extracted_at_utc": extracted_at_utc, "dataset_version": dataset_version}
            for row in cached_rows
        ]

    players = _fetch_json(session, f"{_tournament_dir_url(tournament_id)}/players.json")
    players_url = f"{_tournament_dir_url(tournament_id)}/players.json"

    rows = []
    for player in players:
        team_id = _team_id(player, tournament_id)
        player_id = _player_id(player)
        record = player.get("record") or {}
        for slot_number, member in enumerate(player.get("team", []), start=1):
            rows.append(
                {
                    "event_id": tournament_id,
                    "event_name": metadata["name"],
                    "event_date": metadata["date"],
                    "event_tier": metadata.get("type", ""),
                    "event_format": metadata.get("format", ""),
                    "team_id": team_id,
                    "player_id": player_id,
                    "player_name": player.get("name", ""),
                    "player_country": player.get("country", ""),
                    "placement": player["placement"],
                    "record_wins": record.get("wins", ""),
                    "record_losses": record.get("losses", ""),
                    "slot_number": slot_number,
                    "pokemon_name": member["pokemon"],
                    "form_name": "",
                    "item_name": member.get("item", ""),
                    "ability": member.get("ability", ""),
                    "tera_type": member.get("tera_type", ""),
                    "nature": member.get("nature", ""),
                    "moves": "|".join(member.get("moves", [])),
                    "source_name": SOURCE_NAME,
                    "source_url": players_url,
                    "source_record_id": f"{tournament_id}:{team_id}:{slot_number}",
                    "extracted_at_utc": extracted_at_utc,
                    "dataset_version": dataset_version,
                }
            )
    return rows


def extract(
    output_path: Path,
    tournament_ids: Iterable[str] | None = None,
    *,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    session: requests.Session | None = None,
    previous_snapshot_path: Path | None = None,
) -> None:
    """Fetch MunchStats tournament/team/roster JSON, flatten nested team
    arrays into one row per team member, and write to output_path as CSV
    matching the field list in data/staging/munchstats.schema.json,
    including provenance fields.

    `tournament_ids` defaults to every tournament in
    stats/tournaments/tournaments_index.json; pass an explicit iterable to
    scope the extract to specific events.

    `previous_snapshot_path`, if given, enables incremental extraction
    (backlog.md #44): a tournament whose freshly-fetched metadata.json
    signature matches what's already cached from that prior snapshot
    reuses its cached roster rows instead of re-fetching players.json.
    """
    http = session if session is not None else requests.Session()
    ids = (
        tournament_ids
        if tournament_ids is not None
        else [entry["id"] for entry in _fetch_json(http, TOURNAMENTS_INDEX_URL)]
    )
    extracted_at_utc = datetime.now(UTC).isoformat()
    cached_rows_by_tournament = _load_cached_rows_by_tournament(previous_snapshot_path)

    rows = []
    for tournament_id in ids:
        rows.extend(
            _rows_for_tournament(
                http,
                tournament_id,
                extracted_at_utc=extracted_at_utc,
                dataset_version=dataset_version,
                cached_rows_by_tournament=cached_rows_by_tournament,
            )
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
