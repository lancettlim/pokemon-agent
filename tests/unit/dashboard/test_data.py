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
            "usage_share": None,
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

    assert [r["pokemon_key"] for r in kpis["top_12_pokemon"]] == [f"mon-{i}" for i in range(1, 13)]
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
