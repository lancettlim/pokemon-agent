"""Limitless online tournaments (play.limitlesstcg.com) extraction.

Contracts: data/staging/limitless_play.schema.json (one row per team-sheet
slot) and data/staging/limitless_play_pairings.schema.json (one row per
pairing).
Spec reference: docs/dataset-spec.md, "Added sources > Limitless online
tournaments"; docs/upgrade-plan-2027q2.md, S1 (decision D1).

Hundreds of grassroots Champions events run on Limitless' online tournament
platform every regulation, each with full team sheets (item, ability,
Stat Alignment, moves), W-L-T records, drops and round-by-round pairings.
They are a different population from the official events MunchStats and RK9
cover, and they land as their own `event_tier = 'online'` scope that the
dashboard never blends into the official default. What they buy: about
three times the official sample, and data for a new regulation within days
of its start, weeks before the first Regional reports.

The platform has a public JSON API (docs.limitlesstcg.com/developer.html),
so this is four plain GETs, no scraping:

  - `GET /api/tournaments?game=VGC&limit=500&page=N` lists tournaments,
    newest first, with id, name, date, `format` ("M-C") and player count.
  - `GET /api/tournaments/<id>/standings` is every player with placing,
    record, drop and, when the organiser publishes lists, the team sheet.
  - `GET /api/tournaments/<id>/pairings` is every round's pairings and
    winners (Swiss and top cut, told apart by `phase`).

Which formats count is the regulation registry's
(dbt/seeds/champions_regulations.csv, `limitless_play_format`); nothing here
hardcodes "M-C". Two filters keep the sample comparable: events under
MIN_PLAYERS (16) are skipped, as are Monotype events (MONOTYPE_PATTERN),
which run under house rules on top of the format and would skew usage.

The API allows 50 requests per 5 minutes without a key. Every request goes
through one sliding-window limiter, so a first backfill of a regulation's
~300 qualifying events (two requests each) takes about an hour. After that
it is incremental: a tournament the previous snapshot holds in a copy
fetched at least REFRESH_DAYS after its date (fetched_at_utc) is reused
rather than fetched, and tournaments the previous snapshot holds are kept
even after they leave the lookback window, so history accumulates across
regulations. By default the lookback is the regulation in force plus the
last REFRESH_DAYS + 1 days, so a rollover doesn't strand the outgoing
regulation's final events. A key (LIMITLESS_API_KEY, sent as X-Access-Key)
raises the limit for public-facing projects.

Players are identified by their Limitless handle, which is not a legal
name: online teams never join RK9 or MunchStats identities, and the
dashboard gives them no player pages.

Upcoming tournaments (docs/upgrade-plan-2027q2.md, list #31; contract
data/staging/limitless_play_upcoming.schema.json) are not in the API, which
lists tournaments once they start. extract_upcoming reads the platform's
upcoming page instead, `GET /tournaments/upcoming?game=VGC&format=<label>`,
one request per regulation in force or registered to start within
UPCOMING_DAYS. Its table carries each row's start time, name, organiser,
platform and registration count as `data-*` attributes, so no layout
parsing is needed beyond them and two links (the tournament and organiser
ids). A page without the table raises rather than reporting no events.
"""

from __future__ import annotations

import csv
import html
import os
import re
import time
from collections import deque
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import requests

from pipelines.extract.http import get_with_retry
from pipelines.regulations import Regulation, load_regulations

SOURCE_NAME = "Limitless Online"
BASE_URL = "https://play.limitlesstcg.com"
API_URL = f"{BASE_URL}/api"
DEFAULT_DATASET_VERSION = "0.0.0-dev"
GAME = "VGC"
PAGE_SIZE = 500
MAX_PAGES = 40
MIN_PLAYERS = 16
MONOTYPE_PATTERN = re.compile(r"mono\s*-?\s*type", re.IGNORECASE)
# A tournament is reused from the previous snapshot only once it is this
# old: standings and pairings can still change while one runs.
REFRESH_DAYS = 2
# The API's unauthenticated limit: 50 requests per 5 minutes.
REQUESTS_PER_WINDOW = 50
WINDOW_SECONDS = 300.0
RATE_LIMIT_RETRIES = 3

FIELDNAMES = [
    "tournament_id",
    "tournament_name",
    "tournament_date",
    "tournament_format",
    "player_count",
    "organizer_id",
    "player_handle",
    "player_name",
    "player_country",
    "placement",
    "record_wins",
    "record_losses",
    "record_ties",
    "dropped",
    "slot_number",
    "pokemon_slug",
    "pokemon_display_name",
    "item_name",
    "ability",
    "nature",
    "tera_type",
    "moves",
    "fetched_at_utc",
    "source_name",
    "source_url",
    "source_record_id",
    "extracted_at_utc",
    "dataset_version",
]

PAIRING_FIELDNAMES = [
    "tournament_id",
    "phase",
    "round_number",
    "table_number",
    "player1_handle",
    "player2_handle",
    "winner_handle",
    "fetched_at_utc",
    "source_name",
    "source_url",
    "source_record_id",
    "extracted_at_utc",
    "dataset_version",
]


UPCOMING_FIELDNAMES = [
    "tournament_id",
    "tournament_name",
    "tournament_format",
    "regulation_code",
    "starts_at_utc",
    "platform",
    "organizer_id",
    "organizer_name",
    "registrations",
    "player_cap",
    "registration_open",
    "source_name",
    "source_url",
    "source_record_id",
    "extracted_at_utc",
    "dataset_version",
]
# A regulation registered to start within this many days has its upcoming
# events listed too, so a rollover's first weekend shows before it begins.
UPCOMING_DAYS = 30
_UPCOMING_TABLE = re.compile(r'<table[^>]*class="[^"]*upcoming-tournaments', re.IGNORECASE)
_UPCOMING_ROW = re.compile(r"<tr\s+([^>]*data-date=[^>]*)>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_ATTRIBUTE = re.compile(r'data-([a-z-]+)="([^"]*)"')
_TOURNAMENT_LINK = re.compile(r'href="/tournament/([0-9a-f]+)/')
_ORGANIZER_LINK = re.compile(r'href="/organizer/(\d+)"')
_CAP = re.compile(r">\s*\d+\s*/\s*(\d+)")


class RateLimiter:
    """A sliding window: at most `limit` calls in any `window` seconds. The
    clock and sleep are injectable so tests don't wait."""

    def __init__(self, limit: int, window: float, *, clock=time.monotonic, sleep=time.sleep):
        self.limit = limit
        self.window = window
        self.clock = clock
        self.sleep = sleep
        self.calls: deque[float] = deque()

    def wait(self) -> None:
        now = self.clock()
        while self.calls and now - self.calls[0] >= self.window:
            self.calls.popleft()
        if len(self.calls) >= self.limit:
            self.sleep(self.window - (now - self.calls[0]) + 0.05)
            now = self.clock()
            while self.calls and now - self.calls[0] >= self.window:
                self.calls.popleft()
        self.calls.append(now)


# One limiter per process: the roster and pairings passes share the budget.
_limiter = RateLimiter(
    int(os.environ.get("LIMITLESS_PLAY_REQUESTS_PER_WINDOW", REQUESTS_PER_WINDOW)), WINDOW_SECONDS
)


def _headers() -> dict[str, str]:
    key = os.environ.get("LIMITLESS_API_KEY")
    return {"X-Access-Key": key} if key else {}


def _get_json(session: requests.Session, path: str, params: dict | None = None, *, limiter=None):
    """One API call through the shared limiter. A 429 (the window counted
    differently from ours, or another client shares the address) waits out
    Retry-After, or a whole window when the server gives none, and retries
    up to RATE_LIMIT_RETRIES times rather than failing an hour-long
    backfill."""
    limiter = limiter or _limiter

    def wait_out(response: requests.Response) -> None:
        retry_after = str(response.headers.get("Retry-After") or "")
        limiter.sleep(float(retry_after) if retry_after.isdigit() else limiter.window)

    limiter.wait()
    response = get_with_retry(
        session,
        f"{API_URL}{path}",
        params=params,
        headers=_headers(),
        timeout=60,
        attempts=RATE_LIMIT_RETRIES + 1,
        on_rate_limited=wait_out,
    )
    return response.json()


def tournament_url(tournament_id: str) -> str:
    return f"{BASE_URL}/tournament/{tournament_id}/standings"


def _tournament_date(value: str | None) -> str:
    return (value or "")[:10]


def format_regulations(regulations: Iterable[Regulation]) -> dict[str, Regulation]:
    """Limitless' format label ("M-C") -> its regulation, case-insensitive."""
    return {r.limitless_play_format.upper(): r for r in regulations if r.limitless_play_format}


def qualifies(tournament: dict, formats: dict[str, Regulation], *, min_players: int) -> bool:
    """Whether a listed tournament belongs in the online scope: a registered
    Champions format, at least min_players players, not a Monotype event,
    and already started."""
    if str(tournament.get("format") or "").upper() not in formats:
        return False
    if (tournament.get("players") or 0) < min_players:
        return False
    if MONOTYPE_PATTERN.search(tournament.get("name") or ""):
        return False
    return _tournament_date(tournament.get("date")) <= datetime.now(UTC).date().isoformat()


def list_tournaments(
    session: requests.Session,
    *,
    since: date,
    formats: dict[str, Regulation],
    min_players: int = MIN_PLAYERS,
    limiter=None,
) -> list[dict]:
    """Every qualifying VGC tournament dated on or after `since`, newest
    first, paging until the listing passes `since`."""
    found: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        batch = _get_json(
            session,
            "/tournaments",
            {"game": GAME, "limit": PAGE_SIZE, "page": page},
            limiter=limiter,
        )
        if not batch:
            break
        for tournament in batch:
            if _tournament_date(tournament.get("date")) < since.isoformat():
                continue
            if qualifies(tournament, formats, min_players=min_players):
                found.append(tournament)
        oldest = min(_tournament_date(t.get("date")) for t in batch)
        if oldest < since.isoformat() or len(batch) < PAGE_SIZE:
            break
    return found


def team_rows(
    tournament: dict, standings: list[dict], *, extracted_at_utc: str, dataset_version: str
) -> list[dict]:
    """One row per team-sheet slot. A player whose list the organiser didn't
    publish contributes no rows (their pairings still record results)."""
    rows: list[dict] = []
    tournament_id = tournament["id"]
    for player in standings:
        decklist = player.get("decklist") or []
        handle = player.get("player") or ""
        if not handle or not isinstance(decklist, list):
            continue
        record = player.get("record") or {}
        for slot_number, mon in enumerate(decklist, start=1):
            if not isinstance(mon, dict) or not mon.get("id"):
                continue
            rows.append(
                {
                    "tournament_id": tournament_id,
                    "tournament_name": tournament.get("name"),
                    "tournament_date": _tournament_date(tournament.get("date")),
                    "tournament_format": tournament.get("format"),
                    "player_count": tournament.get("players"),
                    "organizer_id": tournament.get("organizerId"),
                    "player_handle": handle,
                    "player_name": player.get("name") or handle,
                    "player_country": player.get("country") or "",
                    "placement": player.get("placing") or "",
                    "record_wins": record.get("wins", ""),
                    "record_losses": record.get("losses", ""),
                    "record_ties": record.get("ties", ""),
                    "dropped": "true" if player.get("drop") else "false",
                    "slot_number": slot_number,
                    "pokemon_slug": mon["id"],
                    "pokemon_display_name": mon.get("name") or "",
                    "item_name": mon.get("item") or "",
                    "ability": mon.get("ability") or "",
                    "nature": mon.get("nature") or "",
                    "tera_type": mon.get("tera") or "",
                    "moves": "|".join(m for m in (mon.get("attacks") or []) if m),
                    "fetched_at_utc": extracted_at_utc,
                    "source_name": SOURCE_NAME,
                    "source_url": tournament_url(tournament_id),
                    "source_record_id": f"{tournament_id}:{handle}:{slot_number}",
                    "extracted_at_utc": extracted_at_utc,
                    "dataset_version": dataset_version,
                }
            )
    return rows


def pairing_rows(
    tournament_id: str, pairings: list[dict], *, extracted_at_utc: str, dataset_version: str
) -> list[dict]:
    """One row per pairing, the winner as the API reports it: a handle, "0"
    for a tie, "-1" for no result. A pairing with no second player is a
    bye."""
    rows = []
    for index, pairing in enumerate(pairings):
        if not pairing.get("player1"):
            continue
        winner = pairing.get("winner")
        rows.append(
            {
                "tournament_id": tournament_id,
                "phase": pairing.get("phase") or 1,
                "round_number": pairing.get("round") or "",
                "table_number": pairing.get("table") if pairing.get("table") is not None else "",
                "player1_handle": pairing["player1"],
                "player2_handle": pairing.get("player2") or "",
                "winner_handle": "" if winner is None else str(winner),
                "fetched_at_utc": extracted_at_utc,
                "source_name": SOURCE_NAME,
                "source_url": f"{BASE_URL}/tournament/{tournament_id}/pairings",
                "source_record_id": f"{tournament_id}:{pairing.get('phase') or 1}:"
                f"{pairing.get('round')}:{index}",
                "extracted_at_utc": extracted_at_utc,
                "dataset_version": dataset_version,
            }
        )
    return rows


def _load_rows(path: Path | None) -> dict[str, list[dict]]:
    if path is None or not path.exists():
        return {}
    cached: dict[str, list[dict]] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            cached.setdefault(row["tournament_id"], []).append(row)
    return cached


def _restamp(rows: list[dict], extracted_at_utc: str, dataset_version: str) -> list[dict]:
    return [
        {**row, "extracted_at_utc": extracted_at_utc, "dataset_version": dataset_version}
        for row in rows
    ]


def _write(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _regulation_in_force(regulations: list[Regulation], today: date) -> Regulation | None:
    """The regulation whose window holds `today`, else the latest that has
    started (the next set isn't registered yet)."""
    started = [r for r in regulations if r.start_date <= today]
    for regulation in regulations:
        if regulation.start_date <= today < regulation.end_date:
            return regulation
    return started[-1] if started else None


def _is_final(rows: list[dict] | None, tournament_date: str) -> bool:
    """Whether a cached copy of a tournament was fetched once it had
    settled, REFRESH_DAYS after its date: only then is it reused instead of
    re-fetched. Judging by the tournament's age alone would keep a copy
    fetched mid-event forever. A copy without fetched_at_utc (written
    before the column existed) is fetched again once."""
    fetched = str(rows[0].get("fetched_at_utc") or "")[:10] if rows else ""
    if not fetched or not tournament_date:
        return False
    settled_on = (date.fromisoformat(tournament_date) + timedelta(days=REFRESH_DAYS)).isoformat()
    return fetched >= settled_on


def extract(
    output_path: Path,
    *,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    session: requests.Session | None = None,
    previous_snapshot_path: Path | None = None,
    regulations: list[Regulation] | None = None,
    today: date | None = None,
    min_players: int = MIN_PLAYERS,
    limiter=None,
    extracted_at_utc: str | None = None,
) -> list[dict]:
    """Write one row per team-sheet slot of every qualifying online
    tournament to output_path (data/staging/limitless_play.schema.json) and
    return the tournaments it covers, newest first, for extract_pairings.

    The lookback is the regulation in force on `today`, widened to the
    last REFRESH_DAYS + 1 days so a rollover doesn't strand the outgoing
    regulation's final events. Tournaments the previous snapshot holds are
    kept whatever their date, and reused rather than re-fetched once their
    cached copy is final (_is_final); a copy that isn't is fetched again by
    id, listed or not. `extracted_at_utc` lets the CLI stamp both passes
    with one time, so they share a snapshot date."""
    http = session if session is not None else requests.Session()
    regulations = load_regulations() if regulations is None else regulations
    today = today or datetime.now(UTC).date()
    formats = format_regulations(regulations)
    in_force = _regulation_in_force(regulations, today)
    recent = today - timedelta(days=REFRESH_DAYS + 1)
    since = min(in_force.start_date, recent) if in_force else today - timedelta(days=90)
    extracted_at_utc = extracted_at_utc or datetime.now(UTC).isoformat()

    listed = list_tournaments(
        http, since=since, formats=formats, min_players=min_players, limiter=limiter
    )
    cached = _load_rows(previous_snapshot_path)
    by_id: dict[str, dict] = {}
    for tournament_id, rows in cached.items():
        first = rows[0]
        if str(first.get("tournament_format") or "").upper() not in formats:
            continue
        by_id[tournament_id] = {
            "id": tournament_id,
            "name": first.get("tournament_name"),
            "date": first.get("tournament_date"),
            "format": first.get("tournament_format"),
            "players": int(first["player_count"]) if first.get("player_count") else None,
            "organizerId": first.get("organizer_id"),
        }
    for tournament in listed:
        by_id[tournament["id"]] = tournament

    rows: list[dict] = []
    covered: list[dict] = []
    for tournament in sorted(
        by_id.values(), key=lambda t: _tournament_date(t.get("date")), reverse=True
    ):
        tournament_id = tournament["id"]
        reuse = cached.get(tournament_id)
        if reuse and _is_final(reuse, _tournament_date(tournament.get("date"))):
            rows.extend(_restamp(reuse, extracted_at_utc, dataset_version))
            covered.append(tournament)
            continue
        standings = _get_json(http, f"/tournaments/{tournament_id}/standings", limiter=limiter)
        fresh = team_rows(
            tournament,
            standings or [],
            extracted_at_utc=extracted_at_utc,
            dataset_version=dataset_version,
        )
        if fresh:
            rows.extend(fresh)
            covered.append(tournament)
    _write(output_path, FIELDNAMES, rows)
    return covered


def extract_pairings(
    output_path: Path,
    tournaments: list[dict],
    *,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    session: requests.Session | None = None,
    previous_snapshot_path: Path | None = None,
    limiter=None,
    extracted_at_utc: str | None = None,
) -> None:
    """Write every pairing of `tournaments` (extract()'s return value) to
    output_path (data/staging/limitless_play_pairings.schema.json), reusing
    a tournament's pairings from the previous snapshot when that copy is
    final (_is_final)."""
    http = session if session is not None else requests.Session()
    extracted_at_utc = extracted_at_utc or datetime.now(UTC).isoformat()
    cached = _load_rows(previous_snapshot_path)
    rows: list[dict] = []
    for tournament in tournaments:
        tournament_id = tournament["id"]
        reuse = cached.get(tournament_id)
        if reuse and _is_final(reuse, _tournament_date(tournament.get("date"))):
            rows.extend(_restamp(reuse, extracted_at_utc, dataset_version))
            continue
        pairings = _get_json(http, f"/tournaments/{tournament_id}/pairings", limiter=limiter)
        rows.extend(
            pairing_rows(
                tournament_id,
                pairings or [],
                extracted_at_utc=extracted_at_utc,
                dataset_version=dataset_version,
            )
        )
    _write(output_path, PAIRING_FIELDNAMES, rows)


def upcoming_url(regulation: Regulation) -> str:
    return f"{BASE_URL}/tournaments/upcoming?game={GAME}&format={regulation.limitless_play_format}"


def parse_upcoming(
    page: str,
    regulation: Regulation,
    *,
    extracted_at_utc: str,
    dataset_version: str,
) -> list[dict]:
    """The upcoming page's rows for one regulation, as staging rows."""
    if not _UPCOMING_TABLE.search(page):
        raise ValueError(f"no upcoming-tournaments table at {upcoming_url(regulation)}")
    rows = []
    for attributes, body in _UPCOMING_ROW.findall(page):
        data = {key: html.unescape(value) for key, value in _ATTRIBUTE.findall(attributes)}
        tournament = _TOURNAMENT_LINK.search(body)
        if not tournament or not data.get("date"):
            continue
        tournament_id = tournament.group(1)
        organizer = _ORGANIZER_LINK.search(body)
        cap = _CAP.search(body)
        rows.append(
            {
                "tournament_id": tournament_id,
                "tournament_name": data.get("name", "").strip(),
                "tournament_format": regulation.limitless_play_format,
                "regulation_code": regulation.regulation_code,
                "starts_at_utc": data["date"],
                "platform": data.get("platform", ""),
                "organizer_id": organizer.group(1) if organizer else "",
                "organizer_name": data.get("organizer", "").strip(),
                "registrations": int(data["players"]) if data.get("players", "").isdigit() else "",
                "player_cap": int(cap.group(1)) if cap else "",
                "registration_open": 'class="register open"' in body,
                "source_name": SOURCE_NAME,
                "source_url": f"{BASE_URL}/tournament/{tournament_id}/details",
                "source_record_id": tournament_id,
                "extracted_at_utc": extracted_at_utc,
                "dataset_version": dataset_version,
            }
        )
    return rows


def upcoming_regulations(regulations: list[Regulation], today: date) -> list[Regulation]:
    """The regulation in force and any registered to start within
    UPCOMING_DAYS."""
    soon = today + timedelta(days=UPCOMING_DAYS)
    in_force = _regulation_in_force(regulations, today)
    return [r for r in regulations if r is in_force or (today < r.start_date <= soon)]


def extract_upcoming(
    output_path: Path,
    *,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    session: requests.Session | None = None,
    regulations: list[Regulation] | None = None,
    today: date | None = None,
    limiter=None,
    extracted_at_utc: str | None = None,
) -> int:
    """Write the upcoming online tournaments of the regulations
    upcoming_regulations picks (data/staging/limitless_play_upcoming
    .schema.json). Returns the number of rows."""
    http = session if session is not None else requests.Session()
    regulations = load_regulations() if regulations is None else regulations
    extracted_at = extracted_at_utc or datetime.now(UTC).isoformat()
    today = today or datetime.fromisoformat(extracted_at).date()
    limiter = limiter or _limiter
    rows: dict[str, dict] = {}
    for regulation in upcoming_regulations(regulations, today):
        limiter.wait()
        page = get_with_retry(http, upcoming_url(regulation), headers=_headers(), timeout=60).text
        for row in parse_upcoming(
            page, regulation, extracted_at_utc=extracted_at, dataset_version=dataset_version
        ):
            rows.setdefault(row["tournament_id"], row)
    ordered = sorted(rows.values(), key=lambda r: (r["starts_at_utc"], r["tournament_id"]))
    _write(output_path, UPCOMING_FIELDNAMES, ordered)
    return len(ordered)
