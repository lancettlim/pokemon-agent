# TODO

Outstanding work for the v1 Pokémon Champions dataset artifact, derived from
`dataset-spec.md` and `prd.md`.

## Repository scaffolding

- [x] Create placeholder directories for staging, normalized, manifests,
  changelogs, and validation reports (`data/`, `releases/`, `reports/`)
- [x] Add a `manifest.json` starter template (`releases/manifests/manifest.template.json`)
- [x] Add a `CHANGELOG.md` starter template (`releases/changelogs/CHANGELOG.template.md`)
- [x] Add example/schema files for staging snapshots (`data/staging/*.schema.json`)
- [x] Add example/schema files for normalized tables (`data/normalized/*.schema.json`)
- [x] Add a validation report template (`reports/validation/validation_report.template.json`)

## Tooling

- [x] Add `pyproject.toml`/`uv.lock`-managed Python environment (pandas,
  requests, dbt-core, dbt-duckdb, pytest, ruff)
- [x] Add `pipelines/` package skeleton (`extract/` stubs per source,
  `validate/report.py`, `cli.py`)
- [x] Add `dbt/` project: staging sources, normalized models (see Phase 2),
  and singular tests encoding the coverage/null-rate/duplicate-key/
  referential-integrity gates from `dataset-spec.md`
- [x] Add `Makefile` with `setup`/`lint`/`test`/`dbt-build`/`validate`/`check`
  targets
- [x] Update `CLAUDE.md` and `.claude/loop.md` to reflect the build/test
  system
- [x] Add the Playwright dependency and browser-install step (`make setup`
  installs Chromium); implementing the OP.GG scraper itself is tracked
  under "Phase 1 — Ingestion" below

## Phase 1 — Ingestion

- [x] Implement extraction contract for PokéAPI (pokemon identity + base stats)
- [x] Implement extraction contract for OP.GG Pokémon Champions (legal pool +
  rebalanced stats)
- [x] Implement extraction contract for MunchStats (tournament/team/roster data)
- [x] Implement extraction contract for PokéBase (per-regulation legal-pool
  membership; pulled into v1 scope — see "V1 scope" in `dataset-spec.md` —
  once OP.GG proved insufficient for `legality_snapshot.regulation_code`)
- [x] Land staging outputs with raw snapshots and extraction metadata
- [x] Validate source availability and row-level parsing success thresholds
  (see `reports/validation/extraction_summary.json`: 100% request success
  and 0% required-field null rate across all four sources)
- [x] Extend MunchStats extraction (`pipelines/extract/munchstats.py`) to
  additionally capture `metadata.json`'s `type` field (tournament tier,
  e.g. "International"), `players.json`'s `record` field (win-rate proxy),
  and team-member `item`/`ability`/`tera_type`/`moves` fields — only
  `pokemon` is captured per slot today; update
  `data/staging/munchstats.schema.json` to match (see the gap noted in
  `dbt/models/marts/schema.yml`)
  (staging CSV now carries `event_tier`, `record_wins`/`record_losses`,
  `item_name`, `ability`, `tera_type`, and pipe-delimited `moves`; still
  raw/unmapped — Phase 2 normalizes these into the entity dictionary)

## Phase 2 — Normalization

- [x] Standardize IDs and join keys (`pokemon_key`, `pokemon_id`) across
  canonical, Champions, tournament, and legality data (`dbt/models/normalized/pokemon.sql`
  + `dbt/models/intermediate/`; PokéAPI extraction now covers Mega/regional/
  alternate forms too, and `dbt/seeds/*.csv` hold the controlled OP.GG-,
  MunchStats-, and PokéBase-name-to-PokéAPI-form mappings dataset-spec.md
  calls for)
- [x] Build `pokemon_stat_delta` (canonical vs Champions) outputs
- [x] Generate regulation-aware `legality_snapshot` outputs, sourced from
  PokéBase (`dbt/models/intermediate/int_pokebase_mapped.sql`) instead of
  OP.GG — OP.GG's Champions Pokédex page has only a single
  regulation-agnostic legal pool, so `regulation_code` was permanently
  null there; PokéBase publishes real per-Pokémon regulation-set
  membership (`m-a`/`m-b` as of this snapshot) and closes the gap. This
  table's null-rate gate now passes.
- [x] Normalize `tournament_event`, `tournament_team`, `tournament_team_member`
  (`dbt/models/intermediate/int_munchstats_deduped.sql` also resolves 9
  upstream MunchStats teams that were double-recorded under two placements)
- [x] Once the MunchStats extractor captures tier/record/item fields (see
  Phase 1), add them to `docs/dataset-spec.md`'s entity dictionary —
  `tournament_event` (tier), `tournament_team` (win-rate/`record`),
  `tournament_team_member` (`item`/`ability`/`tera_type`/`moves`) — and
  thread them through the corresponding `dbt/models/normalized/` models
  (new "Optional fields" bullets added to each entity, since MunchStats
  doesn't report tier/record/build for every event/player/slot; the three
  `dbt/tests/singular/assert_null_rate_*` gates were deliberately left
  untouched — they track only the pre-existing required-field lists)

## Phase 3 — Analytics and dashboard outputs

- [x] Publish flat analytical exports and summary aggregates
  (`dbt/models/marts/`: `pokemon_usage_summary`, `legality_summary_by_regulation`,
  `stat_change_leaderboard`, written to `data/marts/*.csv`)
- [x] Provide dashboard-ready trend tables (usage, legality, stat changes)
  (same three marts — `stat_change_leaderboard` currently shows every
  Pokémon as a "gainer" with delta 0, consistent with the zero-stat-delta
  snapshot noted in `releases/manifests/manifest-0.1.0.json`'s
  `known_limitations`, not a bug)
- [x] Document KPI views and filter dimensions (regulation/date/tournament tier)
  (`dbt/models/marts/schema.yml`): regulation and date are available now;
  tournament tier, win-rate proxies, and move/item drill-down (`docs/prd.md`'s
  fuller ambition) need MunchStats extraction fields not captured yet
  (`type`, `record`, `item`/`ability`/`moves` are in the raw source per
  `pipelines/extract/munchstats.py`'s docstring) — documented as a gap
  rather than faked
- [x] Once tier/record/item fields are normalized (see Phase 2), extend
  `dbt/models/marts/` and its `schema.yml` to support tournament-tier
  filtering, win-rate-proxy KPIs, and move/item drill-down, closing the
  gap this section's "Document KPI views and filter dimensions" item
  flagged
  (`pokemon_usage_summary` gained an `event_tier` dimension — one overall
  row per Pokémon plus one row per tier, each ranked within its own
  partition; new marts `pokemon_win_rate_summary` (record_wins/losses-based
  win rate), `pokemon_build_usage` (item x ability usage), and
  `pokemon_move_usage` (unnested move usage) cover the rest. Also fixed a
  pre-existing gap where `pipelines/cli.py`'s `extract` subcommand never
  registered the `pokebase` source, and updated `.gitignore`'s comment to
  match — both silently missed when PokéBase was added in an earlier pass.)

## Phase 4 — Visual assets and card rendering

- [x] Implement extraction contract for Bulbagarden Archives
  (`pipelines/extract/bulbagarden.py`: MediaWiki API pagination + batched
  imageinfo resolution + binary image download to a local gitignored cache,
  no HTML parser dependency needed — see its docstring)
- [x] Fetch the real Bulbagarden Champions-menu-sprites category inventory
  (359 titles) and build the `bulbagarden_title_to_pokeapi_form` mapping
  seed against live PokéAPI data (`dbt/seeds/bulbagarden_title_to_pokeapi_form.csv`
  + `dbt/seeds/schema.yml`); 358/359 titles resolved (one, Mega Meowstic,
  deliberately left unmapped rather than guessed, matching
  `opgg_key_to_pokeapi_form`'s precedent for the identical ambiguity)
- [x] Normalize into the new `pokemon_asset` entity
  (`dbt/models/staging/stg_bulbagarden.sql`,
  `dbt/models/intermediate/int_bulbagarden_mapped.sql` — including the
  cosmetic-duplicate dedup Vivillon/Florges/Furfrou/Alcremie/Pyroar need —
  `dbt/models/normalized/pokemon_asset.sql`); 317 final rows; all four
  release gates (duplicate-key, null-rate, referential-integrity, >=85%
  coverage) pass against real extracted data
- [x] Add PokéAPI-sprites-GitHub type/item icon fetch-on-demand helper
  (`pipelines/render/assets.py`) and a static move-name-to-type reference
  seed (`dbt/seeds/pokeapi_move_types.csv`, all 937 PokéAPI moves) for
  card rendering — neither is a dataset entity or release gate, both are
  rendering-support assets only
- [x] Build the team card renderer (`pipelines/render/`: `data_source.py`
  loads a `CardModel` from either real ingested `tournament_team`/
  `tournament_team_member` data by `team_id` or an ad-hoc JSON build spec;
  `template.py` renders Jinja2 HTML/CSS with base64-inlined sprite/icon
  images; `team_card.py` screenshots it to PNG via Playwright's headless
  Chromium) and a `render-card` CLI subcommand
  (`--team-id <id>` or `--spec <path.json>`, `--output <path.png>`)
- [x] Wire real Bulbagarden sprite art into the renderer end-to-end for a
  team_id pulled from real MunchStats data (ran all five extractors +
  `make dbt-build` for real, then `render-card --team-id
  011yDp6gkk3AeXY6wFCm` — confirmed real sprite art, not placeholder, for
  all 6 roster slots: Sneasler, Kingambit, Aerodactyl, Basculegion,
  Sylveon, Alolan Ninetales)
- [x] Extend `pipelines/release/build.py` to copy `pokemon_asset`-
  referenced images into `releases/data/<version>/images/` and add the
  Bulbagarden source + `pokemon_asset` table + images block to the
  manifest/changelog templates, plus a redistribution-posture disclaimer
  (Bulbagarden-sourced artwork is ultimately Nintendo/Game Freak-owned;
  see `docs/dataset-spec.md`'s "Image asset source" section — the copy
  step, manifest/changelog templates, and `releases/data/README.md`
  disclaimer were already in place; fixed a real gap where a missing
  cached image would crash the release with `FileNotFoundError` instead of
  skipping it gracefully — coverage gate is only >=85%, not 100% —  and
  cut `dataset_version 0.2.0`, the first release with real Bulbagarden
  data: 317 images copied, 0 missing, `pokemon_asset` at 317 rows)

## M6 — Dashboard analytics release

The two unchecked `Backlog:` items below (originally three; #30 and #34
have since shipped, see their entries above) mirror `docs/backlog.md`'s
#18-#20/#29-#30 trend-chart work and #31's Streamlit dashboard. Both were
**archived** on 2026-08-02 — excluded from active scope by explicit user
decision, alongside `backlog.md`'s meta-shift/legal-pool/stat-change trend
items — so they stay unchecked but are no longer active work; see
`backlog.md`'s "Archived" notes on those numbered entries for the shared
rationale. They stay here as the committed record either way; `backlog.md`
holds everything not yet committed to.

- [x] Stand up a first-party analytics dashboard (KPI overview cards;
  trend views by regulation window and tournament period; drill-down by
  Pokémon, team core, move, and item) on top of `data/marts/*.csv`, per
  `docs/prd.md`'s M6 milestone and "Dashboard analytics module"
  requirement (`pipelines/dashboard/`: KPI cards, usage-by-tier/
  win-rate/build/move drill-downs are functional today against real data)
- [x] Decide and document the dashboard's tech stack and hosting approach
  (resolved in `docs/prd.md`'s Open questions and `docs/dashboard.md`: a
  static HTML/CSS/vanilla-JS site, Chart.js via CDN, no backend, deployed
  via GitHub Pages serving `/docs`)
- [x] Remove the stat-change leaderboard and legal-pool trend-by-regulation
  sections: both were structurally built but permanently showed a
  "not enough data yet" empty state (zero nonzero stat deltas, only one
  `snapshot_date`), so they were cut from `index.html.jinja`/`app.js`
  rather than ship two always-empty sections — see `docs/dashboard.md`'s
  "Removed sections" note; re-add once a rebalance + multiple snapshots
  make the underlying data real
- [x] Dashboard full redesign (live at
  https://lancettlim.github.io/pokemon-agent/dashboard/): tabbed navigation
  (Overview/Usage/Builds/Moves/Team Cores) replacing the single scrolling
  page; Pokémon sprites, move-type icons, and item icons throughout (KPI
  cards, tables, chart axes, chart tooltips — see `docs/dashboard.md`'s
  "Icon sources"); mobile-responsive layout for the KPI grid, tab nav, and
  tables (breakpoints at 720px/480px, horizontal table scroll); and a new
  `pokemon_team_core_usage` mart + Team Cores drill-down tab, closing the
  "team core" gap named in `docs/prd.md`'s original scope ("Drill-down by
  Pokémon, team core, move, and item usage") but never built until now.
  The stat-change leaderboard and legal-pool-trend sections stay removed
  (still genuinely data-starved, see above) and were not part of this pass.
- [x] Write a UX design system for the dashboard
  (`docs/design-system.md`: design tokens, component catalog, Pokémon-
  representation and naming conventions, ordering conventions) and apply
  it: PascalCase Pokémon display names derived from `pokemon_key`/
  `form_name` instead of the species-only `pokemon_name` column (fixes a
  real bug where alternate forms of one species, e.g. Landorus-Incarnate
  vs. Landorus-Therian, displayed identically —
  `pipelines/dashboard/data.py`'s `to_pascal_case()`, revised from an
  initial camelCase pass); usage-percentage
  (`pokemon_usage_summary.usage_share`) surfaced on the "Most Used" KPI
  card and a new Usage leaders table; explicit descending order-by-usage/
  order-by-win-rate on every Pokémon leaderboard/picker (see
  `docs/design-system.md`'s "Ordering convention"); a new **Speed Tiers**
  tab (bar chart + full table, bucketed into Blazing/Fast/Average/Slow
  badges) built on a new `pokemon_champions_profile` mart (one row per
  legal Pokémon: Champions-format base stats + usage/win-rate); and a new
  **Team Builder** tab (fully client-side, `localStorage`-persisted,
  no backend) for assembling a roster of up to 6 from the legal pool,
  sortable by usage/win-rate/speed, with a speed-order readout reusing
  the Speed Tiers badge scale. Rank badges added to the Usage and Win-rate
  leaders tables for a consistent leaderboard pattern across tabs.
- [x] Backlog: type-effectiveness / head-to-head matchups — **partially
  resolved** by the competitive-UX redesign pass below (new **Matchup**
  tab: type effectiveness + a stats/setup/weather damage calculator, using
  new `pokemon.type_1`/`type_2` and `move_detail` data from PokéAPI). Still
  not buildable: real head-to-head battle-outcome data — MunchStats
  reports team-level win/loss records, not individual battle outcomes
  against a named opponent, so "what beats Pokémon X in practice" has no
  real signal; the Matchup tab's co-usage panel is an explicitly-labeled
  teammate-pairing proxy, not that signal. Closing this for real needs a
  battle-log source not currently in scope or deferred (see
  `docs/design-system.md`'s "Backlog: not yet buildable").
- [x] Broadcast/esports dashboard redesign + feature expansion: full
  visual re-theme (`docs/design-system.md`'s broadcast color-block header,
  `--accent-red`/`--accent-gold` tokens, three-step `--icon-sm/md/lg`
  scale replacing four ad-hoc pixel sizes); removed Chart.js/CDN entirely
  in favor of a dependency-free ranked-list component
  (`renderRankedList()`); merged the Builds/Moves/Team Cores tabs into one
  **Pokémon Profile** tab with a single relevance-sorted picker; Pokémon
  `<select>` dropdowns now sorted by `usage_share` descending instead of
  alphabetically (superseding the prior "dropdowns stay alphabetical"
  convention); sortable `<th>` columns on every leaderboard table
  (resolves the "sortable table columns" backlog item below); new
  **Archetypes** tab (Archetype Explorer) backed by a curated,
  editorial-not-sourced `dbt/seeds/archetype_pokemon_map.csv` seed plus two
  new marts (`pokemon_archetype_usage`, `archetype_summary`); new
  **Regulations** tab (Regulation Comparison) backed by a new
  `cumulative_legal_pokemon_count` column on `legality_summary_by_
  regulation` (naive union across regulations, with the PokéBase
  no-removal-signal caveat shown as visible UI copy — resolves the
  "regulation-code filter" half of the backlog item below); new
  `build_share`/`move_share`/`partner_share` percentage columns on
  `pokemon_build_usage`/`pokemon_move_usage`/`pokemon_team_core_usage` so
  raw counts could be dropped from every view in favor of percentages (a
  small `(n=X)` annotation stays next to win rate specifically, so a
  100%-on-n=1 doesn't read as more authoritative than a well-established
  Pokémon's real win rate); Overview redesigned into a "Top 12" spotlight
  grid + "Top 30" ranked list; a minimum-recorded-matches filter on Win
  rate leaders; `player_name`/`player_country` (real MunchStats fields
  that were previously discarded during extraction, only hashed into an
  opaque `player_id`) now flow through to `tournament_team` and into
  `pipelines/render/`'s `CardModel`; the team-card renderer re-themed to
  match the dashboard's broadcast palette with a player/country banner
  row; and a new **Pro Team Gallery** (curated real teams, pre-rendered
  via `render-card` and committed to `data/reference_teams/`, shown in the
  Team Builder tab with a "Load into my builder" button) — see
  `docs/dashboard.md`'s "Pro Team Gallery", "Cumulative legal pool", and
  "Archetype Explorer" sections.
- [x] Competitive-UX dashboard redesign pass: new PokéAPI extraction
  (`pokemon.type_1`/`type_2`; new `move_detail`/`ability_detail`/
  `item_detail` reference tables, scoped to names seen in real tournament
  rosters) closing the type/move-detail half of the matchup backlog item
  above; new `top_tournament_teams` mart (real MunchStats team leaderboard
  by win_rate); removed the **Archetypes** and **Regulations** tabs
  (`legality_summary_by_regulation` still feeds the page-level Legal Pool
  KPI card, just has no dedicated tab); removed Overview's Top 30 ranked
  list (Top 12 grid only — the Usage tab is the full leaderboard now);
  replaced the ranked-list bar component with a dashboard-wide `.grid-6xn`
  6-column grid (`renderGrid6xn()`) used for every usage/win-rate metric,
  with bolded headline percentages; split the old combined
  `pokemon_build_usage` mart into `pokemon_item_usage`/
  `pokemon_ability_usage`, and gave the Pokémon Profile tab three separate
  Items(top 5)/Ability(top 5)/Moves(top 15) `.grid-6xn` sections instead of
  one combined table, each showing a PokéAPI `short_effect` description; a
  larger `--icon-xl` dual-type badge on the Profile header; new type/role/
  stat-range/usage-range filters (Usage, Speed Tiers, Team Builder); new
  **Matchup** tab (type effectiveness, teammate co-usage, and a damage
  calculator — core mechanics plus a curated item/ability toggle list,
  documented scope in `docs/design-system.md`); new **Top Teams** tab
  (real `top_tournament_teams` leaderboard, the Pro Team Gallery moved
  here from Team Builder, and a pokepast.es-style Showdown-text paste-in/
  out importer/exporter); Team Builder slots now show stats/top-ability/
  top-4-moves per pick, plus an "Export as pokepaste text" button. See
  `docs/design-system.md` for the full component/token reference.
- [x] **Mart-wiring pass (2026-08-03)**: wire every analytics mart the
  backlog had shipped-but-left-unsurfaced into the dashboard.
  `pipelines/dashboard/data.py`'s `MART_FIELDS` listed 11 marts while
  `dbt build` produced 23, so eight real, tested, non-degenerate marts
  were readable only through `docs/local-queries.md`. All eight are now
  wired: **Usage** gained a regulation filter (`pokemon_usage_by_
  regulation`, #12) and a **Success** subtab (`pokemon_placement_weighted_
  usage`, #8) with a rank-movement badge; **Pokémon Profile** gained
  build-concentration badges (`pokemon_build_concentration`, #14) and a
  co-occurrence/synergy-lift toggle on Team Cores (`pokemon_team_synergy`,
  #9); **Speed Tiers** now reads `pokemon_speed_tiers` (#16) with a
  scenario selector (base / max investment / ×1.5 / ×2 / ×3) and an
  "Outruns" benchmark, replacing the flat base-speed view; **Matchup**
  gained a per-side Matchup-profile panel (`pokemon_matchup_summary`); and
  a new **Players & Regions** tab surfaces both halves of #7
  (`pokemon_usage_by_country`, `player_signature_pokemon`).
  `stat_change_leaderboard` (#17), the archetype marts, and
  `roster_source_agreement` stay deliberately unwired — see
  `docs/dashboard.md`'s "Marts wired in the mart-wiring pass" for why, plus
  the payload-slicing rationale for the two large marts. Verified against a
  real `extract all` + `dbt build` + `build-dashboard` run, driven in
  Chromium with zero console errors — which caught two real data-shape
  problems that the mart columns alone would have shipped as misleading
  views: a "signature Pokémon" share is structurally capped at 16.7% (a
  Pokémon appears at most once on a six-slot team), so the specialists
  table ranks on share of the player's *teams* instead; and only three
  Champions events exist at all, so a `>= 3` recorded-teams floor left the
  By-player view showing exactly one player (2,329 players have one team,
  358 have two, one has three) — the floor is 2. Both are documented in
  `docs/dashboard.md`.
- [ ] ARCHIVED (excluded from active scope, 2026-08-02): further dashboard
  capability items not covered by the above redesigns: a tournament-event/
  date filter once multiple snapshots exist (still blocked — only one
  `snapshot_date` in the data; the event-date variant shipped separately,
  see the Usage-tab Trends subtab item above), and trend/line charts once
  that same multi-snapshot data exists. Note the event-date-filter part of
  this specific bullet is now stale on top of being archived — #30 already
  shipped a tournament-*date* filter over `pokemon_usage_by_event_date`;
  what's left here is only the snapshot-date variant, i.e. `backlog.md`'s
  #18-#20.
- [ ] ARCHIVED (excluded from active scope, 2026-08-02): build a dynamic
  Python/Streamlit dashboard on top of `pipelines/dashboard/data.py`'s
  existing mart-loading/KPI logic, once the dataset has enough snapshots/
  trend data (multiple `snapshot_date`s, a real Champions rebalance) to
  justify the added hosting complexity beyond today's free static GitHub
  Pages site — not part of this pass's scope (`backlog.md` #31)

## Foundational enablers (backlog Section 0)

The five items below are mirrored in `docs/backlog.md`'s "Section 0 — Foundational
enablers" (items #1-#5); restating them here per `.claude/loop.md`'s backlog-grooming
loop. Item #1 was the highest-leverage: it unblocked eight other backlog entries.
All five are now shipped.

- [x] Backlog: Append-only staging snapshot history — `pipelines/cli.py`'s
  `extract` subcommand now writes each run to a date-partitioned
  `data/staging/<source>/<date>.csv` (one file per UTC day) instead of the
  extractors overwriting a single file; the extractors themselves (`extract()`
  in each `pipelines/extract/*.py` module) were left untouched since they
  already just write to whatever `output_path` they're given — the
  partitioning lives in the caller. Pruned per source after every write via
  `_RETENTION_COUNTS` (12 weekly PokéAPI snapshots, 14 daily OP.GG/PokéBase,
  7 daily MunchStats given its ~37MB/run size, 10 on-demand Bulbagarden).
  Format stays CSV, not Parquet — matches the existing
  `data/staging/*.schema.json` contracts and needs no new dependency.
  `dbt/models/staging/_sources.yml`'s `external_location` now globs each
  source's directory. `.gitignore` updated to match (`docs/backlog.md` #1)
- [x] Backlog: Snapshot-aware dbt layer — every `dbt/models/staging/stg_*.sql`
  now unions all retained snapshots with a `cast(extracted_at_utc as date) as
  snapshot_date` column (matching `legality_snapshot`'s existing convention),
  making the full extraction history queryable directly from staging. A new
  `dbt/models/intermediate/int_*_latest.sql` selector per source (8 total)
  filters back down to the current point-in-time snapshot; the models that
  used to reference `stg_*` directly (`pokemon`, `pokemon_stat_canonical`,
  `move_detail`, `ability_detail`, `item_detail`, and the four `int_*_mapped`
  models) now reference the corresponding `int_*_latest` model instead — a
  parallel history layer alongside the normalized entities, per the lower-
  disruption option `docs/backlog.md` #2 itself suggested, rather than making
  the normalized layer snapshot-scoped. Verified end-to-end against a
  synthetic two-snapshot PokéAPI fixture (older snapshot with a deliberately
  wrong stat value, newer with the real one): `stg_pokeapi` correctly showed
  both dates, `int_pokeapi_latest` correctly kept only the newer one, and
  `pokemon_stat_canonical.csv` was unaffected — one row per Pokémon, no new
  columns leaked into the normalized CSV output (`docs/backlog.md` #2)
- [x] Backlog: Scheduled refresh automation — new
  `.github/workflows/scheduled-extraction.yml`: daily cron for OP.GG/
  MunchStats/PokéBase, weekly cron for PokéAPI, `workflow_dispatch` for
  ad-hoc runs, Bulbagarden left on-demand-only per its unverified rate-limit
  posture. Since `data/staging/` is intentionally gitignored (see item #1),
  runner-to-runner persistence goes through `actions/cache` (unique key per
  run plus a `restore-keys` prefix fallback, since a cache entry is immutable
  once created) rather than committing snapshots to the repo (`docs/backlog.md` #3)
- [x] Backlog: Plumb `dataset_version` through extraction — new
  `pipelines/versioning.py`'s `latest_published_version()` reads the highest
  version under `releases/manifests/manifest-*.json`; `extract`'s new
  `--dataset-version` flag defaults to it (a routine refresh is staged toward
  a patch bump of the currently-published version unless told otherwise) and
  is threaded through to every extractor call. `pipelines/validate/report.py`'s
  `generate()` uses the same default instead of a hardcoded `"0.1.0"`
  (`docs/backlog.md` #4)
- [x] Backlog: Orchestration entry point — `extract` gained an `all` source
  choice that runs every extractor in dependency order (munchstats before
  pokeapi, so pokeapi's move/ability/item detail fetch has roster names to
  scope to); new Makefile targets `extract-all`, `refresh` (`extract-all` →
  `dbt-build` → `validate`), and `release` (`refresh` → `pipelines.cli
  release`, gated on an explicit `VERSION=X.Y.Z` since picking the next
  dataset version is a human call), chained the same way `dashboard` already
  chains `dbt-build` → `build-dashboard` (`docs/backlog.md` #5)

## Platform hardening (backlog Section 3)

- [x] Backlog #36: Fix vacuously-passing coverage tests — the four
  `dbt/tests/singular/assert_*_coverage.sql` gates (OP.GG legal pool,
  PokéBase legal pool, Bulbagarden sprite, tournament-team-member mapping)
  each had a `when total_count = 0 then 10000` branch that reported 100%
  coverage whenever their source had zero rows, so a total upstream outage
  yielding an empty staging CSV passed every gate and could be released.
  Changed each to report `0` (not `10000`) in that branch instead, so an
  empty source now fails its coverage gate. Confirmed the zero-row branch
  can only be reached by a genuinely empty (but present) snapshot file, not
  a missing one — DuckDB's external-source glob (`_sources.yml`'s
  `external_location`) raises an `IO Error` before the query ever runs if
  no file matches the pattern, verified directly against `duckdb.connect()`
  with a nonexistent vs. an empty (header-only) CSV.
- [x] Backlog #38: Don't swallow the `dbt build` return code —
  `pipelines/cli.py`'s `_run_validate` now captures `dbt build`'s exit code
  instead of discarding it, and treats an exit code outside `{0, 1}` as an
  unexpected crash (returned directly, without generating a report). Even
  for the expected `0`/`1` range, it no longer assumes a `1` means "tests
  ran and some failed" — it now checks that `dbt/target/run_results.json`
  was actually rewritten during this invocation (mtime at or after the
  subprocess call started) before reshaping it into a report, so a compile
  or connection error that exits non-zero without producing fresh results
  is refused rather than silently reshaping a stale prior run's artifacts
  into a false pass. Also switched the subprocess call from bare `dbt` to
  `uv run dbt` to match the Makefile's invocation, and dropped a no-op list
  copy (`[f for f in ...]` -> the list itself). New tests in
  `tests/unit/test_cli.py` cover the clean-pass, gate-failure,
  unexpected-crash-code, and stale-run_results cases.
- [x] Backlog #35: CI workflow — new `.github/workflows/ci.yml`, triggered
  on every PR and push to `main`. `lint`/`test` always run (offline, no
  network dependency). `dbt-build`/`validate` restore the same
  `actions/cache` entry `scheduled-extraction.yml` already populates
  (read-only, via `actions/cache/restore`, so CI never re-extracts or hits
  any external source itself) and run against that; degrades to a skipped
  no-op on a fresh fork with no scheduled run yet, rather than failing.
  Caught firsthand: PR #40 (backlog #8/#10/#12/#13/#14) had zero CI checks
  run against it before this existed.
- [x] Backlog #32: JSON feed alongside the baked-in dashboard data —
  `pipelines/dashboard/build.py`'s `build()` now also writes `data.json`
  (the same payload) alongside `index.html`, which stays the inline-data
  version so it keeps working opened directly via `file://`.
- [x] Backlog #46: Dashboard JS duplication check — new
  `tests/unit/dashboard/test_static_duplication.py`, comparing
  `pipelines/dashboard/static/{app,matchup,teams}.js` directly against
  their committed `docs/dashboard/` copies. Its first run **failed for
  real**: `app.js` had moved on through two more commits (sub-tabs,
  icon-only type badges, a sortable moves table) past the last time
  `docs/dashboard/app.js` was actually republished, so the live GitHub
  Pages dashboard was missing real, already-built UI features. Fixed by
  rerunning `make dashboard` and committing the regenerated
  `docs/dashboard/`.
- [x] Backlog #37: Derive the validation report from dbt's manifest —
  `pipelines/validate/report.py` used to map tests to report sections via
  four hardcoded dicts; five real singular tests (`ability_detail`,
  `item_detail`, `move_detail`'s duplicate-key tests, plus
  `archetype_pokemon_map`'s duplicate-key and referential-integrity tests)
  ran on every build but appeared in no report section, so they could
  never block a release. Every singular test now declares its own
  `{{ config(meta={category: ..., ...}) }}`, and `build_report` buckets by
  `meta.category` instead of a name lookup; an uncategorized test lands in
  a new `uncategorized_checks` section (still gate-eligible) instead of
  vanishing. Verified against a real `extract all` + `dbt build`: all 13
  duplicate-key tables and 9 referential-integrity checks now appear with
  real status.
- [x] Backlog #39: Source freshness gate — `dbt/models/staging/_sources.yml`'s
  seven scheduled sources gained `freshness:`/`loaded_at_field` config
  (thresholds mirroring `docs/dataset-spec.md`'s weekly/daily cadences);
  `pipelines/cli.py`'s `_run_validate` now also runs `dbt source
  freshness`, and `report.py`'s new `build_freshness_checks` folds a stale
  ("error") source into `release_blocking_findings` the same as any other
  failing gate. Verified against a real `extract all` run: all seven
  sources report `pass` with real age data.
- [x] Backlog #47: `sprites.py` rebuild ordering constraint —
  `copy_sprites` used to `rmtree` the whole `images/` output directory,
  which would wipe out `images/icons/`/`images/reference_teams/` if it
  ever ran after those `build.py` steps instead of before (today's order
  happened to be safe, nothing enforced it). It now only unlinks the
  top-level `*.png` files it owns, leaving sibling subdirectories alone
  regardless of call order. New regression test confirms a pre-populated
  icons subdirectory survives a `copy_sprites` call.
- [x] Backlog #40: Row-count anomaly detection — new dbt *generic* test
  (this project's first — see backlog #42's own "not a single generic
  test" observation), `dbt/macros/test_row_count_anomaly.sql`, applied to
  each of the seven scheduled sources in `_sources.yml`'s `data_tests:`.
  Compares the latest `snapshot_date`'s row count against the immediately
  preceding one and fails below 50% of that baseline — the volume-drop
  case (e.g. 106,000 rows to 500) that #36's zero-row gate can't see.
  Fewer than two snapshots passes rather than failing vacuously, since
  there's no baseline yet, not an outage. Wired into
  `pipelines/validate/report.py` as a new `row_count_anomaly_checks`
  category via the same `meta.category` mechanism #37 introduced. Verified
  against a synthetic two-snapshot fixture: a 300→50 drop fails at
  1667bps, a 300→280 fluctuation passes, and a single-snapshot source
  passes.
- [x] Backlog #43: Extractor resilience (retry/backoff) — new shared
  `pipelines/extract/http.py`'s `get_with_retry`: retries a transient
  failure (connection error, timeout, 5xx response) up to three times with
  exponential backoff, failing immediately on a 4xx. Applied to every raw
  HTTP call across all five extractors, including the two paths that had
  none before — `pokeapi.py`'s `_fetch_pokemon_list`/`_fetch_pokemon` (the
  ~1,350-sequential-request path this item names directly) and
  `opgg.py`/`pokebase.py`/`munchstats.py`/`bulbagarden.py`'s page/JSON/
  image fetches. `pokeapi.py`'s move/ability/item lookups already had a
  bespoke retry loop from an earlier pass; that's now deleted in favor of
  the shared helper. Rate limiting (throttling request cadence, not just
  reacting to failures) is the one part of this item's value statement
  still open — a smaller, separate follow-up.
- [x] Backlog #49: Fix bps-based validation-report metrics reading as 0 on
  a passing check — dbt-core's `TestRunner.build_test_run_result`
  (`dbt/task/test.py`) hardcodes `failures = 0` on a passing test, so every
  coverage/null-rate/row-count-anomaly check's `metric_value` in
  `validation_report.json` read `0.0` whenever the check actually passed
  (status was still correct; only the reported number was wrong).
  `pipelines/validate/report.py`'s new `_recompute_bps_ratio` re-executes
  each check's own `compiled_code` (already present per-result in
  `run_results.json`) against the built `dbt/data/warehouse.duckdb`,
  wrapped in the same `fail_calc` expression the manifest already
  declares, recovering the true ratio regardless of pass/fail; falls back
  to the old (fail-path-only-correct) behavior if the warehouse or
  compiled_code isn't available. Needed a `chdir` into `dbt/` for the
  recompute query, since a `source()` reference compiles to a literal
  relative CSV glob path resolved against dbt's own working directory, not
  the repo root — confirmed by testing the naive approach directly:  it
  silently read zero rows instead of erroring. Verified against a real
  `extract all` + `dbt build` + `validate` run: `opgg_legal_pool_coverage`
  now reports `0.9842` (previously `0.0`), matching the real figure
  already documented elsewhere in this repo. `duckdb` is now an explicit
  `pyproject.toml` dependency (`report.py` imports it directly).
- [x] Backlog #44: Incremental extraction — `pipelines/extract/
  munchstats.py`'s `extract` gained a `previous_snapshot_path` parameter
  (wired up munchstats-only in `pipelines/cli.py`'s `_run_extract`, via the
  already-existing `_latest_snapshot_path` helper): each tournament's cheap
  `metadata.json` is still always re-fetched, but the heavy `players.json`
  fetch (the bulk of every run's ~106k rows) is skipped in favor of cached
  rows whenever that tournament's `(name, date, type)` signature is
  unchanged — the same "cheap signal first, skip the expensive download
  only if it still matches" pattern `bulbagarden.py`'s sha1-based
  `skip_existing` already established. Verified against real data:
  re-running `extract munchstats` same-day reproduced the identical
  106,134 rows in 11 seconds, down from the original run's 63 live
  requests fetching ~37MB. (A real request-count gap this content-only
  verification couldn't see — live MunchStats indexes same-venue TCG
  events alongside VGC ones, which this caching couldn't recognize as
  cacheable since they never produce output rows to cache — was caught
  and fixed under backlog #48 below, once real per-request counting
  existed to reveal it.)
- [x] Backlog #48: Extraction run metadata and structured logging —
  `pipelines/extract/http.py` gained `RequestStats`/`track_requests()`
  (instrumenting the one `get_with_retry` chokepoint every extractor's raw
  HTTP calls already share, rather than touching each extractor module);
  new `pipelines/extract/summary.py` computes real `rows_written`/
  `required_field_null_rate` per source and merges just that source's
  entry into `reports/validation/extraction_summary.json` (previously a
  hand-written file dated 2026-07-19 that no code generated or updated).
  `pipelines/cli.py`'s new `_run_tracked_extract` wraps every extraction
  in this tracking and now catches an extractor exception, prints a
  structured one-line error, and returns a controlled exit code instead of
  an unhandled traceback — matching `_run_validate`'s existing catch-log-
  return convention. PokéAPI's move/ability/item detail fetches each get
  their own entry now instead of vanishing into one merged "PokéAPI" row.
  Verified against real, freshly-run extractions: this is exactly what
  caught the real #44 gap described above (MunchStats' `requests_attempted`
  came back as 90, not ~32, revealing live TCG-tournament entries #44's
  caching couldn't recognize) — after that fix, a real re-run confirmed
  the true minimum, 61 requests, with the same 106,134 rows preserved.
- [x] Backlog #41: Schema-drift enforcement — new `pipelines/
  schema_contracts.py` loads a `*.schema.json` contract's declared field
  names; new `tests/unit/extract/test_schema_contracts.py` asserts every
  extractor's `FIELDNAMES` matches its `data/staging/*.schema.json`
  contract (pure code-level, runs on every push); new
  `pipelines/validate/report.py`'s `build_schema_drift_checks` compares
  each real `data/normalized/<entity>.csv` header against its
  `data/normalized/<entity>.schema.json` contract, wired into
  `release_blocking_findings` like any other gate (a missing CSV reports
  `skipped`, not `fail`). Verified against a real `extract` + `dbt build`
  + `validate` run: all 11 present normalized entities pass,
  `pokemon_asset` correctly skips (Bulbagarden wasn't extracted this
  pass).
- [x] Backlog #42: Mart tests — every one of the 21 marts now carries
  `not_null` on its grain column(s) plus a uniqueness check (dbt's
  built-in `unique` for 8 single-column-grain marts, a new generic test
  `dbt/macros/test_unique_combination_of_columns.sql` for the 13
  composite-grain marts — this project's second generic test after
  backlog #40's `row_count_anomaly`). Tagged `meta.category: mart_quality`
  and wired into `report.py` as a new `mart_quality_checks` section,
  deliberately excluded from `release_blocking_findings` since marts
  aren't part of the release package. Caught a real bug while verifying:
  a `unique_combination_of_columns` test was the first query to ever read
  `player_signature_pokemon.csv`'s full row width back into DuckDB, and
  `read_csv`'s auto-detect sniffer (only samples ~20,480 rows) mis-guessed
  the CSV dialect because the first quoted comma in a player name didn't
  appear until row 34,569. Fixed at the source — `dbt_project.yml`'s
  `marts`/`normalized` configs now pin `csv_read_options: {quote: '"',
  escape: '"'}` — rather than working around it in the test, since the
  same latent risk existed for the normalized layer too. Verified against
  real data: a clean `dbt build` (147 pass) and `pipelines.cli validate`
  (54 mart_quality_checks, all pass).
- [x] Backlog #15 (softer step): Archetype seed drift-flagging test — new
  `dbt/tests/singular/assert_archetype_pokemon_map_intra_group_synergy.sql`
  flags (via `severity=warn`, a new non-blocking `archetype_drift`
  `meta.category`) archetypes in the curated `archetype_pokemon_map` seed
  whose members don't show above-chance real team synergy with each other
  (backlog #9's `pokemon_team_synergy.lift`). Verified against real data:
  found genuine drift in 3 of 6 current archetypes — `rain`
  (pelipper/politoed) has zero recorded teams ever fielding both, `sun`
  and `tailwind-hyper-offense` both average well below-chance lift across
  their curated pairs — while correctly leaving `sand` (one genuinely
  strong pair) and the two single-member archetypes unflagged. Full
  data-derived clustering (replacing the curated seed) is still open;
  this only adds a signal for when it disagrees with real data.

## Consumption surfaces (backlog Section 2)

- [x] Backlog #28: Local query and notebook quickstart — new
  `docs/local-queries.md`: how to open `dbt/data/warehouse.duckdb`
  directly (DuckDB CLI or Python) and seven starter queries, each verified
  against a real, freshly-extracted snapshot. Several of the queries
  (team synergy lift, placement-weighted usage, build concentration)
  surface marts not yet wired into the dashboard UI at
  all, so this doc is currently the only way to see their output.
- [x] Backlog #34: Pokémon Profile empty state — decided to keep the
  current default-to-highest-usage behavior rather than build an empty
  state, matching every other tab's "show ranked content immediately"
  convention. Documented in `docs/design-system.md`'s new "Default
  selection, not an empty state (Pokémon Profile)" subsection.
- [x] Backlog #33: GitHub Releases with packaged artifacts — new
  `.github/workflows/publish-release.yml`, triggered by the commit that
  adds a new `releases/manifests/manifest-<version>.json` to `main` (not a
  separate git-tag push, which this repo has never used for dataset
  versions). Zips `releases/data/<version>/` (CSVs + `images/`) with
  `manifest.json` and `CHANGELOG.md` — matching `CLAUDE.md`'s "Release
  package" contents — writes a `sha256sum` checksum file, and publishes
  both as a `data-v<version>`-tagged GitHub Release via `gh release
  create` (preinstalled on GitHub-hosted runners, no third-party action).
  Also runnable via `workflow_dispatch` to (re-)publish a specific
  version. Verified end-to-end against the real `releases/data/0.2.0/`
  (330 files, 11MB zip) with a stubbed `gh` binary, and the added-manifest
  diff logic against a synthetic git history.
- [x] Backlog #29 + #30: Usage-tab Trends subtab — a tournament-date
  filter (`#usage-trend-date-filter`, most recent date selected by
  default) over `pokemon_usage_by_event_date`, plus each Pokémon's usage-
  share *change* versus the immediately preceding tournament date as a
  `▲/▼ Npp` badge (new `.badge-positive`/`.badge-negative` variants,
  reusing the already-defined `--positive`/`--danger` tokens) or a `NEW`
  badge for a Pokémon absent from that previous date — the dependency-free
  stand-in for a line chart both entries flagged as the option once
  Chart.js was removed. Verified against a real `extract all` + `dbt
  build` + `build-dashboard` run: 26 real tournament dates, correct deltas
  and `NEW` badges at a mid-range date, all `—` (no false `NEW`s) at the
  earliest date, zero browser console errors. Also caught and documented a
  real, pre-existing bug while doing that verification: backlog #49, every
  bps-based validation-report metric (coverage/null-rate) reads `0.0` on a
  passing check due to a dbt-core behavior this project's `report.py`
  didn't account for — status/gating is unaffected, but the reported
  numbers have been wrong since the ratio pattern was introduced.

## Analytics depth (backlog Section 1, "buildable today")

Six of the "no new data required" items from `docs/backlog.md`'s Section
1 — the highest value-to-effort ratio in the backlog since every input
already existed in the normalized layer. Verified against a real,
freshly-run `extract all` + `dbt build` pass (not just synthetic
fixtures); all 91 dbt nodes (30 external models, 6 seeds, 35 data tests, 20
view models) pass, and `reports/validation/validation_report.json` reports
zero `release_blocking_findings`. None of the six are wired into the
dashboard UI yet (`pipelines/dashboard/data.py`'s `MART_FIELDS` and
`docs/dashboard.md`) — that's separate, still-open follow-up work; see each
item's `docs/backlog.md` entry.

- [x] Backlog #12: Usage × regulation cross-tab — new
  `dbt/models/marts/pokemon_usage_by_regulation.sql`. `tournament_event`
  carries no `regulation_code` of its own, so this isn't a temporal "usage
  during regulation X" slice; it cross-joins `pokemon_usage_summary`'s
  overall `usage_count` against `legality_snapshot`'s regulation membership
  at the latest `snapshot_date`, with `usage_share`/`usage_rank`
  recomputed within each `regulation_code` partition.
- [x] Backlog #14: Item and build concentration metrics — new
  `dbt/models/marts/pokemon_build_concentration.sql`: a
  Herfindahl-Hirschman Index (sum of squared shares) over
  `pokemon_item_usage.item_share`/`pokemon_ability_usage.ability_share`
  per Pokémon, plus how many distinct items/abilities were observed.
- [x] Backlog #13: Win-rate confidence intervals —
  `dbt/models/marts/pokemon_win_rate_summary.sql` gained
  `wilson_lower_bound` (95% Wilson score CI lower bound) and `wilson_rank`
  columns; `pipelines/dashboard/data.py`'s `compute_kpis` now picks the
  KPI card's `top_win_rate_pokemon` by `wilson_rank` instead of the old
  `RECORD_COUNT_FLOOR = 5`-filter-then-max-`win_rate` heuristic (removed).
  Verified against real data: the old logic picked a 63%-over-3-matches
  outlier; the new logic correctly picks a 50.6%-over-2,384-matches
  Pokémon instead.
- [x] Backlog #8: Placement-weighted usage — new
  `dbt/models/marts/pokemon_placement_weighted_usage.sql`, using
  `tournament_team.placement` (lower is better): a hard top-8-cutoff view
  (`top_cut_usage_count`/`top_cut_usage_share`) and a continuous
  inverse-placement-weighted view (`placement_weighted_score`/
  `weighted_usage_share`), so "successful" and "popular" are both
  answerable, not just the latter.
- [x] Backlog #6: Usage over time from `tournament_event.event_date` — new
  `dbt/models/marts/pokemon_usage_by_event_date.sql`: usage count/share/
  rank per Pokémon x event_date, a real meta-over-time view that doesn't
  need multiple extraction snapshots (Blocker A). Verified against real
  data: 2,073 rows across the real MunchStats event-date history.
- [x] Backlog #9: Team synergy beyond raw co-occurrence — new
  `dbt/models/marts/pokemon_team_synergy.sql`: lift per Pokémon x partner
  pair (`P(A,B) / (P(A) x P(B))`) built on top of
  `pokemon_team_core_usage`'s mirrored pairs, with `pair_team_count`
  exposed since lift is noisy at low counts. Verified against real data
  (10,336 pair rows) that lift surfaces a genuinely different, less
  generically-popular partner set than raw co-occurrence does. Extended on
  2026-08-09 with `pokemon_team_core_triple_usage`: canonical three-member
  cores with support, expected share, triple lift, constituent pair lift,
  event/player coverage, placement, and win-rate context; Pokémon Profile
  now switches between pair and triple cores.
- [x] Backlog #15: Experimental data-derived archetypes — qualifying triple
  cores consolidate when they share two members; every matched team gets a
  primary assignment and only a near-tied (>=90%) secondary assignment.
  `detected_archetype_summary` feeds a neutral-name dashboard view while the
  curated seed remains available for comparison. Against release 0.3.0,
  2,940/3,048 Champions teams receive a primary assignment and 38 groups
  span multiple events; the dashboard shows the top 24 cross-event groups.

## Backlog #25-#27 — the last three blocked items (2026-08-03)

The three items `docs/backlog.md` had recorded as permanently blocked on
missing sources. Checking each against the live source rather than against
its own description resolved all three; two of the three blockers were
stale. See `docs/backlog.md` #25-#27 for the full write-ups.

- [x] Backlog #27: real head-to-head matchups via RK9 — the entry said "no
  signal to derive this from," but named the answer itself
  ("round-by-round pairing data from tournament software") without
  following it up. That software is RK9, already this dataset's upstream
  via MunchStats, and it serves pairings over plain HTTP
  (`rk9.gg/pairings/{event_id}?pod={p}&rnd={n}`). No event-level ID mapping
  was needed: MunchStats reuses RK9's own event ids, so
  `tournament_event.event_id` *is* the pairings key. New
  `pipelines/extract/rk9.py` (rounds enumerated from the division tab strip,
  **not** the fragments' `hx-get` attributes — the active round is rendered
  inline and has none, so reading only those drops every event's final
  round), new normalized entity `tournament_match` with four release gates,
  and new `pokemon_head_to_head`/`pokemon_matchup_summary` marts surfaced in
  the dashboard's Matchup tab. Verified against real data: 13,201 matches
  across the three Champions events (13,127 decided, 69 byes, 5 ties),
  99.8% of 24,139 Masters pairing slots resolved to a `team_id`, and
  competitively sensible output (Incineroar's worst matchup is Lycanroc-Dusk
  at 39.1% over 289 matches). Honest limit, stated in every consumer: the
  grain is *team vs team* — no source names which four of six Pokémon were
  brought, so figures are attributed to the whole roster.
- [x] Backlog #26: Limitless VGC — both stated blockers were false (it needs
  no browser automation; it is server-rendered) and so was its value
  statement (it does *not* extend Champions history — only three Champions
  events exist anywhere, and MunchStats had all three; per event Limitless
  is narrower, publishing the day-2 cut only). Built for its real value
  instead: canonical shared team identity (`team_list`/`team_list_member`,
  359 compositions, 44 fielded by more than one player) and independent
  cross-validation of MunchStats rosters (`roster_source_agreement`). That
  validation earned its keep immediately — it reported **0% exact
  agreement** on first run, surfacing a real modelling error where Limitless
  publishes the base species holding its Mega Stone while MunchStats
  publishes the evolved form, so Limitless rows were joining to
  base-species stats. Fixed via a `limitless_mega_item_to_pokeapi_form`
  seed; agreement is now 97.9-100% exact, 99.2-100% per slot.
- [x] Backlog #25: EV spreads via Victory Road — **resolved as
  unbuildable**, and the entry's other justification turned out to be a
  measurement artifact hiding a real bug. EVs are not published by any
  source: official team sheets (RK9's own, which every source here derives
  from) carry ability, item, nature and moves and nothing more, verified
  directly against both `rk9.gg/teamlist/public/...` and
  `limitlessvgc.com/teams/...`. Victory Road is separately unreachable
  (`victory-road.com` has no DNS record at all; the real
  `victoryroadvgc.com` is permitted by egress policy but its origin resets
  the TLS handshake), but that is beside the point.
- [x] The "MunchStats nature coverage is only ~17%" claim (documented in
  five files) was **not** a coverage gap: 17.2% is the Champions *share* of
  a corpus that also held standard VGC events. Within Champions, nature is
  100% and `tera_type` is 0%; standard VGC is the exact reverse. Root cause:
  `tournament_event` never captured `format`, so every usage and win-rate
  mart silently blended two different games. Fixed by threading
  `event_format` through extraction and adding
  `dbt/models/intermediate/int_champions_roster.sql`, which all 14
  roster-derived marts now read. The correction is large and visible:
  Incineroar drops from #1 (7,641 appearances) to #5 (1,029), and
  Gholdengo/Dragonite/Whimsicott/Farigiraf leave the Champions top 8
  entirely. Consequently `pokemon_tera_type_usage` is permanently empty for
  Champions and was removed (backlog #10 reopened), following the same
  precedent as the stat-change leaderboard and legal-pool trend sections.

## 2027 Q1 upgrade plan — "Built for players"

The entries proposed in `docs/upgrade-plan-2027q1.md`, promoted here on
acceptance (backlog → todo). Each names its plan item; the plan's Status
table tracks sprint progress.

- [x] Routing: pushState + popstate, full view state in the hash, legacy `#tab` redirects (U1).
  `static/app.js`'s router maps `#/pokemon/<key>/<subtab>`,
  `#/compare/<a>,<b>`, `#/matchup/<a>/<b>`, `#/teams/<view>`,
  `#/cores/<key>[/triple]`, `#/usage/<view>`, `#/players/<view>` and
  `#/data/<view>` to views; every Pokémon name, sprite, tile and tier chip
  is a real link. Old `#usage` and `?tab=compare&a=&b=` links are rewritten
  in place.
- [x] Compact sticky header; status pills to footer; drop duplicate panel headers; events/teams KPI (U2).
  Content now starts 114px from the top on desktop and 110px on a 390px
  phone. The first KPI reads "5 events · 3,770 teams" from the new
  `tournament_event_summary` mart.
- [x] Regulation-in-force beats a stale remembered choice; thin-new-regulation fallback; rollover fixture test (U3).
  A remembered regulation is kept only if it was chosen while the same
  regulation was in force; a regulation in force with fewer than 300 teams
  opens on the previous one with a banner (`data.py`'s
  `default_scope_for` and `app.js`'s `resolveRegulationScope` apply the
  same rule). Covered by `tests/unit/dashboard/test_data.py` and
  `tests/browser/test_regulation_rollover.py` against a fixture M-D row.
- [x] Copy pass, glossary tooltips, denominators on every percentage (U4).
  Repo paths and internal names are gone from the page (the Data section's
  descriptions strip schema.yml's "See data/…" pointers too). One `GLOSSARY`
  map in `static/app.js` backs both the inline terms (usage share, roster
  slot, Wilson bound, HHI, Locked in, synergy lift, pts, top cut and more)
  and the Data section's "How to read this page". Table cells show their
  denominator ("487 of 5,644 team sheets") with the same tooltip, which now
  opens on tap as well as hover: a tap's compatibility mouseover and focus
  used to open the tip only for the click to close it again.
- [x] Shared sortable table component, adopted in Usage, Profile, Speed Tiers, Cores, Players (U5).
  `createDataTable` in `static/app.js`: sticky sortable header, sprite +
  name cells, inline share bars, row → route, two-line rows on phones.
  Card grids remain only on Overview and the Tier List.
- [x] Type filter popover (U6); mobile sub-tab scroll cues, import moved to Builder (U7).
  One "Any type ▾" button replaces the 18-icon row in Usage, Speed Tiers
  and the Builder; tab rows fade at the clipped edge and centre the active
  tab; the pokepaste import is the Builder's "Import team"; phone tap
  targets are 44px.
- [x] Playwright route smoke test + payload budget in CI (U8).
  `tests/browser/` builds the dashboard from synthetic marts, opens every
  route at 1440px and 390px and fails on a console error or an empty
  panel; it also covers Back/Forward, legacy links and the default view's
  fetch count. The core payload (page, scripts, `core.json` and the default
  regulation's shard) is held under 500KB compressed (483KB after Sprint 9, up from 448KB). CI
  installs Chromium for them.
- [x] Type icons instead of the type-colour side bar on Pokémon cards (U9).
  Overview and calculator tiles and Team Builder slots show one or two type
  emblems in their top-right corner (`typeIconsHtml` in `static/app.js`,
  one `role="img"` labelled "dragon / ground type"); the profile header
  drops its bar, since its pills already name the types. The type colours
  now only fill those pills. Also fixes the Builder on phones, whose second
  column of slots ran off the screen.
- [x] `pokemon_set_variants` mart and real-set tabs on the profile (P1).
  Exact (item + ability + nature + 4 moves) and core (item + ability + top
  3 moves) levels, top 5 per Pokémon and scope with a Wilson-ranked win
  rate. dbt tests check shares sum to at most 1 and that every exact set
  appears verbatim on its example team's sheet. The per-slot modal card is
  gone.
- [x] Pokémon hub v2: per-regulation trend, featuring teams, teammates, meta pressure (P2).
  The profile header draws usage share across every regulation with win
  rate and n under each point (`pokemon_usage_by_regulation` now carries
  `win_rate`/`record_count`); new Teams and Meta pressure views; Teammates
  is a table ranked by synergy lift; a recently-viewed strip is kept per
  browser. Meta pressure is labelled type-based, not battle results.
- [x] Calculator presets from real sets; "vs the meta" mode (P3).
  Each side starts on its #1 real set's item/ability toggles (and the
  defender's Intimidate); "Top 12 of the meta" (`#/matchup/<a>/meta`)
  lists damage ranges and OHKO/2HKO/3HKO verdicts against the regulation's
  most-used Pokémon, labelled as a full-investment level-50 estimate.
- [x] Builder: use a real team, saved teams, share link (P4); starter teams strip (P5).
  "Use this team" loads a real sheet (`#/builder/team/<id>`,
  `#/builder/list/<id>`); up to five named teams save per browser; "Copy
  share link" gives `?reg=<scope>#/builder/<key>.<set>,...` with real-set
  indices. The Builder carries natures. The Overview's "Copy and play"
  strip shows three top-placing fully reported teams.
- [x] Event pages and `pokemon_event_usage_vs_regulation` mart (C1).
  `#/events` lists every event in the regulation (`tournament_event_summary`);
  `#/event/<id>` shows the header with RK9/MunchStats source links, the top
  8 as team cards with full sets and copy, and the Pokémon the field over-
  and under-used against the regulation average (withheld below 100
  teams). The Overview has a Latest event card. Code in `static/events.js`.
- [x] Top Teams: record/placement headline, placement ranking, copy actions (C2).
  Cards lead with "1st 15–2", rank by placement within event tier, and
  offer win rate as a sort; `?tier=` and `?sort=` live in the route. Every
  card has Copy for Showdown and Use this team (`#/builder/team/<id>`);
  converged lists load their Limitless sets (`team_list_sheets`).
- [x] Player pages (C3).
  The Players tab opens on "Find a player" (`#/players`): a name search
  over `player_index`, derived at build time from `tournament_team_results`
  (names as the sources spell them). `#/player/<id>` lists their events in
  the selected regulation as team cards (with sets where a top-16 sheet
  exists), links their other regulations, their most-brought Pokémon, and
  their team-level record against detected archetypes from the new
  `player_archetype_record` mart (at least two matches, labelled team vs
  team). Code in `static/players.js`.
- [x] Event-window filter, pre-rendered share cards, OG image, copy-with-citation, labelled baseline (C4).
  Usage's "Events" filter (latest, last N, since an event) compares the
  window with the regulation's earlier events. `render-share-cards`
  (`pipelines/render/share_cards.py`) renders the newest event's top 8 and a
  What changed card per regulation, the default one doubling as the Open
  Graph image; the build adds download buttons and OG/Twitter tags. Every
  data table has "Copy with citation". The What changed panel names its
  baseline's events and teams and opens on early vs recent events when
  the previous regulation is thin (M-B is one Worlds field).
- [x] Release-asset distribution and the release contract change (D1); **publishing 0.4.0 is a manual step.**
  `release --package` zips the CSVs, images, manifest and changelog into
  `releases/packages/` and records `{file_name, sha256, size_bytes,
  release_tag, url}` as the manifest's `package` block; from 0.4.0 only the
  manifest and changelog are committed (`docs/dataset-spec.md`'s
  "Distribution"). The new `cut-release.yml` workflow (manual dispatch)
  refreshes, validates, packages, creates the GitHub Release with the zip
  and opens a PR with the manifest and changelog. A local dry run built a
  62MB package. To publish, run that workflow with version `0.4.0` and the
  note "Releases before 0.4.0 exclude Reg M-B and M-C events."
- [x] Data section table cards and a generated data dictionary (D2).
  `pipelines/dashboard/dictionary.py` builds both at dashboard build time,
  from `dbt/models/*/schema.yml` and the newest release manifest, into one
  on-demand `data/data_dictionary.json`. Data → Tables has a card per
  release table (description, rows, key, download: the release zip from
  0.4.0, the committed CSV before) and per served mart (rows, grain, JSON
  file); Data → Dictionary lists every served field with its description.
- [x] Regulation rollover playbook and M-D dry run (D3).
  `docs/dashboard.md`'s "Regulation rollover playbook". The dry run added a
  fixture M-D row and ran the real pipeline end to end; its one finding
  (the staleness banner repeating the rollover banner) is fixed. The drift
  alarm was also probed by withholding M-C.

## Release readiness (v1 definition of done)

All release gates pass as of this writing (see
`reports/validation/validation_report.json`: `release_blocking_findings: []`)
and **`dataset_version 0.3.0` has been published** (the current latest;
`0.1.0` was the first release, `0.2.0` the first with Bulbagarden data) —
`releases/data/0.3.0/*.csv`, `releases/manifests/manifest-0.3.0.json`,
`releases/changelogs/CHANGELOG-0.3.0.md`. 0.3.0 is a MINOR bump: it adds
the `tournament_match`, `team_list` and `team_list_member` entities
(backlog #26/#27) with no breaking changes to existing ones, and is the
first release whose usage figures are scoped to the Champions format
(backlog #25 — see that section above; the corrected numbers differ
substantially from 0.2.0's).

Cutting it also fixed a real, previously-unhit bug in
`pipelines/release/build.py`: `SOURCES` still pointed at pre-backlog-#1 flat
staging paths (`data/staging/pokeapi.csv`), which no longer exist now that
snapshots are date-partitioned, so `_build_sources` would have raised
`FileNotFoundError` for every source. It went unnoticed because no release
had been cut since that change landed.

- [x] Coverage: >=95% of OP.GG legal pool mapped to canonical `pokemon_id`
  (currently 98.4%, 312/317 legal-pool rows)
- [x] Coverage: >=90% of targeted tournament records mapped to normalized team
  tables (currently ~99.9%)
- [x] Coverage: >=95% of PokéBase legal-pool rows mapped to canonical
  `pokemon_id` (currently ~98.7%, 306/310 rows)
- [x] Data quality: required-field null rate <=1% for core tables (all nine
  pass, including `legality_snapshot` now that `regulation_code` is real —
  nine since `pokemon_asset` joined the core entity list in Phase 4)
- [x] Data quality: zero duplicate primary-key violations
- [x] Data quality: referential integrity checks pass for Pokémon/team/event
  joins
- [x] Export: versioned CSV outputs for all core entities (`pipelines/release/build.py`,
  `python -m pipelines.cli release --version X.Y.Z`) — twelve tables as of
  0.3.0
- [x] Export: versioned JSON manifest with source lineage and run stats (same
  command; also writes `releases/changelogs/CHANGELOG-<version>.md`)
- [x] Validate example analysis queries (`dbt/analyses/`, see its `README.md`):
  top stat gainers/losers and most-used legal Pokémon both validated with
  real, non-degenerate results; largest legal-pool changes by regulation is
  structurally validated but still currently degenerate for a narrower
  reason now — `regulation_code` is populated, but there's only one
  extraction run (one `snapshot_date`) so far to diff against

## Deferred (post-v1)

No sources remain deferred. Both former entries were resolved on
2026-08-03: Limitless VGC was brought into scope (for shared team identity
and cross-source validation, not the historical coverage it was deferred
for), and Victory Road was closed as unbuildable — the EV data it was
wanted for is published by no source at all. RK9.gg was added in the same
pass to supply match-level results. See "Formerly deferred sources" and
"Added sources" in `dataset-spec.md`.
