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
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pipelines.regulations import Regulation, load_regulations

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
    "pokemon_nature_usage": (("usage_count", "usage_rank"), ("nature_share",)),
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
    "pokemon_usage_by_regulation": (
        ("usage_count", "usage_rank", "record_count"),
        ("usage_share", "win_rate"),
    ),
    "pokemon_build_concentration": (
        ("item_count", "ability_count"),
        ("item_hhi", "ability_hhi"),
    ),
    "pokemon_team_synergy": (("pair_team_count", "lift_rank"), ("lift",)),
    "pokemon_regulation_movers": (
        (
            "usage_count",
            "usage_rank",
            "previous_usage_count",
            "previous_usage_rank",
            "rank_change",
            "record_count",
            "previous_record_count",
            "team_count",
            "previous_team_count",
        ),
        (
            "usage_share",
            "previous_usage_share",
            "usage_share_delta",
            "win_rate",
            "previous_win_rate",
            "win_rate_delta",
        ),
    ),
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
    # docs/upgrade-plan-2027q1.md's event, team, set and player marts.
    "tournament_event_summary": (
        (
            "team_count",
            "player_count",
            "recorded_team_count",
            "match_count",
            "winner_record_wins",
            "winner_record_losses",
            "recency_rank",
        ),
        (),
    ),
    "tournament_team_results": (
        ("placement", "event_team_count", "record_wins", "record_losses", "roster_size"),
        ("win_rate",),
    ),
    "tournament_team_sheets": (("slot_number",), ()),
    "team_list_sheets": (("slot_number",), ()),
    "pokemon_set_variants": (
        (
            "set_rank",
            "team_count",
            "pokemon_slot_count",
            "total_wins",
            "total_losses",
            "record_count",
        ),
        ("share_of_pokemon", "win_rate", "wilson_lower_bound"),
    ),
    "pokemon_event_usage_vs_regulation": (
        ("usage_count", "event_slot_count", "event_team_count", "total_wins", "total_losses"),
        ("event_usage_share", "regulation_usage_share", "usage_share_delta"),
    ),
    "player_archetype_record": (("matches_played", "wins", "losses"), ("win_rate",)),
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
# The Core Explorer lists at most 24 partners per Pokémon, and the Profile's
# Team Cores tab fewer. pokemon_team_core_usage is every co-occurring pair
# in every regulation scope, most of it one-off pairings no view shows.
MAX_CORE_PARTNERS_PER_POKEMON = 24
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


def _top_per_anchor(rows: list[dict[str, Any]], *, metric: str, limit: int) -> list[dict[str, Any]]:
    """The `limit` highest-`metric` rows per (regulation_scope, pokemon_key)."""
    per_anchor: dict[tuple[str, str], int] = {}
    out = []
    ordered = sorted(
        rows,
        key=lambda r: (r.get("regulation_scope", ""), r["pokemon_key"], -(r.get(metric) or 0)),
    )
    for row in ordered:
        anchor = (row.get("regulation_scope", ""), row["pokemon_key"])
        seen = per_anchor.get(anchor, 0)
        if seen >= limit:
            continue
        per_anchor[anchor] = seen + 1
        out.append(row)
    return out


def _slice_team_synergy(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept = [r for r in rows if (r.get("pair_team_count") or 0) >= MIN_SYNERGY_PAIR_TEAMS]
    return _top_per_anchor(kept, metric="lift", limit=MAX_SYNERGY_PARTNERS_PER_POKEMON)


def _slice_team_core_usage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _top_per_anchor(rows, metric="co_occurrence_count", limit=MAX_CORE_PARTNERS_PER_POKEMON)


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


# tournament_team_results holds every Champions team, several thousand
# rows. The event's name, tier and date are already in
# tournament_event_summary, which every view reading team results also
# loads, so the browser copy drops them rather than repeating each one per
# team. The CSV mart keeps them for local queries.
_TEAM_RESULT_BROWSER_DROP = ("event_name", "event_tier", "event_date", "roster_size")


def _slice_team_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in row.items() if k not in _TEAM_RESULT_BROWSER_DROP} for row in rows]


# The profile shows a Pokémon's top 3 real sets per level
# (docs/upgrade-plan-2027q1.md, P1); the mart keeps 5 for local queries.
MAX_SET_VARIANTS_SHOWN = 3


def _slice_set_variants(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if (row.get("set_rank") or 0) <= MAX_SET_VARIANTS_SHOWN]


# Top Teams, event pages and a profile's "Teams featuring" list only show
# top-16 finishes, so they read this derived slice of
# tournament_team_results (a few hundred rows, in the core shard) instead
# of fetching every team. Player pages fetch the full mart.
TOP_CUT_PLACEMENT = 16


def top_cut_teams(team_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in team_results if r.get("placement") and r["placement"] <= TOP_CUT_PLACEMENT]


def player_index(
    team_results: list[dict[str, Any]], events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """One row per player for the Players search and player pages
    (docs/upgrade-plan-2027q1.md, C3): their name and country as the source
    spells them, how many teams they have on record (one per event), their
    best finish, their latest event date and the regulations they played.
    teams_by_regulation and best_by_regulation ("m-b:1|m-c:3") carry the
    same two figures per regulation, so a regulation-scoped list ranks by
    that regulation's results rather than a player's best anywhere.
    Nothing is inferred beyond the tournament data."""
    dates = {e["event_id"]: e.get("event_date") or "" for e in events}
    players: dict[str, dict[str, Any]] = {}
    for row in team_results:
        player_id = row.get("player_id")
        if not player_id:
            continue
        entry = players.setdefault(
            player_id,
            {
                "player_id": player_id,
                "player_name": row.get("player_name"),
                "player_country": row.get("player_country"),
                "team_count": 0,
                "best_placement": None,
                "latest_event_date": "",
                "regulations": {},
            },
        )
        placement = row.get("placement")
        entry["team_count"] += 1
        entry["best_placement"] = _better_placement(entry["best_placement"], placement)
        entry["latest_event_date"] = max(entry["latest_event_date"], dates.get(row["event_id"], ""))
        if row.get("regulation_code"):
            teams, best = entry["regulations"].get(row["regulation_code"], (0, None))
            entry["regulations"][row["regulation_code"]] = (
                teams + 1,
                _better_placement(best, placement),
            )
    rows = []
    for entry in sorted(players.values(), key=lambda e: (e["player_name"] or "").lower()):
        codes = sorted(entry["regulations"])
        rows.append(
            {
                **entry,
                "regulations": "|".join(codes),
                "teams_by_regulation": "|".join(
                    f"{code}:{entry['regulations'][code][0]}" for code in codes
                ),
                "best_by_regulation": "|".join(
                    f"{code}:{entry['regulations'][code][1]}"
                    for code in codes
                    if entry["regulations"][code][1] is not None
                ),
            }
        )
    return rows


def _better_placement(current: int | None, placement: int | None) -> int | None:
    if not placement:
        return current
    return placement if current is None else min(current, placement)


MART_SLICERS = {
    "pokemon_set_variants": _slice_set_variants,
    "tournament_team_results": _slice_team_results,
    "pokemon_team_synergy": _slice_team_synergy,
    "pokemon_team_core_usage": _slice_team_core_usage,
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
NAME_JOINS = (
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
            for key_field, name_field in NAME_JOINS:
                key = row.get(key_field)
                if key:
                    row = {**row, name_field: pokemon_names.get(key, key)}
            joined_rows.append(row)
        joined[mart_name] = joined_rows
    return joined


ALL_SCOPE = "all"

# Below this many teams on either side, a regulation-to-regulation delta is
# mostly noise, so the "What changed" panel shows counts but no deltas.
MIN_MOVER_TEAMS = 100
MAX_MOVERS_PER_LIST = 6

# docs/upgrade-plan-2027q1.md, U3: a regulation in force with fewer teams
# than this on record isn't a usable default yet -- the first week of a new
# set has one small event at most -- so the page opens on the previous
# regulation instead and says so. static/app.js applies the same rule
# against the viewer's own date (MIN_DEFAULT_SCOPE_TEAMS there).
MIN_DEFAULT_SCOPE_TEAMS = 300

# Event tiers, most prestigious first, for ranking by placement within tier
# (docs/upgrade-plan-2027q1.md, C2 and P5). Unknown tiers sort last.
EVENT_TIER_ORDER = ("Worlds", "International", "Special", "Regional")
MAX_STARTER_TEAMS = 3


def regulation_in_force(regulations: list[Regulation], today: date) -> Regulation | None:
    """The regulation whose [start_date, end_date) contains `today`, else
    the latest one when today is past every registered set (the next one
    hasn't been added yet), else None. Mirrors
    pipelines.regulations.current_regulation, over an explicit list so tests
    can pass a fixture registry."""
    if not regulations:
        return None
    for regulation in regulations:
        if regulation.start_date <= today < regulation.end_date:
            return regulation
    later = [r for r in regulations if r.start_date <= today]
    return later[-1] if later else regulations[0]


def _tier_rank(tier: str | None) -> int:
    return EVENT_TIER_ORDER.index(tier) if tier in EVENT_TIER_ORDER else len(EVENT_TIER_ORDER)


def _events_in_scope(marts: dict[str, list[dict[str, Any]]], scope: str) -> list[dict[str, Any]]:
    events = marts.get("tournament_event_summary", [])
    if scope == ALL_SCOPE:
        return list(events)
    return [e for e in events if e.get("regulation_code") == scope]


def _truthy(value: Any) -> bool:
    return str(value).lower() == "true"


def starter_teams(
    marts: dict[str, list[dict[str, Any]]], scope: str, limit: int = MAX_STARTER_TEAMS
) -> list[dict[str, Any]]:
    """docs/upgrade-plan-2027q1.md, P5: the top-placing fully reported
    teams of a scope, with their full sheets, for the Overview's "Copy and
    play" strip. Ranked by placement, then event tier, then the event's
    size and recency, so a regional win doesn't outrank a Worlds win. Only
    teams whose sheet lists six complete sets qualify: a starter team a
    player can't paste into Showdown as published is no use to them."""
    events = {e["event_id"]: e for e in _events_in_scope(marts, scope)}
    sheets: dict[str, list[dict[str, Any]]] = {}
    for row in marts.get("tournament_team_sheets", []):
        sheets.setdefault(row["team_id"], []).append(row)
    candidates = [
        r
        for r in marts.get("tournament_team_results", [])
        if r.get("event_id") in events
        and _truthy(r.get("is_fully_reported"))
        and r.get("placement")
        and r["team_id"] in sheets
    ]
    # Two stable sorts: newest event first as the final tie-break, then the
    # ranking proper.
    candidates.sort(
        key=lambda r: (events[r["event_id"]].get("event_date") or "", r["team_id"]), reverse=True
    )
    candidates.sort(
        key=lambda r: (
            r["placement"],
            _tier_rank(events[r["event_id"]].get("event_tier")),
            -(events[r["event_id"]].get("team_count") or 0),
        )
    )
    out = []
    for row in candidates[:limit]:
        event = events[row["event_id"]]
        out.append(
            {
                "team_id": row["team_id"],
                "event_id": row["event_id"],
                "event_name": event.get("event_name"),
                "event_date": event.get("event_date"),
                "event_tier": event.get("event_tier"),
                "event_team_count": event.get("team_count"),
                "player_id": row.get("player_id"),
                "player_name": row.get("player_name"),
                "player_country": row.get("player_country"),
                "placement": row.get("placement"),
                "record_wins": row.get("record_wins"),
                "record_losses": row.get("record_losses"),
                "pokemon_keys": row.get("pokemon_keys"),
                "sets": [
                    {
                        "pokemon_key": slot["pokemon_key"],
                        "item_name": slot.get("item_name"),
                        "ability": slot.get("ability"),
                        "nature": slot.get("nature"),
                        "moves": slot.get("moves"),
                    }
                    for slot in sorted(sheets[row["team_id"]], key=lambda s: s["slot_number"] or 0)
                ],
            }
        )
    return out


_EVENT_NAME_NOISE = re.compile(
    r"^\d{4}\s+|\bPok(?:é|e)mon\b|\bVGC\b|\bChampionships?\b|\bChampions\b", re.IGNORECASE
)


def short_event_name(event_name: str | None) -> str:
    """A compact event label for cards and tables: "2027 Louisville Pokémon
    VGC Regional Championships" -> "Louisville Regional". The season year,
    the game and "Championships" repeat on every event, so they carry no
    information in a list of them. Pages titled by the event keep the full
    name. static/app.js's shortEventName mirrors this."""
    if not event_name:
        return ""
    short = " ".join(_EVENT_NAME_NOISE.sub(" ", event_name).split())
    if short.lower() == "world":
        return "World Championships"
    return short or event_name


def _latest_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The newest event in a scope, for the Overview's "Latest event" card
    (docs/upgrade-plan-2027q1.md, C1)."""
    if not events:
        return None
    newest = max(events, key=lambda e: (e.get("event_date") or "", e.get("event_id") or ""))
    keys = (
        "event_id",
        "event_name",
        "event_date",
        "event_tier",
        "regulation_code",
        "team_count",
        "winner_player_name",
        "winner_player_country",
        "winner_record_wins",
        "winner_record_losses",
        "winner_pokemon_keys",
    )
    return {
        **{key: newest.get(key) for key in keys},
        "short_name": short_event_name(newest.get("event_name")),
    }


def marts_for_scope(
    marts: dict[str, list[dict[str, Any]]], scope: str
) -> dict[str, list[dict[str, Any]]]:
    """Marts cut down to one regulation_scope ("m-c" or "all"). Marts with
    no regulation_scope column (head-to-head, cores, legality, ...) pass
    through unchanged."""
    scoped = {}
    for name, rows in marts.items():
        if rows and "regulation_scope" in rows[0]:
            scoped[name] = [r for r in rows if r.get("regulation_scope") == scope]
        else:
            scoped[name] = rows
    return scoped


def _mover_row(row: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "pokemon_key",
        "pokemon_name",
        "usage_share",
        "previous_usage_share",
        "usage_share_delta",
        "usage_rank",
        "previous_usage_rank",
        "win_rate",
    )
    return {key: row.get(key) for key in keys}


def summarize_movers(
    movers_rows: list[dict[str, Any]], regulation_code: str
) -> dict[str, Any] | None:
    """Risers, fallers and new arrivals for one regulation against the one
    before it (pokemon_regulation_movers). `reliable` is false when either
    side has fewer than MIN_MOVER_TEAMS teams; the UI then shows the sample
    sizes and new arrivals but holds back the deltas."""
    rows = [r for r in movers_rows if r.get("regulation_code") == regulation_code]
    if not rows:
        return None
    team_count = rows[0].get("team_count") or 0
    previous_team_count = rows[0].get("previous_team_count") or 0
    is_new = [r for r in rows if str(r.get("is_new_to_format")).lower() == "true"]
    carried = [r for r in rows if str(r.get("is_new_to_format")).lower() != "true"]
    risers = sorted(
        (r for r in carried if (r.get("usage_share_delta") or 0) > 0),
        key=lambda r: -(r.get("usage_share_delta") or 0),
    )
    fallers = sorted(
        (r for r in carried if (r.get("usage_share_delta") or 0) < 0),
        key=lambda r: r.get("usage_share_delta") or 0,
    )
    arrivals = sorted(
        (r for r in is_new if (r.get("usage_count") or 0) > 0),
        key=lambda r: -(r.get("usage_share") or 0),
    )
    return {
        "regulation_code": regulation_code,
        "previous_regulation_code": rows[0].get("previous_regulation_code"),
        "team_count": team_count,
        "previous_team_count": previous_team_count,
        "reliable": min(team_count, previous_team_count) >= MIN_MOVER_TEAMS,
        "risers": [_mover_row(r) for r in risers[:MAX_MOVERS_PER_LIST]],
        "fallers": [_mover_row(r) for r in fallers[:MAX_MOVERS_PER_LIST]],
        "new_arrivals": [_mover_row(r) for r in arrivals[:MAX_MOVERS_PER_LIST]],
    }


# docs/upgrade-plan-2027q1.md, C4 (finding 6): a previous regulation with
# fewer events than this is a thin baseline -- M-B is one elite Worlds field
# -- so the "What changed" panel defaults to comparing the selected
# regulation's own early and recent events instead.
MIN_BASELINE_EVENTS = 2
# A Pokémon below this share on both sides of an early-vs-recent comparison
# isn't a mover worth listing, whatever its delta.
MIN_WINDOW_MOVER_SHARE = 0.005


def summarize_event_window_movers(
    event_usage_rows: list[dict[str, Any]], events: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Risers and fallers between a regulation's early and recent events
    (C4): the newest half of its events (by date) against the rest, with
    shares of roster slots summed over each side from
    pokemon_event_usage_vs_regulation. None with fewer than two events.
    `reliable` follows the same MIN_MOVER_TEAMS floor as summarize_movers."""
    ordered = sorted(events, key=lambda e: (e.get("event_date") or "", e.get("event_id") or ""))
    if len(ordered) < 2:
        return None
    recent_count = len(ordered) // 2
    early_ids = [e["event_id"] for e in ordered[: len(ordered) - recent_count]]
    recent_ids = [e["event_id"] for e in ordered[len(ordered) - recent_count :]]

    def side(ids: list[str]) -> tuple[dict[str, int], int]:
        usage: dict[str, int] = {}
        slots: dict[str, int] = {}
        for row in event_usage_rows:
            if row.get("event_id") not in ids:
                continue
            usage[row["pokemon_key"]] = usage.get(row["pokemon_key"], 0) + (
                row.get("usage_count") or 0
            )
            slots[row["event_id"]] = row.get("event_slot_count") or 0
        return usage, sum(slots.values())

    early_usage, early_slots = side(early_ids)
    recent_usage, recent_slots = side(recent_ids)
    if not early_slots or not recent_slots:
        return None
    names = {r["pokemon_key"]: r.get("pokemon_name") for r in event_usage_rows}
    rows = []
    for key in set(early_usage) | set(recent_usage):
        early_share = early_usage.get(key, 0) / early_slots
        recent_share = recent_usage.get(key, 0) / recent_slots
        if max(early_share, recent_share) < MIN_WINDOW_MOVER_SHARE:
            continue
        rows.append(
            {
                "pokemon_key": key,
                "pokemon_name": names.get(key) or key,
                "usage_share": round(recent_share, 4),
                "previous_usage_share": round(early_share, 4),
                "usage_share_delta": round(recent_share - early_share, 4),
            }
        )
    by_id = {e["event_id"]: e for e in ordered}
    early_teams = sum(by_id[i].get("team_count") or 0 for i in early_ids)
    recent_teams = sum(by_id[i].get("team_count") or 0 for i in recent_ids)
    risers = sorted(
        (r for r in rows if r["usage_share_delta"] > 0), key=lambda r: -r["usage_share_delta"]
    )
    fallers = sorted(
        (r for r in rows if r["usage_share_delta"] < 0), key=lambda r: r["usage_share_delta"]
    )
    return {
        "early_events": [short_event_name(by_id[i].get("event_name")) for i in early_ids],
        "recent_events": [short_event_name(by_id[i].get("event_name")) for i in recent_ids],
        "team_count": recent_teams,
        "previous_team_count": early_teams,
        "reliable": min(early_teams, recent_teams) >= MIN_MOVER_TEAMS,
        "risers": risers[:MAX_MOVERS_PER_LIST],
        "fallers": fallers[:MAX_MOVERS_PER_LIST],
    }


def _current_regulation_kpi(
    legal_pool_by_regulation: list[dict[str, Any]],
    today: date | None,
    regulation_code: str | None = None,
    regulations: list[Regulation] | None = None,
) -> dict[str, Any] | None:
    """A regulation from dbt/seeds/champions_regulations.csv and its
    legal-pool size: `regulation_code` if given, otherwise the one in force
    today. This is what the header and the legal-pool KPI lead with, so the
    page always says which format it's describing."""
    regulations = load_regulations() if regulations is None else regulations
    if regulation_code is not None:
        regulation = next((r for r in regulations if r.regulation_code == regulation_code), None)
    else:
        regulation = regulation_in_force(regulations, today or date.today())
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
    marts: dict[str, list[dict[str, Any]]],
    today: date | None = None,
    scope: str = ALL_SCOPE,
    regulations: list[Regulation] | None = None,
) -> dict[str, Any]:
    """KPIs for one regulation scope. `marts` is expected to be cut down to
    that scope already (marts_for_scope); `scope` picks which regulation the
    legal-pool card describes and which movers summary is attached."""
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

    # docs/upgrade-plan-2027q1.md, U2: "5 events · 3,770 teams" tells every
    # reader how much data the page rests on, so it replaced the
    # distinct-Pokémon count as the first KPI.
    events = _events_in_scope(marts, scope)
    movers = (
        None
        if scope == ALL_SCOPE
        else summarize_movers(marts.get("pokemon_regulation_movers", []), scope)
    )
    if movers is not None:
        # The comparison regulation's own size, shown beside the heading
        # (C4, finding 6), and whether it is too thin to lead with.
        previous_events = _events_in_scope(marts, movers.get("previous_regulation_code") or "")
        movers["previous_event_count"] = len(previous_events)
        movers["event_count"] = len(events)
        movers["baseline_thin"] = (
            len(previous_events) < MIN_BASELINE_EVENTS
            or (movers.get("previous_team_count") or 0) < MIN_DEFAULT_SCOPE_TEAMS
        )

    return {
        "latest_snapshot_date": latest_snapshot_date,
        "legal_pool_by_regulation": legal_pool_by_regulation,
        "scope": scope,
        "event_count": len(events),
        "team_count": sum(e.get("team_count") or 0 for e in events),
        "latest_event": _latest_event(events),
        "starter_teams": starter_teams(marts, scope),
        "current_regulation": _current_regulation_kpi(
            legal_pool_by_regulation,
            today,
            None if scope == ALL_SCOPE else scope,
            regulations,
        ),
        "movers": movers,
        "window_movers": (
            None
            if scope == ALL_SCOPE
            else summarize_event_window_movers(
                marts.get("pokemon_event_usage_vs_regulation", []), events
            )
        ),
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


def default_scope_for(
    by_scope: dict[str, dict[str, Any]],
    regulations: list[Regulation],
    today: date,
) -> str:
    """The scope the page opens on (docs/upgrade-plan-2027q1.md, U3): the
    regulation in force today when it has at least MIN_DEFAULT_SCOPE_TEAMS
    teams on record; otherwise the newest earlier regulation with data (the
    first weeks of a new set); otherwise the newest regulation with data;
    otherwise "all". static/app.js re-applies this against the viewer's
    date, so a page built before a rollover still opens correctly after it."""
    with_data = [r for r in regulations if r.regulation_code in by_scope]
    in_force = regulation_in_force(regulations, today)
    if in_force is not None:
        kpis = by_scope.get(in_force.regulation_code)
        if kpis and (kpis.get("team_count") or 0) >= MIN_DEFAULT_SCOPE_TEAMS:
            return in_force.regulation_code
        earlier = [r for r in with_data if r.start_date < in_force.start_date]
        if earlier:
            return earlier[-1].regulation_code
        if kpis:
            return in_force.regulation_code
    if with_data:
        return with_data[-1].regulation_code
    return ALL_SCOPE


def compute_kpis_by_scope(
    marts: dict[str, list[dict[str, Any]]],
    today: date | None = None,
    regulations: list[Regulation] | None = None,
) -> tuple[dict[str, dict[str, Any]], str]:
    """KPIs for every regulation with usage data plus "all", and the scope
    the page should open on (see default_scope_for)."""
    regulations = load_regulations() if regulations is None else regulations
    usage_scopes = {r.get("regulation_scope") for r in marts.get("pokemon_usage_summary", [])}
    with_data = [r for r in regulations if r.regulation_code in usage_scopes]
    scopes = [r.regulation_code for r in with_data] + [ALL_SCOPE]
    by_scope = {
        scope: compute_kpis(marts_for_scope(marts, scope), today, scope, regulations)
        for scope in scopes
    }
    return by_scope, default_scope_for(by_scope, regulations, today or date.today())


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
    regulations: list[Regulation] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    regulations = load_regulations() if regulations is None else regulations
    marts = load_marts(marts_dir)
    pokemon_names = load_pokemon_names(normalized_dir)
    marts = _join_pokemon_names(marts, pokemon_names)
    marts["tournament_top_cut_teams"] = top_cut_teams(marts.get("tournament_team_results", []))
    marts["player_index"] = player_index(
        marts.get("tournament_team_results", []), marts.get("tournament_event_summary", [])
    )
    kpis_by_scope, default_scope = compute_kpis_by_scope(marts, today, regulations)
    return {
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        # The page swaps DATA.kpis for kpis_by_scope[<selected scope>] on
        # load (static/app.js); kpis is the default scope's, so anything
        # reading it directly (the template's first paint, tests) still
        # gets a coherent single-scope view.
        "kpis": kpis_by_scope[default_scope],
        "kpis_by_scope": kpis_by_scope,
        "default_scope": default_scope,
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
            for r in regulations
        ],
        # static/app.js's rollover rule reads the same threshold the build
        # used (see default_scope_for), rather than restating the number.
        "min_default_scope_teams": MIN_DEFAULT_SCOPE_TEAMS,
    }
