"""Limitless VGC extraction.

Contract: data/staging/limitless.schema.json
Spec reference: docs/dataset-spec.md, "Source-specific extraction contracts > Limitless VGC"

docs/data-sources.md used to describe extracting this source by "browser
table extraction tool (e.g. Table Capture extension)" and screenshotting
tables. That is not necessary and never was: limitlessvgc.com is
server-rendered, and every page this extractor needs is a plain HTTP GET
with the data already in the markup, much of it on `data-` attributes:

  - `GET /tournaments?time=all` lists every tournament as a `<tr>` carrying
    data-date/data-country/data-name/data-format/data-players/data-winner
    plus a `/tournaments/<id>` link. `data-format` is the regulation set
    ("m-a", "m-b", "m-c"), so Champions events are identifiable without
    fetching them.
  - `GET /tournaments/<id>` is the standings table: one `<tr>` per player
    with data-rank/data-name/data-country, a `/players/<id>` link, and --
    for players whose list was published -- a `/teams/<id>` link.
  - `GET /teams/<id>` is the team list itself: six `div.pkmn[data-id]`
    blocks with item, ability, nature and moves.

Why this source, given MunchStats already covers the same events: what
Limitless has that MunchStats does not is **shared team identity**. A
`/teams/<id>` is a canonical team composition reused across players and
events -- team 6449 is credited to both a Regional winner and a 23rd-place
NAIC finish -- whereas MunchStats mints a fresh per-player team_id every
time. That makes `team_list` a real entity this dataset otherwise lacks,
and gives an independent second reading of the same rosters to
cross-validate against (see dbt/models/marts/roster_source_agreement.sql).

What this source is NOT for, despite docs/data-sources.md's original
framing: extending tournament history. Limitless does not reach further
back than MunchStats for this format -- both sources list the same
Champions-format events (nine across M-A/M-B/M-C as of 2026-10-18). Its
other tournaments are standard VGC (regulations F/H/I), which is out of
scope per docs/prd.md. `format_filter` therefore defaults to Champions.

Team lists are fetched per distinct team id across the whole run, not per
player: the same team recurs across players and events, so deduplicating
first turns ~1,100 player rows per event into a few hundred fetches total.
Note `/tournaments/<id>/teams` renders many lists on one page, but only for
the day-2 cut (156 of 1,096 at NAIC), so it is not a substitute -- and it
omits the team ids that are this source's whole point.

Known risk, same posture as bulbagarden.py and rk9.py: Limitless'
rate-limiting/ToS stance for sustained scheduled access has not been
independently verified beyond confirming plain GETs work.
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
from pipelines.regulations import limitless_formats

SOURCE_NAME = "Limitless VGC"
BASE_URL = "https://limitlessvgc.com"
TOURNAMENTS_URL = f"{BASE_URL}/tournaments?time=all"
DEFAULT_DATASET_VERSION = "0.0.0-dev"

# Limitless' own slugs for the Champions regulation sets, as they appear in
# each tournament row's data-format attribute. Read from
# dbt/seeds/champions_regulations.csv; this used to be the single "m-a".
CHAMPIONS_FORMATS = limitless_formats()

_TOURNAMENT_ROW_PATTERN = re.compile(
    r"<tr\s+data-date=\"([^\"]*)\"\s+data-country=\"([^\"]*)\"\s*"
    r"data-name=\"([^\"]*)\"\s+data-format=\"([^\"]*)\"\s*"
    r"data-players=\"([^\"]*)\"\s+data-winner=\"([^\"]*)\"\s*>(.*?)</tr>",
    re.DOTALL,
)
_TOURNAMENT_LINK_PATTERN = re.compile(r'href="/tournaments/(\d+)"')

_STANDINGS_ROW_PATTERN = re.compile(
    r"<tr\s+data-rank=\"([^\"]*)\"\s+data-name=\"([^\"]*)\"\s+data-country=\"([^\"]*)\"[^>]*>(.*?)</tr>",
    re.DOTALL,
)
_PLAYER_LINK_PATTERN = re.compile(r'href="/players/(\d+)"')
_TEAM_LINK_PATTERN = re.compile(r'href="/teams/(\d+)"')
# Each tournament page links out to the same event on RK9, which is the id
# MunchStats uses too -- a real, sourced join key between this source and
# tournament_event, instead of guessing at one from names or dates (the two
# sources agree on neither: "NAIC 2026, New Orleans" vs "2026 North America
# Pokémon VGC International Championships", dated a day apart).
_RK9_EVENT_PATTERN = re.compile(r'href="https://rk9\.gg/(?:pairings|roster)/([A-Za-z0-9]+)"')

_PKMN_BLOCK_PATTERN = re.compile(
    r'<div class="pkmn" data-id="([^"]*)"\s*>(.*?)<ul class="moves">(.*?)</ul>', re.DOTALL
)
_NAME_PATTERN = re.compile(r'<div class="name">\s*<a[^>]*>(.*?)</a>', re.DOTALL)
_ITEM_PATTERN = re.compile(r'<div class="item">(.*?)</div>', re.DOTALL)
_ABILITY_PATTERN = re.compile(r'<div class="ability">\s*Ability:\s*(.*?)</div>', re.DOTALL)
_NATURE_PATTERN = re.compile(r'<div class="nature">\s*(.*?)\s+Nature\s*</div>', re.DOTALL)
_MOVE_PATTERN = re.compile(r"<li>(.*?)</li>", re.DOTALL)
_TAG_PATTERN = re.compile(r"<[^>]+>")

FIELDNAMES = [
    "limitless_team_id",
    "tournament_id",
    "rk9_event_id",
    "tournament_name",
    "tournament_date",
    "regulation_set",
    "placement",
    "player_name",
    "player_country",
    "limitless_player_id",
    "slot_number",
    "pokemon_slug",
    "pokemon_display_name",
    "item_name",
    "ability",
    "nature",
    "moves",
    "source_name",
    "source_url",
    "source_record_id",
    "extracted_at_utc",
    "dataset_version",
]


def _text(fragment: str) -> str:
    return " ".join(html.unescape(_TAG_PATTERN.sub(" ", fragment)).split())


def _fetch_text(session: requests.Session, url: str) -> str:
    return get_with_retry(session, url, timeout=30).text


def _parse_tournaments(listing_html: str) -> list[dict]:
    tournaments = []
    for (
        date,
        country,
        name,
        regulation_set,
        players,
        winner,
        body,
    ) in _TOURNAMENT_ROW_PATTERN.findall(listing_html):
        link = _TOURNAMENT_LINK_PATTERN.search(body)
        if link is None:
            continue
        tournaments.append(
            {
                "tournament_id": link.group(1),
                "tournament_date": date,
                "tournament_country": html.unescape(country),
                "tournament_name": html.unescape(name),
                "regulation_set": regulation_set,
                "players": players,
                "winner": html.unescape(winner),
            }
        )
    return tournaments


def _parse_standings(standings_html: str) -> list[dict]:
    """One entry per player in the standings table. A player whose list was
    never published has no /teams/ link; they're returned with an empty
    team id so the caller can count them rather than silently lose them."""
    standings = []
    for rank, name, country, body in _STANDINGS_ROW_PATTERN.findall(standings_html):
        player_link = _PLAYER_LINK_PATTERN.search(body)
        team_link = _TEAM_LINK_PATTERN.search(body)
        standings.append(
            {
                "placement": rank,
                "player_name": html.unescape(name),
                "player_country": country.upper(),
                "limitless_player_id": player_link.group(1) if player_link else "",
                "limitless_team_id": team_link.group(1) if team_link else "",
            }
        )
    return standings


def _held_item(raw: str) -> str:
    """Normalize the held-item cell. Limitless renders a bare "Held Item:"
    label when a Pokémon carries nothing at all -- a real and deliberate
    build choice, not missing data (an item-less Talonflame is how
    Acrobatics gets its doubled power). That placeholder becomes an empty
    item rather than being stored as if it were an item named "Held Item:"."""
    text = _text(raw)
    return "" if text.rstrip().endswith(":") else text


def _parse_team_list(team_html: str) -> list[dict]:
    """Six slots per team: species slug plus item/ability/nature/moves.
    Any of item/ability/nature can be absent from a published list, so each
    is optional and blank rather than assumed."""
    slots = []
    for slot_number, (slug, details, moves_block) in enumerate(
        _PKMN_BLOCK_PATTERN.findall(team_html), start=1
    ):
        name_match = _NAME_PATTERN.search(details)
        item_match = _ITEM_PATTERN.search(details)
        ability_match = _ABILITY_PATTERN.search(details)
        nature_match = _NATURE_PATTERN.search(details)
        slots.append(
            {
                "slot_number": slot_number,
                "pokemon_slug": slug,
                "pokemon_display_name": _text(name_match.group(1)) if name_match else "",
                "item_name": _held_item(item_match.group(1)) if item_match else "",
                "ability": _text(ability_match.group(1)) if ability_match else "",
                "nature": _text(nature_match.group(1)) if nature_match else "",
                "moves": "|".join(_text(move) for move in _MOVE_PATTERN.findall(moves_block)),
            }
        )
    return slots


def _team_url(team_id: str) -> str:
    return f"{BASE_URL}/teams/{team_id}"


def extract(
    output_path: Path,
    tournament_ids: Iterable[str] | None = None,
    *,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    session: requests.Session | None = None,
    format_filter: Collection[str] | None = CHAMPIONS_FORMATS,
) -> None:
    """Fetch Limitless tournaments, standings and team lists, and write one
    row per (team, tournament, player, roster slot) to output_path as CSV
    matching data/staging/limitless.schema.json, including provenance
    fields.

    `tournament_ids` defaults to every Champions-format tournament in the
    site's own listing; pass an explicit iterable to scope the run, or
    `format_filter=None` to take every listed tournament regardless of
    regulation set.
    """
    http = session if session is not None else requests.Session()
    tournaments = _parse_tournaments(_fetch_text(http, TOURNAMENTS_URL))
    if tournament_ids is not None:
        wanted = set(tournament_ids)
        tournaments = [t for t in tournaments if t["tournament_id"] in wanted]
    elif format_filter is not None:
        tournaments = [t for t in tournaments if t["regulation_set"] in format_filter]

    extracted_at_utc = datetime.now(UTC).isoformat()

    # (tournament, standings entry) pairs first, so team lists can be
    # fetched once per distinct team rather than once per player.
    entries: list[tuple[dict, dict]] = []
    for tournament in tournaments:
        standings_url = f"{BASE_URL}/tournaments/{tournament['tournament_id']}"
        standings_html = _fetch_text(http, standings_url)
        rk9_match = _RK9_EVENT_PATTERN.search(standings_html)
        tournament["rk9_event_id"] = rk9_match.group(1) if rk9_match else ""
        for entry in _parse_standings(standings_html):
            if entry["limitless_team_id"]:
                entries.append((tournament, entry))

    slots_by_team: dict[str, list[dict]] = {}
    for _, entry in entries:
        team_id = entry["limitless_team_id"]
        if team_id not in slots_by_team:
            slots_by_team[team_id] = _parse_team_list(_fetch_text(http, _team_url(team_id)))

    rows = []
    for tournament, entry in entries:
        team_id = entry["limitless_team_id"]
        for slot in slots_by_team.get(team_id, []):
            rows.append(
                {
                    "limitless_team_id": team_id,
                    "tournament_id": tournament["tournament_id"],
                    "rk9_event_id": tournament["rk9_event_id"],
                    "tournament_name": tournament["tournament_name"],
                    "tournament_date": tournament["tournament_date"],
                    "regulation_set": tournament["regulation_set"],
                    "placement": entry["placement"],
                    "player_name": entry["player_name"],
                    "player_country": entry["player_country"],
                    "limitless_player_id": entry["limitless_player_id"],
                    "slot_number": slot["slot_number"],
                    "pokemon_slug": slot["pokemon_slug"],
                    "pokemon_display_name": slot["pokemon_display_name"],
                    "item_name": slot["item_name"],
                    "ability": slot["ability"],
                    "nature": slot["nature"],
                    "moves": slot["moves"],
                    "source_name": SOURCE_NAME,
                    "source_url": _team_url(team_id),
                    "source_record_id": (
                        f"{tournament['tournament_id']}:{team_id}:"
                        f"{entry['limitless_player_id'] or entry['player_name']}:"
                        f"{slot['slot_number']}"
                    ),
                    "extracted_at_utc": extracted_at_utc,
                    "dataset_version": dataset_version,
                }
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
