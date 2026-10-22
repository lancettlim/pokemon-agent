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


def test_square_badge_draws_our_glyph_on_the_type_colour():
    """docs/upgrade-plan-2027q2.md, V6: one definition for site and cards."""
    from pipelines.render import type_glyphs
    from pipelines.render.template import TYPE_COLORS

    assert set(type_glyphs.GLYPHS) == {name for name in TYPE_COLORS if name}
    html = str(type_glyphs.square_badge_html("Fire", 20))
    assert TYPE_COLORS["fire"] in html and 'aria-label="Fire type"' in html
    assert "<svg" in html and 'fill="#fff"' in html
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
