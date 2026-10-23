"""pipelines/dashboard/graph.py: the Meta Graph's build-time layout,
edge cap, clusters and check-edge direction (docs/plan-synergy-checks-
graph.md, G4/G5)."""

from pipelines.dashboard import graph


def _synergy(scope, a, b, teams, lift, z):
    # pokemon_team_synergy is mirrored: both directions are present.
    return [
        {
            "regulation_scope": scope,
            "pokemon_key": a,
            "partner_pokemon_key": b,
            "pair_team_count": teams,
            "lift": lift,
            "synergy_z": z,
        },
        {
            "regulation_scope": scope,
            "pokemon_key": b,
            "partner_pokemon_key": a,
            "pair_team_count": teams,
            "lift": lift,
            "synergy_z": z,
        },
    ]


def _two_cliques(scope="all"):
    rows = []
    left = ["a1", "a2", "a3", "a4"]
    right = ["b1", "b2", "b3", "b4"]
    for group in (left, right):
        for i, x in enumerate(group):
            for y in group[i + 1 :]:
                rows += _synergy(scope, x, y, 30, 3.0, 8.0)
    # One weak bridge between the two groups.
    rows += _synergy(scope, "a1", "b1", 6, 1.2, 0.5)
    return rows


def _usage(scope, keys):
    return [
        {"regulation_scope": scope, "pokemon_key": k, "usage_count": 10 + i}
        for i, k in enumerate(keys)
    ]


def test_synergy_edges_read_one_direction_and_apply_floors():
    rows = _synergy("all", "a", "b", 10, 2.0, 3.0)
    rows += _synergy("all", "a", "c", 4, 5.0, 9.0)  # under the 5-team floor
    rows += _synergy("all", "a", "d", 50, 0.8, -2.0)  # below chance
    assert graph.synergy_edges(rows) == [("a", "b", 10, 2.0, 3.0)]


def test_edge_cap_keeps_each_nodes_strongest_by_z():
    rows = []
    for i in range(10):
        rows += _synergy("all", "hub", f"p{i}", 20, 2.0, float(i))
    edges = graph.synergy_edges(rows, per_node=3)
    # Every spoke is kept by its leaf (each leaf has one edge), so the cap
    # can't drop any of them: a niche Pokémon keeps its best partner.
    assert len(edges) == 10
    # With a second edge on each leaf that outranks the hub, the hub's
    # cap and the leaves' caps both bind.
    for i in range(10):
        rows += _synergy("all", f"p{i}", f"q{i}", 20, 2.0, 100.0)
    edges = graph.synergy_edges(rows, per_node=1)
    hub_edges = [e for e in edges if "hub" in e[:2]]
    assert hub_edges == [("hub", "p9", 20, 2.0, 9.0)]


def test_check_edges_keep_the_positive_direction_with_evidence():
    rows = [
        {
            "pokemon_key": "a",
            "opponent_pokemon_key": "b",
            "matches_played": 40,
            "wins": 30,
            "observed_win_rate": 0.75,
            "expected_win_rate": 0.5,
            "z_score": 3.16,
            "q_value": 0.05,
            "evidence": "strong",
        },
        {
            "pokemon_key": "b",
            "opponent_pokemon_key": "a",
            "matches_played": 40,
            "wins": 10,
            "observed_win_rate": 0.25,
            "expected_win_rate": 0.5,
            "z_score": -3.16,
            "q_value": 0.05,
            "evidence": "strong",
        },
        {
            "pokemon_key": "c",
            "opponent_pokemon_key": "d",
            "matches_played": 40,
            "wins": 21,
            "observed_win_rate": 0.525,
            "expected_win_rate": 0.5,
            "z_score": 0.3,
            "q_value": 0.9,
            "evidence": "none",
        },
    ]
    assert graph.check_edges(rows) == [["a", "b", 40, 30, 0.75, 0.5, 3.16, 0.05, "strong"]]


def test_layout_is_deterministic_and_in_frame():
    edges = graph.synergy_edges(_two_cliques())
    nodes = sorted({k for e in edges for k in e[:2]})
    first = graph.layout(nodes, edges, iterations=80)
    second = graph.layout(nodes, edges, iterations=80)
    assert first == second
    # A full layout runs free; fitting it fills the frame inside the margin.
    fitted = graph.fit_to_frame(first)
    xs = [p[0] for p in fitted.values()]
    ys = [p[1] for p in fitted.values()]
    assert min(xs) == graph.MARGIN and max(xs) == graph.WIDTH - graph.MARGIN
    assert min(ys) == graph.MARGIN and max(ys) == graph.HEIGHT - graph.MARGIN


def test_a_refinement_stays_inside_the_frame():
    edges = graph.synergy_edges(_two_cliques())
    nodes = sorted({k for e in edges for k in e[:2]})
    start = graph.fit_to_frame(graph.layout(nodes, edges, iterations=80))
    refined = graph.layout(nodes, edges, initial=start, iterations=40)
    for x, y in refined.values():
        assert graph.MARGIN <= x <= graph.WIDTH - graph.MARGIN
        assert graph.MARGIN <= y <= graph.HEIGHT - graph.MARGIN


def test_layout_pulls_partners_together():
    edges = graph.synergy_edges(_two_cliques())
    nodes = sorted({k for e in edges for k in e[:2]})
    pos = graph.layout(nodes, edges)

    def dist(a, b):
        return ((pos[a][0] - pos[b][0]) ** 2 + (pos[a][1] - pos[b][1]) ** 2) ** 0.5

    within = dist("a2", "a3") + dist("b2", "b3")
    across = dist("a2", "b3") + dist("b2", "a3")
    assert within < across


def test_label_propagation_finds_the_two_cliques():
    edges = graph.synergy_edges(_two_cliques())
    nodes = sorted({k for e in edges for k in e[:2]})
    labels = graph.label_propagation(nodes, edges)
    assert len({labels[k] for k in ("a1", "a2", "a3", "a4")}) == 1
    assert len({labels[k] for k in ("b1", "b2", "b3", "b4")}) == 1
    assert labels["a2"] != labels["b2"]
    assert graph.label_propagation(nodes, edges) == labels


def test_clusters_are_numbered_by_size_and_small_ones_fold_to_zero():
    labels = {"a": 7, "b": 7, "c": 7, "d": 3, "e": 3, "f": 3, "g": 9}
    counts = {"a": 1, "b": 1, "c": 1, "d": 50, "e": 50, "f": 50, "g": 500}
    numbered = graph.number_clusters(labels, counts)
    assert numbered["d"] == 1  # the cluster with the most teams
    assert numbered["a"] == 2
    assert numbered["g"] == 0  # a cluster of one is unclustered


def test_regulation_layouts_start_from_the_all_layout():
    rows = _two_cliques("all") + _two_cliques("m-c")
    keys = ["a1", "a2", "a3", "a4", "b1", "b2", "b3", "b4"]
    usage = _usage("all", keys) + _usage("m-c", keys)
    graphs = {
        g["regulation_scope"]: g
        for g in graph.build_graphs(rows, [], usage, {"all": 100, "m-c": 50})
    }
    assert set(graphs) == {"all", "m-c"}
    base = {n["k"]: (n["x"], n["y"]) for n in graphs["all"]["nodes"]}
    moved = [
        ((n["x"] - base[n["k"]][0]) ** 2 + (n["y"] - base[n["k"]][1]) ** 2) ** 0.5
        for n in graphs["m-c"]["nodes"]
    ]
    # Same edges, so the short refinement barely moves anything.
    assert max(moved) < graph.WIDTH / 20


def test_build_graphs_shapes_one_row_per_scope():
    rows = _two_cliques("m-c")
    keys = ["a1", "a2", "a3", "a4", "b1", "b2", "b3", "b4"]
    archetypes = [
        {"archetype_key": "x", "pokemon_key_a": "a1", "pokemon_key_b": "a2", "pokemon_key_c": "zz"}
    ]
    (only,) = graph.build_graphs(rows, [], _usage("m-c", keys), {"m-c": 100}, archetypes)
    assert only["regulation_scope"] == "m-c"
    assert only["total_teams"] == 100
    assert {n["k"] for n in only["nodes"]} == set(keys)
    node = next(n for n in only["nodes"] if n["k"] == "a1")
    assert node["teams"] == 10 and node["share"] == 0.1
    assert len(only["clusters"]) == 2
    clustered = next(c for c in only["clusters"] if "a1" in c["members"])
    assert clustered["archetype"]["archetype_key"] == "x"
    assert clustered["label"] == f"Cluster {clustered['cluster']}"


def test_empty_input_builds_no_graphs():
    assert graph.build_graphs([], [], [], {}) == []


def test_team_counts_ignore_event_tier_rows():
    # pokemon_usage_summary carries an overall row and one per event tier;
    # a tier row listed after the overall one must not overwrite it.
    keys = ["a1", "a2", "a3", "a4", "b1", "b2", "b3", "b4"]
    usage = _usage("m-c", keys) + [
        {"regulation_scope": "m-c", "pokemon_key": k, "event_tier": "Regional", "usage_count": 1}
        for k in keys
    ]
    (only,) = graph.build_graphs(_two_cliques("m-c"), [], usage, {"m-c": 100})
    node = next(n for n in only["nodes"] if n["k"] == "a1")
    assert node["teams"] == 10
