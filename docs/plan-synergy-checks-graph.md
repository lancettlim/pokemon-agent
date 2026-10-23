# Feature plan — Synergy and checks graph, per regulation

Written 2026-10-23. This is a proposal, filed as `docs/backlog.md` #50.
Nothing here is committed until its items move into `docs/todo.md`.

The site already answers "who does X pair with?" one Pokémon at a time (the
profile's Team Cores, the Core Explorer) and "how do teams with X do against
teams with Y?" one pair at a time (Matchup). It never shows the whole
metagame at once: which Pokémon form clusters, which clusters press on
which, and how that picture changes from M-A to M-B to M-C. This feature
adds that view as a graph, scoped to the regulation picked in the header.

## 1. What the feature is

One new view at `#/graph`, with two layers over the same nodes:

| Layer | Node | Edge | Reads as |
|---|---|---|---|
| **Synergy** (`#/graph/synergy`) | A Pokémon, sized by team share | Undirected; thickness is lift, opacity is shared-team count | "These two share teams more often than their popularity predicts" |
| **Checks** (`#/graph/checks`) | Same | Directed A → B; thickness is the size of the effect, and the line is solid only at strong evidence | "Teams with A beat teams with B more often than the two teams' overall records predict" |

Shared state lives in the hash, like every other view:
`#/graph/<layer>?focus=<pokemon_key>&min=<n>`. The regulation comes from
the header select, the same as every regulation-scoped view.

Focus mode (`?focus=`) is the main way people will use it. It shows one
Pokémon in the centre and its partners, its checks and the Pokémon that
check it in rings around it. That is also the phone layout (section 5).

## 2. What exists today, measured

Measured on 2026-10-23 against the published `docs/dashboard/data/` shards.

**Synergy is ready.** `pokemon_team_synergy` already carries
`regulation_scope` and ships per scope, floored at 5 shared teams
(`MIN_SYNERGY_PAIR_TEAMS` in `pipelines/dashboard/data.py`). Graph size by
floor, counting undirected edges:

| Scope | ≥5 teams | ≥10 | ≥20 | ≥40 |
|---|---|---|---|---|
| M-A | 435 edges / 93 nodes | 274 / 73 | 204 / 58 | 128 / 50 |
| M-B | 173 / 49 | 106 / 34 | 75 / 27 | 27 / 15 |
| M-C | 478 / 107 | 286 / 77 | 199 / 61 | 138 / 51 |
| all | 651 / 144 | 404 / 110 | 297 / 88 | 209 / 73 |

About 100 nodes and a few hundred edges is a readable graph with a floor
and a per-node edge cap. M-B (395 teams, one event) is thin and needs the
existing thin-regulation banner.

**Checks are not ready, for two reasons.**

1. **`pokemon_head_to_head` has no `regulation_scope`.** It pools every
   regulation, so a check from M-A shows up in M-C. This is the main data
   gap for a per-regulation feature. `matchup.js` reads the same pooled
   mart today.
2. **A raw head-to-head win rate is mostly a measure of the Pokémon's own
   strength.** Teams with a strong Pokémon beat nearly everyone, so "best
   matchup" ends up ranking opponents by how weak they are. A check edge
   needs a baseline. The baseline proposed here is the log5 expectation
   from each side's overall win rate, `p = (pA − pA·pB) / (pA + pB − 2·pA·pB)`,
   and the edge is how far the observed record sits from it.

**Most check edges would be noise.** A prototype of that residual over the
current pooled mart (pairs with ≥20 matches) found:

| | Pairs |
|---|---|
| Pairs with ≥20 matches | 3,476 |
| \|z\| ≥ 2 | 240 |
| Expected by chance at \|z\| ≥ 2 (4.6%) | ~160 |
| Pass Benjamini–Hochberg at q ≤ 0.10 | **9** |

The edges that survive make competitive sense. Most are weather and
terrain wars: Tyranitar-Mega teams over Indeedee-F teams (38% vs an
expected 50%, n=368), Excadrill over Indeedee-F, and Tyranitar-Mega over
Torkoal. Kommo-o and Delphox-Mega teams also over-perform against
Rillaboom teams (n=815 and n=870). The signal is real but sparse, and it
gets thinner once the data is split by regulation.

So the tournament checks layer must show its evidence level, and it must
not be drawn as a dense web. The dense version comes from S2 (below).

**A Pokémon-vs-Pokémon source is already planned.** Smogon's monthly chaos
files (`docs/upgrade-plan-2027q2.md` S2, decision D2) carry Checks and
Counters from 1.6M ladder battles per month in M-C. That is real
battle-log grain and dense enough for a full graph. It is a different
population and is never blended with tournament data.

## 3. Data work

All of it reads `int_champions_roster_scoped` and carries
`regulation_scope`, per CLAUDE.md's regulation-registry rule. No format
string or regulation slug is hardcoded.

**G1. Scope `pokemon_head_to_head` by regulation.** Add `regulation_scope`.
Each match takes the regulation of its event (`tournament_event.
regulation_code`), with the `'all'` roll-up beside it. The unique key
becomes `(regulation_scope, pokemon_key, opponent_pokemon_key)`. Update
`pokemon_matchup_summary` to match, and update `matchup.js` to filter on
the selected scope. This changes the numbers on Matchup, so it needs a
changelog line. Size: M.

**G2. New mart `pokemon_check_edges`.** One row per scope and ordered pair
(A, B) with:

- `matches_played`, `wins`, `observed_win_rate`
- `expected_win_rate`: log5, from each Pokémon's overall win rate in the
  same scope (`pokemon_win_rate_summary`)
- `edge = observed − expected`, and `z = (wins − n·p) / sqrt(n·p·(1−p))`
- `q_value`: Benjamini–Hochberg within the scope
- `evidence`: `strong` (q ≤ 0.10), `suggestive` (|z| ≥ 2) or `none`

Rules:

- Drop **mirror contamination**. Leave out a match when the A team also
  fields B, or the B team also fields A, because the effect then cancels
  out by construction.
- Use a minimum of 20 matches, set as a Jinja variable like
  `pokemon_matchup_summary`'s `min_matches`.
- The header comment and `schema.yml` description repeat the team-vs-team
  caveat word for word.

Size: M.

**G3. Add confidence columns to `pokemon_team_synergy`.** Add
`expected_pair_team_count` (the team count times both shares) and a
Poisson `synergy_z`. Both are additive, so no consumer breaks. The graph
then gets a floor based on evidence as well as raw count. Size: S.

**G4. Graph builder `pipelines/dashboard/graph.py`.** This runs at
dashboard build time and is not a dbt model.

- **Precomputed layout.** A seeded Fruchterman–Reingold layout in pure
  Python, one per scope and layer. About 100 nodes takes well under a
  second. It needs no new dependency, keeps screenshots and tests
  deterministic, costs a phone no CPU, and fits the dashboard's
  no-chart-library rule (`app.js` header).
- **Clusters.** Label propagation on the synergy layer, seeded. Clusters
  get neutral names ("Cluster 3"), the same rule `detected_archetype_*`
  follows, plus a link to the detected archetype they overlap most.
- **Edge cap.** Keep each node's top k = 6 synergy edges by `synergy_z`,
  so the graph doesn't become a hairball.
- **Output.** One on-demand shard per scope, `data/graph-<scope>.json`,
  holding nodes (key, team share, x, y, cluster) and edges. It is listed
  in `ON_DEMAND_MARTS` and kept out of `core.json`, so the 500KB core
  budget doesn't move. The estimate is 30–50KB per scope.

Size: M.

**G5. Tests.**

- dbt: uniqueness on the new keys, and
  `assert_check_edges_antisymmetric`, which checks that z(A→B) equals
  −z(B→A) within rounding. Both register as `mart_quality` checks.
- pytest: layout determinism (the same seed gives the same coordinates),
  Benjamini–Hochberg against a hand-worked example, and the edge cap.
- `tests/browser/`: both layers and focus mode at every width in the M1
  matrix, with no overflow, no console errors and no empty panel on a thin
  scope.

## 4. UI

- **Canvas.** Inline SVG, rendered from the precomputed coordinates.
  - Nodes use the existing sprites and type colours.
  - Hovering or tapping a node dims everything that isn't a neighbour.
  - Tapping again sets `?focus=`.
- **Controls.**
  - Layer: Synergy or Checks.
  - Minimum shared teams (synergy) or minimum matches (checks).
  - Evidence: Strong only, or Strong + suggestive (checks only).
  - A Pokémon search to set the focus.
- **Focus mode.** The focused Pokémon sits in the centre with three rings:
  partners (synergy), "its teams beat" and "teams that beat its teams". The
  ring layout is computed in the browser, which is cheap at about 20 nodes.
- **Table twin.** Every graph has a table of the same edges below it,
  built with `createDataTable`, for screen readers and for exact numbers.
- **Labels.**
  - The checks layer always shows: *"Team vs team: teams with A beat teams
    with B more often than their overall records predict. No source
    records which Pokémon were brought, so this is not a battle log."*
  - Suggestive edges are dashed, and the legend says what dashed means.
- **Entry points.**
  - The profile's Team Cores gets a "See on the graph" link.
  - Matchup's best and worst matchups link to `?focus=`.
  - Later, the Builder threat list (laundry-list item 23) can highlight
    Pokémon that check two or more of the six in the team.

## 5. Phones and tablets

Per Track M, the per-tier layout is decided before the build:

| Tier | Layout |
|---|---|
| Phone (<720px) | Focus mode is the default. With no focus set, show the five Pokémon with the highest team share as chips and the table twin. The full graph is behind a "Full graph" button, in a pinch-zoomable sheet. |
| Tablet (720–1023px) | Full graph, with the controls in a band above it. |
| Desktop | Full graph with a side panel for the selected node. |

Touch targets on nodes are at least 44px, using an invisible hit circle
around each sprite.

## 6. Later: the ladder layer

Once S2 ships, the checks layer gets a source switch: **Tournament (team vs
team)** or **Ladder (battle logs)**.

- Ladder edges come from `ladder_checks_counters`, are drawn in the
  LADDER accent colour and carry the LADDER chip.
- The two sources are never blended.
- Where both have an edge, the side panel shows them side by side. How
  often they agree is also a useful check on G2's method.

## 7. Sequencing

The plan fits after the 2027 Q2 cycle's Sprint 10, because the M1 matrix
has to exist first.

| Step | Scope | Exit criteria |
|---|---|---|
| 1 — Data | G1, G2, G3 and their dbt tests | `pokemon_head_to_head` and `pokemon_check_edges` are scoped. Matchup reads the selected scope. The changelog notes the change to Matchup numbers. |
| 2 — Synergy graph | G4, the synergy layer, focus mode, table twin, G5 browser tests | `#/graph/synergy` passes the M1 matrix in every scope, including M-B's thin-data banner. |
| 3 — Checks layer | The checks layer with evidence tiers and links from Matchup and the profile | Strong and suggestive edges are drawn differently. The caveat shows on every checks view. |
| 4 — Ladder | The source switch | Comes after S2 (and D2). |

Steps 1–3 are about one sprint of work, or two if G1's change to the
Matchup view needs extra review.

## 8. Decisions needed

| # | Decision | Recommendation |
|---|---|---|
| GD1 | How to decide a check edge is real | **Log5 residual plus Benjamini–Hochberg at q ≤ 0.10**, with \|z\| ≥ 2 shown as "suggestive". A plain \|z\| cut would draw about 160 chance edges as if they were real. |
| GD2 | Where the layout is computed | **At build time, in Python.** It's deterministic, testable and free on phones. A force simulation in the browser would need a library or a hand-written solver, and every load would look different. |
| GD3 | What node colour means | **Synergy cluster.** Type colour stays on the sprite ring, where it already is. |
| GD4 | Should Matchup switch to scoped head-to-head (G1)? | **Yes.** A pooled figure on a page that is otherwise scoped to one regulation is the same blending bug the regulation registry was built to stop. |

## 9. Risks

| Risk | Mitigation |
|---|---|
| A check edge gets read as "A beats B in battle" | Caveat text on every checks view; the layer's name says "teams"; the ladder layer is the battle-grain answer and is labelled as a different population |
| Readers trust chance edges | Evidence tiers; strong edges only by default; `q_value` in the table twin |
| Core partners are confounded. When Incineroar and Rillaboom share most teams, they inherit the same check edges | Say so in the side panel ("often on the same team as X; their edges overlap"). Partial controls are out of scope for this version |
| The graph turns into a hairball | Floors, the per-node edge cap and focus mode by default on phones |
| Thin scopes (M-B, a new regulation) | The existing thin-regulation banner; checks hidden below the minimum number of matches, with an empty state that says why |
| Anti-synergy is invisible. Pairs that never share a team have no row in `pokemon_team_core_usage` | Out of scope for this version. Listed here so nobody reads a missing edge as "neutral" |
