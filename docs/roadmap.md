# Development roadmap

The original implementation backlog is closed: the ingestion, normalization,
release, renderer, dashboard, and platform-hardening work is shipped. This
roadmap captures the next product cycle and keeps data limitations explicit.

> **Next up (2026 Q4 → 2027 Q2):** `docs/upgrade-plan-2027q2.md` comes before
> the phases below. It covers broadcast-grade visuals modelled on the official
> "Top 12 Pokémon" card, team share as the headline metric, event-weekend
> features, and two new candidate sources: Limitless online events and the
> Showdown ladder. The ladder's Checks and Counters data is the first input
> for Phase 4 below. The previous cycles, `docs/upgrade-plan-2026q4.md`
> (Sprints 1–4) and `docs/upgrade-plan-2027q1.md` (Sprints 5–9), have shipped.

## Phase 1 — Team Analyst 1.0

Status: implemented in the Team Builder pass.

The Team Builder now reports four fast, source-backed checks for the current
roster:

- damaging-move coverage across the 18 defending types;
- shared defensive pressure points and available resistances/immunities;
- base-Speed range and recorded speed/priority utility;
- a screen against the twelve most-used Pokémon in the current Champions
  profile mart.

These are screening metrics. They do not infer EVs, IVs, exact sets, or which
four Pokémon were brought to an individual battle.

## Phase 2 — Historical operations

Status: groundwork implemented; accumulation is operational work.

The scheduled extraction workflow retains date-partitioned snapshots in the
Actions cache and now uploads extraction diagnostics as a short-lived artifact.
The dashboard Data & Sources tab also reports:

- retained snapshot count and date span by source;
- whether enough dates exist for snapshot-over-snapshot analysis;
- published release versions, table counts, image counts, quality failures,
  and known-limitation counts.

Next acceptance gate: at least two clean snapshot dates for each relevant
source, followed by a fresh `make refresh` and a comparison of row counts,
legality membership, and usage outputs before restoring snapshot-based trend
surfaces.

## Phase 3 — Historical comparison views

Build only after Phase 2 has real history:

1. add a snapshot selector to the Data & Sources view;
2. add release-to-release usage and legal-pool diffs;
3. restore meta-shift and legal-pool trend views with explicit sample/date
   coverage;
4. add regression tests for new, removed, and unchanged Pokémon rows.

The existing event-date Usage Trends view remains useful before this phase;
it measures tournament history rather than extraction history.

## Phase 4 — Battle-level analytics discovery

Status: planned research, not yet implementable from the current sources.

The current `tournament_match` data is team-vs-team. A real Pokémon-level
matchup product needs a source that publishes at least one of the following:

- the four Pokémon actually brought to each battle;
- battle turns, active Pokémon, and faint/KO events;
- a stable replay or battle-log identifier tied to an event and players.

Before adding an extractor:

1. identify a permitted, stable source and confirm its redistribution/usage
   terms;
2. write a source contract and a small fixture with provenance fields;
3. measure event, player, and battle coverage against RK9/MunchStats;
4. define normalized `battle`, `battle_side`, and `battle_pokemon` grains;
5. add attribution rules that never present roster-level outcomes as
   individual Pokémon outcomes;
6. build battle-level marts only after coverage and join-quality gates pass;
7. keep the current team-vs-team matchup surface beside the new view, clearly
   labeled for comparison.

Do not add EV/IV fields as a substitute: the repository has verified that no
current in-scope source publishes them.

## Deferred decisions

- A dynamic Streamlit dashboard is not justified while the static GitHub Pages
  surface and current data volume are sufficient.
- Tera analytics should remain absent unless Champions gains a Tera mechanic.
- A Champions rebalance is required before stat-delta analytics can become
  non-degenerate; it cannot be manufactured in the pipeline.
