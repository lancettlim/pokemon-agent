"""Loads data/marts/*.csv into the JSON payload the dashboard template
bakes into its generated HTML.

Uses plain csv.DictReader (no pandas/dbt runtime), matching the rest of
this codebase's convention of not requiring a build runtime just to read
already-materialized output (see pipelines/render/data_source.py). Missing
mart files degrade to an empty list rather than raising, so the dashboard
still builds before `make dbt-build` has ever been run. (An earlier version
of this module also computed empty-state flags for two now-removed
sections — stat-change leaderboard and legal-pool trend — that were cut
because the underlying data is permanently degenerate; see
docs/dashboard.md's "Removed sections" note. No empty-state computation
remains here.)
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pipelines.regulations import current_regulation, load_regulations

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MARTS_DIR = REPO_ROOT / "data" / "marts"
DEFAULT_NORMALIZED_DIR = REPO_ROOT / "data" / "normalized"
DEFAULT_REPORTS_DIR = REPO_ROOT / "reports" / "validation"
DEFAULT_STAGING_DIR = REPO_ROOT / "data" / "staging"
DEFAULT_MANIFESTS_DIR = REPO_ROOT / "releases" / "manifests"

_STAGING_LABELS = {
    "bulbagarden": "Bulbagarden Archives",
    "limitless": "Limitless VGC",
    "munchstats": "MunchStats",
    "opgg_champions": "OP.GG Pokémon Champions",
    "pokeapi": "PokéAPI",
    "pokeapi_ability": "PokéAPI (ability detail)",
    "pokeapi_artwork": "PokéAPI (artwork)",
    "pokeapi_item": "PokéAPI (item detail)",
    "pokeapi_move": "PokéAPI (move detail)",
    "pokebase": "PokéBase",
    "rk9_pairings": "RK9.gg",
}

# mart_name -> (int_fields, float_fields) for numeric coercion; every other
# column is left as a string.
MART_FIELDS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "pokemon_usage_summary": (("usage_count", "usage_rank"), ("usage_share",)),
    "legality_summary_by_regulation": (
        ("legal_pokemon_count", "cumulative_legal_pokemon_count"),
        (),
    ),
    "pokemon_win_rate_summary": (
        ("total_wins", "total_losses", "record_count", "wilson_rank"),
        ("win_rate", "wilson_lower_bound"),
    ),
    "pokemon_item_usage": (("usage_count", "usage_rank"), ("item_share",)),
    "pokemon_ability_usage": (("usage_count", "usage_rank"), ("ability_share",)),
    "pokemon_move_usage": (
        ("usage_count", "usage_rank", "power", "accuracy", "priority", "pp"),
        ("move_share",),
    ),
    "pokemon_team_core_usage": (("co_occurrence_count", "usage_rank"), ("partner_share",)),
    "pokemon_champions_profile": (
        (
            "hp",
            "attack",
            "defense",
            "sp_attack",
            "sp_defense",
            "speed",
            "stat_total",
            "usage_count",
            "record_count",
        ),
        ("usage_share", "win_rate"),
    ),
    "top_tournament_teams": (
        ("record_wins", "record_losses", "placement", "team_rank"),
        ("win_rate",),
    ),
    "pokemon_usage_by_event_date": (("usage_count", "usage_rank"), ("usage_share",)),
    "pokemon_head_to_head": (
        ("matches_played", "wins", "losses", "matchup_rank"),
        ("win_rate", "wilson_lower_bound"),
    ),
    "pokemon_matchup_summary": (
        (
            "distinct_opponents",
            "total_matchup_appearances",
            "best_matchup_matches",
            "worst_matchup_matches",
            "min_matches_threshold",
        ),
        ("overall_win_rate", "best_matchup_win_rate", "worst_matchup_win_rate"),
    ),
    "pokemon_placement_weighted_usage": (
        ("usage_count", "top_cut_usage_count", "weighted_usage_rank"),
        ("top_cut_usage_share", "placement_weighted_score", "weighted_usage_share"),
    ),
    "pokemon_usage_by_regulation": (("usage_count", "usage_rank"), ("usage_share",)),
    "pokemon_build_concentration": (
        ("item_count", "ability_count"),
        ("item_hhi", "ability_hhi"),
    ),
    "pokemon_team_synergy": (("pair_team_count", "lift_rank"), ("lift",)),
    "pokemon_team_core_triple_usage": (
        (
            "triple_team_count",
            "player_count",
            "event_count",
            "total_wins",
            "total_losses",
            "support_rank",
            "lift_rank",
        ),
        (
            "triple_team_share",
            "expected_team_share",
            "triple_lift",
            "min_pair_lift",
            "avg_pair_lift",
            "win_rate",
            "avg_placement",
        ),
    ),
    "detected_archetype_summary": (
        (
            "candidate_count",
            "team_count",
            "player_count",
            "event_count",
            "total_wins",
            "total_losses",
            "extension_team_count",
            "archetype_rank",
        ),
        ("team_share", "win_rate", "avg_placement", "top_extension_share"),
    ),
    "pokemon_speed_tiers": (
        (
            "base_speed",
            "max_investment_speed",
            "plus_one_speed",
            "scarf_speed",
            "plus_two_speed",
            "tailwind_speed",
            "scarf_tailwind_speed",
            "usage_count",
            "record_count",
        ),
        ("usage_share", "win_rate"),
    ),
    "pokemon_usage_by_country": (
        ("usage_count", "country_usage_rank"),
        ("usage_share",),
    ),
    "player_signature_pokemon": (
        ("player_team_count", "usage_count", "player_pokemon_rank"),
        ("player_usage_share",),
    ),
    # Cross-source agreement per event (Limitless vs MunchStats rosters),
    # feeding the Data & Sources tab rather than any competitive view.
    "roster_source_agreement": (
        ("covered_players", "exact_agreement_players"),
        ("exact_agreement_rate", "slot_agreement_rate"),
    ),
    "team_list_convergence": (
        (
            "player_count",
            "tournament_count",
            "best_placement",
            "roster_size",
            "convergence_rank",
        ),
        (),
    ),
}

# Two of the marts above are far larger than anything the dashboard can
# display, and the whole payload is inlined into the committed
# docs/dashboard/index.html (see pipelines/dashboard/build.py's docstring)
# — player_signature_pokemon alone is ~44,500 rows, which would roughly
# double that already-7MB committed file for rows no view ever reads.
#
# Each slice below is also the analytically honest cut, not just a size
# cut: both marts' own schema.yml entries warn that their headline metric
# is noise below a sample-size floor (lift is unstable at low
# pair_team_count; a "signature Pokémon" claim from a player with one
# recorded team is weak evidence), and both expose that sample size as a
# column precisely so consumers can apply a floor. The floors are applied
# here rather than in dbt so the marts themselves stay complete for
# docs/local-queries.md's ad-hoc querying.
MIN_SYNERGY_PAIR_TEAMS = 5
MAX_SYNERGY_PARTNERS_PER_POKEMON = 12
MIN_TRIPLE_CORE_TEAMS = 5
MAX_DETECTED_ARCHETYPES = 24
# Deliberately 2, not a larger "established player" number: only three
# Champions-format events exist anywhere (see backlog.md #26), so three
# recorded teams is the ceiling, not a modest bar. Measured against the
# real mart, 2,329 players have exactly one recorded team, 358 have two,
# and exactly one has three -- a floor of 3 would leave the whole view
# showing a single player. Two teams is therefore the strongest "this
# wasn't one event's worth of choices" signal the format can produce.
MIN_SIGNATURE_PLAYER_TEAMS = 2
MAX_SIGNATURE_PICKS_PER_PLAYER = 6


def _slice_team_synergy(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept = [r for r in rows if (r.get("pair_team_count") or 0) >= MIN_SYNERGY_PAIR_TEAMS]
    per_anchor: dict[str, int] = {}
    out = []
    for row in sorted(kept, key=lambda r: (r["pokemon_key"], -(r.get("lift") or 0))):
        seen = per_anchor.get(row["pokemon_key"], 0)
        if seen >= MAX_SYNERGY_PARTNERS_PER_POKEMON:
            continue
        per_anchor[row["pokemon_key"]] = seen + 1
        out.append(row)
    return out


def _slice_player_signature(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if (row.get("player_team_count") or 0) >= MIN_SIGNATURE_PLAYER_TEAMS
        and (row.get("player_pokemon_rank") or 0) <= MAX_SIGNATURE_PICKS_PER_PLAYER
    ]


def _slice_team_core_triples(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the mart complete on disk while excluding one-off triple lift
    noise from the browser payload."""
    return [row for row in rows if (row.get("triple_team_count") or 0) >= MIN_TRIPLE_CORE_TEAMS]


def _slice_detected_archetypes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The experimental UI leads with cross-event groups, not single-event
    or tiny emerging fragments. The complete candidate/membership/summary
    marts remain queryable locally."""
    stable = [row for row in rows if row.get("stability_label") == "cross-event"]
    return sorted(stable, key=lambda row: row.get("archetype_rank") or 10**9)[
        :MAX_DETECTED_ARCHETYPES
    ]


MART_SLICERS = {
    "pokemon_team_synergy": _slice_team_synergy,
    "pokemon_team_core_triple_usage": _slice_team_core_triples,
    "detected_archetype_summary": _slice_detected_archetypes,
    "player_signature_pokemon": _slice_player_signature,
}


# Species whose display name isn't the title-cased slug: punctuation,
# accents, or letters that the slug folds away.
_SPECIES_NAME_OVERRIDES = {
    "mr-mime": "Mr. Mime",
    "mr-rime": "Mr. Rime",
    "mime-jr": "Mime Jr.",
    "farfetchd": "Farfetch\u2019d",
    "sirfetchd": "Sirfetch\u2019d",
    "type-null": "Type: Null",
    "ho-oh": "Ho-Oh",
    "porygon-z": "Porygon-Z",
    "jangmo-o": "Jangmo-o",
    "hakamo-o": "Hakamo-o",
    "kommo-o": "Kommo-o",
    "nidoran-f": "Nidoran\u2640",
    "nidoran-m": "Nidoran\u2642",
    "flabebe": "Flab\u00e9b\u00e9",
    "wo-chien": "Wo-Chien",
    "chien-pao": "Chien-Pao",
    "ting-lu": "Ting-Lu",
    "chi-yu": "Chi-Yu",
}

# Regional form suffix -> adjective that goes before the species name.
_REGIONAL_PREFIXES = {
    "alola": "Alolan",
    "galar": "Galarian",
    "hisui": "Hisuian",
    "paldea": "Paldean",
}

# Gendered forms render as a symbol after the name rather than a word.
_GENDER_SYMBOLS = {"male": "\u2642", "female": "\u2640"}


def _title_words(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-") if part)


def _infer_species(pokemon_key: str, known_species: set[str]) -> str:
    """The longest known species slug that prefixes pokemon_key, falling
    back to the first token when the species list isn't available."""
    parts = pokemon_key.split("-")
    for end in range(len(parts), 0, -1):
        candidate = "-".join(parts[:end])
        if candidate in known_species:
            return candidate
    return parts[0]


def display_name(pokemon_key: str, species: str | None = None) -> str:
    """A player-facing name for a pokemon_key (PokéAPI form slug):

        charizard-mega-y     -> Mega Charizard Y
        absol-mega-z         -> Mega Absol Z
        meowstic-male-mega   -> Mega Meowstic \u2642
        basculegion-male     -> Basculegion \u2642
        ninetales-alola      -> Alolan Ninetales
        tauros-paldea-aqua-breed -> Paldean Tauros (Aqua)
        landorus-therian     -> Landorus (Therian)
        great-tusk           -> Great Tusk
        farfetchd            -> Farfetch\u2019d

    `species` is PokéAPI's species slug (data/normalized/pokemon.csv's
    pokemon_name). It's what separates the species from the form suffix
    for multi-word species like great-tusk. Without it, the first hyphen
    token is assumed to be the species.

    This replaced the PascalCase convention ("CharizardMegaY",
    "BasculegionMale"): those names read as internal identifiers, and long
    ones broke mid-word in the KPI cards (docs/upgrade-plan-2026q4.md, B1).
    """
    if not pokemon_key:
        return pokemon_key
    species = species or pokemon_key.split("-")[0]
    if not pokemon_key.startswith(species):
        species = pokemon_key.split("-")[0]
    base = _SPECIES_NAME_OVERRIDES.get(species, _title_words(species))
    form_parts = [p for p in pokemon_key[len(species) :].split("-") if p]
    if not form_parts:
        return base

    prefix = ""
    suffix_tokens: list[str] = []
    if "mega" in form_parts:
        prefix = "Mega "
        form_parts.remove("mega")
    elif "gmax" in form_parts:
        prefix = "Gigantamax "
        form_parts.remove("gmax")
    if form_parts and form_parts[0] in _REGIONAL_PREFIXES:
        prefix += _REGIONAL_PREFIXES[form_parts.pop(0)] + " "
        if form_parts and form_parts[-1] == "breed":
            form_parts.pop()
    gender = ""
    if form_parts and form_parts[0] in _GENDER_SYMBOLS:
        gender = " " + _GENDER_SYMBOLS[form_parts.pop(0)]
    # A lone trailing letter after "mega" is the X/Y/Z variant letter.
    if prefix.startswith("Mega") and len(form_parts) == 1 and len(form_parts[0]) == 1:
        suffix_tokens.append(form_parts.pop().upper())
    name = prefix + base + gender
    if suffix_tokens:
        name += " " + " ".join(suffix_tokens)
    if form_parts:
        name += f" ({' '.join(p.capitalize() for p in form_parts)})"
    return name


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _coerce(
    row: dict[str, str], *, int_fields: tuple[str, ...], float_fields: tuple[str, ...]
) -> dict[str, Any]:
    coerced: dict[str, Any] = dict(row)
    for field in int_fields:
        value = coerced.get(field)
        coerced[field] = int(value) if value not in (None, "") else None
    for field in float_fields:
        value = coerced.get(field)
        coerced[field] = float(value) if value not in (None, "") else None
    return coerced


def load_mart(marts_dir: Path, mart_name: str) -> list[dict[str, Any]]:
    """Returns [] (not an error) if the mart's CSV doesn't exist yet.
    Marts listed in MART_SLICERS are cut down to the dashboard-relevant
    slice after coercion — see that dict's comment for why."""
    int_fields, float_fields = MART_FIELDS[mart_name]
    rows = _read_csv_rows(marts_dir / f"{mart_name}.csv")
    coerced = [_coerce(row, int_fields=int_fields, float_fields=float_fields) for row in rows]
    slicer = MART_SLICERS.get(mart_name)
    return slicer(coerced) if slicer else coerced


def load_pokemon_names(normalized_dir: Path = DEFAULT_NORMALIZED_DIR) -> dict[str, str]:
    """pokemon_key -> player-facing display name (see display_name). The
    name comes from pokemon_key (== form_name), using the CSV's species-only
    pokemon_name column only to split species from form, so a species'
    forms never collide. Returns {} gracefully if
    data/normalized/pokemon.csv isn't present."""
    rows = _read_csv_rows(normalized_dir / "pokemon.csv")
    known_species = {row.get("pokemon_name", "") for row in rows}
    return {
        row["pokemon_key"]: display_name(
            row["pokemon_key"],
            row.get("pokemon_name") or _infer_species(row["pokemon_key"], known_species),
        )
        for row in rows
    }


def load_marts(marts_dir: Path = DEFAULT_MARTS_DIR) -> dict[str, list[dict[str, Any]]]:
    return {mart_name: load_mart(marts_dir, mart_name) for mart_name in MART_FIELDS}


def load_snapshot_history(staging_dir: Path = DEFAULT_STAGING_DIR) -> dict[str, Any]:
    """Summarize retained extraction snapshots without reading their rows.

    Snapshot CSVs are deliberately gitignored and may be absent from a clean
    checkout, so this is an optional observability feed. Filenames are the
    extractor's UTC dates (YYYY-MM-DD.csv); malformed filenames are ignored so
    a stray file cannot break a dashboard build.
    """
    source_rows: list[dict[str, Any]] = []
    all_dates: set[str] = set()
    if staging_dir.exists():
        for source_dir in sorted(path for path in staging_dir.iterdir() if path.is_dir()):
            dates = []
            for path in source_dir.glob("*.csv"):
                candidate = path.stem
                if len(candidate) != 10 or candidate[4] != "-" or candidate[7] != "-":
                    continue
                try:
                    datetime.fromisoformat(candidate)
                except ValueError:
                    continue
                dates.append(candidate)
            dates.sort()
            if not dates:
                continue
            all_dates.update(dates)
            source_key = source_dir.name
            source_rows.append(
                {
                    "source_name": _STAGING_LABELS.get(source_key, source_key),
                    "staging_subdir": source_key,
                    "snapshot_count": len(dates),
                    "first_snapshot_date": dates[0],
                    "latest_snapshot_date": dates[-1],
                    "history_days": (
                        (datetime.fromisoformat(dates[-1]) - datetime.fromisoformat(dates[0])).days
                        if len(dates) > 1
                        else 0
                    ),
                }
            )
    return {
        "snapshot_count": len(all_dates),
        "first_snapshot_date": min(all_dates) if all_dates else None,
        "latest_snapshot_date": max(all_dates) if all_dates else None,
        "has_multiple_snapshots": len(all_dates) > 1,
        "sources": source_rows,
    }


def load_release_history(manifests_dir: Path = DEFAULT_MANIFESTS_DIR) -> list[dict[str, Any]]:
    """Read compact release metadata for the Data & Sources history view."""
    releases: list[dict[str, Any]] = []
    if not manifests_dir.exists():
        return releases
    for path in sorted(manifests_dir.glob("manifest-*.json")):
        manifest = _read_json(path)
        if not manifest.get("dataset_version"):
            continue
        quality_checks = manifest.get("quality_checks") or []
        releases.append(
            {
                "dataset_version": manifest["dataset_version"],
                "published_at_utc": manifest.get("published_at_utc"),
                "table_count": len(manifest.get("tables") or []),
                "image_count": (manifest.get("images") or {}).get("count"),
                "quality_check_count": len(quality_checks),
                "quality_failure_count": sum(
                    1 for check in quality_checks if check.get("status") != "pass"
                ),
                "known_limitation_count": len(manifest.get("known_limitations") or []),
            }
        )
    return sorted(
        releases, key=lambda row: (row.get("published_at_utc") or "", row["dataset_version"])
    )


# <key column> -> <display-name column> pairs resolved against the
# pokemon_key -> display name map (see display_name), so every mart row carries a
# ready-to-render name rather than each view looking it up client-side.
_NAME_JOINS = (
    ("pokemon_key", "pokemon_name"),
    ("partner_pokemon_key", "partner_pokemon_name"),
    ("opponent_pokemon_key", "opponent_pokemon_name"),
    ("best_matchup_pokemon_key", "best_matchup_pokemon_name"),
    ("worst_matchup_pokemon_key", "worst_matchup_pokemon_name"),
    ("pokemon_key_a", "pokemon_name_a"),
    ("pokemon_key_b", "pokemon_name_b"),
    ("pokemon_key_c", "pokemon_name_c"),
    ("top_extension_pokemon_key", "top_extension_pokemon_name"),
)


def _join_pokemon_names(
    marts: dict[str, list[dict[str, Any]]], pokemon_names: dict[str, str]
) -> dict[str, list[dict[str, Any]]]:
    joined = {}
    for mart_name, rows in marts.items():
        joined_rows = []
        for row in rows:
            for key_field, name_field in _NAME_JOINS:
                key = row.get(key_field)
                if key:
                    row = {**row, name_field: pokemon_names.get(key, key)}
            joined_rows.append(row)
        joined[mart_name] = joined_rows
    return joined


def _current_regulation_kpi(
    legal_pool_by_regulation: list[dict[str, Any]], today: date | None
) -> dict[str, Any] | None:
    """The regulation in force today (dbt/seeds/champions_regulations.csv)
    and its legal-pool size. This is what the header and the legal-pool KPI
    lead with, so the page always says which format it's describing."""
    regulation = current_regulation(today)
    if regulation is None:
        return None
    legal_count = next(
        (
            r["legal_pokemon_count"]
            for r in legal_pool_by_regulation
            if r["regulation_code"] == regulation.regulation_code
        ),
        None,
    )
    return {
        "regulation_code": regulation.regulation_code,
        "regulation_name": regulation.regulation_name,
        "start_date": regulation.start_date.isoformat(),
        "end_date": regulation.end_date.isoformat(),
        "legal_pokemon_count": legal_count,
    }


def compute_kpis(
    marts: dict[str, list[dict[str, Any]]], today: date | None = None
) -> dict[str, Any]:
    usage_rows = [r for r in marts["pokemon_usage_summary"] if not r.get("event_tier")]
    legality_rows = marts["legality_summary_by_regulation"]
    win_rate_rows = marts["pokemon_win_rate_summary"]

    latest_snapshot_date = max((r["snapshot_date"] for r in legality_rows), default=None)
    legal_pool_by_regulation = [
        {
            "regulation_code": r["regulation_code"],
            "legal_pokemon_count": r["legal_pokemon_count"],
            "cumulative_legal_pokemon_count": r["cumulative_legal_pokemon_count"],
        }
        for r in legality_rows
        if r["snapshot_date"] == latest_snapshot_date
    ]

    top_used = min(usage_rows, key=lambda r: r["usage_rank"], default=None)

    # Ranked by wilson_rank (pokemon_win_rate_summary's Wilson score lower
    # bound, backlog.md #13) rather than raw win_rate, so a 1-0 record
    # doesn't outrank a well-established Pokémon's real win rate -- the
    # confidence interval accounts for sample size directly instead of
    # relying on an arbitrary record_count cutoff.
    top_win_rate = min(win_rate_rows, key=lambda r: r["wilson_rank"], default=None)

    # Overview tab spotlight grid (docs/design-system.md's "3-tier tab
    # layout convention"): drawn from the overall usage ranking, sliced to
    # a 6-wide-grid-friendly 12 -- the old Top 30 ranked list was removed
    # (dashboard "remove top 30 in overview" ask) since the grid tier
    # already covers the headline Pokémon and a full Usage-tab table
    # exists for raw drill-down. pokemon_usage_summary itself has no
    # win_rate column, so it's joined in here (win_rate stays None if the
    # Pokémon has no recorded win/loss data) -- otherwise every spotlight
    # card would show a uniform, uninformative "no win rate" placeholder.
    # Types are joined in for the same reason win_rate is, plus one more:
    # Overview is the only tab that renders without waiting for the marts
    # fetch (build.py's critical payload), so it cannot look types up
    # client-side through pokemon_champions_profile the way every other
    # grid does. Without this the spotlight grid would be the one
    # Pokémon-keyed grid with no type accent.
    win_rate_by_key = {r["pokemon_key"]: r["win_rate"] for r in win_rate_rows}
    profile_by_key = {r["pokemon_key"]: r for r in marts.get("pokemon_champions_profile", [])}
    ranked_usage = sorted(usage_rows, key=lambda r: r["usage_rank"])
    ranked_usage = [
        {
            **r,
            "win_rate": win_rate_by_key.get(r["pokemon_key"]),
            "type_1": profile_by_key.get(r["pokemon_key"], {}).get("type_1"),
            "type_2": profile_by_key.get(r["pokemon_key"], {}).get("type_2"),
        }
        for r in ranked_usage
    ]
    top_12_pokemon = ranked_usage[:12]

    return {
        "latest_snapshot_date": latest_snapshot_date,
        "legal_pool_by_regulation": legal_pool_by_regulation,
        "current_regulation": _current_regulation_kpi(legal_pool_by_regulation, today),
        # Newest tournament the marts cover. The staleness banner compares
        # this against the viewer's own clock (static/app.js), so a site
        # nobody has rebuilt still says it's out of date.
        "latest_event_date": max(
            (
                r["event_date"]
                for r in marts.get("pokemon_usage_by_event_date", [])
                if r.get("event_date")
            ),
            default=None,
        ),
        "distinct_pokemon_used": len(usage_rows),
        "top_used_pokemon": top_used,
        "top_win_rate_pokemon": top_win_rate,
        "top_12_pokemon": top_12_pokemon,
    }


def _read_json(path: Path) -> dict[str, Any]:
    """Missing or unparseable -> {}, matching load_marts' degrade-don't-raise
    contract. A malformed report should cost the Data & Sources tab its
    content, not fail the whole dashboard build."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def load_provenance(
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    staging_dir: Path = DEFAULT_STAGING_DIR,
    manifests_dir: Path = DEFAULT_MANIFESTS_DIR,
) -> dict[str, Any]:
    """The Data & Sources tab's feed: where the numbers came from and
    whether they passed their gates.

    Two files, with deliberately different availability:

    * `extraction_summary.json` is committed, so a published dashboard
      always carries per-source endpoint/availability/success-rate/row-count
      provenance even when built from a clean checkout.
    * `validation_report.json` is gitignored (regenerated by `make
      validate`, which `make dashboard` runs first). Its gate results are
      *baked into the payload here* so the published site carries them even
      though the report itself never lands in git.

    Both degrade to empty rather than raising, matching load_marts' missing
    file convention — a dashboard built before `make validate` has run
    simply shows the gates as unavailable.
    """
    summary = _read_json(reports_dir / "extraction_summary.json")
    report = _read_json(reports_dir / "validation_report.json")

    gates: list[dict[str, Any]] = []
    for check in report.get("coverage_checks", []):
        gates.append(
            {
                "category": "coverage",
                "name": check.get("check_name"),
                "description": check.get("description"),
                "threshold": check.get("threshold"),
                "metric_value": check.get("metric_value"),
                "status": check.get("status"),
            }
        )
    for check in report.get("null_rate_checks", []):
        gates.append(
            {
                "category": "null_rate",
                "name": check.get("table_name"),
                "description": "Required-field null rate",
                "threshold": check.get("threshold"),
                "metric_value": check.get("metric_value"),
                "status": check.get("status"),
            }
        )
    for check in report.get("duplicate_key_checks", []):
        gates.append(
            {
                "category": "duplicate_key",
                "name": check.get("table_name"),
                "description": "Duplicate " + str(check.get("primary_key")),
                "threshold": "=0",
                "metric_value": check.get("duplicate_count"),
                "status": check.get("status"),
            }
        )
    for check in report.get("referential_integrity_checks", []):
        gates.append(
            {
                "category": "referential_integrity",
                "name": check.get("check_name"),
                "description": "Rows resolving to their parent entity",
                "threshold": "=0 violations",
                "metric_value": check.get("violation_count"),
                "status": check.get("status"),
            }
        )

    return {
        "dataset_version": summary.get("dataset_version") or report.get("dataset_version"),
        "extraction_generated_at_utc": summary.get("generated_at_utc"),
        "validation_generated_at_utc": report.get("generated_at_utc"),
        "sources": summary.get("sources", []),
        "gates": gates,
        "release_blocking_findings": report.get("release_blocking_findings", []),
        "validation_available": bool(report),
        "snapshot_history": load_snapshot_history(staging_dir),
        "release_history": load_release_history(manifests_dir),
    }


def build_payload(
    marts_dir: Path = DEFAULT_MARTS_DIR,
    normalized_dir: Path = DEFAULT_NORMALIZED_DIR,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    staging_dir: Path = DEFAULT_STAGING_DIR,
    manifests_dir: Path = DEFAULT_MANIFESTS_DIR,
) -> dict[str, Any]:
    marts = load_marts(marts_dir)
    pokemon_names = load_pokemon_names(normalized_dir)
    marts = _join_pokemon_names(marts, pokemon_names)
    return {
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kpis": compute_kpis(marts),
        "provenance": load_provenance(reports_dir, staging_dir, manifests_dir),
        "marts": marts,
        # Full pokemon_key -> display name map, needed client-side wherever
        # a row can't be joined 1:1 by _join_pokemon_names -- e.g.
        # top_tournament_teams' pipe-delimited pokemon_keys roster field,
        # and the pokepaste import/export + Matchup tab's ad-hoc species
        # lookups (docs/design-system.md's Top Teams / Matchup tabs).
        "pokemon_names": pokemon_names,
        # The regulation registry, so the page can work out which set is in
        # force on the day it's viewed, not the day it was built.
        "regulations": [
            {
                "regulation_code": r.regulation_code,
                "regulation_name": r.regulation_name,
                "start_date": r.start_date.isoformat(),
                "end_date": r.end_date.isoformat(),
            }
            for r in load_regulations()
        ],
    }
