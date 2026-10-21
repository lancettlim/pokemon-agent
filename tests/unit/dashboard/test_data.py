import csv
import json

from pipelines.dashboard import data


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_load_mart_returns_empty_list_when_file_missing(tmp_path):
    assert data.load_mart(tmp_path, "pokemon_usage_summary") == []


def test_load_mart_coerces_numeric_fields(tmp_path):
    _write_csv(
        tmp_path / "pokemon_win_rate_summary.csv",
        [
            {
                "pokemon_key": "pikachu",
                "total_wins": "10",
                "total_losses": "5",
                "win_rate": "0.6667",
                "record_count": "15",
                "wilson_lower_bound": "0.4",
                "wilson_rank": "1",
            }
        ],
    )
    rows = data.load_mart(tmp_path, "pokemon_win_rate_summary")
    assert rows == [
        {
            "pokemon_key": "pikachu",
            "total_wins": 10,
            "total_losses": 5,
            "win_rate": 0.6667,
            "record_count": 15,
            "wilson_lower_bound": 0.4,
            "wilson_rank": 1,
        }
    ]


def test_display_name():
    assert data.display_name("pikachu") == "Pikachu"
    assert data.display_name("landorus-therian", "landorus") == "Landorus (Therian)"
    assert data.display_name("charizard-mega-x", "charizard") == "Mega Charizard X"
    assert data.display_name("absol-mega-z", "absol") == "Mega Absol Z"
    assert data.display_name("basculegion-male", "basculegion") == "Basculegion \u2642"
    assert data.display_name("meowstic-female-mega", "meowstic") == "Mega Meowstic \u2640"
    assert data.display_name("ninetales-alola", "ninetales") == "Alolan Ninetales"
    assert data.display_name("tauros-paldea-blaze-breed", "tauros") == "Paldean Tauros (Blaze)"
    assert data.display_name("great-tusk", "great-tusk") == "Great Tusk"
    assert data.display_name("porygon-z", "porygon-z") == "Porygon-Z"
    assert data.display_name("mr-mime-galar", "mr-mime") == "Galarian Mr. Mime"


def test_display_name_without_species_assumes_first_token():
    assert data.display_name("rotom-wash") == "Rotom (Wash)"


def test_load_pokemon_names_returns_empty_dict_when_file_missing(tmp_path):
    assert data.load_pokemon_names(tmp_path) == {}


def test_load_pokemon_names(tmp_path):
    # Display names are derived from pokemon_key (== form_name), not the
    # species-only pokemon_name column — landorus-therian's species-level
    # pokemon_name would just be "Landorus", which would collide with
    # Landorus-Incarnate's row if used directly.
    _write_csv(
        tmp_path / "pokemon.csv",
        [
            {"pokemon_key": "pikachu", "pokemon_name": "Pikachu"},
            {"pokemon_key": "landorus-therian", "pokemon_name": "Landorus"},
        ],
    )
    assert data.load_pokemon_names(tmp_path) == {
        "pikachu": "Pikachu",
        "landorus-therian": "Landorus (Therian)",
    }


def test_build_payload_joins_pokemon_names_and_computes_kpis(tmp_path):
    marts_dir = tmp_path / "marts"
    normalized_dir = tmp_path / "normalized"
    _write_csv(
        normalized_dir / "pokemon.csv",
        [{"pokemon_key": "pikachu", "pokemon_name": "Pikachu"}],
    )
    _write_csv(
        marts_dir / "pokemon_usage_summary.csv",
        [{"pokemon_key": "pikachu", "event_tier": "", "usage_count": "100", "usage_rank": "1"}],
    )
    # legality_summary_by_regulation, stat_change_leaderboard, etc. are left
    # unpopulated on purpose to exercise the missing-mart-file path.
    payload = data.build_payload(marts_dir, normalized_dir)

    assert payload["marts"]["pokemon_usage_summary"] == [
        {
            "pokemon_key": "pikachu",
            "event_tier": "",
            "usage_count": 100,
            "usage_rank": 1,
            "pokemon_name": "Pikachu",
        }
    ]
    assert payload["kpis"]["distinct_pokemon_used"] == 1
    assert payload["kpis"]["top_used_pokemon"]["pokemon_name"] == "Pikachu"
    assert payload["pokemon_names"] == {"pikachu": "Pikachu"}
    assert "generated_at_utc" in payload


def test_load_mart_coerces_usage_share(tmp_path):
    _write_csv(
        tmp_path / "pokemon_usage_summary.csv",
        [
            {
                "pokemon_key": "pikachu",
                "event_tier": "",
                "usage_count": "3",
                "usage_share": "0.75",
                "usage_rank": "1",
            }
        ],
    )
    rows = data.load_mart(tmp_path, "pokemon_usage_summary")
    assert rows[0]["usage_share"] == 0.75


def test_load_mart_coerces_champions_profile_fields(tmp_path):
    _write_csv(
        tmp_path / "pokemon_champions_profile.csv",
        [
            {
                "pokemon_key": "pikachu",
                "hp": "35",
                "attack": "55",
                "defense": "40",
                "sp_attack": "50",
                "sp_defense": "50",
                "speed": "90",
                "stat_total": "320",
                "usage_count": "3",
                "usage_share": "0.75",
                "win_rate": "0.6",
                "record_count": "5",
            }
        ],
    )
    rows = data.load_mart(tmp_path, "pokemon_champions_profile")
    assert rows == [
        {
            "pokemon_key": "pikachu",
            "hp": 35,
            "attack": 55,
            "defense": 40,
            "sp_attack": 50,
            "sp_defense": 50,
            "speed": 90,
            "stat_total": 320,
            "usage_count": 3,
            "usage_share": 0.75,
            "win_rate": 0.6,
            "record_count": 5,
        }
    ]


def test_load_mart_coerces_team_core_usage_fields(tmp_path):
    _write_csv(
        tmp_path / "pokemon_team_core_usage.csv",
        [
            {
                "pokemon_key": "pikachu",
                "partner_pokemon_key": "raichu",
                "co_occurrence_count": "3",
                "partner_share": "0.75",
                "usage_rank": "1",
            }
        ],
    )
    rows = data.load_mart(tmp_path, "pokemon_team_core_usage")
    assert rows == [
        {
            "pokemon_key": "pikachu",
            "partner_pokemon_key": "raichu",
            "co_occurrence_count": 3,
            "partner_share": 0.75,
            "usage_rank": 1,
        }
    ]


def test_load_mart_coerces_team_core_triple_fields(tmp_path):
    _write_csv(
        tmp_path / "pokemon_team_core_triple_usage.csv",
        [
            {
                "pokemon_key_a": "archaludon",
                "pokemon_key_b": "pelipper",
                "pokemon_key_c": "rillaboom",
                "triple_team_count": "12",
                "player_count": "11",
                "event_count": "3",
                "triple_team_share": "0.021",
                "expected_team_share": "0.004",
                "triple_lift": "5.25",
                "min_pair_lift": "1.2",
                "avg_pair_lift": "2.4",
                "total_wins": "80",
                "total_losses": "40",
                "win_rate": "0.6667",
                "avg_placement": "18.5",
                "support_rank": "2",
                "lift_rank": "8",
            }
        ],
    )

    row = data.load_mart(tmp_path, "pokemon_team_core_triple_usage")[0]

    assert row["triple_team_count"] == 12
    assert row["event_count"] == 3
    assert row["triple_lift"] == 5.25
    assert row["avg_placement"] == 18.5


def test_load_mart_coerces_detected_archetype_summary_fields(tmp_path):
    _write_csv(
        tmp_path / "detected_archetype_summary.csv",
        [
            {
                "archetype_key": "detected-rain",
                "pokemon_key_a": "archaludon",
                "pokemon_key_b": "pelipper",
                "pokemon_key_c": "rillaboom",
                "candidate_count": "3",
                "team_count": "20",
                "player_count": "18",
                "event_count": "3",
                "team_share": "0.04",
                "total_wins": "120",
                "total_losses": "80",
                "win_rate": "0.6",
                "avg_placement": "24.2",
                "top_extension_pokemon_key": "incineroar",
                "extension_team_count": "12",
                "top_extension_share": "0.6",
                "stability_label": "cross-event",
                "archetype_rank": "1",
            }
        ],
    )

    row = data.load_mart(tmp_path, "detected_archetype_summary")[0]

    assert row["team_count"] == 20
    assert row["team_share"] == 0.04
    assert row["top_extension_share"] == 0.6


def test_detected_archetype_payload_keeps_only_ranked_cross_event_groups(tmp_path):
    rows = []
    for rank in range(1, data.MAX_DETECTED_ARCHETYPES + 3):
        rows.append(
            {
                "archetype_key": f"stable-{rank}",
                "team_count": "20",
                "player_count": "18",
                "event_count": "3",
                "team_share": "0.04",
                "stability_label": "cross-event",
                "archetype_rank": str(rank),
            }
        )
    rows.append(
        {
            "archetype_key": "emerging",
            "team_count": "5",
            "player_count": "5",
            "event_count": "1",
            "team_share": "0.001",
            "stability_label": "emerging",
            "archetype_rank": "0",
        }
    )
    _write_csv(tmp_path / "detected_archetype_summary.csv", rows)

    sliced = data.load_mart(tmp_path, "detected_archetype_summary")

    assert len(sliced) == data.MAX_DETECTED_ARCHETYPES
    assert sliced[0]["archetype_key"] == "stable-1"
    assert all(row["stability_label"] == "cross-event" for row in sliced)


def test_load_mart_coerces_usage_by_event_date_fields(tmp_path):
    _write_csv(
        tmp_path / "pokemon_usage_by_event_date.csv",
        [
            {
                "pokemon_key": "incineroar",
                "event_date": "2026-07-01",
                "usage_count": "40",
                "usage_share": "0.4",
                "usage_rank": "1",
            }
        ],
    )
    rows = data.load_mart(tmp_path, "pokemon_usage_by_event_date")
    assert rows == [
        {
            "pokemon_key": "incineroar",
            "event_date": "2026-07-01",
            "usage_count": 40,
            "usage_share": 0.4,
            "usage_rank": 1,
        }
    ]


def test_load_mart_coerces_legality_cumulative_field(tmp_path):
    _write_csv(
        tmp_path / "legality_summary_by_regulation.csv",
        [
            {
                "regulation_code": "m-b",
                "snapshot_date": "2026-01-01",
                "legal_pokemon_count": "39",
                "cumulative_legal_pokemon_count": "307",
            }
        ],
    )
    rows = data.load_mart(tmp_path, "legality_summary_by_regulation")
    assert rows == [
        {
            "regulation_code": "m-b",
            "snapshot_date": "2026-01-01",
            "legal_pokemon_count": 39,
            "cumulative_legal_pokemon_count": 307,
        }
    ]


def test_load_mart_coerces_item_and_ability_usage_fields(tmp_path):
    _write_csv(
        tmp_path / "pokemon_item_usage.csv",
        [
            {
                "pokemon_key": "pikachu",
                "item_name": "Light Ball",
                "short_effect": "Doubles Attack and Special Attack.",
                "usage_count": "10",
                "item_share": "0.8",
                "usage_rank": "1",
            }
        ],
    )
    _write_csv(
        tmp_path / "pokemon_ability_usage.csv",
        [
            {
                "pokemon_key": "pikachu",
                "ability": "Static",
                "short_effect": "May paralyze on contact.",
                "usage_count": "10",
                "ability_share": "1.0",
                "usage_rank": "1",
            }
        ],
    )
    assert data.load_mart(tmp_path, "pokemon_item_usage") == [
        {
            "pokemon_key": "pikachu",
            "item_name": "Light Ball",
            "short_effect": "Doubles Attack and Special Attack.",
            "usage_count": 10,
            "item_share": 0.8,
            "usage_rank": 1,
        }
    ]
    assert data.load_mart(tmp_path, "pokemon_ability_usage") == [
        {
            "pokemon_key": "pikachu",
            "ability": "Static",
            "short_effect": "May paralyze on contact.",
            "usage_count": 10,
            "ability_share": 1.0,
            "usage_rank": 1,
        }
    ]


def test_load_mart_coerces_move_usage_detail_fields(tmp_path):
    _write_csv(
        tmp_path / "pokemon_move_usage.csv",
        [
            {
                "pokemon_key": "pikachu",
                "move_name": "Thunderbolt",
                "move_type": "electric",
                "power": "90",
                "accuracy": "100",
                "category": "special",
                "priority": "0",
                "pp": "15",
                "short_effect": "Has a 10% chance to paralyze.",
                "usage_count": "10",
                "move_share": "0.8",
                "usage_rank": "1",
            }
        ],
    )
    rows = data.load_mart(tmp_path, "pokemon_move_usage")
    assert rows == [
        {
            "pokemon_key": "pikachu",
            "move_name": "Thunderbolt",
            "move_type": "electric",
            "power": 90,
            "accuracy": 100,
            "category": "special",
            "priority": 0,
            "pp": 15,
            "short_effect": "Has a 10% chance to paralyze.",
            "usage_count": 10,
            "move_share": 0.8,
            "usage_rank": 1,
        }
    ]


def test_load_mart_coerces_top_tournament_teams_fields(tmp_path):
    _write_csv(
        tmp_path / "top_tournament_teams.csv",
        [
            {
                "team_id": "team-1",
                "event_name": "Regionals",
                "event_tier": "regional",
                "event_date": "2026-01-01",
                "player_name": "Ash",
                "player_country": "JP",
                "placement": "1",
                "record_wins": "7",
                "record_losses": "1",
                "win_rate": "0.875",
                "pokemon_keys": "pikachu|raichu",
                "team_rank": "1",
            }
        ],
    )
    rows = data.load_mart(tmp_path, "top_tournament_teams")
    assert rows == [
        {
            "team_id": "team-1",
            "event_name": "Regionals",
            "event_tier": "regional",
            "event_date": "2026-01-01",
            "player_name": "Ash",
            "player_country": "JP",
            "placement": 1,
            "record_wins": 7,
            "record_losses": 1,
            "win_rate": 0.875,
            "pokemon_keys": "pikachu|raichu",
            "team_rank": 1,
        }
    ]


def test_compute_kpis_top_12_and_cumulative_legal_pool():
    usage_rows = [
        {"pokemon_key": f"mon-{i}", "event_tier": "", "usage_rank": i, "usage_count": 100 - i}
        for i in range(1, 41)
    ]
    marts = {
        "pokemon_usage_summary": usage_rows,
        "legality_summary_by_regulation": [
            {
                "regulation_code": "m-a",
                "snapshot_date": "2026-01-01",
                "legal_pokemon_count": 268,
                "cumulative_legal_pokemon_count": 268,
            },
            {
                "regulation_code": "m-b",
                "snapshot_date": "2026-01-01",
                "legal_pokemon_count": 39,
                "cumulative_legal_pokemon_count": 307,
            },
        ],
        "pokemon_win_rate_summary": [],
    }
    kpis = data.compute_kpis(marts)

    board = kpis["top_12_boards"]["all"]["forms"]
    assert [r["pokemon_key"] for r in board] == [f"mon-{i}" for i in range(1, 13)]
    assert kpis["legal_pool_by_regulation"] == [
        {
            "regulation_code": "m-a",
            "legal_pokemon_count": 268,
            "cumulative_legal_pokemon_count": 268,
        },
        {
            "regulation_code": "m-b",
            "legal_pokemon_count": 39,
            "cumulative_legal_pokemon_count": 307,
        },
    ]


def test_join_pokemon_names_resolves_partner_pokemon_key(tmp_path):
    marts_dir = tmp_path / "marts"
    normalized_dir = tmp_path / "normalized"
    _write_csv(
        normalized_dir / "pokemon.csv",
        [
            {"pokemon_key": "pikachu", "pokemon_name": "Pikachu"},
            {"pokemon_key": "raichu", "pokemon_name": "Raichu"},
        ],
    )
    _write_csv(
        marts_dir / "pokemon_team_core_usage.csv",
        [
            {
                "pokemon_key": "pikachu",
                "partner_pokemon_key": "raichu",
                "co_occurrence_count": "3",
                "partner_share": "0.75",
                "usage_rank": "1",
            }
        ],
    )
    payload = data.build_payload(marts_dir, normalized_dir)

    assert payload["marts"]["pokemon_team_core_usage"] == [
        {
            "pokemon_key": "pikachu",
            "partner_pokemon_key": "raichu",
            "co_occurrence_count": 3,
            "partner_share": 0.75,
            "usage_rank": 1,
            "pokemon_name": "Pikachu",
            "partner_pokemon_name": "Raichu",
        }
    ]


def test_load_mart_coerces_speed_tier_bracket_fields(tmp_path):
    _write_csv(
        tmp_path / "pokemon_speed_tiers.csv",
        [
            {
                "pokemon_key": "dragapult",
                "type_1": "dragon",
                "type_2": "ghost",
                "base_speed": "142",
                "max_investment_speed": "213",
                "plus_one_speed": "319",
                "scarf_speed": "319",
                "plus_two_speed": "426",
                "tailwind_speed": "426",
                "scarf_tailwind_speed": "639",
                "usage_count": "40",
                "usage_share": "0.021",
                "win_rate": "0.51",
                "record_count": "80",
            }
        ],
    )
    rows = data.load_mart(tmp_path, "pokemon_speed_tiers")
    assert rows[0]["base_speed"] == 142
    assert rows[0]["max_investment_speed"] == 213
    assert rows[0]["scarf_tailwind_speed"] == 639
    assert rows[0]["usage_share"] == 0.021
    assert rows[0]["type_2"] == "ghost"


def test_load_mart_coerces_placement_weighted_usage_fields(tmp_path):
    _write_csv(
        tmp_path / "pokemon_placement_weighted_usage.csv",
        [
            {
                "pokemon_key": "incineroar",
                "usage_count": "1029",
                "top_cut_usage_count": "18",
                "top_cut_usage_share": "0.0721",
                "placement_weighted_score": "12.5",
                "weighted_usage_share": "0.0654",
                "weighted_usage_rank": "1",
            }
        ],
    )
    assert data.load_mart(tmp_path, "pokemon_placement_weighted_usage") == [
        {
            "pokemon_key": "incineroar",
            "usage_count": 1029,
            "top_cut_usage_count": 18,
            "top_cut_usage_share": 0.0721,
            "placement_weighted_score": 12.5,
            "weighted_usage_share": 0.0654,
            "weighted_usage_rank": 1,
        }
    ]


def test_load_mart_slices_team_synergy_to_the_dashboard_cut(tmp_path):
    # Pairs below MIN_SYNERGY_PAIR_TEAMS are dropped (lift is noise at that
    # sample size), and each anchor keeps at most
    # MAX_SYNERGY_PARTNERS_PER_POKEMON of its highest-lift partners.
    rows = [
        {
            "pokemon_key": "pikachu",
            "partner_pokemon_key": f"partner-{i:02d}",
            "pair_team_count": "20",
            "lift": str(20 - i),
            "lift_rank": str(i + 1),
        }
        for i in range(15)
    ]
    rows.append(
        {
            "pokemon_key": "pikachu",
            "partner_pokemon_key": "rare-partner",
            "pair_team_count": "2",
            "lift": "99.0",
            "lift_rank": "16",
        }
    )
    _write_csv(tmp_path / "pokemon_team_synergy.csv", rows)

    sliced = data.load_mart(tmp_path, "pokemon_team_synergy")

    assert len(sliced) == data.MAX_SYNERGY_PARTNERS_PER_POKEMON
    partner_keys = [row["partner_pokemon_key"] for row in sliced]
    # The extreme-lift pair is excluded by the pair_team_count floor, not
    # kept because its lift is the highest in the file.
    assert "rare-partner" not in partner_keys
    assert partner_keys[0] == "partner-00"
    assert sliced[0]["lift"] == 20.0


def test_load_mart_slices_player_signature_to_established_players(tmp_path):
    _write_csv(
        tmp_path / "player_signature_pokemon.csv",
        [
            {
                "player_id": "established",
                "player_name": "Ash",
                "player_country": "JP",
                "player_team_count": "2",
                "pokemon_key": "pikachu",
                "usage_count": "11",
                "player_usage_share": "0.297",
                "player_pokemon_rank": "1",
            },
            {
                "player_id": "established",
                "player_name": "Ash",
                "player_country": "JP",
                "player_team_count": "2",
                "pokemon_key": "raichu",
                "usage_count": "1",
                "player_usage_share": "0.027",
                "player_pokemon_rank": "7",
            },
            {
                "player_id": "one-off",
                "player_name": "Gary",
                "player_country": "JP",
                "player_team_count": "1",
                "pokemon_key": "eevee",
                "usage_count": "1",
                "player_usage_share": "1.0",
                "player_pokemon_rank": "1",
            },
        ],
    )

    sliced = data.load_mart(tmp_path, "player_signature_pokemon")

    # A one-team player's 100% "signature" share is exactly the weak
    # evidence the floor exists to exclude; so is a rank-7 pick nothing
    # displays.
    assert [(row["player_id"], row["player_pokemon_rank"]) for row in sliced] == [
        ("established", 1)
    ]


def test_join_pokemon_names_resolves_matchup_summary_best_and_worst(tmp_path):
    marts_dir = tmp_path / "marts"
    normalized_dir = tmp_path / "normalized"
    _write_csv(
        normalized_dir / "pokemon.csv",
        [
            {"pokemon_key": "incineroar", "pokemon_name": "Incineroar"},
            {"pokemon_key": "torkoal", "pokemon_name": "Torkoal"},
            {"pokemon_key": "lycanroc-dusk", "pokemon_name": "Lycanroc"},
        ],
    )
    _write_csv(
        marts_dir / "pokemon_matchup_summary.csv",
        [
            {
                "pokemon_key": "incineroar",
                "overall_win_rate": "0.51",
                "distinct_opponents": "180",
                "total_matchup_appearances": "9000",
                "best_matchup_pokemon_key": "torkoal",
                "best_matchup_win_rate": "0.61",
                "best_matchup_matches": "290",
                "worst_matchup_pokemon_key": "lycanroc-dusk",
                "worst_matchup_win_rate": "0.391",
                "worst_matchup_matches": "289",
                "min_matches_threshold": "10",
            }
        ],
    )
    row = data.build_payload(marts_dir, normalized_dir)["marts"]["pokemon_matchup_summary"][0]

    assert row["pokemon_name"] == "Incineroar"
    assert row["best_matchup_pokemon_name"] == "Torkoal"
    # Display names come from pokemon_key via display_name, so the form
    # survives — "Lycanroc (Dusk)", not the species-only "Lycanroc".
    assert row["worst_matchup_pokemon_name"] == "Lycanroc (Dusk)"


def test_join_pokemon_names_leaves_a_null_best_matchup_alone(tmp_path):
    # pokemon_matchup_summary left-joins best/worst, so a Pokémon with no
    # qualifying opponent has null keys — those must not resolve to a
    # display name at all rather than to an empty-string one.
    marts_dir = tmp_path / "marts"
    normalized_dir = tmp_path / "normalized"
    _write_csv(
        normalized_dir / "pokemon.csv",
        [{"pokemon_key": "pikachu", "pokemon_name": "Pikachu"}],
    )
    _write_csv(
        marts_dir / "pokemon_matchup_summary.csv",
        [
            {
                "pokemon_key": "pikachu",
                "overall_win_rate": "0.5",
                "distinct_opponents": "1",
                "total_matchup_appearances": "2",
                "best_matchup_pokemon_key": "",
                "best_matchup_win_rate": "",
                "best_matchup_matches": "",
                "worst_matchup_pokemon_key": "",
                "worst_matchup_win_rate": "",
                "worst_matchup_matches": "",
                "min_matches_threshold": "10",
            }
        ],
    )
    row = data.build_payload(marts_dir, normalized_dir)["marts"]["pokemon_matchup_summary"][0]

    assert "best_matchup_pokemon_name" not in row
    assert "worst_matchup_pokemon_name" not in row
    assert row["best_matchup_win_rate"] is None


# --- provenance (Data & Sources tab) ---


def test_load_provenance_degrades_when_reports_are_absent(tmp_path):
    # A clean checkout has neither report: extraction_summary.json is
    # committed but may not exist in a test fixture, and
    # validation_report.json is gitignored. Neither absence should fail a
    # dashboard build.
    prov = data.load_provenance(tmp_path)

    assert prov["sources"] == []
    assert prov["gates"] == []
    assert prov["validation_available"] is False
    assert prov["dataset_version"] is None


def test_load_provenance_survives_a_malformed_report(tmp_path):
    (tmp_path / "validation_report.json").write_text("{not json", encoding="utf-8")

    assert data.load_provenance(tmp_path)["validation_available"] is False


def test_load_provenance_flattens_all_four_gate_categories(tmp_path):
    (tmp_path / "extraction_summary.json").write_text(
        json.dumps(
            {
                "dataset_version": "1.2.3",
                "generated_at_utc": "2026-01-02T00:00:00Z",
                "sources": [{"source_name": "PokéAPI", "rows_written": 7}],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "validation_report.json").write_text(
        json.dumps(
            {
                "generated_at_utc": "2026-01-03T00:00:00Z",
                "coverage_checks": [
                    {
                        "check_name": "pokeapi_artwork_coverage",
                        "description": "d",
                        "threshold": ">=0.95",
                        "metric_value": 1.0,
                        "status": "pass",
                    }
                ],
                "null_rate_checks": [
                    {
                        "table_name": "pokemon_asset",
                        "metric_value": 0.0,
                        "threshold": "<=0.01",
                        "status": "pass",
                    }
                ],
                "duplicate_key_checks": [
                    {
                        "table_name": "pokemon_asset",
                        "primary_key": "pokemon_asset_key",
                        "duplicate_count": 0,
                        "status": "pass",
                    }
                ],
                "referential_integrity_checks": [
                    {
                        "check_name": "pokemon_asset_resolves_to_pokemon",
                        "violation_count": 0,
                        "status": "pass",
                    }
                ],
                "release_blocking_findings": [],
            }
        ),
        encoding="utf-8",
    )

    prov = data.load_provenance(tmp_path)

    assert prov["dataset_version"] == "1.2.3"
    assert prov["validation_available"] is True
    assert prov["sources"] == [{"source_name": "PokéAPI", "rows_written": 7}]
    assert [gate["category"] for gate in prov["gates"]] == [
        "coverage",
        "null_rate",
        "duplicate_key",
        "referential_integrity",
    ]


def test_load_snapshot_history_summarizes_retained_dates(tmp_path):
    source_dir = tmp_path / "munchstats"
    source_dir.mkdir(parents=True)
    (source_dir / "2026-01-01.csv").write_text("x\n", encoding="utf-8")
    (source_dir / "2026-01-08.csv").write_text("x\n", encoding="utf-8")
    (source_dir / "notes.csv").write_text("x\n", encoding="utf-8")

    history = data.load_snapshot_history(tmp_path)

    assert history["snapshot_count"] == 2
    assert history["has_multiple_snapshots"] is True
    assert history["first_snapshot_date"] == "2026-01-01"
    assert history["latest_snapshot_date"] == "2026-01-08"
    assert history["sources"] == [
        {
            "source_name": "MunchStats",
            "staging_subdir": "munchstats",
            "snapshot_count": 2,
            "first_snapshot_date": "2026-01-01",
            "latest_snapshot_date": "2026-01-08",
            "history_days": 7,
        }
    ]


def test_load_release_history_reads_compact_manifest_metadata(tmp_path):
    (tmp_path / "manifest-0.1.0.json").write_text(
        json.dumps(
            {
                "dataset_version": "0.1.0",
                "published_at_utc": "2026-01-01T00:00:00Z",
                "tables": [{"name": "pokemon"}],
                "images": {"count": 0},
                "quality_checks": [{"status": "pass"}],
                "known_limitations": ["example"],
            }
        ),
        encoding="utf-8",
    )

    assert data.load_release_history(tmp_path) == [
        {
            "dataset_version": "0.1.0",
            "published_at_utc": "2026-01-01T00:00:00Z",
            "table_count": 1,
            "image_count": 0,
            "quality_check_count": 1,
            "quality_failure_count": 0,
            "known_limitation_count": 1,
        }
    ]


def test_marts_for_scope_filters_only_scoped_marts():
    marts = {
        "pokemon_usage_summary": [
            {"regulation_scope": "m-c", "pokemon_key": "rillaboom"},
            {"regulation_scope": "all", "pokemon_key": "sneasler"},
        ],
        "pokemon_head_to_head": [{"pokemon_key": "a", "opponent_pokemon_key": "b"}],
    }
    scoped = data.marts_for_scope(marts, "m-c")
    assert scoped["pokemon_usage_summary"] == [
        {"regulation_scope": "m-c", "pokemon_key": "rillaboom"}
    ]
    assert scoped["pokemon_head_to_head"] == marts["pokemon_head_to_head"]


def _mover(key, delta, share, *, new=False, teams=500, prev_teams=400):
    return {
        "regulation_code": "m-c",
        "previous_regulation_code": "m-b",
        "pokemon_key": key,
        "pokemon_name": key.title(),
        "usage_count": 10 if share else 0,
        "usage_share": share,
        "previous_usage_share": share - delta,
        "usage_share_delta": delta,
        # Team share (docs/upgrade-plan-2027q2.md, V1) is what the summary
        # ranks by; about six times the slot share.
        "team_share": share * 6,
        "previous_team_share": (share - delta) * 6,
        "team_share_delta": delta * 6,
        "usage_rank": 1,
        "previous_usage_rank": 2,
        "win_rate": 0.5,
        "is_new_to_format": "true" if new else "false",
        "team_count": teams,
        "previous_team_count": prev_teams,
    }


def test_summarize_movers_splits_risers_fallers_and_arrivals():
    rows = [
        _mover("gholdengo", 0.036, 0.046),
        _mover("charizard-mega-y", -0.052, 0.024),
        _mover("rillaboom", 0.087, 0.087, new=True),
        _mover("unused-newcomer", 0.0, 0.0, new=True),
    ]
    summary = data.summarize_movers(rows, "m-c")
    assert summary["reliable"] is True
    assert [r["pokemon_key"] for r in summary["risers"]] == ["gholdengo"]
    assert [r["pokemon_key"] for r in summary["fallers"]] == ["charizard-mega-y"]
    # New arrivals are not risers, and one never brought isn't an arrival.
    assert [r["pokemon_key"] for r in summary["new_arrivals"]] == ["rillaboom"]
    assert data.summarize_movers(rows, "m-a") is None


def test_summarize_movers_flags_a_thin_sample_as_unreliable():
    rows = [_mover("gholdengo", 0.03, 0.05, teams=40, prev_teams=400)]
    assert data.summarize_movers(rows, "m-c")["reliable"] is False


def _event(event_id, regulation, event_date, teams, tier="Regional"):
    return {
        "event_id": event_id,
        "event_name": event_id.title(),
        "event_date": event_date,
        "event_tier": tier,
        "regulation_code": regulation,
        "team_count": teams,
    }


def _regulation(code, start, end):
    from datetime import date

    from pipelines.regulations import Regulation

    return Regulation(
        regulation_code=code,
        regulation_name=f"Regulation Set {code.upper()}",
        munchstats_format=f"fmt-{code}",
        limitless_format=code,
        start_date=date.fromisoformat(start),
        end_date=date.fromisoformat(end),
    )


# A fixture registry with a regulation after M-C: the U3 rollover cases
# (docs/upgrade-plan-2027q1.md) are about the days after a set changes,
# before the real seed has any events for the new one.
_FIXTURE_REGULATIONS = [
    _regulation("m-b", "2026-06-17", "2026-09-09"),
    _regulation("m-c", "2026-09-09", "2026-12-02"),
    _regulation("m-d", "2026-12-02", "2027-03-03"),
]


def test_default_scope_falls_back_when_the_new_regulation_has_no_events():
    from datetime import date

    by_scope = {"m-b": {"team_count": 395}, "m-c": {"team_count": 3770}, "all": {}}
    # The day after M-C ends: M-D is in force but nothing has been played.
    assert data.default_scope_for(by_scope, _FIXTURE_REGULATIONS, date(2026, 12, 3)) == "m-c"


def test_default_scope_falls_back_while_the_new_regulation_is_thin():
    from datetime import date

    by_scope = {
        "m-c": {"team_count": 3770},
        "m-d": {"team_count": data.MIN_DEFAULT_SCOPE_TEAMS - 1},
        "all": {},
    }
    assert data.default_scope_for(by_scope, _FIXTURE_REGULATIONS, date(2026, 12, 8)) == "m-c"
    by_scope["m-d"]["team_count"] = data.MIN_DEFAULT_SCOPE_TEAMS
    assert data.default_scope_for(by_scope, _FIXTURE_REGULATIONS, date(2026, 12, 8)) == "m-d"


def test_default_scope_keeps_a_thin_regulation_when_nothing_precedes_it():
    from datetime import date

    by_scope = {"m-b": {"team_count": 12}, "all": {}}
    assert data.default_scope_for(by_scope, _FIXTURE_REGULATIONS, date(2026, 7, 1)) == "m-b"


def test_compute_kpis_by_scope_uses_the_registry_it_is_given():
    from datetime import date

    marts = {
        "pokemon_usage_summary": [
            {
                "regulation_scope": scope,
                "pokemon_key": "rillaboom",
                "event_tier": None,
                "usage_count": 5,
                "usage_share": 0.1,
                "usage_rank": 1,
                "pokemon_name": "Rillaboom",
            }
            for scope in ("m-c", "all")
        ],
        "legality_summary_by_regulation": [],
        "pokemon_win_rate_summary": [],
        "tournament_event_summary": [_event("louisville", "m-c", "2026-10-09", 1013)],
    }
    by_scope, default = data.compute_kpis_by_scope(
        marts, today=date(2026, 12, 3), regulations=_FIXTURE_REGULATIONS
    )
    assert default == "m-c"
    assert by_scope["m-c"]["current_regulation"]["regulation_code"] == "m-c"
    assert by_scope["all"]["current_regulation"]["regulation_code"] == "m-d"


def test_starter_teams_rank_complete_sheets_by_placement_then_tier():
    def team(team_id, event_id, placement, complete=True):
        return {
            "team_id": team_id,
            "event_id": event_id,
            "player_id": f"p-{team_id}",
            "player_name": team_id.title(),
            "player_country": "US",
            "placement": placement,
            "record_wins": 9,
            "record_losses": 2,
            "pokemon_keys": "a|b|c|d|e|f",
            "is_fully_reported": "true" if complete else "false",
        }

    def sheet(team_id):
        return [
            {
                "team_id": team_id,
                "slot_number": slot,
                "pokemon_key": key,
                "item_name": "Sitrus Berry",
                "ability": "Intimidate",
                "nature": "Adamant",
                "moves": "Protect|Fake Out|Knock Off|Flare Blitz",
            }
            for slot, key in enumerate("abcdef", start=1)
        ]

    marts = {
        "tournament_event_summary": [
            _event("regional", "m-c", "2026-10-09", 1013),
            _event("worlds", "m-c", "2026-08-28", 395, tier="Worlds"),
            _event("other-reg", "m-b", "2026-07-01", 500),
        ],
        "tournament_team_results": [
            team("regional-winner", "regional", 1),
            team("worlds-winner", "worlds", 1),
            team("worlds-second", "worlds", 2),
            team("incomplete-winner", "regional", 1, complete=False),
            team("other-winner", "other-reg", 1),
        ],
        "tournament_team_sheets": [
            row
            for team_id in (
                "regional-winner",
                "worlds-winner",
                "worlds-second",
                "incomplete-winner",
                "other-winner",
            )
            for row in sheet(team_id)
        ],
    }
    teams = data.starter_teams(marts, "m-c")
    # A Worlds win outranks a regional win; an incomplete sheet never
    # qualifies; another regulation's teams stay out of this scope.
    assert [t["team_id"] for t in teams] == ["worlds-winner", "regional-winner", "worlds-second"]
    assert teams[0]["event_name"] == "Worlds"
    assert [s["pokemon_key"] for s in teams[0]["sets"]] == list("abcdef")


def test_team_results_slicer_drops_columns_the_event_summary_carries():
    rows = [{"team_id": "t", "event_id": "e", "event_name": "E", "event_date": "d", "placement": 1}]
    assert data._slice_team_results(rows) == [{"team_id": "t", "event_id": "e", "placement": 1}]


def test_compute_kpis_by_scope_defaults_to_the_regulation_in_force():
    from datetime import date

    def usage(scope, key):
        return {
            "regulation_scope": scope,
            "pokemon_key": key,
            "event_tier": None,
            "usage_count": 5,
            "usage_share": 0.1,
            "usage_rank": 1,
            "pokemon_name": key,
        }

    marts = {
        "pokemon_usage_summary": [
            usage("m-b", "kingambit"),
            usage("m-c", "rillaboom"),
            usage("all", "sneasler"),
        ],
        "legality_summary_by_regulation": [],
        "pokemon_win_rate_summary": [],
        "tournament_event_summary": [
            _event("wcs", "m-b", "2026-08-28", 395),
            _event("louisville", "m-c", "2026-10-09", 1013),
        ],
    }
    by_scope, default = data.compute_kpis_by_scope(marts, today=date(2026, 10, 18))
    assert list(by_scope) == ["m-b", "m-c", "all"]
    assert default == "m-c"
    assert (by_scope["m-c"]["event_count"], by_scope["m-c"]["team_count"]) == (1, 1013)
    assert (by_scope["all"]["event_count"], by_scope["all"]["team_count"]) == (2, 1408)
    assert by_scope["m-c"]["latest_event"]["event_id"] == "louisville"
    assert by_scope["m-c"]["top_used_pokemon"]["pokemon_key"] == "rillaboom"
    assert by_scope["all"]["top_used_pokemon"]["pokemon_key"] == "sneasler"
    # After M-C ends with no newer data, the newest regulation with data wins.
    _, later_default = data.compute_kpis_by_scope(marts, today=date(2027, 3, 1))
    assert later_default == "m-c"


def test_team_core_slicer_caps_partners_per_scope_and_pokemon():
    rows = [
        {
            "regulation_scope": scope,
            "pokemon_key": "a",
            "partner_pokemon_key": f"p{i}",
            "co_occurrence_count": i,
        }
        for scope in ("m-c", "all")
        for i in range(data.MAX_CORE_PARTNERS_PER_POKEMON + 5)
    ]
    kept = data._slice_team_core_usage(rows)
    for scope in ("m-c", "all"):
        scoped = [r for r in kept if r["regulation_scope"] == scope]
        assert len(scoped) == data.MAX_CORE_PARTNERS_PER_POKEMON
        assert min(r["co_occurrence_count"] for r in scoped) == 5


def test_set_variant_slicer_keeps_the_three_sets_the_profile_shows():
    rows = [{"pokemon_key": "a", "set_level": "full", "set_rank": rank} for rank in range(1, 6)]
    assert [r["set_rank"] for r in data._slice_set_variants(rows)] == [1, 2, 3]


def test_top_cut_teams_are_the_top_sixteen_finishes():
    rows = [{"team_id": str(p), "placement": p} for p in (1, 8, 16, 17, 200)]
    rows.append({"team_id": "unplaced", "placement": None})
    assert [r["team_id"] for r in data.top_cut_teams(rows)] == ["1", "8", "16"]


def test_short_event_name_drops_the_words_every_event_shares():
    assert data.short_event_name("2027 Louisville Pokémon VGC Regional Championships") == (
        "Louisville Regional"
    )
    assert data.short_event_name("2026 Pokémon VGC World Championship") == "World Championships"
    assert data.short_event_name("") == ""


def test_window_movers_compare_recent_events_with_earlier_ones():
    events = [
        _event("a", "m-c", "2026-09-18", 300),
        _event("b", "m-c", "2026-09-26", 300),
        _event("c", "m-c", "2026-10-03", 200),
        _event("d", "m-c", "2026-10-09", 200),
    ]

    def usage(event_id, key, count):
        return {
            "event_id": event_id,
            "pokemon_key": key,
            "pokemon_name": key.title(),
            "usage_count": count,
            "event_slot_count": 1000,
            "event_team_count": 200,
        }

    rows = [
        usage("a", "garchomp", 100),
        usage("b", "garchomp", 100),
        usage("c", "garchomp", 10),
        usage("d", "garchomp", 10),
        usage("a", "sneasler", 10),
        usage("b", "sneasler", 10),
        usage("c", "sneasler", 90),
        usage("d", "sneasler", 90),
    ]
    summary = data.summarize_event_window_movers(rows, events)
    # The newest half (c, d) against the rest (a, b).
    assert summary["recent_events"] == ["C", "D"]
    assert summary["early_events"] == ["A", "B"]
    assert (summary["team_count"], summary["previous_team_count"]) == (400, 600)
    assert summary["reliable"] is True
    assert [r["pokemon_key"] for r in summary["risers"]] == ["sneasler"]
    assert summary["risers"][0]["usage_share_delta"] == 0.08
    # Ranked and reported by team share: 180 of 400 teams against 20 of 400.
    assert summary["risers"][0]["team_share_delta"] == 0.4
    assert [r["pokemon_key"] for r in summary["fallers"]] == ["garchomp"]
    assert data.summarize_event_window_movers(rows, events[:1]) is None


def test_movers_flag_a_one_event_previous_regulation_as_a_thin_baseline():
    marts = {
        "pokemon_usage_summary": [],
        "legality_summary_by_regulation": [],
        "pokemon_win_rate_summary": [],
        "pokemon_regulation_movers": [_mover("gholdengo", 0.03, 0.05, teams=3770, prev_teams=395)],
        "tournament_event_summary": [
            _event("wcs", "m-b", "2026-08-28", 395, tier="Worlds"),
            _event("bal", "m-c", "2026-09-18", 1079),
            _event("lou", "m-c", "2026-10-09", 1013),
        ],
        "pokemon_event_usage_vs_regulation": [],
    }
    movers = data.compute_kpis(marts, scope="m-c")["movers"]
    assert movers["previous_event_count"] == 1
    assert movers["event_count"] == 2
    assert movers["baseline_thin"] is True


def test_player_index_has_one_row_per_player_with_their_record():
    events = [
        {"event_id": "E1", "event_date": "2026-08-01"},
        {"event_id": "E2", "event_date": "2026-09-01"},
    ]
    teams = [
        {
            "event_id": "E1",
            "player_id": "P1",
            "player_name": "zoe",
            "player_country": "US",
            "placement": 12,
            "regulation_code": "m-b",
        },
        {
            "event_id": "E2",
            "player_id": "P1",
            "player_name": "zoe",
            "player_country": "US",
            "placement": 3,
            "regulation_code": "m-c",
        },
        {
            "event_id": "E2",
            "player_id": "P2",
            "player_name": "Ash",
            "player_country": None,
            "placement": None,
            "regulation_code": "m-c",
        },
        {"event_id": "E2", "player_id": None, "player_name": "Unknown"},
    ]
    index = data.player_index(teams, events)
    # Sorted by name, case-insensitively; rows with no player_id are skipped.
    assert [row["player_id"] for row in index] == ["P2", "P1"]
    zoe = index[1]
    assert zoe["team_count"] == 2
    assert zoe["best_placement"] == 3
    assert zoe["latest_event_date"] == "2026-09-01"
    assert zoe["regulations"] == "m-b|m-c"
    # Per regulation too, so an M-C list can rank by M-C results.
    assert zoe["teams_by_regulation"] == "m-b:1|m-c:1"
    assert zoe["best_by_regulation"] == "m-b:12|m-c:3"
    assert index[0]["best_placement"] is None
    assert index[0]["best_by_regulation"] == ""


# docs/upgrade-plan-2027q2.md, V1/V2: team share and the Top 12 board.


def test_species_group_key_folds_megas_into_the_stone_holder():
    assert data.species_group_key("charizard-mega-y") == "charizard"
    assert data.species_group_key("lucario-mega-z") == "lucario"
    assert data.species_group_key("salamence-mega") == "salamence"
    assert data.species_group_key("meowstic-male-mega") == "meowstic-male"
    # Every other form keeps its own key, as on the official card.
    assert data.species_group_key("basculegion-male") == "basculegion-male"
    assert data.species_group_key("floette-eternal") == "floette-eternal"
    assert data.species_group_key("meganium") == "meganium"


def _usage(key, count, rank, teams=1000):
    return {
        "pokemon_key": key,
        "pokemon_name": data.display_name(key),
        "event_tier": None,
        "usage_count": count,
        "usage_rank": rank,
        "usage_share": round(count / (teams * 6), 4),
        "team_share": round(count / teams, 4),
        "scope_team_count": teams,
    }


def test_top_board_ranks_forms_by_team_share_with_their_denominator():
    rows = [_usage("raichu-mega-y", 300, 2), _usage("rillaboom", 500, 1), _usage("raichu", 50, 3)]
    profiles = {"rillaboom": {"type_1": "grass", "pokemon_name": "Rillaboom"}}
    tiles = data.top_board(rows, profiles, "forms")
    assert [t["pokemon_key"] for t in tiles] == ["rillaboom", "raichu-mega-y", "raichu"]
    assert tiles[0]["team_share"] == 0.5
    assert tiles[0]["team_total"] == 1000
    assert tiles[0]["type_1"] == "grass"


def test_top_board_species_folds_megas_and_takes_the_base_forms_identity():
    rows = [
        _usage("rillaboom", 500, 1),
        _usage("raichu-mega-y", 300, 2),
        _usage("raichu-mega-x", 150, 3),
        _usage("raichu", 100, 4),
    ]
    profiles = {
        "raichu": {"type_1": "electric", "pokemon_name": "Raichu"},
        "raichu-mega-y": {
            "type_1": "electric",
            "type_2": "psychic",
            "pokemon_name": "Mega Raichu Y",
        },
    }
    tiles = data.top_board(rows, profiles, "species")
    assert [t["pokemon_key"] for t in tiles] == ["raichu", "rillaboom"]
    raichu = tiles[0]
    # 550 of 1,000 teams: one Mega Stone per species, so no team counts twice.
    assert raichu["team_share"] == 0.55
    assert raichu["usage_count"] == 550
    assert raichu["pokemon_name"] == "Raichu"
    assert (raichu["type_1"], raichu["type_2"]) == ("electric", None)
    assert raichu["form_keys"] == "raichu-mega-y|raichu-mega-x|raichu"


def test_kpis_carry_a_board_per_player_scope():
    marts = {
        "pokemon_usage_summary": [_usage("rillaboom", 500, 1), _usage("sneasler", 400, 2)],
        "legality_summary_by_regulation": [],
        "pokemon_win_rate_summary": [],
        "tournament_event_summary": [
            {
                "event_id": "e1",
                "regulation_code": "m-c",
                "team_count": 1000,
                "event_date": "2026-10-09",
            }
        ],
    }
    kpis = data.compute_kpis(marts, scope="m-c", regulations=[])
    board = kpis["top_12_boards"]["all"]
    assert board["label"] == "All players"
    assert (board["team_count"], board["event_count"]) == (1000, 1)
    assert [t["pokemon_key"] for t in board["forms"]] == ["rillaboom", "sneasler"]
    assert [t["pokemon_key"] for t in board["species"]] == ["rillaboom", "sneasler"]


def test_latest_event_carries_the_winners_sheet_for_the_team_strip():
    """docs/upgrade-plan-2027q2.md, V3: the Overview's winner strip shows held
    items without fetching the sheets."""
    events = [
        {"event_id": "old", "event_date": "2026-09-01", "winner_team_id": "t0"},
        {"event_id": "new", "event_date": "2026-10-09", "winner_team_id": "t1", "event_name": "X"},
    ]
    sheets = [
        {"team_id": "t1", "slot_number": 2, "pokemon_key": "b", "item_name": "Focus Sash"},
        {"team_id": "t1", "slot_number": 1, "pokemon_key": "a", "item_name": "Choice Scarf"},
        {"team_id": "t0", "slot_number": 1, "pokemon_key": "z", "item_name": "Leftovers"},
    ]
    latest = data._latest_event(events, sheets)
    assert latest["event_id"] == "new"
    assert [s["pokemon_key"] for s in latest["winner_sets"]] == ["a", "b"]
    assert latest["winner_sets"][0]["item_name"] == "Choice Scarf"
    assert data._latest_event(events)["winner_sets"] == []
