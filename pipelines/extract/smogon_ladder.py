"""Smogon's monthly Pokémon Showdown ladder statistics (smogon.com/stats).

Contracts: data/staging/smogon_ladder.schema.json (usage, one row per
Pokémon per file), data/staging/smogon_ladder_counters.schema.json (checks
and counters) and data/staging/smogon_ladder_spreads.schema.json (Stat
Point spreads).
Spec reference: docs/dataset-spec.md, "Added sources > Smogon ladder
statistics"; docs/upgrade-plan-2027q2.md, S2 (decisions D2 and D3).

Smogon publishes, once a month, usage statistics for every Showdown ladder,
computed from every rated battle: September 2026's Reg M-C file covers
1,631,943 battles and 277 Pokémon. Each "chaos" JSON file gives, per
Pokémon, its weighted usage (a share of teams, comparable with tournament
team share), and from the battle logs themselves its Checks and Counters:
for each opponent, how often the pair met and how often this Pokémon was
KO'd or forced out. That is the only Pokémon-vs-Pokémon battle signal any
source publishes; tournament data is team vs team. The files also carry
the Stat Point spreads players ran, which tournament team sheets never
publish.

It is a different population from tournament players (anyone on the
ladder, weighted by rating), so it lands as its own `ladder` lens that is
never blended into tournament figures.

  - `GET /stats/` lists the months; `GET /stats/<YYYY-MM>/chaos/` the files.
  - A file is `<metagame>[bo3]-<cutoff>.json`. The metagame slug is the
    regulation registry's `munchstats_format` ("gen9championsvgc2026regmc",
    the name Showdown and MunchStats share); nothing here hardcodes it.
  - CUTOFFS are the rating floors kept: 1760 (the strongest players) and 0
    (everyone). VARIANTS are Bo1 and Bo3.

For each registered regulation the month kept is the newest one Smogon has
its file for in which the regulation was in force for at least half the
month (pick_month): August 2026 for M-B, which ended on 9 September, so its
September file is mostly play from after M-C began; September for M-C,
which started on the 9th. A regulation with no such month yet (its first,
partial month) takes its newest month with a file instead. A published
month never changes, so a file the previous snapshots already hold is
reused rather than downloaded again (each is 3-16MB).

Checks and Counters come from the all-ratings (cutoff 0) files. Smogon
lists a pair only above about 20 encounters, a doubles battle rarely
reaches the one-on-one moments the statistic counts, and at 1760 each
encounter is weighted by the chance its players are rated that high, so
the 1760 files carry almost none (13 pairs in September 2026's M-C file,
against 35,013 at cutoff 0). The extractor keeps each file's pairs met at
least MIN_COUNTER_ENCOUNTERS times; ladder_checks_counters reads cutoff 0.

Credit: Smogon University and Pokémon Showdown (smogon.com/stats).
"""

from __future__ import annotations

import calendar
import csv
import re
from datetime import UTC, date, datetime
from pathlib import Path

import requests

from pipelines.extract.http import get_with_retry
from pipelines.regulations import Regulation, load_regulations

SOURCE_NAME = "Smogon usage statistics"
BASE_URL = "https://www.smogon.com/stats"
DEFAULT_DATASET_VERSION = "0.0.0-dev"
CUTOFFS = (1760, 0)
VARIANTS = ("bo1", "bo3")
# Per Pokémon: the opponents with the strongest Checks and Counters score
# among those met at least MIN_COUNTER_ENCOUNTERS times, and the most-run
# spreads.
MAX_COUNTERS = 20
MIN_COUNTER_ENCOUNTERS = 100
MAX_SPREADS = 10

_MONTH_PATTERN = re.compile(r'href="(\d{4}-\d{2})/"')
_FILE_PATTERN = re.compile(r'href="([a-z0-9]+-\d+\.json)"')
# "Adamant:32/32/0/0/2/0"
_SPREAD_PATTERN = re.compile(r"^([A-Za-z]+):(\d+)/(\d+)/(\d+)/(\d+)/(\d+)/(\d+)$")

_KEY_FIELDS = [
    "month",
    "metagame",
    "regulation_code",
    "variant",
    "cutoff",
    "battles",
    "pokemon_name",
]
_PROVENANCE = [
    "source_name",
    "source_url",
    "source_record_id",
    "extracted_at_utc",
    "dataset_version",
]
FIELDNAMES = [*_KEY_FIELDS, "raw_count", "usage", *_PROVENANCE]
COUNTER_FIELDNAMES = [
    *_KEY_FIELDS,
    "counter_name",
    "encounters",
    "ko_or_switch_rate",
    "std_dev",
    *_PROVENANCE,
]
SPREAD_FIELDNAMES = [
    *_KEY_FIELDS,
    "nature",
    "sp_hp",
    "sp_atk",
    "sp_def",
    "sp_spa",
    "sp_spd",
    "sp_spe",
    "weight",
    "share",
    *_PROVENANCE,
]


def _get(session: requests.Session, url: str) -> requests.Response:
    return get_with_retry(session, url, timeout=120)


def list_months(session: requests.Session) -> list[str]:
    """Published months, newest first."""
    return sorted(set(_MONTH_PATTERN.findall(_get(session, f"{BASE_URL}/").text)), reverse=True)


def list_files(session: requests.Session, month: str) -> set[str]:
    return set(_FILE_PATTERN.findall(_get(session, f"{BASE_URL}/{month}/chaos/").text))


def file_name(regulation: Regulation, variant: str, cutoff: int) -> str:
    suffix = "bo3" if variant == "bo3" else ""
    return f"{regulation.munchstats_format}{suffix}-{cutoff}.json"


def file_url(month: str, name: str) -> str:
    return f"{BASE_URL}/{month}/chaos/{name}"


def _key(month: str, name: str) -> str:
    return f"{month}/{name}"


def parse_file(
    payload: dict,
    *,
    month: str,
    regulation: Regulation,
    variant: str,
    cutoff: int,
    extracted_at_utc: str,
    dataset_version: str,
) -> tuple[list[dict], list[dict], list[dict]]:
    """One chaos file -> (usage rows, counter rows, spread rows)."""
    name = file_name(regulation, variant, cutoff)
    url = file_url(month, name)
    info = payload.get("info") or {}
    base = {
        "month": month,
        "metagame": info.get("metagame") or name.rsplit("-", 1)[0],
        "regulation_code": regulation.regulation_code,
        "variant": variant,
        "cutoff": cutoff,
        "battles": info.get("number of battles"),
        "source_name": SOURCE_NAME,
        "source_url": url,
        "extracted_at_utc": extracted_at_utc,
        "dataset_version": dataset_version,
    }
    usage_rows: list[dict] = []
    counter_rows: list[dict] = []
    spread_rows: list[dict] = []
    for pokemon, stats in sorted((payload.get("data") or {}).items()):
        record = f"{_key(month, name)}:{pokemon}"
        usage_rows.append(
            {
                **base,
                "pokemon_name": pokemon,
                "raw_count": stats.get("Raw count"),
                "usage": stats.get("usage"),
                "source_record_id": record,
            }
        )
        counters = [
            (opponent, values)
            for opponent, values in (stats.get("Checks and Counters") or {}).items()
            if isinstance(values, dict) and (values.get("n") or 0) >= MIN_COUNTER_ENCOUNTERS
        ]
        # Smogon ranks checks and counters by p - 4d: a high KO-or-switch
        # rate that is also well measured.
        counters.sort(key=lambda item: -((item[1].get("p") or 0) - 4 * (item[1].get("d") or 0)))
        for opponent, values in counters[:MAX_COUNTERS]:
            counter_rows.append(
                {
                    **base,
                    "pokemon_name": pokemon,
                    "counter_name": opponent,
                    "encounters": round(values.get("n") or 0, 2),
                    "ko_or_switch_rate": round(values.get("p") or 0, 4),
                    "std_dev": round(values.get("d") or 0, 4),
                    "source_record_id": f"{record}:{opponent}",
                }
            )
        spreads = stats.get("Spreads") or {}
        total = sum(spreads.values()) or 0
        for spread, weight in sorted(spreads.items(), key=lambda item: -item[1])[:MAX_SPREADS]:
            match = _SPREAD_PATTERN.match(spread)
            if not match or not total:
                continue
            nature, *points = match.groups()
            spread_rows.append(
                {
                    **base,
                    "pokemon_name": pokemon,
                    "nature": nature,
                    **dict(
                        zip(
                            ("sp_hp", "sp_atk", "sp_def", "sp_spa", "sp_spd", "sp_spe"),
                            (int(p) for p in points),
                            strict=True,
                        )
                    ),
                    "weight": round(weight, 4),
                    "share": round(weight / total, 4),
                    "source_record_id": f"{record}:{spread}",
                }
            )
    return usage_rows, counter_rows, spread_rows


def _load(path: Path | None) -> dict[str, list[dict]]:
    """A previous snapshot's rows by file (month/name)."""
    if path is None or not path.exists():
        return {}
    by_file: dict[str, list[dict]] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            by_file.setdefault(row["source_url"], []).append(row)
    return by_file


def _write(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _days_in_force(month: str, regulation: Regulation) -> tuple[int, int]:
    """(days of `month` the regulation was in force, days in the month)."""
    year, number = (int(part) for part in month.split("-"))
    length = calendar.monthrange(year, number)[1]
    first, last = date(year, number, 1), date(year, number, length)
    start, end = max(first, regulation.start_date), min(last, regulation.end_date)
    return max((end - start).days + 1, 0), length


def pick_month(regulation: Regulation, months_with_file: list[str]) -> str | None:
    """The newest month with the regulation's file in which it was in force
    for at least half the month, else the newest month it overlaps at all."""
    overlapping = [m for m in months_with_file if _days_in_force(m, regulation)[0] > 0]
    mostly = [
        m
        for m in overlapping
        if 2 * _days_in_force(m, regulation)[0] >= _days_in_force(m, regulation)[1]
    ]
    return max(mostly or overlapping, default=None)


def plan_files(
    session: requests.Session, regulations: list[Regulation]
) -> list[tuple[str, Regulation, str, int]]:
    """(month, regulation, variant, cutoff) for every file to keep: each
    regulation's month (pick_month, judged on its 1760 Bo1 file) and
    whichever of the other variants and cutoffs that month has. Only months
    a regulation was in force are listed."""
    published = list_months(session)
    listings: dict[str, set[str]] = {}
    planned = []
    for regulation in regulations:
        window = [m for m in published if _days_in_force(m, regulation)[0] > 0]
        for month in window:
            if month not in listings:
                listings[month] = list_files(session, month)
        month = pick_month(
            regulation,
            [m for m in window if file_name(regulation, "bo1", CUTOFFS[0]) in listings[m]],
        )
        if month is None:
            continue
        for variant in VARIANTS:
            for cutoff in CUTOFFS:
                if file_name(regulation, variant, cutoff) in listings[month]:
                    planned.append((month, regulation, variant, cutoff))
    return planned


def extract(
    output_path: Path,
    counters_path: Path,
    spreads_path: Path,
    *,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    session: requests.Session | None = None,
    previous_paths: tuple[Path | None, Path | None, Path | None] = (None, None, None),
    regulations: list[Regulation] | None = None,
    extracted_at_utc: str | None = None,
) -> None:
    """Write the three ladder tables. A file the previous snapshots already
    hold is reused (a published month never changes); the others are
    downloaded. Reuse needs all three previous snapshots, since a file can
    rightly have no counter rows: with one missing, everything is
    downloaded rather than a held month losing that table."""
    http = session if session is not None else requests.Session()
    regulations = load_regulations() if regulations is None else regulations
    extracted_at_utc = extracted_at_utc or datetime.now(UTC).isoformat()
    complete = all(path is not None and path.exists() for path in previous_paths)
    previous = [_load(path) if complete else {} for path in previous_paths]
    tables: tuple[list[dict], list[dict], list[dict]] = ([], [], [])
    for month, regulation, variant, cutoff in plan_files(http, regulations):
        url = file_url(month, file_name(regulation, variant, cutoff))
        cached = [table.get(url) for table in previous]
        if cached[0]:
            for table, rows in zip(tables, cached, strict=True):
                table.extend(
                    {
                        **row,
                        "extracted_at_utc": extracted_at_utc,
                        "dataset_version": dataset_version,
                    }
                    for row in rows or []
                )
            continue
        parsed = parse_file(
            _get(http, url).json(),
            month=month,
            regulation=regulation,
            variant=variant,
            cutoff=cutoff,
            extracted_at_utc=extracted_at_utc,
            dataset_version=dataset_version,
        )
        for table, rows in zip(tables, parsed, strict=True):
            table.extend(rows)
    _write(output_path, FIELDNAMES, tables[0])
    _write(counters_path, COUNTER_FIELDNAMES, tables[1])
    _write(spreads_path, SPREAD_FIELDNAMES, tables[2])
