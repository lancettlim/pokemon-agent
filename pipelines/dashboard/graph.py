"""Builds the synergy and checks graph (docs/plan-synergy-checks-graph.md,
G4): one graph per regulation scope, laid out here at build time so the
browser only draws it.

Why the layout is computed here rather than in the browser (decision GD2):
a seeded layout is deterministic, so screenshots and tests are stable and
every visitor sees the same picture; it costs a phone no CPU; and it keeps
the dashboard free of a charting or physics library (static/app.js's
header).

Positions are kept stable across regulations. The 'all' graph is laid out
first, and each regulation starts from those positions and runs only a
short refinement, so a Pokémon sits in roughly the same place whichever
regulation the header shows.

Each scope's graph carries:
  nodes     every Pokémon with a kept edge: team count and share, x/y in a
            fixed WIDTH x HEIGHT frame, and its synergy cluster
  synergy   undirected [a, b, pair_team_count, lift, synergy_z] edges,
            floored at MIN_PAIR_TEAMS shared teams and capped at each
            node's top EDGES_PER_NODE by synergy_z
  checks    directed [a, b, matches, wins, observed, expected, z, q,
            evidence] edges from pokemon_check_edges, one per pair, pointing
            from the side whose teams over-perform; only 'strong' and
            'suggestive' pairs
  clusters  label-propagation communities over the synergy edges, named
            "Cluster N" (neutral, the rule detected_archetype_* follows)
            with the detected archetype whose core they overlap most

Pure Python, no new dependency. About 150 nodes lays out in a few seconds.
"""

from __future__ import annotations

import math
import random
from typing import Any

ALL_SCOPE = "all"
WIDTH = 1000.0
HEIGHT = 700.0
MIN_PAIR_TEAMS = 5
EDGES_PER_NODE = 6
# A cluster smaller than this is folded into cluster 0 ("unclustered"):
# a pair of Pokémon is a core, not a region of the metagame.
MIN_CLUSTER_SIZE = 3
SEED = 50
FULL_ITERATIONS = 300
REFINE_ITERATIONS = 60
# Force balance. SPREAD scales the ideal edge length; GRAVITY is a weak
# pull toward the centre that keeps disconnected pieces from drifting to
# the frame's edge. The 'all' layout is then stretched to fill the frame
# (fit_to_frame), so these set the shape, not the size.
SPREAD = 1.3
GRAVITY = 0.006
MARGIN = 40.0

SynergyEdge = tuple[str, str, int, float, float]


def _num(value: Any) -> float:
    return float(value) if value not in (None, "") else 0.0


def synergy_edges(
    rows: list[dict[str, Any]],
    *,
    min_pair_teams: int = MIN_PAIR_TEAMS,
    per_node: int = EDGES_PER_NODE,
) -> list[SynergyEdge]:
    """One scope's undirected synergy edges. pokemon_team_synergy is
    mirrored, so each pair is read from its canonical (a < b) direction.
    Only pairings above chance (lift > 1) count. An edge is kept when it is
    among either endpoint's `per_node` strongest by synergy_z, so a popular
    Pokémon can't take every edge and a niche one keeps its best partners.
    """
    candidates: dict[tuple[str, str], SynergyEdge] = {}
    for row in rows:
        a, b = row["pokemon_key"], row["partner_pokemon_key"]
        if a >= b:
            continue
        teams = int(_num(row.get("pair_team_count")))
        lift = _num(row.get("lift"))
        if teams < min_pair_teams or lift <= 1:
            continue
        candidates[(a, b)] = (a, b, teams, round(lift, 3), round(_num(row.get("synergy_z")), 2))

    by_node: dict[str, list[SynergyEdge]] = {}
    for edge in candidates.values():
        by_node.setdefault(edge[0], []).append(edge)
        by_node.setdefault(edge[1], []).append(edge)
    kept: set[tuple[str, str]] = set()
    for edges in by_node.values():
        edges.sort(key=lambda e: (-e[4], -e[2], e[0], e[1]))
        kept.update((e[0], e[1]) for e in edges[:per_node])
    return sorted((candidates[pair] for pair in kept), key=lambda e: (e[0], e[1]))


def check_edges(rows: list[dict[str, Any]]) -> list[list[Any]]:
    """One scope's check edges, from pokemon_check_edges. That mart is
    antisymmetric, so each pair keeps only its positive-z direction: the
    arrow points from the side whose teams beat the other's more than
    their records predict."""
    out = []
    for row in rows:
        if row.get("evidence") not in ("strong", "suggestive"):
            continue
        if _num(row.get("z_score")) <= 0:
            continue
        out.append(
            [
                row["pokemon_key"],
                row["opponent_pokemon_key"],
                int(_num(row.get("matches_played"))),
                int(_num(row.get("wins"))),
                round(_num(row.get("observed_win_rate")), 4),
                round(_num(row.get("expected_win_rate")), 4),
                round(_num(row.get("z_score")), 2),
                round(_num(row.get("q_value")), 4),
                row["evidence"],
            ]
        )
    out.sort(key=lambda e: (-e[6], e[0], e[1]))
    return out


def label_propagation(
    nodes: list[str], edges: list[SynergyEdge], *, seed: int = SEED, max_rounds: int = 50
) -> dict[str, int]:
    """Seeded label propagation over the synergy edges, weighted by
    synergy_z. Each node in turn takes the label its neighbours carry the
    most weight for; ties go to the smallest label, so the result depends
    only on the seed. Returns node -> raw label (an index into `nodes`)."""
    index = {key: i for i, key in enumerate(nodes)}
    neighbours: dict[str, list[tuple[str, float]]] = {key: [] for key in nodes}
    for a, b, _teams, _lift, z in edges:
        weight = max(z, 0.1)
        neighbours[a].append((b, weight))
        neighbours[b].append((a, weight))
    labels = dict(index)
    order = list(nodes)
    rng = random.Random(seed)
    for _ in range(max_rounds):
        rng.shuffle(order)
        changed = False
        for key in order:
            if not neighbours[key]:
                continue
            weight_by_label: dict[int, float] = {}
            for other, weight in neighbours[key]:
                weight_by_label[labels[other]] = weight_by_label.get(labels[other], 0.0) + weight
            best = max(weight_by_label.values())
            choice = min(label for label, w in weight_by_label.items() if w == best)
            if choice != labels[key]:
                labels[key] = choice
                changed = True
        if not changed:
            break
    return labels


def number_clusters(
    labels: dict[str, int], team_counts: dict[str, int], *, min_size: int = MIN_CLUSTER_SIZE
) -> dict[str, int]:
    """Renumbers raw labels 1..N by each cluster's total team count, largest
    first, and folds clusters under `min_size` into 0 ("unclustered")."""
    members: dict[int, list[str]] = {}
    for key, label in labels.items():
        members.setdefault(label, []).append(key)
    sized = [group for group in members.values() if len(group) >= min_size]
    sized.sort(key=lambda group: (-sum(team_counts.get(k, 0) for k in group), min(group)))
    numbered = {key: 0 for key in labels}
    for number, group in enumerate(sized, start=1):
        for key in group:
            numbered[key] = number
    return numbered


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def layout(
    nodes: list[str],
    edges: list[SynergyEdge],
    *,
    initial: dict[str, tuple[float, float]] | None = None,
    iterations: int = FULL_ITERATIONS,
    seed: int = SEED,
    start_temperature: float | None = None,
) -> dict[str, tuple[float, float]]:
    """Seeded Fruchterman-Reingold layout in a fixed WIDTH x HEIGHT frame.

    `initial` pins the starting position of any node it names (the 'all'
    layout, for a regulation's refinement); other nodes start at the mean
    of their already-placed neighbours, or at a seeded random point. A
    weak pull toward the centre keeps disconnected pieces in frame.
    Attraction is weighted by log lift, so stronger pairings sit closer.
    """
    rng = random.Random(seed)
    margin = MARGIN
    initial = initial or {}
    pos: dict[str, list[float]] = {}
    for key in nodes:
        if key in initial:
            pos[key] = list(initial[key])
    adjacency: dict[str, list[str]] = {key: [] for key in nodes}
    for a, b, *_rest in edges:
        adjacency[a].append(b)
        adjacency[b].append(a)
    for key in nodes:
        if key in pos:
            continue
        placed = [pos[n] for n in adjacency[key] if n in pos]
        if placed:
            x = sum(p[0] for p in placed) / len(placed) + rng.uniform(-20, 20)
            y = sum(p[1] for p in placed) / len(placed) + rng.uniform(-20, 20)
        else:
            x = rng.uniform(margin, WIDTH - margin)
            y = rng.uniform(margin, HEIGHT - margin)
        pos[key] = [_clamp(x, margin, WIDTH - margin), _clamp(y, margin, HEIGHT - margin)]
    if not nodes:
        return {}

    k = math.sqrt((WIDTH * HEIGHT) / len(nodes)) * SPREAD
    weights = [(a, b, 1.0 + math.log(max(lift, 1.0))) for a, b, _t, lift, _z in edges]
    temperature = start_temperature if start_temperature is not None else WIDTH / 10
    cooling = temperature / max(iterations, 1)
    cx, cy = WIDTH / 2, HEIGHT / 2
    for _ in range(iterations):
        disp = {key: [0.0, 0.0] for key in nodes}
        for i, a in enumerate(nodes):
            pa = pos[a]
            for b in nodes[i + 1 :]:
                pb = pos[b]
                dx, dy = pa[0] - pb[0], pa[1] - pb[1]
                dist2 = dx * dx + dy * dy
                if dist2 < 0.01:
                    dx, dy, dist2 = rng.uniform(-1, 1), rng.uniform(-1, 1), 1.0
                force = (k * k) / dist2
                disp[a][0] += dx * force
                disp[a][1] += dy * force
                disp[b][0] -= dx * force
                disp[b][1] -= dy * force
        for a, b, weight in weights:
            pa, pb = pos[a], pos[b]
            dx, dy = pa[0] - pb[0], pa[1] - pb[1]
            dist = math.sqrt(dx * dx + dy * dy) or 0.01
            force = dist * weight / k
            disp[a][0] -= dx * force
            disp[a][1] -= dy * force
            disp[b][0] += dx * force
            disp[b][1] += dy * force
        for key in nodes:
            p, d = pos[key], disp[key]
            d[0] += (cx - p[0]) * GRAVITY * k
            d[1] += (cy - p[1]) * GRAVITY * k
            length = math.sqrt(d[0] * d[0] + d[1] * d[1]) or 0.01
            step = min(length, temperature)
            p[0] += d[0] / length * step
            p[1] += d[1] / length * step
            # A refinement stays inside the frame it inherited; a full
            # layout runs free and is fitted to the frame afterwards, so
            # nodes don't pile up against the walls.
            if initial:
                p[0] = _clamp(p[0], margin, WIDTH - margin)
                p[1] = _clamp(p[1], margin, HEIGHT - margin)
        temperature = max(temperature - cooling, 0.5)
    return {key: (round(p[0], 1), round(p[1], 1)) for key, p in pos.items()}


def fit_to_frame(positions: dict[str, tuple[float, float]]) -> dict[str, tuple[float, float]]:
    """Stretches a layout to fill the WIDTH x HEIGHT frame inside MARGIN.
    Applied to the 'all' layout only: a regulation keeps the coordinates it
    inherited, so a Pokémon stays put when the header switches regulation,
    at the cost of a thin regulation using less of the frame."""
    if len(positions) < 2:
        return positions
    xs = [p[0] for p in positions.values()]
    ys = [p[1] for p in positions.values()]
    span_x = (max(xs) - min(xs)) or 1.0
    span_y = (max(ys) - min(ys)) or 1.0
    scale_x = (WIDTH - 2 * MARGIN) / span_x
    scale_y = (HEIGHT - 2 * MARGIN) / span_y
    return {
        key: (
            round(MARGIN + (x - min(xs)) * scale_x, 1),
            round(MARGIN + (y - min(ys)) * scale_y, 1),
        )
        for key, (x, y) in positions.items()
    }


def _archetype_overlap(
    members: list[str], archetypes: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """The detected archetype whose anchor core (detected_archetype_summary's
    three anchor Pokémon) shares the most Pokémon with a cluster, at least
    two, or None. Archetypes are matched, not merged: a cluster is a region
    of the synergy graph, an archetype a set of real teams."""
    best = None
    best_overlap = 1
    member_set = set(members)
    for archetype in archetypes:
        core = [archetype.get(f"pokemon_key_{s}") for s in "abc"]
        overlap = len({k for k in core if k} & member_set)
        if overlap > best_overlap:
            best, best_overlap = archetype, overlap
    if not best:
        return None
    return {
        "archetype_key": best.get("archetype_key"),
        "core": [best.get(f"pokemon_key_{s}") for s in "abc" if best.get(f"pokemon_key_{s}")],
        "overlap": best_overlap,
    }


def _scope_graph(
    scope: str,
    synergy_rows: list[dict[str, Any]],
    check_rows: list[dict[str, Any]],
    team_counts: dict[str, int],
    total_teams: int,
    archetypes: list[dict[str, Any]],
    initial: dict[str, tuple[float, float]] | None,
) -> dict[str, Any]:
    synergy = synergy_edges(synergy_rows)
    checks = check_edges(check_rows)
    keys = {e[0] for e in synergy} | {e[1] for e in synergy}
    keys |= {e[0] for e in checks} | {e[1] for e in checks}
    nodes = sorted(keys, key=lambda k: (-team_counts.get(k, 0), k))

    if initial is None:
        positions = fit_to_frame(layout(nodes, synergy))
    else:
        positions = layout(
            nodes,
            synergy,
            initial=initial,
            iterations=REFINE_ITERATIONS,
            start_temperature=WIDTH / 60,
        )
    clusters = number_clusters(label_propagation(nodes, synergy), team_counts)

    cluster_members: dict[int, list[str]] = {}
    for key in nodes:
        cluster_members.setdefault(clusters[key], []).append(key)
    cluster_rows = []
    for number in sorted(n for n in cluster_members if n):
        members = cluster_members[number]
        cluster_rows.append(
            {
                "cluster": number,
                "label": f"Cluster {number}",
                "members": members,
                "team_count": sum(team_counts.get(k, 0) for k in members),
                "archetype": _archetype_overlap(members, archetypes),
            }
        )

    return {
        "regulation_scope": scope,
        "total_teams": total_teams,
        "width": WIDTH,
        "height": HEIGHT,
        "min_pair_teams": MIN_PAIR_TEAMS,
        "edges_per_node": EDGES_PER_NODE,
        "nodes": [
            {
                "k": key,
                "teams": team_counts.get(key, 0),
                "share": round(team_counts.get(key, 0) / total_teams, 4) if total_teams else 0,
                "x": positions[key][0],
                "y": positions[key][1],
                "c": clusters[key],
            }
            for key in nodes
        ],
        "synergy": [list(e) for e in synergy],
        "checks": checks,
        "clusters": cluster_rows,
    }


def build_graphs(
    synergy_rows: list[dict[str, Any]],
    check_rows: list[dict[str, Any]],
    usage_rows: list[dict[str, Any]],
    team_count_by_scope: dict[str, int],
    archetype_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Every scope's graph, as one row per scope (the shape the dashboard's
    shard writer expects of a scoped mart). `synergy_rows` is the full
    pokemon_team_synergy mart, not the dashboard's sliced copy: the graph
    caps edges by synergy_z, not lift. `usage_rows` is pokemon_usage_summary
    (a team fields a Pokémon at most once, so its usage_count is a team
    count); `team_count_by_scope` is each scope's team total."""
    archetype_rows = archetype_rows or []

    def by_scope(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row.get("regulation_scope") or ALL_SCOPE, []).append(row)
        return grouped

    synergy_by_scope = by_scope(synergy_rows)
    checks_by_scope = by_scope(check_rows)
    usage_by_scope = by_scope(usage_rows)
    scopes = sorted(set(synergy_by_scope) | set(checks_by_scope), key=lambda s: (s != ALL_SCOPE, s))

    graphs = []
    base: dict[str, tuple[float, float]] | None = None
    for scope in scopes:
        # pokemon_usage_summary also carries one row per event tier; only
        # the overall row (no event_tier) is the scope's team count.
        team_counts = {
            row["pokemon_key"]: int(_num(row.get("usage_count")))
            for row in usage_by_scope.get(scope, [])
            if not row.get("event_tier")
        }
        graph = _scope_graph(
            scope,
            synergy_by_scope.get(scope, []),
            checks_by_scope.get(scope, []),
            team_counts,
            team_count_by_scope.get(scope, 0),
            # detected_archetype_summary has no regulation_scope: its
            # archetypes are matched against every scope's clusters.
            archetype_rows,
            # Every regulation refines the 'all' layout. If there is no
            # 'all' graph (a test fixture), each scope lays out from scratch.
            None if scope == ALL_SCOPE else base,
        )
        if scope == ALL_SCOPE:
            base = {n["k"]: (n["x"], n["y"]) for n in graph["nodes"]}
        graphs.append(graph)
    return graphs
