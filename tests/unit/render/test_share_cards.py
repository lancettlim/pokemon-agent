"""pipelines/render/share_cards.py's pure parts (docs/upgrade-plan-2027q1.md,
C4). Rendering itself needs Chromium and is exercised by `make dashboard`."""

from pipelines.render import share_cards


def _summary(**extra):
    return {
        "team_count": 1235,
        "previous_team_count": 2535,
        "reliable": True,
        "risers": [
            {
                "pokemon_key": "garchomp-mega-z",
                "pokemon_name": "Mega Garchomp Z",
                "team_share": 0.258,
                "team_share_delta": 0.192,
            }
        ],
        "fallers": [
            {
                "pokemon_key": "salamence-mega",
                "pokemon_name": "Mega Salamence",
                "team_share": 0.138,
                "team_share_delta": -0.174,
            }
        ],
        **extra,
    }


def test_whats_changed_card_follows_the_overviews_default_comparison():
    kpis = {
        "movers": _summary(previous_regulation_code="m-b", baseline_thin=True),
        "window_movers": _summary(
            early_events=["Baltimore Regional"], recent_events=["Louisville Regional"]
        ),
    }
    context = share_cards.whats_changed_context(
        kpis, "m-c", lambda key: f"data:{key}", dataset_version="0.3.0"
    )
    # A thin previous regulation means the card compares early and recent events.
    assert context["title"] == "What changed within Reg M-C"
    assert (
        "Louisville Regional (1,235 teams) vs Baltimore Regional (2,535 teams)"
        == context["subtitle"]
    )
    rising = context["columns"][0]["rows"][0]
    assert (rising["name"], rising["share"], rising["delta"]) == (
        "Mega Garchomp Z",
        "25.8%",
        "+19.2 pts",
    )
    assert rising["sprite"] == "data:garchomp-mega-z"
    assert context["columns"][1]["rows"][0]["delta"] == "-17.4 pts"
    assert "dataset 0.3.0" in context["footer"]

    kpis["movers"]["baseline_thin"] = False
    context = share_cards.whats_changed_context(kpis, "m-c", lambda key: "", dataset_version=None)
    assert context["title"] == "What changed in Reg M-C"
    assert context["subtitle"].startswith("vs Reg M-B")


def test_no_card_without_a_reliable_comparison():
    kpis = {
        "movers": _summary(previous_regulation_code="m-b", reliable=False),
        "window_movers": None,
    }
    assert (
        share_cards.whats_changed_context(kpis, "m-c", lambda key: "", dataset_version=None) is None
    )


def test_newest_event_top_cut_orders_by_placement():
    payload = {
        "marts": {
            "tournament_event_summary": [
                {"event_id": "old", "event_date": "2026-09-18"},
                {"event_id": "new", "event_date": "2026-10-09"},
            ],
            "tournament_team_results": [
                {"team_id": "n2", "event_id": "new", "placement": 2},
                {"team_id": "n1", "event_id": "new", "placement": 1},
                {"team_id": "n9", "event_id": "new", "placement": 9},
                {"team_id": "o1", "event_id": "old", "placement": 1},
            ],
        }
    }
    event, teams = share_cards.newest_event_top_cut(payload)
    assert event["event_id"] == "new"
    assert [t["team_id"] for t in teams] == ["n1", "n2"]


def test_type_badge_is_the_in_game_emblem():
    """One logo per type for the site and its cards (design-system.md)."""
    from pipelines.render import type_glyphs
    from pipelines.render.template import TYPE_COLORS

    for name in (n for n in TYPE_COLORS if n):
        assert (type_glyphs.ICON_DIR / f"{name}.png").exists()
    html = str(type_glyphs.square_badge_html("Fire", 20))
    assert "data:image/png;base64," in html and 'aria-label="Fire type"' in html
    assert str(type_glyphs.square_badge_html("unknown")) == ""


def test_the_og_card_falls_back_to_the_newest_earlier_regulation():
    # docs/upgrade-plan-2027q2.md, S1: a rollover can open on M-D's online
    # events before M-D has a card; the OG image stays M-C's.
    from pipelines.render.share_cards import og_card

    regulations = [{"regulation_code": code} for code in ("m-b", "m-c", "m-d")]
    cards = {"m-b": "b.png", "m-c": "c.png"}
    payload = {"default_scope": "m-d:online", "regulations": regulations}
    assert og_card(cards, payload) == "c.png"
    assert og_card(cards, {**payload, "default_scope": "m-c:online"}) == "c.png"
    assert og_card(cards, {**payload, "default_scope": "m-b"}) == "b.png"
    assert og_card({}, payload) is None


def _tile_board(n, phase_label="All players"):
    return {
        "label": phase_label,
        "team_count": 500,
        "event_count": 3,
        "forms": [
            {
                "pokemon_key": f"mon-{i}",
                "pokemon_name": f"Mon {i}",
                "team_share": round(0.5 - i * 0.02, 4),
                "type_1": "grass",
                "type_2": None,
            }
            for i in range(n)
        ],
    }


def test_regulation_top12_reads_the_board_the_overview_shows():
    from pipelines.render.share_cards import regulation_top12

    kpis = {"top_12_boards": {"all": _tile_board(14), "day2": _tile_board(12, "Day 2")}}
    tiles = regulation_top12(kpis, "all")
    assert len(tiles) == 12
    assert tiles[0] == {
        "pokemon_key": "mon-0",
        "name": "Mon 0",
        "share": 0.5,
        "type_1": "grass",
        "type_2": None,
    }
    assert regulation_top12(kpis, "online") == []


def test_event_top12_reads_the_field_or_day2():
    from pipelines.render.share_cards import event_top12

    marts = {
        "pokemon_champions_profile": [
            {"regulation_scope": "m-c", "pokemon_key": "a", "type_1": "fire", "type_2": None}
        ],
        "pokemon_event_usage_vs_regulation": [
            {
                "event_id": "E",
                "pokemon_key": "b",
                "usage_count": 5,
                "event_team_count": 10,
                "event_team_share": 0.5,
            },
            {
                "event_id": "E",
                "pokemon_key": "a",
                "usage_count": 8,
                "event_team_count": 10,
                "event_team_share": 0.8,
            },
            {
                "event_id": "other",
                "pokemon_key": "c",
                "usage_count": 9,
                "event_team_count": 10,
                "event_team_share": 0.9,
            },
        ],
        "pokemon_event_phase_usage": [
            {
                "scope_kind": "event",
                "event_id": "E",
                "phase": "day2",
                "pokemon_key": "b",
                "team_share": 0.75,
                "team_count": 3,
                "phase_team_count": 4,
                "usage_rank": 1,
            },
            {
                "scope_kind": "regulation",
                "event_id": "",
                "phase": "day2",
                "pokemon_key": "a",
                "team_share": 0.9,
                "team_count": 9,
                "phase_team_count": 10,
                "usage_rank": 1,
            },
        ],
    }
    event = {"event_id": "E", "regulation_code": "m-c"}
    tiles, n = event_top12(marts, event, "all")
    assert [t["pokemon_key"] for t in tiles] == ["a", "b"]
    assert (n, tiles[0]["type_1"]) == (10, "fire")
    day2, day2_n = event_top12(marts, event, "day2")
    assert [t["pokemon_key"] for t in day2] == ["b"]
    assert day2_n == 4


def test_top12_context_formats_shares_and_square_badges():
    from pipelines.render.share_cards import top12_context

    tiles = [{"pokemon_key": "a", "name": "A", "share": 0.519, "type_1": "grass", "type_2": "dark"}]
    context = top12_context(
        tiles,
        layout="story",
        scope_label="Reg M-C",
        sample="3,770 teams · 5 events",
        phase="day2",
        citation="Reg M-C, n = 536 teams",
        art_uri=lambda key: f"art:{key}",
        font_uri="",
    )
    assert context["phase_label"] == "Day 2"
    tile = context["tiles"][0]
    assert (tile["share"], tile["art"]) == ("51.9%", "art:a")
    # Two square badges, story-sized.
    assert str(tile["types"]).count('class="type-emblem"') == 2
    assert "width:40px" in str(tile["types"])
    assert context["site"] == "lancettlim.github.io/pokemon-agent/dashboard"
