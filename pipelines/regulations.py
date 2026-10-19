"""Read the Pokémon Champions regulation registry
(dbt/seeds/champions_regulations.csv) from Python.

The dbt seed is the single source of truth for which formats count as
Champions. The RK9 and Limitless extractors filter their event lists with
it, and the dashboard uses it to pick the regulation in force today, so
that adding a regulation stays a one-row change. This replaces the three
hardcoded M-A constants that used to drop every M-B/M-C event
(docs/upgrade-plan-2026q4.md, A1).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REGISTRY_PATH = (
    Path(__file__).resolve().parent.parent / "dbt" / "seeds" / "champions_regulations.csv"
)


@dataclass(frozen=True)
class Regulation:
    regulation_code: str
    regulation_name: str
    munchstats_format: str
    limitless_format: str
    start_date: date
    end_date: date


def load_regulations(path: Path = REGISTRY_PATH) -> list[Regulation]:
    """Every registered regulation, ordered by start_date."""
    with path.open(newline="", encoding="utf-8") as fh:
        regulations = [
            Regulation(
                regulation_code=row["regulation_code"],
                regulation_name=row["regulation_name"],
                munchstats_format=row["munchstats_format"],
                limitless_format=row["limitless_format"],
                start_date=date.fromisoformat(row["start_date"]),
                end_date=date.fromisoformat(row["end_date"]),
            )
            for row in csv.DictReader(fh)
        ]
    return sorted(regulations, key=lambda r: r.start_date)


def munchstats_formats(path: Path = REGISTRY_PATH) -> frozenset[str]:
    return frozenset(r.munchstats_format for r in load_regulations(path))


def limitless_formats(path: Path = REGISTRY_PATH) -> frozenset[str]:
    return frozenset(r.limitless_format for r in load_regulations(path))


def current_regulation(today: date | None = None, path: Path = REGISTRY_PATH) -> Regulation | None:
    """The regulation in force on `today`. If today falls after every
    registered set (the next one hasn't been added yet), the latest set is
    returned instead, so the dashboard keeps defaulting to the newest data.
    None only if the registry is empty."""
    regulations = load_regulations(path)
    if not regulations:
        return None
    today = today or date.today()
    for regulation in regulations:
        if regulation.start_date <= today < regulation.end_date:
            return regulation
    return regulations[-1]
