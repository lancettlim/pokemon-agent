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
                "usage_share": 0.043,
                "usage_share_delta": 0.032,
            }
        ],
        "fallers": [
            {
                "pokemon_key": "salamence-mega",
                "pokemon_name": "Mega Salamence",
                "usage_share": 0.023,
                "usage_share_delta": -0.029,
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
        "4.3%",
        "+3.2 pts",
    )
    assert rising["sprite"] == "data:garchomp-mega-z"
    assert context["columns"][1]["rows"][0]["delta"] == "-2.9 pts"
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
