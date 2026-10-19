# Product Requirements Document (PRD)

## Product name
Pokémon Champions Competitive Data Platform

## Document status
Draft v1.1

## Problem statement
Competitive Pokémon Champions data is fragmented across canonical game sources, format-specific balance sources, and tournament/team archives. Analysts, creators, and players must manually gather and normalize this information before they can run useful competitive analysis.

## Product vision
Provide a single, trustworthy, and regularly updated data product for Pokémon Champions that combines canonical game data, format-specific rule/balance data, and tournament usage intelligence.

## Goals
- Create one unified dataset with stable schemas and documented lineage.
- Reduce manual data collection effort for users by at least 80%.
- Enable repeatable analysis for legality, balance deltas, usage trends, and team composition patterns.
- Publish predictable update cadences aligned with format and tournament changes.
- Deliver dashboard analytics for rapid metagame monitoring and decision support.

## Non-goals
- Building a full public consumer-facing battle simulator.
- Real-time ingestion of every live match.
- Replacing source-of-truth ownership from original platforms.

## Target users
- **Competitive analysts**: need clean, queryable historical and current metagame data.
- **Content creators**: need reliable trend snapshots and supporting stats.
- **Team builders/coaches**: need legal pool validation, usage patterns, and matchup context.
- **Internal product teams**: need stable data contracts for downstream dashboards or tools.

## Success metrics
- Dataset freshness SLA met in >=95% of scheduled updates.
- <=1% critical schema/data integrity errors per monthly release.
- >=70% reduction in ingestion-to-analysis lead time for internal users.
- Adoption: at least 3 recurring downstream consumers in first phase.

## Scope
### In scope (Phase 1)
- Source ingestion from:
  - PokéAPI (canonical data)
  - OP.GG Pokémon Champions (format-specific balance/legal pool)
  - MunchStats (tournament and team data)
  - PokéBase app (per-regulation legal-pool membership — pulled in from
    "out of scope" once OP.GG's regulation-agnostic legal pool proved
    insufficient to populate `legality_snapshot.regulation_code`, a locked
    required field; see `dataset-spec.md`'s "V1 scope" section)
- Normalized core entities:
  - Pokémon, forms, canonical stats, Champions stats, stat deltas, legal status
  - Tournament event, player, team, team member, placements
- Change-tracking layer:
  - Canonical vs Champions stat deltas
  - Daily legality snapshots for the OP.GG legal pool
- Documentation:
  - Data dictionary
  - Source lineage and extraction notes
  - Refresh cadence, release package contents, and known limitations
- Dashboard analytics module:
  - KPI overview cards (usage, win-rate proxies, legality changes)
  - Trend views by regulation window and tournament period
  - Drill-down by Pokémon, team core, move, and item usage

### Out of scope (Phase 1)
- Limitless ingestion
- Victory Road ingestion
- Advanced predictive modeling APIs
- Full web application UX
- Community write-back/edit workflows

## Functional requirements
1. System must ingest each in-scope source into staging with source timestamp metadata.
2. System must normalize records into consistent IDs and join keys.
3. System must store both canonical values and Champions-modified values where relevant.
4. System must expose regulation-aware legality fields by snapshot date.
5. System must preserve tournament provenance (event/source/date) for all team and placement records.
6. System must produce exportable flat files for analysis use (CSV/JSON).
7. System must publish schema and field definitions with every release.
8. System must provide dashboard-ready aggregate tables for trend and ranking visualizations.
9. System must support filtered dashboard analytics by regulation, date range, and tournament tier.
10. System must publish a versioned release manifest and changelog for every dataset release.
11. System must enforce documented release gates for coverage, null-rate, duplicate-key, and referential-integrity checks.

## Non-functional requirements
- **Reliability**: deterministic transformations; reproducible outputs.
- **Traceability**: every record mapped to source and extraction run.
- **Maintainability**: modular extraction/transformation steps per source.
- **Compliance**: no unauthorized redistribution of protected content; attribution retained.

## User stories
- As an analyst, I can compare canonical vs Champions stats by Pokémon and form.
- As a team builder, I can filter legal Pokémon by current regulation and item constraints.
- As a creator, I can query top-used cores and moves from recent tournaments.
- As a data consumer, I can trust that each field has clear definitions and provenance.
- As a competitive strategist, I can use dashboards to monitor usage and trend shifts without manual data prep.

## Milestones
1. **M1 – Data contract definition**
   - Finalize schema, primary keys, join keys, provenance rules, and release package contract.
2. **M2 – Source ingestion baseline**
   - Land repeatable extraction for PokéAPI, OP.GG, MunchStats, and PokéBase.
3. **M3 – Normalization and delta layer**
   - Deliver canonical-vs-Champions diff outputs.
4. **M4 – Tournament enrichment**
   - Integrate event/team/player structures.
5. **M5 – Release readiness**
   - Publish v1 dataset package, manifest, changelog, and documentation.
6. **M6 – Dashboard analytics release**
   - Launch first-party analytics dashboard views on top of v1 dataset outputs.

## Risks and mitigations
- **Source structure changes** → Add source-specific validation checks and fallback parsing.
- **Data licensing/usage ambiguity** → Track attribution and limit distribution scope where required.
- **ID mismatches across sources** → Maintain mapping tables and confidence flags.
- **Coverage gaps in tournament data** → Use multi-source triangulation and completeness scoring.

## Open questions
- Which downstream interface is prioritized first (files only vs query endpoint)?
- What governance is needed for schema versioning and deprecations?
- ~~Which dashboard tool stack and hosting model should be used for Phase 1?~~
  **Resolved**: a static HTML/CSS/vanilla-JS site (Jinja2-rendered, no
  backend, no build tooling), generated by `pipelines/dashboard/` and
  deployed via GitHub Pages serving `/docs` on the default branch (the
  dashboard itself lives at `docs/dashboard/`). Chosen for zero server/
  hosting cost and minimal new dependencies, consistent with this repo's
  existing lightweight Python/dbt tooling. Chart.js (originally used) was
  removed entirely in a later redesign pass in favor of a dependency-free
  grid/table component — see `docs/design-system.md`'s "6-wide grid"
  section — so this is now a zero-CDN-dependency page. A dynamic Python/
  Streamlit dashboard is a possible future upgrade once the dataset has
  enough snapshots/trend data to justify the added hosting complexity —
  see `docs/todo.md`'s M6 backlog item. See `docs/dashboard.md` for the
  full architecture writeup.
- ~~Can the dashboard offer real matchup/type-effectiveness context for
  team builders/coaches (line 30's user story)?~~ **Resolved, partially**:
  yes for type-effectiveness and a stats/setup/weather damage calculator
  (the Matchup tab, `docs/design-system.md`'s "Matchup" section) — closed
  by adding real Pokémon type and move detail data from PokéAPI. Real
  head-to-head battle-outcome matchups ("what beats Pokémon X in
  practice") are still not buildable: no in-scope source publishes
  individual battle outcomes against a named opponent, only team-level
  win/loss records. See `docs/design-system.md`'s "Backlog: not yet
  buildable" and `docs/todo.md`'s M6 backlog.
