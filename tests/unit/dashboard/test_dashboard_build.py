import csv
import json

from pipelines.dashboard import build


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _embedded_payload(html: str) -> dict:
    start = html.index("window.DASHBOARD_DATA = ") + len("window.DASHBOARD_DATA = ")
    end = html.index("</script>", start)
    raw = html[start:end].rstrip().rstrip(";")
    return json.loads(raw)


def _populate_marts(marts_dir, normalized_dir):
    _write_csv(
        normalized_dir / "pokemon.csv",
        [
            {"pokemon_key": "pikachu", "pokemon_name": "Pikachu"},
            {"pokemon_key": "raichu", "pokemon_name": "Raichu"},
        ],
    )
    _write_csv(
        marts_dir / "pokemon_usage_summary.csv",
        [
            {"pokemon_key": "pikachu", "event_tier": "", "usage_count": "100", "usage_rank": "1"},
            {"pokemon_key": "raichu", "event_tier": "", "usage_count": "50", "usage_rank": "2"},
        ],
    )
    _write_csv(
        marts_dir / "pokemon_win_rate_summary.csv",
        [
            {
                "pokemon_key": "pikachu",
                "total_wins": "10",
                "total_losses": "5",
                "win_rate": "0.6667",
                "record_count": "15",
                "wilson_lower_bound": "0.41",
                "wilson_rank": "1",
            }
        ],
    )
    _write_csv(
        marts_dir / "pokemon_item_usage.csv",
        [
            {
                "pokemon_key": "pikachu",
                "item_name": "Light Ball",
                "short_effect": "Doubles Attack and Special Attack.",
                "usage_count": "10",
                "item_share": "1.0",
                "usage_rank": "1",
            }
        ],
    )
    _write_csv(
        marts_dir / "pokemon_ability_usage.csv",
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
    _write_csv(
        marts_dir / "pokemon_move_usage.csv",
        [
            {
                "pokemon_key": "pikachu",
                "move_name": "Thunderbolt",
                "move_type": "electric",
                "power": "90",
                "accuracy": "100",
                "category": "special",
                "priority": "0",
                "short_effect": "Has a 10% chance to paralyze.",
                "usage_count": "8",
                "move_share": "1.0",
                "usage_rank": "1",
            }
        ],
    )
    _write_csv(
        marts_dir / "legality_summary_by_regulation.csv",
        [
            {
                "regulation_code": "m-a",
                "snapshot_date": "2026-01-01",
                "legal_pokemon_count": "2",
                "cumulative_legal_pokemon_count": "2",
            }
        ],
    )


def _build(marts_dir, normalized_dir, output_dir, **kwargs):
    # fetch_icons=False keeps these tests offline/deterministic — item-icon
    # resolution is the one part of a dashboard build that needs network
    # access (see pipelines/dashboard/build.py's _resolve_item_icons).
    kwargs.setdefault("fetch_icons", False)
    return build.build(
        marts_dir=marts_dir, normalized_dir=normalized_dir, output_dir=output_dir, **kwargs
    )


def test_build_writes_index_html_and_app_js(tmp_path):
    marts_dir = tmp_path / "marts"
    normalized_dir = tmp_path / "normalized"
    output_dir = tmp_path / "out"
    _populate_marts(marts_dir, normalized_dir)

    payload = _build(marts_dir, normalized_dir, output_dir)

    assert (output_dir / "index.html").exists()
    for script_name in build.SCRIPT_NAMES:
        assert (output_dir / script_name).exists()
        assert (output_dir / script_name).read_bytes() == (
            build.STATIC_DIR / script_name
        ).read_bytes()

    html = (output_dir / "index.html").read_text(encoding="utf-8")
    embedded = _embedded_payload(html)
    assert embedded["kpis"]["distinct_pokemon_used"] == payload["kpis"]["distinct_pokemon_used"]


def test_build_writes_sharded_json_feed_and_critical_only_inline_payload(tmp_path):
    # The payload split. data.json carries every non-mart key plus
    # mart_files, the index of the shard files holding the marts; together
    # they are backlog.md #32's complete feed. index.html inlines only the
    # critical keys, so first paint doesn't parse any mart rows.
    marts_dir = tmp_path / "marts"
    normalized_dir = tmp_path / "normalized"
    output_dir = tmp_path / "out"
    _populate_marts(marts_dir, normalized_dir)

    payload = _build(marts_dir, normalized_dir, output_dir)

    feed = json.loads((output_dir / "data.json").read_text(encoding="utf-8"))
    assert "marts" not in feed
    assert feed["mart_files"] == payload["mart_files"]

    # Reassembling the shards gives back every mart, each scoped mart's
    # rows split across its scope files without loss.
    # The Data section's dictionary and table cards ride along as one more
    # on-demand file; they describe the marts rather than being one.
    reassembled: dict = {}
    files = feed["mart_files"]
    paths = {files["core"], *files["scopes"].values(), *files["on_demand"].values()}
    for path in sorted(paths):
        for name, rows in json.loads((output_dir / path).read_text(encoding="utf-8")).items():
            reassembled.setdefault(name, []).extend(rows)
    assert set(reassembled) == set(payload["marts"]) | {"data_dictionary", "release_tables"}
    assert {entry["table"] for entry in reassembled["data_dictionary"]} == set(payload["marts"])
    for name, rows in payload["marts"].items():
        assert len(reassembled[name]) == len(rows), name

    html = (output_dir / "index.html").read_text(encoding="utf-8")
    embedded = _embedded_payload(html)

    # "marts" is the one key held back, and it is the only one.
    assert "marts" not in embedded
    assert set(embedded) == set(payload) - {"marts"}
    for key in embedded:
        assert embedded[key] == payload[key], key

    # The inline payload still carries everything the header/KPI row and
    # Overview render from, so the landing view needs no fetch.
    assert embedded["kpis"]["distinct_pokemon_used"] == payload["kpis"]["distinct_pokemon_used"]
    assert "Pikachu" in html


def test_build_omits_removed_stat_change_and_trend_sections(tmp_path):
    marts_dir = tmp_path / "marts"
    normalized_dir = tmp_path / "normalized"
    output_dir = tmp_path / "out"
    _populate_marts(marts_dir, normalized_dir)

    _build(marts_dir, normalized_dir, output_dir)
    html = (output_dir / "index.html").read_text(encoding="utf-8")

    assert "Stat change leaderboard" not in html
    assert "Legal pool trend by regulation" not in html
    assert 'id="stat-change-table"' not in html
    assert 'id="legality-chart"' not in html


def test_build_has_tab_markup_for_all_tabs(tmp_path):
    marts_dir = tmp_path / "marts"
    normalized_dir = tmp_path / "normalized"
    output_dir = tmp_path / "out"
    _populate_marts(marts_dir, normalized_dir)

    _build(marts_dir, normalized_dir, output_dir)
    html = (output_dir / "index.html").read_text(encoding="utf-8")

    for tab in (
        "overview",
        "usage",
        "pokemon-profile",
        "archetypes",
        "speed-tiers",
        "matchup",
        "team-builder",
        "top-teams",
    ):
        assert f'data-tab="{tab}"' in html
        assert f'data-panel="{tab}"' in html

    assert 'id="profile-team-core-size"' in html
    assert 'id="detected-archetype-grid"' in html
    assert 'id="team-builder-analysis"' in html
    assert 'id="ds-snapshot-table"' in html
    assert 'id="ds-release-table"' in html


def test_build_populates_sprites_and_type_icons(tmp_path):
    marts_dir = tmp_path / "marts"
    normalized_dir = tmp_path / "normalized"
    output_dir = tmp_path / "out"
    asset_cache_dir = tmp_path / "asset_cache"
    _populate_marts(marts_dir, normalized_dir)
    _write_csv(
        normalized_dir / "pokemon_asset.csv",
        [{"pokemon_key": "pikachu", "image_kind": "menu_sprite", "local_cache_path": "0025.png"}],
    )
    sprite_path = asset_cache_dir / "0025.png"
    sprite_path.parent.mkdir(parents=True, exist_ok=True)
    sprite_path.write_bytes(b"fake-png-bytes")

    payload = _build(marts_dir, normalized_dir, output_dir, asset_cache_dir=asset_cache_dir)

    assert payload["sprites"] == {"pikachu": "images/pikachu.png"}
    assert (output_dir / "images" / "pikachu.png").read_bytes() == b"fake-png-bytes"
    # raichu is referenced by pokemon_usage_summary but has no asset row,
    # so it's simply absent rather than raising.
    assert "raichu" not in payload["sprites"]

    assert set(payload["type_icons"].keys()) == {
        p.stem for p in (build.STATIC_ICONS_DIR / "types").glob("*.png")
    }
    for rel_path in payload["type_icons"].values():
        assert (output_dir / rel_path).exists()


def test_build_skips_item_icons_when_fetch_icons_false(tmp_path):
    marts_dir = tmp_path / "marts"
    normalized_dir = tmp_path / "normalized"
    output_dir = tmp_path / "out"
    _populate_marts(marts_dir, normalized_dir)

    payload = _build(marts_dir, normalized_dir, output_dir)

    assert payload["item_icons"] == {}
    assert not (output_dir / "images" / "icons" / "items").exists()


def test_build_reference_teams_empty_when_directory_missing(tmp_path):
    marts_dir = tmp_path / "marts"
    normalized_dir = tmp_path / "normalized"
    output_dir = tmp_path / "out"
    _populate_marts(marts_dir, normalized_dir)

    payload = _build(
        marts_dir,
        normalized_dir,
        output_dir,
        reference_teams_dir=tmp_path / "reference_teams_absent",
    )

    assert payload["reference_teams"] == []


def test_build_copies_reference_team_cards(tmp_path):
    marts_dir = tmp_path / "marts"
    normalized_dir = tmp_path / "normalized"
    output_dir = tmp_path / "out"
    reference_teams_dir = tmp_path / "reference_teams"
    _populate_marts(marts_dir, normalized_dir)

    cards_dir = reference_teams_dir / "cards"
    cards_dir.mkdir(parents=True)
    (cards_dir / "worlds-2026-team.png").write_bytes(b"fake-card-png-bytes")
    (reference_teams_dir / "reference_teams.json").write_text(
        json.dumps(
            [
                {
                    "team_id": "worlds-2026",
                    "player_name": "Ada Lovelace",
                    "country": "GB",
                    "event_name": "2026 World Championships",
                    "placement": 1,
                    "archetype_key": "rain",
                    "card_image": "worlds-2026-team.png",
                }
            ]
        ),
        encoding="utf-8",
    )

    payload = _build(marts_dir, normalized_dir, output_dir, reference_teams_dir=reference_teams_dir)

    assert payload["reference_teams"] == [
        {
            "team_id": "worlds-2026",
            "player_name": "Ada Lovelace",
            "country": "GB",
            "event_name": "2026 World Championships",
            "placement": 1,
            "archetype_key": "rain",
            "card_image": "images/reference_teams/worlds-2026-team.png",
        }
    ]
    assert (
        output_dir / "images" / "reference_teams" / "worlds-2026-team.png"
    ).read_bytes() == b"fake-card-png-bytes"


def test_safe_json_escapes_script_close_tag():
    payload = {"marts": {"pokemon_usage_summary": [{"pokemon_name": "</script><script>alert(1)"}]}}
    rendered = build._safe_json(payload)
    assert "</script>" not in rendered
    assert "\\u003c/script>" in rendered


def test_share_card_manifest_keeps_only_cards_that_exist(tmp_path):
    cards = tmp_path / "images" / "cards"
    cards.mkdir(parents=True)
    (cards / "t1.png").write_bytes(b"png")
    (cards / "og.png").write_bytes(b"png")
    (cards / "manifest.json").write_text(
        json.dumps(
            {
                "teams": {"t1": "images/cards/t1.png", "t2": "images/cards/t2.png"},
                "whats_changed": {"m-c": "images/cards/missing.png"},
                "og_image": "images/cards/og.png",
            }
        ),
        encoding="utf-8",
    )
    manifest = build._load_share_cards(tmp_path)
    assert manifest["teams"] == {"t1": "images/cards/t1.png"}
    assert manifest["whats_changed"] == {}
    assert manifest["og_image"] == "images/cards/og.png"
    assert build._load_share_cards(tmp_path / "nowhere") == {}


def test_site_meta_describes_the_default_regulation(tmp_path):
    payload = {
        "default_scope": "m-c",
        "kpis": {
            "top_used_pokemon": {"pokemon_name": "Rillaboom", "usage_share": 0.0866},
            "team_count": 3770,
            "event_count": 5,
        },
        "share_cards": {"og_image": "images/cards/og.png"},
    }
    meta = build._site_meta(payload)
    assert meta["title"] == "Pokémon Champions Data — Reg M-C"
    assert meta["description"].startswith(
        "Reg M-C: Rillaboom leads at 8.7% of roster slots across 3,770 teams from 5 events."
    )
    assert meta["og_image"] == build.SITE_URL + "images/cards/og.png"


def test_built_page_carries_open_graph_tags(tmp_path):
    marts_dir = tmp_path / "marts"
    normalized_dir = tmp_path / "normalized"
    _populate_marts(marts_dir, normalized_dir)
    _build(marts_dir, normalized_dir, tmp_path / "out")
    html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert '<meta property="og:title"' in html
    assert '<meta name="description"' in html


def test_an_on_demand_mart_with_a_scope_column_ships_whole_not_per_scope(tmp_path):
    # player_archetype_record carries regulation_scope but loads with the
    # player page; copying it into each scope file too would put it in the
    # default view's download.
    marts = {
        "player_archetype_record": [
            {"player_id": "P1", "regulation_scope": "m-c"},
            {"player_id": "P1", "regulation_scope": "all"},
        ],
        "pokemon_usage_summary": [{"pokemon_key": "a", "regulation_scope": "m-c"}],
    }
    index = build._write_mart_shards(marts, {"m-c": {}, "all": {}}, tmp_path)
    scope_file = json.loads((tmp_path / index["scopes"]["m-c"]).read_text(encoding="utf-8"))
    assert set(scope_file) == {"pokemon_usage_summary"}
    whole = json.loads(
        (tmp_path / index["on_demand"]["player_archetype_record"]).read_text(encoding="utf-8")
    )
    assert len(whole["player_archetype_record"]) == 2
