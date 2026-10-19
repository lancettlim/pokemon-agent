"""A small, coherent synthetic dataset for building the dashboard in tests.

Every mart pipelines/dashboard/data.py loads gets rows here, drawn from one
eight-Pokémon, three-event universe, so every route the dashboard serves has
something to render. Numbers are made up but internally consistent where a
view cross-checks them (shares sum sensibly, top cuts have placements, team
sheets match their team's roster).
"""

from __future__ import annotations

import csv
import itertools
from pathlib import Path

POKEMON = {
    # key: (name, type_1, type_2, hp, atk, def, spa, spd, spe)
    "rillaboom": ("Rillaboom", "grass", "", 100, 125, 90, 60, 70, 85),
    "sneasler": ("Sneasler", "fighting", "poison", 80, 130, 60, 40, 80, 120),
    "incineroar": ("Incineroar", "fire", "dark", 95, 115, 90, 80, 90, 60),
    "garchomp": ("Garchomp", "dragon", "ground", 108, 130, 95, 80, 85, 102),
    "kingambit": ("Kingambit", "dark", "steel", 100, 135, 120, 60, 85, 50),
    "gholdengo": ("Gholdengo", "steel", "ghost", 87, 60, 95, 133, 91, 84),
    "whimsicott": ("Whimsicott", "grass", "fairy", 60, 67, 85, 77, 75, 116),
    "pelipper": ("Pelipper", "water", "flying", 60, 50, 100, 95, 70, 65),
}
KEYS = list(POKEMON)

SETS = {
    "rillaboom": (
        "Miracle Seed",
        "Grassy Surge",
        "Adamant",
        "Fake Out|Grassy Glide|Wood Hammer|U-turn",
    ),
    "sneasler": ("Focus Sash", "Unburden", "Jolly", "Close Combat|Dire Claw|Fake Out|Protect"),
    "incineroar": (
        "Sitrus Berry",
        "Intimidate",
        "Careful",
        "Fake Out|Flare Blitz|Knock Off|Parting Shot",
    ),
    "garchomp": (
        "Choice Scarf",
        "Rough Skin",
        "Adamant",
        "Dragon Claw|Earthquake|Rock Slide|Stomping Tantrum",
    ),
    "kingambit": (
        "Black Glasses",
        "Defiant",
        "Adamant",
        "Iron Head|Kowtow Cleave|Protect|Sucker Punch",
    ),
    "gholdengo": (
        "Choice Specs",
        "Good as Gold",
        "Modest",
        "Make It Rain|Shadow Ball|Power Gem|Trick",
    ),
    "whimsicott": ("Covert Cloak", "Prankster", "Timid", "Moonblast|Protect|Tailwind|Encore"),
    "pelipper": ("Damp Rock", "Drizzle", "Bold", "Hurricane|Protect|Tailwind|Weather Ball"),
}

MOVES = {
    # name: (type, power, accuracy, category, priority, pp)
    "Fake Out": ("normal", 40, 100, "physical", 3, 10),
    "Grassy Glide": ("grass", 55, 100, "physical", 0, 20),
    "Wood Hammer": ("grass", 120, 100, "physical", 0, 15),
    "U-turn": ("bug", 70, 100, "physical", 0, 20),
    "Close Combat": ("fighting", 120, 100, "physical", 0, 5),
    "Dire Claw": ("poison", 80, 100, "physical", 0, 15),
    "Protect": ("normal", "", "", "status", 4, 10),
    "Flare Blitz": ("fire", 120, 100, "physical", 0, 15),
    "Knock Off": ("dark", 65, 100, "physical", 0, 20),
    "Parting Shot": ("dark", "", 100, "status", 0, 20),
    "Dragon Claw": ("dragon", 80, 100, "physical", 0, 15),
    "Earthquake": ("ground", 100, 100, "physical", 0, 10),
    "Rock Slide": ("rock", 75, 90, "physical", 0, 10),
    "Stomping Tantrum": ("ground", 75, 100, "physical", 0, 10),
    "Iron Head": ("steel", 80, 100, "physical", 0, 15),
    "Kowtow Cleave": ("dark", 85, "", "physical", 0, 10),
    "Sucker Punch": ("dark", 70, 100, "physical", 1, 5),
    "Make It Rain": ("steel", 120, 95, "special", 0, 5),
    "Shadow Ball": ("ghost", 80, 100, "special", 0, 15),
    "Power Gem": ("rock", 80, 100, "special", 0, 20),
    "Trick": ("psychic", "", 100, "status", 0, 10),
    "Moonblast": ("fairy", 95, 100, "special", 0, 15),
    "Tailwind": ("flying", "", "", "status", 0, 15),
    "Encore": ("normal", "", 100, "status", 0, 5),
    "Hurricane": ("flying", 110, 70, "special", 0, 10),
    "Weather Ball": ("normal", 50, 100, "special", 0, 10),
}

# event_id: (name, date, tier, regulation, team_count)
EVENTS = {
    "EVT-WCS": ("2026 Pokémon VGC World Championship", "2026-08-28", "Worlds", "m-b", 395),
    "EVT-BAL": (
        "2027 Baltimore Pokémon VGC Regional Championships",
        "2026-09-18",
        "Regional",
        "m-c",
        350,
    ),
    "EVT-LOU": (
        "2027 Louisville Pokémon VGC Regional Championships",
        "2026-10-09",
        "Regional",
        "m-c",
        360,
    ),
}
TEAMS_PER_EVENT = 12
SCOPES = ("m-b", "m-c", "all")


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _rosters() -> list[dict]:
    """TEAMS_PER_EVENT teams per event; each a rotating six of the eight."""
    teams = []
    combos = list(itertools.combinations(KEYS, 6))
    for event_index, event_id in enumerate(EVENTS):
        for i in range(TEAMS_PER_EVENT):
            keys = list(combos[(event_index * 5 + i) % len(combos)])
            wins = 9 - i // 2
            teams.append(
                {
                    "team_id": f"{event_id}-T{i + 1:02d}",
                    "event_id": event_id,
                    "player_id": f"P{i:03d}",
                    "player_name": f"Player {i + 1}",
                    "player_country": ("US", "JP", "GB", "BR")[i % 4],
                    "placement": i + 1,
                    "record_wins": wins,
                    "record_losses": 9 - wins + 1,
                    "keys": keys,
                }
            )
    return teams


def write_fixture_marts(marts_dir: Path, normalized_dir: Path) -> None:
    teams = _rosters()
    _write(
        normalized_dir / "pokemon.csv",
        [{"pokemon_key": key, "pokemon_name": key} for key in KEYS],
    )

    def scoped(fn):
        return [row for scope in SCOPES for row in fn(scope)]

    def share(i):
        return round(0.1 - i * 0.008, 4)

    _write(
        marts_dir / "pokemon_usage_summary.csv",
        scoped(
            lambda scope: [
                {
                    "regulation_scope": scope,
                    "pokemon_key": key,
                    "event_tier": tier,
                    "usage_count": 60 - i * 5,
                    "usage_share": share(i),
                    "usage_rank": i + 1,
                }
                for tier in ("", "Regional")
                for i, key in enumerate(KEYS)
            ]
        ),
    )
    _write(
        marts_dir / "pokemon_win_rate_summary.csv",
        scoped(
            lambda scope: [
                {
                    "regulation_scope": scope,
                    "pokemon_key": key,
                    "total_wins": 120 - i * 7,
                    "total_losses": 100 + i * 3,
                    "win_rate": round(0.56 - i * 0.015, 4),
                    "record_count": 60 - i * 5,
                    "wilson_lower_bound": round(0.44 - i * 0.015, 4),
                    "wilson_rank": i + 1,
                }
                for i, key in enumerate(KEYS)
            ]
        ),
    )
    _write(
        marts_dir / "pokemon_item_usage.csv",
        scoped(
            lambda scope: [
                {
                    "regulation_scope": scope,
                    "pokemon_key": key,
                    "item_name": item,
                    "short_effect": "Fixture effect text.",
                    "usage_count": count,
                    "item_share": round(count / 50, 4),
                    "usage_rank": rank,
                }
                for key in KEYS
                for rank, (item, count) in enumerate(
                    (
                        (SETS[key][0], 35),
                        ("Sitrus Berry" if SETS[key][0] != "Sitrus Berry" else "Leftovers", 15),
                    ),
                    start=1,
                )
            ]
        ),
    )
    _write(
        marts_dir / "pokemon_ability_usage.csv",
        scoped(
            lambda scope: [
                {
                    "regulation_scope": scope,
                    "pokemon_key": key,
                    "ability": SETS[key][1],
                    "short_effect": "Fixture ability text.",
                    "usage_count": 50,
                    "ability_share": 1.0,
                    "usage_rank": 1,
                }
                for key in KEYS
            ]
        ),
    )
    _write(
        marts_dir / "pokemon_nature_usage.csv",
        scoped(
            lambda scope: [
                {
                    "regulation_scope": scope,
                    "pokemon_key": key,
                    "nature": SETS[key][2],
                    "usage_count": 50,
                    "nature_share": 1.0,
                    "usage_rank": 1,
                }
                for key in KEYS
            ]
        ),
    )

    def move_rows(scope):
        rows = []
        for key in KEYS:
            for rank, move in enumerate(SETS[key][3].split("|"), start=1):
                move_type, power, accuracy, category, priority, pp = MOVES[move]
                rows.append(
                    {
                        "regulation_scope": scope,
                        "pokemon_key": key,
                        "move_name": move,
                        "move_type": move_type,
                        "power": power,
                        "accuracy": accuracy,
                        "category": category,
                        "priority": priority,
                        "pp": pp,
                        "short_effect": "Fixture move text.",
                        "usage_count": 50 - rank * 5,
                        "move_share": round(0.3 - rank * 0.05, 4),
                        "usage_rank": rank,
                    }
                )
        return rows

    _write(marts_dir / "pokemon_move_usage.csv", scoped(move_rows))

    def partner_rows(scope):
        rows = []
        for key in KEYS:
            partners = [k for k in KEYS if k != key]
            for rank, partner in enumerate(partners, start=1):
                rows.append(
                    {
                        "regulation_scope": scope,
                        "pokemon_key": key,
                        "partner_pokemon_key": partner,
                        "co_occurrence_count": 40 - rank * 3,
                        "partner_share": round(0.5 - rank * 0.05, 4),
                        "usage_rank": rank,
                    }
                )
        return rows

    _write(marts_dir / "pokemon_team_core_usage.csv", scoped(partner_rows))
    _write(
        marts_dir / "pokemon_team_synergy.csv",
        scoped(
            lambda scope: [
                {
                    "regulation_scope": scope,
                    "pokemon_key": row["pokemon_key"],
                    "partner_pokemon_key": row["partner_pokemon_key"],
                    "pair_team_count": row["co_occurrence_count"],
                    "lift": round(1.8 - row["usage_rank"] * 0.1, 3),
                    "lift_rank": row["usage_rank"],
                }
                for row in partner_rows(scope)
            ]
        ),
    )
    _write(
        marts_dir / "pokemon_team_core_triple_usage.csv",
        [
            {
                "pokemon_key_a": a,
                "pokemon_key_b": b,
                "pokemon_key_c": c,
                "triple_team_count": 20 - i,
                "player_count": 18 - i,
                "event_count": 3,
                "triple_team_share": round(0.2 - i * 0.01, 4),
                "expected_team_share": 0.05,
                "triple_lift": round(2.5 - i * 0.1, 3),
                "min_pair_lift": 1.2,
                "avg_pair_lift": 1.4,
                "total_wins": 80,
                "total_losses": 60,
                "win_rate": 0.5714,
                "avg_placement": 6.5,
                "support_rank": i + 1,
                "lift_rank": i + 1,
            }
            for i, (a, b, c) in enumerate(
                itertools.islice(itertools.combinations(sorted(KEYS), 3), 10)
            )
        ],
    )

    def profile_rows(scope, speed_tiers=False):
        rows = []
        for i, key in enumerate(KEYS):
            name, type_1, type_2, hp, atk, df, spa, spd, spe = POKEMON[key]
            max_speed = int((2 * spe + 31 + 63) * 50 / 100 + 5) * 11 // 10
            row = {
                "regulation_scope": scope,
                "pokemon_key": key,
                "type_1": type_1,
                "type_2": type_2,
            }
            if speed_tiers:
                row.update(
                    {
                        "base_speed": spe,
                        "max_investment_speed": max_speed,
                        "plus_one_speed": max_speed * 3 // 2,
                        "scarf_speed": max_speed * 3 // 2,
                        "plus_two_speed": max_speed * 2,
                        "tailwind_speed": max_speed * 2,
                        "scarf_tailwind_speed": max_speed * 3,
                    }
                )
            else:
                row.update(
                    {
                        "hp": hp,
                        "attack": atk,
                        "defense": df,
                        "sp_attack": spa,
                        "sp_defense": spd,
                        "speed": spe,
                        "max_investment_speed": max_speed,
                        "stat_total": hp + atk + df + spa + spd + spe,
                    }
                )
            row.update(
                {
                    "usage_count": 60 - i * 5,
                    "usage_share": share(i),
                    "win_rate": round(0.56 - i * 0.015, 4),
                    "record_count": 60 - i * 5,
                }
            )
            rows.append(row)
        return rows

    _write(marts_dir / "pokemon_champions_profile.csv", scoped(profile_rows))
    _write(
        marts_dir / "pokemon_speed_tiers.csv",
        scoped(lambda scope: profile_rows(scope, speed_tiers=True)),
    )
    _write(
        marts_dir / "pokemon_build_concentration.csv",
        scoped(
            lambda scope: [
                {
                    "regulation_scope": scope,
                    "pokemon_key": key,
                    "item_hhi": 0.58,
                    "item_count": 2,
                    "ability_hhi": 1.0,
                    "ability_count": 1,
                }
                for key in KEYS
            ]
        ),
    )
    _write(
        marts_dir / "pokemon_placement_weighted_usage.csv",
        scoped(
            lambda scope: [
                {
                    "regulation_scope": scope,
                    "pokemon_key": key,
                    "usage_count": 60 - i * 5,
                    "top_cut_usage_count": 8 - i // 2,
                    "top_cut_usage_share": round(0.12 - i * 0.01, 4),
                    "placement_weighted_score": 3.2 - i * 0.2,
                    "weighted_usage_share": round(0.11 - i * 0.009, 4),
                    "weighted_usage_rank": i + 1,
                }
                for i, key in enumerate(KEYS)
            ]
        ),
    )

    def set_rows(scope):
        rows = []
        for key in KEYS:
            item, ability, nature, moves = SETS[key]
            sorted_moves = "|".join(sorted(moves.split("|")))
            for level in ("full", "core"):
                for rank in (1, 2):
                    rows.append(
                        {
                            "regulation_scope": scope,
                            "pokemon_key": key,
                            "set_level": level,
                            "set_rank": rank,
                            "item_name": item if rank == 1 else "Sitrus Berry",
                            "ability": ability,
                            "nature": nature if level == "full" else "",
                            "moves": sorted_moves
                            if level == "full"
                            else "|".join(sorted(moves.split("|")[:3])),
                            "team_count": 30 if rank == 1 else 12,
                            "pokemon_slot_count": 60,
                            "share_of_pokemon": 0.5 if rank == 1 else 0.2,
                            "total_wins": 150,
                            "total_losses": 120,
                            "record_count": 30 if rank == 1 else 12,
                            "win_rate": 0.5556,
                            "wilson_lower_bound": 0.38,
                            "example_team_id": "EVT-LOU-T01",
                        }
                    )
        return rows

    _write(marts_dir / "pokemon_set_variants.csv", scoped(set_rows))

    _write(
        marts_dir / "legality_summary_by_regulation.csv",
        [
            {
                "regulation_code": code,
                "snapshot_date": "2026-10-19",
                "legal_pokemon_count": count,
                "cumulative_legal_pokemon_count": count,
            }
            for code, count in (("m-a", 6), ("m-b", 7), ("m-c", 8))
        ],
    )
    _write(
        marts_dir / "pokemon_usage_by_regulation.csv",
        [
            {
                "regulation_code": code,
                "pokemon_key": key,
                "usage_count": 50 - i * 4,
                "usage_share": share(i) + (0.01 if code == "m-b" else 0),
                "usage_rank": i + 1,
                "win_rate": round(0.55 - i * 0.01, 4),
                "record_count": 50 - i * 4,
            }
            for code in ("m-b", "m-c")
            for i, key in enumerate(KEYS)
        ],
    )
    _write(
        marts_dir / "pokemon_regulation_movers.csv",
        [
            {
                "regulation_code": "m-c",
                "previous_regulation_code": "m-b",
                "pokemon_key": key,
                "usage_count": 60 - i * 5,
                "usage_share": share(i),
                "usage_rank": i + 1,
                "previous_usage_count": 0 if key == "pelipper" else 50,
                "previous_usage_share": 0 if key == "pelipper" else round(0.09 - (i % 3) * 0.02, 4),
                "previous_usage_rank": "" if key == "pelipper" else 8 - i,
                "usage_share_delta": round(share(i) - (0.09 - (i % 3) * 0.02), 4),
                "rank_change": i - 3,
                "win_rate": 0.53,
                "previous_win_rate": 0.5,
                "win_rate_delta": 0.03,
                "record_count": 50,
                "previous_record_count": 40,
                "is_new_to_format": "true" if key == "pelipper" else "false",
                "team_count": 710,
                "previous_team_count": 395,
            }
            for i, key in enumerate(KEYS)
        ],
    )
    _write(
        marts_dir / "pokemon_usage_by_event_date.csv",
        [
            {
                "pokemon_key": key,
                "event_date": event[1],
                "usage_count": 30 - i * 2,
                "usage_share": share(i),
                "usage_rank": i + 1,
            }
            for event in EVENTS.values()
            for i, key in enumerate(KEYS)
        ],
    )
    _write(
        marts_dir / "pokemon_head_to_head.csv",
        [
            {
                "pokemon_key": a,
                "opponent_pokemon_key": b,
                "matches_played": 40,
                "wins": 22 if a < b else 18,
                "losses": 18 if a < b else 22,
                "win_rate": 0.55 if a < b else 0.45,
                "wilson_lower_bound": 0.39 if a < b else 0.3,
                "matchup_rank": 1,
            }
            for a in KEYS
            for b in KEYS
            if a != b
        ],
    )
    _write(
        marts_dir / "pokemon_matchup_summary.csv",
        [
            {
                "pokemon_key": key,
                "overall_win_rate": 0.52,
                "distinct_opponents": 7,
                "total_matchup_appearances": 280,
                "best_matchup_pokemon_key": KEYS[(i + 1) % 8],
                "best_matchup_win_rate": 0.6,
                "best_matchup_matches": 40,
                "worst_matchup_pokemon_key": KEYS[(i + 2) % 8],
                "worst_matchup_win_rate": 0.4,
                "worst_matchup_matches": 40,
                "min_matches_threshold": 10,
            }
            for i, key in enumerate(KEYS)
        ],
    )
    _write(
        marts_dir / "pokemon_usage_by_country.csv",
        [
            {
                "pokemon_key": key,
                "player_country": country,
                "usage_count": 20 - i,
                "usage_share": share(i),
                "country_usage_rank": i + 1,
            }
            for country in ("US", "JP", "GB")
            for i, key in enumerate(KEYS)
        ],
    )
    _write(
        marts_dir / "player_signature_pokemon.csv",
        [
            {
                "player_id": f"P{p:03d}",
                "player_name": f"Player {p + 1}",
                "player_country": ("US", "JP", "GB", "BR")[p % 4],
                "player_team_count": 3,
                "pokemon_key": key,
                "usage_count": 3 - rank // 3,
                "player_usage_share": round((3 - rank // 3) / 18, 4),
                "player_pokemon_rank": rank + 1,
            }
            for p in range(4)
            for rank, key in enumerate(KEYS[:6])
        ],
    )
    _write(
        marts_dir / "detected_archetype_summary.csv",
        [
            {
                "archetype_key": f"arch-{i}",
                "anchor_candidate_key": f"cand-{i}",
                "pokemon_key_a": a,
                "pokemon_key_b": b,
                "pokemon_key_c": c,
                "candidate_count": 2,
                "team_count": 30 - i * 5,
                "player_count": 28 - i * 5,
                "event_count": 3,
                "team_share": round(0.08 - i * 0.01, 4),
                "total_wins": 150,
                "total_losses": 140,
                "win_rate": 0.5172,
                "avg_placement": 7.5,
                "top_extension_pokemon_key": "pelipper",
                "extension_team_count": 10,
                "top_extension_share": 0.33,
                "stability_label": "cross-event",
                "archetype_rank": i + 1,
            }
            for i, (a, b, c) in enumerate(
                (
                    ("garchomp", "incineroar", "rillaboom"),
                    ("gholdengo", "kingambit", "sneasler"),
                    ("pelipper", "whimsicott", "garchomp"),
                )
            )
        ],
    )
    _write(
        marts_dir / "roster_source_agreement.csv",
        [
            {
                "event_id": event_id,
                "event_name": event[0],
                "covered_players": 64,
                "exact_agreement_players": 60,
                "exact_agreement_rate": 0.9375,
                "slot_agreement_rate": 0.98,
            }
            for event_id, event in EVENTS.items()
        ],
    )
    _write(
        marts_dir / "team_list_convergence.csv",
        [
            {
                "team_list_id": f"TL{i}",
                "player_count": 5 - i,
                "tournament_count": 2,
                "best_placement": i + 1,
                "first_seen_date": "2026-09-18",
                "regulation_set": "m-c",
                "pokemon_keys": "|".join(KEYS[i : i + 6]),
                "roster_size": 6,
                "convergence_rank": i + 1,
            }
            for i in range(3)
        ],
    )
    _write(
        marts_dir / "top_tournament_teams.csv",
        [
            {
                "regulation_scope": scope,
                "team_id": team["team_id"],
                "event_name": EVENTS[team["event_id"]][0],
                "event_tier": EVENTS[team["event_id"]][2],
                "event_date": EVENTS[team["event_id"]][1],
                "player_name": team["player_name"],
                "player_country": team["player_country"],
                "placement": team["placement"],
                "record_wins": team["record_wins"],
                "record_losses": team["record_losses"],
                "win_rate": round(
                    team["record_wins"] / (team["record_wins"] + team["record_losses"]), 4
                ),
                "pokemon_keys": "|".join(team["keys"]),
                "team_rank": rank,
            }
            for scope in SCOPES
            for rank, team in enumerate(
                sorted(
                    (t for t in teams if scope == "all" or EVENTS[t["event_id"]][3] == scope),
                    key=lambda t: (-t["record_wins"], t["team_id"]),
                ),
                start=1,
            )
        ],
    )

    winners = {t["event_id"]: t for t in teams if t["placement"] == 1}
    _write(
        marts_dir / "tournament_event_summary.csv",
        [
            {
                "event_id": event_id,
                "event_name": name,
                "event_date": date,
                "event_tier": tier,
                "regulation_code": regulation,
                "team_count": team_count,
                "player_count": team_count,
                "recorded_team_count": team_count,
                "match_count": team_count * 4,
                "winner_team_id": winners[event_id]["team_id"],
                "winner_player_name": winners[event_id]["player_name"],
                "winner_player_country": winners[event_id]["player_country"],
                "winner_record_wins": winners[event_id]["record_wins"],
                "winner_record_losses": winners[event_id]["record_losses"],
                "winner_pokemon_keys": "|".join(winners[event_id]["keys"]),
                "source_name": "MunchStats",
                "source_url": "https://example.invalid/munchstats",
                "pairings_url": f"https://rk9.gg/pairings/{event_id}",
                "recency_rank": 1,
            }
            for event_id, (name, date, tier, regulation, team_count) in EVENTS.items()
        ],
    )
    _write(
        marts_dir / "tournament_team_results.csv",
        [
            {
                "team_id": team["team_id"],
                "event_id": team["event_id"],
                "event_name": EVENTS[team["event_id"]][0],
                "event_date": EVENTS[team["event_id"]][1],
                "event_tier": EVENTS[team["event_id"]][2],
                "regulation_code": EVENTS[team["event_id"]][3],
                "player_id": team["player_id"],
                "player_name": team["player_name"],
                "player_country": team["player_country"],
                "placement": team["placement"],
                "event_team_count": EVENTS[team["event_id"]][4],
                "record_wins": team["record_wins"],
                "record_losses": team["record_losses"],
                "win_rate": round(
                    team["record_wins"] / (team["record_wins"] + team["record_losses"]), 4
                ),
                "pokemon_keys": "|".join(team["keys"]),
                "roster_size": 6,
                "is_fully_reported": "true",
                "primary_archetype_key": "arch-0" if team["placement"] % 2 else "arch-1",
            }
            for team in teams
        ],
    )
    _write(
        marts_dir / "tournament_team_sheets.csv",
        [
            {
                "team_id": team["team_id"],
                "slot_number": slot,
                "pokemon_key": key,
                "item_name": SETS[key][0],
                "ability": SETS[key][1],
                "nature": SETS[key][2],
                "moves": SETS[key][3],
            }
            for team in teams
            for slot, key in enumerate(team["keys"], start=1)
        ],
    )
    _write(
        marts_dir / "pokemon_event_usage_vs_regulation.csv",
        [
            {
                "regulation_code": regulation,
                "event_id": event_id,
                "event_date": date,
                "pokemon_key": key,
                "usage_count": 40 - i * 3 + (5 if event_id == "EVT-LOU" else 0),
                "event_slot_count": team_count * 6,
                "event_team_count": team_count,
                "event_usage_share": round(share(i) + (0.02 if i % 2 else -0.02), 4),
                "regulation_usage_share": share(i),
                "usage_share_delta": 0.02 if i % 2 else -0.02,
                "total_wins": 100,
                "total_losses": 90,
            }
            for event_id, (_, date, _, regulation, team_count) in EVENTS.items()
            for i, key in enumerate(KEYS)
        ],
    )
    _write(
        marts_dir / "team_list_sheets.csv",
        [
            {
                "team_list_id": f"TL{i}",
                "slot_number": slot,
                "pokemon_key": key,
                "item_name": SETS[key][0],
                "ability": SETS[key][1],
                "nature": SETS[key][2],
                "moves": SETS[key][3],
            }
            for i in range(3)
            for slot, key in enumerate(KEYS[i : i + 6], start=1)
        ],
    )
    _write(
        marts_dir / "player_archetype_record.csv",
        [
            {
                "player_id": f"P{p:03d}",
                "regulation_code": "m-c",
                "opponent_archetype_key": f"arch-{a}",
                "matches_played": 4,
                "wins": 3 - a,
                "losses": 1 + a,
                "win_rate": (3 - a) / 4,
            }
            for p in range(4)
            for a in range(2)
        ],
    )
