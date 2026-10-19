# Backlog

A wish list of features and improvements for the Pokémon Champions
Competitive Data Platform, kept deliberately broad — moonshots sit next to
afternoon-sized wins, each flagged so the list can be filtered rather than
pre-filtered.

**This is not a commitment.** `docs/todo.md` is the committed checklist:
everything in it is meant to get done. Items here graduate in one direction
only — backlog → todo — once accepted, matching the handoff described in
`.claude/loop.md`'s backlog-grooming loop. `docs/dataset-spec.md` remains the
source of truth for v1 scope; nothing here changes it until it's promoted.

Items are numbered so dependencies can reference each other. **Numbers are
stable and never reused** — a completed or dropped item keeps its number.

## Progress overview

*Last updated 2026-08-03.* 49 numbered items exist (#1-#49, none dropped).
This table is maintained by hand alongside each grooming/implementation
pass — if it drifts from the per-item statuses below, the per-item entries
are the source of truth.

| Status | Count | Meaning |
|---|---|---|
| **Done** | 41 | Shipped and verified against real data: #1-#16, #22-#24, #26-#30, #32, #33, #35-#49 (every item in this range except #17, #25 and #34, see below) |
| **Resolved, no build needed** | 3 | #17 — deliberately left unwired, not an oversight; #25 — the EV data does not exist at any source, so there is nothing to build; #34 — current default-to-highest-usage behavior decided to be correct as-is; see each entry |
| **Open, buildable now** | 0 | Every previously-open, unblocked item has shipped |
| **Blocked** | 0 | The last three (#25-#27) were resolved on 2026-08-03; two of the three blockers turned out to be stale |
| **Archived** | 5 | Excluded from active scope by user decision (2026-08-02): meta-shift/legal-pool/stat-change trend items (#18-#21) and the Streamlit dashboard (#31). Not resolved — deprioritized; each stays blocked underneath (Blocker A/B or snapshot-dependent hosting) and can be un-archived if reprioritized |

By section:

| Section | Done | Resolved | Open | Blocked | Archived | Total |
|---|---|---|---|---|---|---|
| 0 — Foundational enablers | 5 | 0 | 0 | 0 | 0 | 5 |
| 1 — Buildable today (#6-#17) | 11 | 1 | 0 | 0 | 0 | 12 |
| 1 — Blocked on Blocker A (#18-#20) | 0 | 0 | 0 | 0 | 3 | 3 |
| 1 — Blocked on Blocker B (#21) | 0 | 0 | 0 | 0 | 1 | 1 |
| 1 — Needs new provenance (#22-#27) | 5 | 1 | 0 | 0 | 0 | 6 |
| 2 — Consumption surfaces (#28-#34) | 5 | 1 | 0 | 0 | 1 | 7 |
| 3 — Platform, quality, and ops (#35-#49) | 15 | 0 | 0 | 0 | 0 | 15 |
| **Total** | **41** | **3** | **0** | **0** | **5** | **49** |

**2026-08-03, mart-wiring pass: every shipped mart that answers a
competitive question is now actually on the dashboard.** This file's own
"DONE" statuses were accurate about the *data* and quietly incomplete about
the *surface* — six entries (#7, #8, #9, #12, #14, #16) ended with some
form of "not yet wired into the dashboard UI," and
`pipelines/dashboard/data.py` read 11 of the 23 marts `dbt build`
produces. All eight unsurfaced marts are wired now; the three that remain
unwired are unwired on purpose and say so (#17's `stat_change_leaderboard`,
the archetype marts, `roster_source_agreement`). See each entry's updated
note and `docs/dashboard.md`'s "Marts wired in the mart-wiring pass".

Verifying against the real page rather than the mart columns caught two
data-shape problems that would otherwise have shipped as confident-looking
but misleading views — the same pattern several earlier passes hit: a
"signature Pokémon" share is structurally capped at 16.7% (a Pokémon
appears at most once on a six-slot team), and only three Champions events
exist at all, so the ≥3-recorded-teams floor this file's #7 entry implied
left the player view showing exactly one player. Both are recorded in
`docs/dashboard.md`.

Takeaways: **every unblocked item in the backlog is now done.** Sections 0,
1's "buildable today" subsection (except #17, a deliberate non-build), 2,
and 3 are all fully closed out. This pass closed the remaining six "open,
buildable now" items in one sweep — #45 (CLI dispatch test coverage for
`release`/`render-card`/`build-dashboard`), #7 (player/country dimension
marts — `pokemon_usage_by_country`, `player_signature_pokemon`), #44
(incremental MunchStats extraction, `teams_scraped`-aware), #16 (speed
-tier bracket mart — `max_investment_speed`, `pokemon_speed_tiers`), #48
(real, code-generated `extraction_summary.json` + structured per-request
stats — which caught and fixed a real gap in #44's own caching logic that
content-only verification had missed), #41 (schema-drift enforcement,
staging and normalized layers), #42 (quality tests on all 21 marts — which
caught and fixed a real DuckDB CSV-sniffing bug), and #15's softer step
(archetype seed drift-flagging, which found genuine drift in 3 of 6
curated archetypes against real data). Three of these passes (#48, #42,
and #15) each surfaced a real, previously-unknown issue while verifying
against live data rather than synthetic fixtures — not hypothetical risk,
actual bugs and actual data-vs-editorial mismatches caught in the act.

A 2026-08-02 pass then archived five items — #18-#21 (meta-shift/
legal-pool/stat-change trend work) and #31 (the Streamlit dashboard) — by
explicit user decision to exclude them from active planning. Archiving is
not resolution: each stays exactly as blocked as before (Blocker A, Blocker
B, or #31's snapshot-dependent hosting justification), just no longer
counted among the items this file is actively tracking toward. See each
entry's "Archived" note, and #18's note for the shared rationale.

**2026-08-03: the last three blocked items (#25-#27) are now resolved, and
two of the three blockers were stale rather than real.** Checking them
against the live sources instead of against this file's own description
changed the answer in every case:

- **#27 was not blocked at all.** Its own text named the missing piece
  ("round-by-round pairing data from tournament software") without following
  it up. That software is RK9 — already this dataset's upstream, via
  MunchStats — and it serves pairings over plain HTTP. Shipped as
  `tournament_match` plus two head-to-head marts.
- **#26's blockers were both false**: Limitless needs no browser automation,
  and it does not extend Champions history (only three Champions events
  exist anywhere). Built anyway, for the real value its entry had missed —
  canonical shared team identity, and cross-source validation.
- **#25 is genuinely, permanently unbuildable**, but for a different reason
  than recorded: EVs are not published by *any* source, including the
  official team sheets every source here derives from. Victory Road's
  unreachability turned out to be beside the point.

Two of these passes surfaced real bugs while verifying against live data:
#26's cross-validation caught a Mega-form modelling error, and #25's
investigation caught the format-mixing bug that had every usage mart
blending Champions with standard VGC events. Neither was hypothetical.

## Entry format

- **Size**: `S` an afternoon · `M` a day or two · `L` a week-ish ·
  `XL` a project in its own right
- **Value**: the question it lets you answer, or the failure it prevents
- **Blocked by**: what must be true first — another item, new data, or a new
  source
- **Touches**: the extractor, model, mart, or table it lands in

## The two systemic blockers

Most of the analytics ambition in this repo is gated behind one of two
things. Individual entries below reference these rather than re-explaining
them:

**Blocker A — only one `snapshot_date` has ever existed.** ~~Every extractor
opens its staging CSV with `open(..., "w")`~~ **Fixed by items #1-#3** (all
shipped): `pipelines/cli.py`'s `extract` now writes date-partitioned
snapshots and a `.github/workflows/scheduled-extraction.yml` cron keeps them
accumulating on the cadences `docs/dataset-spec.md` specifies, and
`snapshot_date` is a real, queryable dbt dimension (see Section 0 below for
the full writeup). The blocker's *symptoms* — the degenerate
`dbt/analyses/largest_legal_pool_changes_by_regulation.sql`, the two cut
dashboard sections, every trend view in `docs/prd.md`'s ambition — still
need real multiple-snapshot history to accumulate in production before they
resolve; the engineering blocker is gone, but the calendar time to build up
that history isn't. Item #19 revisits the legal-pool-change query once
enough snapshots exist.

**Blocker B — no Champions rebalance has happened yet.** Every mapped
Pokémon currently has a `stat_total_delta` of exactly `0` (see
`dbt/analyses/README.md`). This is real data, not a bug: the snapshot
predates any balance patch. Nothing in this repo can unblock it — it
resolves when the format changes.

A useful distinction: Blocker A is an engineering problem you can fix today.
Blocker B is a waiting problem. Don't confuse work blocked on one for work
blocked on the other.

---

## Section 0 — Foundational enablers

**All five items in this section are shipped** — see `docs/todo.md`'s
"Foundational enablers (backlog Section 0)" for the implementation writeup.
Entries kept below per "numbers are stable and never reused."

### 1. Append-only staging snapshot history — DONE

- **Size**: XL
- **Value**: The single highest-leverage item in this file. Turns a
  point-in-time dataset into a time series, which is the difference between
  "what is the meta" and "how is the meta changing."
- **Blocked by**: nothing
- **Touches**: `pipelines/cli.py` (the extractors' own `extract()` functions
  didn't need to change — they already just write to whatever `output_path`
  they're given), `data/staging/` layout, `dbt/models/staging/_sources.yml`,
  `.gitignore`

Shipped as date-partitioned `data/staging/<source>/<date>.csv` snapshots,
pruned per source by `pipelines/cli.py`'s `_RETENTION_COUNTS` (12 weekly
PokéAPI, 14 daily OP.GG/PokéBase, 7 daily MunchStats given its ~37MB/run
size, 10 on-demand Bulbagarden). Stayed CSV, not Parquet — matches the
existing schema contracts, no new dependency.

### 2. Snapshot-aware dbt layer — DONE

- **Size**: L
- **Value**: Makes `snapshot_date` a real dimension you can group by rather
  than an incidental column, without which #1's history is inert.
- **Blocked by**: #1
- **Touches**: `dbt/models/staging/`, `dbt/models/intermediate/`,
  `dbt/models/normalized/`, `data/normalized/*.schema.json`

Went with the parallel-history-layer option this entry flagged as less
disruptive: `stg_*.sql` now exposes the full unioned history with
`snapshot_date`, a new `int_*_latest.sql` per source selects the current
point-in-time snapshot, and the normalized layer's primary keys/referential-
integrity tests are untouched. Verified against a synthetic two-snapshot
fixture — see `docs/todo.md` for the walkthrough.

### 3. Scheduled refresh automation — DONE

- **Size**: M
- **Value**: `docs/dataset-spec.md` specifies daily/weekly refresh cadences
  per source that nothing in this repo implements — every snapshot to date
  has been a manual run. Without this, #1 accumulates history only as often
  as you remember to.
- **Blocked by**: nothing (but pairs with #1 — scheduling an overwriting
  extractor accumulates nothing)
- **Touches**: new `.github/workflows/`, `pipelines/cli.py`

Shipped as `.github/workflows/scheduled-extraction.yml`: daily cron for
OP.GG/MunchStats/PokéBase, weekly for PokéAPI. Bulbagarden stays on-demand
per the caveat at `pipelines/extract/bulbagarden.py:39-42` (rate-limiting/
ToS posture for sustained automated access never independently verified).
`data/staging/` being gitignored (see #1) meant runner-to-runner
persistence needed `actions/cache` rather than committing snapshots.

### 4. Plumb `dataset_version` through extraction — DONE

- **Size**: S
- **Value**: Fixes a provenance hole that contradicts the repo's own
  mandatory-provenance convention. Every staging row ever written carries
  `dataset_version = "0.0.0-dev"`.
- **Blocked by**: nothing
- **Touches**: `pipelines/cli.py`, `pipelines/validate/report.py`, new
  `pipelines/versioning.py`

Both defaults now resolve via `pipelines/versioning.py`'s
`latest_published_version()` (highest version under
`releases/manifests/manifest-*.json`) instead of hardcoded placeholders;
`extract` also takes an explicit `--dataset-version` override.

### 5. Orchestration entry point — DONE

- **Size**: S
- **Value**: A full refresh is currently five separate commands plus a build
  plus a validate, in an order you have to remember. Cheap to fix, removes a
  recurring friction and a class of "forgot to re-run X" errors.
- **Blocked by**: nothing
- **Touches**: `pipelines/cli.py`, `Makefile`

`extract all` runs every source in dependency order; new `make extract-all`,
`make refresh` (extract-all → dbt-build → validate), and `make release
VERSION=X.Y.Z` (refresh → release) chain the rest, mirroring `dashboard`'s
existing `dbt-build` → `build-dashboard` chain.

---

## Section 1 — Analytics depth

The main section. Split by what's actually blocking each item, because the
distinction matters more than the feature descriptions do.

### Buildable today — no new data required

These need only SQL and a mart. Every input already exists in the normalized
layer. This is the highest ratio of value to effort in the file.

#### 6. Usage over time from `tournament_event.event_date` — DONE

- **Size**: M
- **Value**: Real meta-over-time **without waiting on Blocker A**. Events
  already carry dates spanning the tournament history; usage trends can be
  computed across events rather than across extraction snapshots. This is
  the near-term win hiding in plain sight.
- **Blocked by**: nothing
- **Touches**: new `dbt/models/marts/pokemon_usage_trend.sql`,
  `tournament_event`, `tournament_team_member`

Shipped as `dbt/models/marts/pokemon_usage_by_event_date.sql` (named to
match its grain rather than the originally-proposed `pokemon_usage_trend`):
usage count/share/rank per Pokémon x event_date, partitioned by
event_date. Verified against real data: 2,073 rows across the real
MunchStats event-date history. Not yet wired into the dashboard UI (#29's
trend/line charts are the natural consumer, but that item is bigger scope
than this mart alone).

#### 7. Player and country dimension mart — DONE

- **Size**: S
- **Value**: Answers "who plays what," "which regions favor which
  archetypes," and "does this player have a signature Pokémon."
- **Blocked by**: nothing
- **Touches**: new mart, `tournament_team`

`player_name`/`player_country` already surfaced in `top_tournament_teams`
(`dbt/models/marts/top_tournament_teams.sql`, shipped as part of the M6
Top Teams tab work), answering "who plays what" for the top 100 teams by
win rate, but that mart is team-grain, not player- or country-grain. This
pass closed the real gap with two new sibling marts. New
`dbt/models/marts/pokemon_usage_by_country.sql`: usage x player_country
cross-tab (usage_count/usage_share/country_usage_rank within each
country), restricted to the current legal pool and to roster rows with a
reported player_country. New
`dbt/models/marts/player_signature_pokemon.sql`: one row per player_id x
pokemon_key they've fielded across their *entire* recorded history (not
just their best single team), with player_usage_share and
player_pokemon_rank (rank 1 = signature Pokémon) plus player_team_count as
a sample-size signal, since a "signature" claim from a player with one
recorded team is much weaker evidence than one from a player with dozens.
Both use "which Pokémon," not archetype, as the practical unit of
analysis -- deriving a real per-country/per-player *archetype* profile
would additionally require joining the curated, NOT-sourced
`archetype_pokemon_map` seed, which is a bigger, separate ask than this
item's own S sizing. Verified against real data (a fresh `extract
munchstats`+`opgg`+`pokebase`+`pokeapi` and `dbt build`, not a synthetic
fixture): `pokemon_usage_by_country` produced 2,433 rows across 69
countries with a #1 Pokémon (e.g. Incineroar at 14.8% share in Germany,
569 roster appearances); `player_signature_pokemon` produced 44,533 rows,
8,431 players with a rank-1 signature pick, and real, plausible signature
picks at non-trivial sample sizes (e.g. a French player fielding
Incineroar in 11 of 11 recorded teams' legal-pool slots, a 29.7% overall
share).

**Wired into the dashboard on 2026-08-03** by the mart-wiring pass, as a
new **Players & Regions** tab (By region / By player subtabs) — see
`docs/dashboard.md`'s "Marts wired in the mart-wiring pass". Two things
that entry's own figures got wrong, corrected there against the real
Champions-scoped marts: `player_usage_share` is structurally capped at
16.7% (a Pokémon appears at most once per six-slot team), so the
specialists view ranks on share of a player's *teams* instead; and the
"a French player fielding Incineroar in 11 of 11 recorded teams" example
above predates the format-scoping fix in #25 — no player can have more
than three recorded teams, because only three Champions events exist.
Related polish still open: `docs/dashboard.md` notes country codes render
as plain two-letter text because no flag-emoji/ISO lookup exists.

#### 8. Placement-weighted usage — DONE

- **Size**: M
- **Value**: Distinguishes "popular" from "successful." Raw usage counts
  treat a last-place team the same as a winning one, which flatters
  crowd-favorite picks and hides quiet top-cut staples.
- **Blocked by**: nothing
- **Touches**: new mart, `tournament_team.placement`,
  `record_wins`/`record_losses`

Shipped as `dbt/models/marts/pokemon_placement_weighted_usage.sql`: both
views this entry asked for. `top_cut_usage_count`/`top_cut_usage_share`
use a hard top-8 cutoff (the standard VGC/Champions bracket size);
`placement_weighted_score`/`weighted_usage_share` use a continuous
inverse-placement (`1/placement`) weight per appearance instead, so a
1st-place finish counts far more than a 200th with no cutoff
discontinuity. **Wired into the dashboard on 2026-08-03** as the Usage
tab's **Success** subtab (both views selectable), with a client-side
rank-movement badge comparing each Pokémon's weighted rank against its
raw `pokemon_usage_summary.usage_rank` — the "quiet top-cut staple vs.
crowd favourite" read this entry was written for. (The "Incineroar leads
both views" note above is from the pre-#25 format-mixed corpus; on the
Champions-scoped data it's Kingambit, with Incineroar +3 places on top-cut
share.)

#### 9. Team synergy beyond raw co-occurrence — DONE (pairs and triples)

- **Size**: M
- **Value**: `pokemon_team_core_usage` reports how often two Pokémon appear
  together, which mostly just re-ranks the individually popular ones. Lift
  or PMI against expected co-occurrence surfaces genuine pairings — the ones
  that appear together far more than their individual usage predicts.
- **Blocked by**: nothing
- **Touches**: `dbt/models/marts/pokemon_team_core_usage.sql` or a sibling
  mart

Shipped as a sibling mart, `dbt/models/marts/pokemon_team_synergy.sql`,
built on top of `pokemon_team_core_usage`'s already-mirrored pairs: lift
per pair (`P(A,B) / (P(A) x P(B))`, using distinct-team membership as the
probability space), with `pair_team_count` exposed alongside it since lift
is noisy at low pair counts. Verified against real data: 10,336 pair rows;
spot-checked Incineroar's top partners by lift (Vileplume, Slowking,
Steelix, Hawlucha-Mega, Sceptile) against its top partners by raw
co-occurrence and confirmed they're a different, less-generically-popular
set, as intended. **Wired into the dashboard on 2026-08-03**: the Pokémon
Profile tab's Team Cores section is now rankable by co-occurrence or by
lift, showing `×N.N` with `pair_team_count` alongside it (the dashboard's
one non-percentage headline value — see `docs/design-system.md`'s
"Multiplier values"). The floor this entry asks consumers to apply is
applied there: pairs below 5 shared teams never reach the page.

**Extended to triples on 2026-08-09.**
`pokemon_team_core_triple_usage` generates the 20 canonical three-Pokémon
combinations from each six-member Champions roster and reports team/player/
event support, observed and expected team share, three-way lift, constituent
pair-lift summaries, placement, and win rate. Pokémon Profile's Team Cores
view now switches between pairs and triples while retaining the existing
co-occurrence/lift choice. Triples below five real teams stay in the mart
for local analysis but do not enter the browser payload.

#### 10. Tera type usage mart — REMOVED; the Champions format has no Tera

- **Size**: S
- **Value**: Tera type is a defining format mechanic and is entirely absent
  from the analytics layer.
- **Blocked by**: nothing (though see the optional-field caveat at
  `dbt/models/marts/schema.yml:123-127` — coverage is partial)
- **Touches**: new mart, `tournament_team_member.tera_type`

Shipped as `dbt/models/marts/pokemon_tera_type_usage.sql`, then
**removed on 2026-08-03** — reopened as unbuildable, with the reason
established by measurement.

This entry's premise ("Tera type is a defining format mechanic") is true of
standard VGC and false of Champions: **the Champions format has no Tera
mechanic at all**, and `tera_type` is reported for 0.0% of its 18,284 roster
slots (100% of standard VGC's). The mart looked populated only because
`tournament_event` did not yet capture `event_format`, so it was silently
counting standard VGC events this dataset is not scoped to (see #25). Once
`int_champions_roster` scoped the marts correctly, it returned zero rows
permanently.

Removed rather than shipped as a guaranteed-empty view, following the same
precedent that removed the stat-change leaderboard and legal-pool trend
dashboard sections. Re-add only if the Champions format ever gains Tera.

#### 11. Move-type coverage analysis — SUPERSEDED, mostly resolved

- **Size**: M
- **Value**: Answers "what types can this team actually hit" and "what's the
  format's offensive coverage profile" — a real teambuilding question.
- **Blocked by**: nothing
- **Touches**: `dbt/seeds/pokeapi_move_types.csv`,
  `dbt/models/marts/pokemon_move_usage.sql`, new mart

This entry's originally-described path (`pokeapi_move_types` seed ->
`pokemon_move_usage`) shipped, and then went further: `pokemon_move_usage`
now joins real PokéAPI `move_detail` (not the static seed) for
`move_type`/`power`/`accuracy`/`category`/`priority`/`pp` per move, and the
dashboard's Matchup tab computes real type effectiveness and a
stats/setup/weather-aware damage calculator client-side from it (see the
Competitive-UX redesign pass in `docs/todo.md`'s M6 section). What's
genuinely still open, and belongs to backlog #23/#27 rather than here: a
*team-level* offensive coverage score (e.g. "what fraction of types can
this specific 6-Pokémon team hit super-effectively") — today's Matchup tab
answers per-move/per-Pokémon matchups, not a precomputed team-composition
coverage metric.

#### 12. Usage × regulation cross-tab — DONE

- **Size**: S
- **Value**: Usage is currently sliced by `event_tier` but never scoped to a
  regulation, so a Pokémon's usage number silently mixes regulations with
  different legal pools.
- **Blocked by**: nothing
- **Touches**: `dbt/models/marts/pokemon_usage_summary.sql`,
  `legality_snapshot`

Shipped as a new sibling mart, `dbt/models/marts/pokemon_usage_by_
regulation.sql`, rather than a modification to `pokemon_usage_summary`
itself: `tournament_event` carries no `regulation_code` of its own (no
temporal "usage during regulation X" signal exists to slice by), so this
cross-joins the existing overall `usage_count` against
`legality_snapshot`'s regulation membership at the latest `snapshot_date`,
with `usage_share`/`usage_rank` recomputed within each `regulation_code`
partition. **Wired into the dashboard on 2026-08-03** as the Usage tab's
Regulation filter: selecting one swaps the leaderboard's source to this
mart and *disables* the tier select, since the two dimensions genuinely
can't be combined (this mart's own header explains why) — disabled rather
than silently ignored.

#### 13. Win-rate confidence intervals — DONE

- **Size**: S
- **Value**: A 100% win rate over 3 recorded matches currently outranks 62%
  over 200. Wilson scoring fixes the ordering and removes an arbitrary
  cutoff.
- **Blocked by**: nothing
- **Touches**: `dbt/models/marts/pokemon_win_rate_summary.sql`,
  `pipelines/dashboard/data.py:169`

`pokemon_win_rate_summary.sql` now computes `wilson_lower_bound` (a 95%
Wilson score confidence interval lower bound) and `wilson_rank` per
Pokémon; `pipelines/dashboard/data.py`'s `compute_kpis` now picks the KPI
card's `top_win_rate_pokemon` by `wilson_rank` instead of the old
`RECORD_COUNT_FLOOR = 5` filter-then-max-by-`win_rate` heuristic, which is
now removed. Verified against real data: the old logic's top pick was
Victreebel-Mega at 63% over 3 matches; the new logic correctly picks
Kingambit at 50.6% over 2,384 matches. The Usage tab's Win rate leaders
table still uses its own user-selectable min-record-count filter
(unrelated UI control, left as-is) — only the KPI card's single "top"
pick and the underlying mart changed.

#### 14. Item and build concentration metrics — DONE

- **Size**: S
- **Value**: Distinguishes Pokémon with one locked-in optimal build from
  ones with genuinely contested item/ability choices — a signal about where
  the metagame is still unsettled.
- **Blocked by**: nothing
- **Touches**: `dbt/models/marts/pokemon_build_usage.sql`

`pokemon_build_usage` itself no longer exists (split into
`pokemon_item_usage`/`pokemon_ability_usage` by the M6 broadcast redesign,
before this item was picked up). Shipped as a new sibling mart,
`dbt/models/marts/pokemon_build_concentration.sql`: a Herfindahl-Hirschman
Index (sum of squared shares) over each of `pokemon_item_usage.item_share`
and `pokemon_ability_usage.ability_share` per Pokémon, plus how many
distinct items/abilities were observed at all. **Wired into the dashboard
on 2026-08-03** as a Locked in / Semi-contested / Contested badge above
the Pokémon Profile tab's Items and Ability grids, with the "only one
recorded" case labelled separately for exactly the reason this entry
gives — see `docs/design-system.md`'s "Build-concentration badge".

#### 15. Data-derived archetype clustering — EXPERIMENTAL DERIVATION DONE

- **Size**: L
- **Value**: `archetype_pokemon_map` is a 33-row hand-curated seed and the
  repo's one documented exception to mandatory provenance
  (`dbt/seeds/schema.yml:131-152`). It needs manual upkeep as the meta
  shifts and encodes your opinion rather than the data's. Deriving
  archetypes from real co-occurrence clustering would close the exception.
- **Blocked by**: nothing, though #9 is the natural foundation
- **Touches**: `dbt/seeds/archetype_pokemon_map.csv`,
  `dbt/models/marts/pokemon_archetype_usage.sql`, `archetype_summary.sql`

Shipped exactly the softer intermediate step this entry itself proposed,
not the full L-sized clustering rebuild: the curated seed stays, and a new
singular test, `dbt/tests/singular/
assert_archetype_pokemon_map_intra_group_synergy.sql`, flags archetypes
whose curated members don't actually show above-chance real team synergy
with each other, using #9's `pokemon_team_synergy.lift` as the "observed
cluster" signal to check the editorial judgment against. Per archetype:
averages `lift` across every pair of its own curated members (a pair that
never co-occurred on a real team at all has no `pokemon_team_synergy` row
-- a left join preserves that as a real "no observed pairs" signal rather
than silently dropping it); flags `drifted` (avg lift <= 1.0, no better
than chance) or `no_observed_pairs`; a single-member archetype (no pair
exists to judge) is `insufficient_data` and never flagged.
`severity=warn` (this test's own config) plus a new `archetype_drift`
`meta.category` (excluded from `release_blocking_findings` in
`pipelines/validate/report.py`, the same deliberate-exception treatment
backlog #42's `mart_quality` category already gets) means a real drift
surfaces in `reports/validation/validation_report.json`'s new
`archetype_drift_checks` section without ever blocking `dbt build`, CI, or
`pipelines.cli release`.

Verified against real data, and it immediately found real, non-hypothetical
drift in half the curated archetypes (not a contrived example): of the 6
current archetypes, `rain` (pelipper/politoed) has genuinely **zero**
recorded teams fielding both together despite being a textbook rain-team
pairing; `sun` (torkoal/ninetales/venusaur-mega/charizard-mega-y) averages
0.53 lift (real co-occurrence *below* chance for most pairs); `tailwind
-hyper-offense` (whimsicott/grimmsnarl) averages 0.098 (far below chance).
`sand` correctly stays unflagged (average pulled to 7.58 by a genuinely
strong tyranitar-mega/excadrill pairing at 20.4 lift, even though one of
its other pairs is weak) and the two single-member archetypes
(`trick-room`, `bulky-balance`) correctly report no pairs to judge. This
is real evidence for this item's own "encodes your opinion rather than the
data's" concern, not just a theoretical risk.

An experimental data-derived path shipped on 2026-08-09 without prematurely
deleting the curated seed. `detected_archetype_candidates` promotes triples
seen on at least five teams with above-chance triple and average-pair lift,
then consolidates cores sharing two members under their strongest one-hop
neighbour. `detected_archetype_team_membership` assigns one primary identity
per team and retains one secondary identity only when it scores within 90%
of the primary. `detected_archetype_summary` exposes representative cores,
team/player/event support, performance, top extensions, and stability.

Measured against the committed 0.3.0 release data: 2,940 of 3,048 Champions
teams receive a primary assignment (96.5%), 377 receive a near-tied
secondary assignment, and 38 detected groups meet the cross-event stability
label. The dashboard deliberately shows only the top 24 cross-event groups
and uses neutral core names; composition alone does not prove an editorial
label such as “Rain.” The curated seed remains as a comparison surface until
future events establish that the generated groups are stable enough to
replace it, so retirement of the seed—not data-derived discovery—is the
remaining decision.

#### 16. Speed-tier bracket mart — DONE

- **Size**: M
- **Value**: The Speed Tiers tab currently shows flat base speed. Real speed
  tiers are the modified brackets — +1/+2 stages, Choice Scarf, Tailwind —
  which is what actually determines who moves first.
- **Blocked by**: nothing (pure derivation from existing stats)
- **Touches**: `dbt/models/marts/pokemon_champions_profile.sql`, new mart

Took exactly the honest-simplification path this entry named: a documented
"max speed investment" convention (252 EVs, a beneficial nature, a perfect
31 IV, Level 50) rather than waiting on #25's real per-roster EV data.
`pokemon_champions_profile` gained a `max_investment_speed` column
(`floor((base_speed + 52) * 1.1)`, Bulbapedia's standard stat formula
simplified for this specific EV/nature/IV/level combination — verified
against a known reference value: base speed 142 (Dragapult) produces 213,
matching the commonly-cited real figure). New sibling mart
`dbt/models/marts/pokemon_speed_tiers.sql` builds the actual bracket table
on top of it: `plus_one_speed`/`scarf_speed` (x1.5) and
`plus_two_speed`/`tailwind_speed` (x2.0) are numerically-identical pairs
kept as separately-named columns since they answer different real
questions, plus `scarf_tailwind_speed` (x3.0) for the common
scarfed-under-Tailwind combination — the multipliers themselves are fixed
game-mechanics constants, the same treatment `pokemon_champions_profile`'s
schema.yml entry already gives `app.js`'s `SPEED_TIERS` thresholds and
`matchup.js`'s `TYPE_CHART`, so they're applied as plain SQL multiplication
rather than sourced from anywhere. Verified against real data (`dbt
build` against the existing warehouse): 312 legal-pool rows, correct
values end-to-end for Dragapult (213/319/319/426/426/639) and internally
consistent for every row (`plus_one_speed == scarf_speed`,
`plus_two_speed == tailwind_speed`, `scarf_tailwind_speed ==
plus_two_speed * 1.5`). **Wired into the dashboard on 2026-08-03**: the
Speed Tiers tab now reads this mart through a scenario selector (base /
max investment / ×1.5 / ×2 / ×3), with the grid, the range filter and a
new "Outruns" benchmark all following the selected column. One thing this
entry didn't anticipate: the Blazing/Fast/Average/Slow badge stays pinned
to *base* speed, because `SPEED_TIERS`' thresholds are calibrated to the
base-stat scale and would read "Blazing" for every row against a ×3
number. Item #25 (real per-roster EVs) would
still make this exact instead of assumed, unchanged from this entry's own
original note.

#### 17. Wire up `stat_change_leaderboard` — RESOLVED, staying unwired on purpose

- **Size**: S
- **Value**: The mart is built by every `dbt build` and consumed by nothing.
  Either connect it or drop it — a materialized dead-end mart is worse than
  neither.
- **Blocked by**: nothing to wire; **Blocker B** for it to show anything
- **Touches**: `pipelines/dashboard/data.py:29-64`,
  `dbt/models/marts/stat_change_leaderboard.sql`

This entry's "connect it or drop it" framing predates a decision that
already answers it: `docs/todo.md`'s M6 section records that a stat-change
leaderboard dashboard section was built, then deliberately **removed**
(see `docs/dashboard.md`'s "Removed sections" note) specifically because
Blocker B makes every row a `stat_total_delta` of 0 — a permanently empty
state is worse than no section. So the mart stays deliberately unwired,
not accidentally: recorded here so it doesn't read as an open gap.
Revisit only alongside #21, when Blocker B actually resolves.

Mart-count note, updated 2026-08-03: this gap is now closed. It had grown
worse before it got better — `MART_FIELDS` listed 11 marts against the 23
`dbt build` produces — and the mart-wiring pass wired all eight that were
unsurfaced for the "real output, dashboard surfacing is separate work"
reason. What's left unwired is only the three that are unwired *on
purpose*: this item's own `stat_change_leaderboard` (Blocker B), the two
archetype marts (tab removed by explicit request), and
`roster_source_agreement` (a data-quality check, not an analytics view).
See `docs/dashboard.md`'s "Marts wired in the mart-wiring pass".

### Blocked on snapshot history (Blocker A)

Items #1-#3 shipped (see Section 0), so the mechanism for this history now
exists — `data/staging/` accumulates real dated snapshots on a schedule. The
items below stay "blocked" in practice, not in mechanism: each needs actual
elapsed time in production for multiple real snapshots to accumulate before
it has non-degenerate data to work with. All three (#18-#20) are also now
**archived** — excluded from active scope by user decision (see #18's note)
— on top of remaining genuinely blocked.

#### 18. Meta-shift and movers view — ARCHIVED (excluded from active scope)

- **Size**: M
- **Value**: "What's rising, what's falling, what's new this week" — the
  headline view of any competitive meta report.
- **Blocked by**: real multi-snapshot history accumulating now that #1-#3 are live
- **Touches**: new mart, `pokemon_usage_summary`

Partially approximable today via #6's event-date axis.

**Archived 2026-08-02**: excluded from active scope by user decision, along
with #19-#21 and #31 (meta-shift/legal-pool/stat-change trend items and the
Streamlit dashboard). Not resolved — deprioritized. Still genuinely blocked
on Blocker A underneath; un-archive if this is reprioritized.

#### 19. Legal-pool change tracking — ARCHIVED (excluded from active scope)

- **Size**: S once unblocked
- **Value**: Revives an analysis that already exists and has never returned
  a non-degenerate row.
- **Blocked by**: real multi-snapshot history accumulating now that #1-#3 are live
- **Touches**: `dbt/analyses/largest_legal_pool_changes_by_regulation.sql`,
  `dbt/models/marts/legality_summary_by_regulation.sql`

Carries a permanent caveat regardless: PokéBase publishes only positive
legality signals, so absence can't distinguish "banned" from "not yet
observed" (`legality_summary_by_regulation.sql:14-21`). A second source with
explicit ban signals would be the real fix.

**Archived 2026-08-02**: excluded from active scope by user decision (see
#18's note). Not resolved — deprioritized.

#### 20. Restore the legal-pool trend dashboard section — ARCHIVED (excluded from active scope)

- **Size**: S
- **Value**: The code already existed and was cut for permanently rendering
  an empty state; `docs/dashboard.md` describes re-adding it as "a small,
  self-contained addition" with the removed code recoverable from git
  history.
- **Blocked by**: #19
- **Touches**: `pipelines/dashboard/`, `docs/dashboard/`

**Archived 2026-08-02**: excluded from active scope by user decision (see
#18's note). Not resolved — deprioritized.

### Blocked on a Champions rebalance (Blocker B)

The one item in this subsection (#21) is also now **archived** — excluded
from active scope by user decision (see #18's note) — on top of remaining
genuinely blocked on Blocker B.

#### 21. Stat-change leaderboard surface — ARCHIVED (excluded from active scope)

- **Size**: S
- **Value**: The whole `pokemon_stat_delta` entity — a core part of the
  original value proposition, "canonical vs. Champions" — has never shown a
  single nonzero row.
- **Blocked by**: **Blocker B**; #17 for the wiring
- **Touches**: `pipelines/dashboard/`, `docs/design-system.md:32`

The `--positive`/`--positive-bg` design tokens are already reserved for
exactly this. Nothing to do but be ready.

**Archived 2026-08-02**: excluded from active scope by user decision (see
#18's note). Not resolved — deprioritized. Still genuinely blocked on
Blocker B underneath; un-archive if this is reprioritized.

### Needs new provenance — with a sourcing path

**All six items in this subsection are now closed** (#22-#24 shipped
earlier; #25-#27 on 2026-08-03). Each entry named a real path to provenance
rather than proposing a hardcoded, unsourced table — and in #26/#27's case
the path turned out to be considerably shorter than the entry assumed, once
the live source was checked rather than the entry's own description of it.
#25 is the one genuine dead end: the data it wanted is published by nobody.

#### 22. `pokemon_type` entity via PokéAPI `/type` — DONE, via a lighter path

- **Size**: M
- **Value**: The cleanest unblock in this file. Type is the most fundamental
  Pokémon attribute and the dataset does not have it — which is why the
  matchup gap has stayed open. PokéAPI is **already an in-scope source**;
  `/type` is just an endpoint nobody has fetched.
- **Blocked by**: nothing
- **Touches**: `pipelines/extract/pokeapi.py`, new normalized entity,
  `docs/dataset-spec.md` entity dictionary

Shipped by the Competitive-UX redesign pass (`docs/todo.md`'s M6 section),
via a lighter path than this entry proposed: `type_1`/`type_2` landed as
new columns on the existing `pokemon` entity (real PokéAPI data, full
provenance) rather than a standalone `pokemon_type` dimension entity — no
`MINOR` version bump needed, since it extended an existing entity instead
of adding a tenth one. `docs/dataset-spec.md`'s entity dictionary already
documents `pokemon.type_1`/`type_2`, so that update isn't owed either.

#### 23. Type-effectiveness matrix — DONE, via a lighter path

- **Size**: M
- **Value**: Closes the type half of the long-standing matchup gap recorded
  at `dbt/models/marts/schema.yml:115-121` and in `docs/todo.md`'s M6
  backlog — with real provenance, since PokéAPI publishes
  `damage_relations` per type.
- **Blocked by**: #22
- **Touches**: `pipelines/extract/pokeapi.py`, new normalized entity, new
  mart

Shipped as a client-side `TYPE_CHART` constant in
`pipelines/dashboard/static/matchup.js`, not a new normalized entity/mart
fed by PokéAPI's `damage_relations` as originally proposed. Deliberate,
documented divergence, not a provenance shortcut: type effectiveness is a
fixed game-mechanics fact, not a per-record extracted fact, so it gets the
same treatment `pokemon_champions_profile`'s schema.yml entry already
gives `app.js`'s `SPEED_TIERS` bucketing constant and weather-boost
multipliers. Powers the Matchup tab's type-effectiveness view and damage
calculator against real `pokemon.type_1`/`type_2` and `move_detail` data.
Still the real open half of the matchup gap, unrelated to this item: real
head-to-head battle-outcome data (#27) — no source provides it.

#### 24. Ability and move metadata from PokéAPI — DONE

- **Size**: M
- **Value**: Move power, accuracy, damage class, and ability effects unlock
  damage-calc-style analysis. Today `moves` is a pipe-delimited string of
  names with no properties attached.
- **Blocked by**: nothing (same in-scope source)
- **Touches**: `pipelines/extract/pokeapi.py`, new normalized entities

Shipped exactly as described, by the Competitive-UX redesign pass: three
new normalized entities with real PokéAPI provenance —
`dbt/models/normalized/move_detail.sql` (type/power/accuracy/category/
priority/pp/short_effect), `ability_detail.sql`, and `item_detail.sql` —
scoped to names actually seen in real tournament rosters rather than
PokéAPI's full catalog. All three are documented in `docs/dataset-spec.md`'s
entity dictionary and joined into `pokemon_move_usage`/
`pokemon_ability_usage`/`pokemon_item_usage`. The Champions-move-rebalance
question this entry flagged is still unresolved, but unverifiable from any
in-scope source, not a gap in this item's own scope.

#### 25. EV spreads via Victory Road — RESOLVED, will not build; the data does not exist

- **Size**: L
- **Value**: EVs were framed as "the missing half of how this Pokémon is
  actually built," plus a fix for MunchStats' ~17% nature coverage and a way
  to make #16's speed tiers exact instead of assumed.
- **Blocked by**: nothing that can be unblocked — see below
- **Touches**: `docs/data-sources.md`, `docs/dashboard.md`,
  `docs/design-system.md`, `pipelines/extract/munchstats.py`,
  `dbt/models/intermediate/int_champions_roster.sql`

Closed by measurement rather than by building an extractor, and **both
halves of this entry's premise turned out to be false**.

**The EV half: structurally unavailable, not deferred.** Three findings, in
increasing order of importance:

1. `docs/data-sources.md` pointed at `victory-road.com`, which **has no DNS
   record at all** — the URL was simply wrong. The real site is
   `victoryroadvgc.com`.
2. `victoryroadvgc.com` is unreachable from this project's egress. It is
   *permitted* by network policy (CONNECT tunnel established, HTTP 200) but
   the origin resets the TLS handshake right after ClientHello — reproduced
   across TLS 1.2/1.3, with and without ALPN, via both curl and
   `openssl s_client`, while control hosts handshake normally. Not a
   pipeline-side problem and not routable around.
3. **Decisively: nobody publishes EVs.** Official tournament team sheets —
   RK9's own, which both MunchStats and Limitless derive from — carry
   Ability, Held Item, "Stat Alignment" (nature) and moves, and nothing
   else. Verified directly against `rk9.gg/teamlist/public/{event}/{team}`
   and `limitlessvgc.com/teams/{id}`: zero EV/IV data on either. Any EV
   spread published anywhere is community-reconstructed, not sourced, so
   ingesting it would violate this repo's mandatory-provenance rule.

So #16's speed tiers stay on their documented max-investment convention.
That is now a permanent answer, not a placeholder.

**The nature-coverage half: a measurement artifact, and fixing it exposed a
real bug.** "MunchStats' nature coverage is only ~17%" was repeated in five
files. It is not a coverage gap: **17.2% is the Champions share of the
corpus.** MunchStats indexes standard VGC events (regulations F/H/I)
alongside Champions ones, and `tournament_event` never captured `format`, so
every usage and win-rate mart in this repo had been silently blending two
different games with different legal pools and mechanics.

Measured, per format:

| Event format | roster slots | nature | tera_type |
|---|---|---|---|
| `gen9championsvgc2026regma` | 18,284 | **100%** | 0% |
| standard VGC (`regf`/`regh`/`regi`) | 87,850 | 0% | **100%** |

Champions team sheets report nature and the format has no Tera mechanic;
standard VGC is the exact reverse. Fixed by capturing `event_format` through
extraction into `tournament_event`, and adding
`dbt/models/intermediate/int_champions_roster.sql`, which every
roster-derived mart now reads instead of `tournament_team_member`.

The correction is large and visible: Incineroar was the #1 most-used Pokémon
at 7,641 appearances and is really #5 at 1,029; Gholdengo, Dragonite,
Whimsicott and Farigiraf leave the Champions top 8 entirely, replaced by
Basculegion-Male, Kingambit, Garchomp and Charizard-Mega-Y. Consequently
`pokemon_tera_type_usage` (backlog #10) is now **permanently empty** for
Champions and was removed, following the same precedent that removed the
stat-change leaderboard and legal-pool trend sections — see #10's note.

#### 26. Limitless VGC — DONE, built for a different reason than this entry gave

- **Size**: XL as written; actually M once the premise was checked
- **Value**: as delivered — canonical shared team identity, and an
  independent second source to cross-validate MunchStats rosters against.
  NOT, as originally written, deeper historical coverage.
- **Blocked by**: nothing; both stated blockers were false
- **Touches**: `pipelines/extract/limitless.py`, `data/staging/limitless*`,
  `dbt/models/{staging,intermediate,normalized}/`, two new seeds,
  `dbt/models/marts/roster_source_agreement.sql`

Both of this entry's blockers were wrong, and so was its value statement.

- **"No API exists / manual browser table capture"** — false.
  limitlessvgc.com is server-rendered; every page needed is a plain GET with
  the data on `data-` attributes. No browser automation, no screenshotting.
- **"Extends the meta history further back than MunchStats reaches"** —
  false. Only **three** Champions-format events exist anywhere, and
  MunchStats already had all three. Limitless' other 22 tournaments are
  standard VGC, out of scope per `docs/prd.md`. Per event it is in fact
  *narrower*: team lists cover the day-2 cut only (156 of 1,096 at NAIC).

What it does have, and what it was built for, is **identity**: a
`/teams/<id>` is a canonical team *composition* reused across every player
and event that fielded it, where MunchStats mints a fresh team id per player
per event. Shipped as `team_list` (359 compositions; 44 fielded by more than
one player, 8 across more than one tournament) and `team_list_member`.

The cross-validation paid for itself immediately. New
`roster_source_agreement` reported **0% exact agreement** on first run,
which surfaced a real modelling error: Limitless publishes the *base*
species holding its Mega Stone ("Charizard" + "Charizardite Y") where
MunchStats publishes the evolved form ("Charizard-Mega-Y"). Taken literally
the Limitless row joined to base-species stats — not the stats that Pokémon
actually played with. Fixed with a `limitless_mega_item_to_pokeapi_form`
seed keyed on (slug, item), after which agreement is **97.9-100% exact and
99.2-100% per slot**, with Turin at a clean 100%. Two cases the mechanical
rule could not derive and that are recorded explicitly: `Eviolite` is a
generic item that ends in `-ite`, and Floette's Mega evolves from the
Eternal Flower form onto `floette-mega`.

The residual ~1-2% disagreement is real and left visible: Limitless
publishes a bare `maushold` slug with no family-size distinction, so three
Maushold-Family-of-Three teams map to family-of-four.

#### 27. Head-to-head matchups — DONE via RK9; the "no signal" premise was stale

- **Size**: XL as written; actually M
- **Value**: delivered — "what beats Pokémon X" is answerable from real
  match outcomes for the first time.
- **Blocked by**: nothing
- **Touches**: `pipelines/extract/rk9.py`, `data/staging/rk9_pairings*`,
  `dbt/models/normalized/tournament_match.sql`,
  `dbt/models/marts/pokemon_head_to_head.sql`,
  `pokemon_matchup_summary.sql`, the dashboard's Matchup tab

This entry said "MunchStats reports team-level win/loss records, not
per-battle outcomes against a named opponent, so there is no signal to
derive this from." True of MunchStats — but it named the answer itself
without following it up: "round-by-round pairing data from tournament
software." That software is **RK9**, the same source MunchStats scrapes for
rosters, and it publishes pairings over plain HTTP.

`GET rk9.gg/pairings/{event_id}?pod={p}&rnd={n}` returns each round's
matches with winner/loser, table number and both players' running records.
No new ID mapping was needed at the event level: MunchStats reuses RK9's own
event ids verbatim, so `tournament_event.event_id` *is* the pairings key.
Players resolve to `team_id` on (name, country) at **99.8%** across 24,139
Masters pairing slots.

Shipped as `tournament_match` (13,201 real matches across the three
Champions events: 13,127 decided, 69 byes, 5 ties) plus
`pokemon_head_to_head` (16,763 pairs, Wilson-ranked) and
`pokemon_matchup_summary`, surfaced in the Matchup tab beside the co-usage
panel that had been standing in for this. Results are non-degenerate and
competitively sensible — Incineroar's worst matchup is Lycanroc-Dusk at
39.1% over 289 matches, its best Torkoal at 61.0% over 290.

**One honest limit remains, and it is narrower than this entry's original
scope.** An outcome is *team vs team*. No source names which four of a
team's six Pokémon were brought to a given match, or which knocked out
which, so every head-to-head figure is attributed to the whole roster.
Closing that needs a battle-log or replay source; none is in scope or
deferred. Every consumer of these marts states this — see
`dbt/models/marts/schema.yml`.

---

## Section 2 — Consumption surfaces

Deliberately thin: with a single user, query ergonomics matter more than
distribution.

### 28. Local query and notebook quickstart — DONE

- **Size**: S
- **Value**: Probably the highest-value consumption item for a single user.
  The DuckDB warehouse at `dbt/data/warehouse.duckdb` already holds every
  model; a short recipe doc plus a few starter queries beats any amount of
  dashboard work for ad-hoc questions.
- **Blocked by**: nothing
- **Touches**: new doc or `notebooks/`, `dbt/analyses/`

Shipped as `docs/local-queries.md`: how to open the warehouse (DuckDB CLI or
Python, both from `dbt/`, since external tables resolve paths relative to
that working directory), how to list every queryable table, and seven
starter queries — each run against a real, freshly-extracted snapshot to
confirm non-degenerate output, not just checked for syntax. Several of the
queries (team synergy lift, placement-weighted usage, build
concentration) surface marts that still aren't wired into the
dashboard UI at all, so this doc is currently the only way to see their
output.

### 29. Trend and line charts in the dashboard — DONE, event-date variant

- **Size**: M
- **Value**: The trend views `docs/prd.md` describes and the dashboard has
  never been able to show.
- **Blocked by**: ~~real multi-snapshot history accumulating (#1-#3 are
  live; or #6 for the event-date variant)~~ #6 shipped
  `pokemon_usage_by_event_date`, so the event-date variant's data
  dependency is resolved — this item is no longer blocked, just not yet
  built. The snapshot-date variant still needs #1-#3's history to actually
  accumulate multiple snapshots in production.
- **Touches**: `pipelines/dashboard/templates/`, `static/app.js`

Note the broadcast redesign removed the charting library entirely, so this
means either reintroducing a dependency or extending the dependency-free
ranked-list components.

Shipped the event-date variant as the Usage tab's new **Trends** subtab
(combined with #30 below, since both landed in the same date-filtered
view): took the "extend the dependency-free components" branch rather
than reintroducing a charting dependency, per this entry's own note. Each
Pokémon's row shows its `usage_share` *change* versus the immediately
preceding tournament date (not a fixed time window) as a colored `▲/▼
Npp` badge, or a `NEW` badge for a Pokémon absent from that previous
date — new `.badge-positive`/`.badge-negative`/`.badge-new` variants
reusing the already-defined `--positive`/`--danger`/`--warning` tokens (no
new color pair needed). A Pokémon on the *very first* tournament date on
record shows neither (no prior date exists at all, a different case from
a specific Pokémon being new) — see `docs/design-system.md`'s new "Trend
delta badge" entry. Verified against a real `extract all` + `dbt build` +
`build-dashboard` run: 26 real tournament dates, correct deltas/NEW badges
at a mid-range date, and all "—" (no false NEW badges) at the earliest
date, with zero browser console errors. The snapshot-date variant (real
multi-extraction history, not tournament dates) is still open, gated on
Blocker A's elapsed time as before.

### 30. Tournament and date filter — DONE

- **Size**: S
- **Value**: One of the three open `docs/todo.md` M6 backlog items.
- **Blocked by**: ~~real multi-snapshot history accumulating (#1-#3 are
  live) or #6~~ #6 shipped; a real `event_date` dimension exists to filter
  by now (`pokemon_usage_by_event_date`). Not yet built.
- **Touches**: `pipelines/dashboard/static/app.js`

Shipped as `#usage-trend-date-filter` in the same Trends subtab #29 added:
a plain `<select>` of every distinct `pokemon_usage_by_event_date.
event_date`, most recent first and selected by default. Deliberately not
routed through the shared `fillSelect()` helper (which always prepends an
"All" option) — an unfiltered/all-dates view doesn't mean anything for a
per-date usage snapshot, so the select only ever offers real dates.

### 31. Dynamic Streamlit dashboard — ARCHIVED (excluded from active scope)

- **Size**: L
- **Value**: Mirrors the existing `docs/todo.md` M6 backlog item. Would
  build on `pipelines/dashboard/data.py`'s existing mart-loading and KPI
  logic.
- **Blocked by**: real multi-snapshot history accumulating — the item's own
  stated condition is "once the dataset has enough snapshots/trend data to
  justify the added hosting complexity"; #1-#3 shipped the mechanism, not
  the elapsed time
- **Touches**: new package, `pipelines/dashboard/data.py`

Worth weighing against #28: for a single user, a notebook may deliver most
of the same value with none of the hosting cost.

**Archived 2026-08-02**: excluded from active scope by user decision (see
#18's note). Not resolved — deprioritized.

### 32. JSON feed alongside the baked-in dashboard data — DONE

- **Size**: S
- **Value**: Dashboard data is inlined into `index.html` as
  `window.DASHBOARD_DATA` (deliberately, to survive `file://` CORS). A
  sibling `.json` file makes the same data scriptable without re-running
  dbt.
- **Blocked by**: nothing
- **Touches**: `pipelines/dashboard/build.py`

`build()` now also writes `data.json` (the exact same payload
`json.dumps`'d, not reparsed from the escaped inline script) alongside
`index.html`. `index.html` stays the inline-data version — not switched to
`fetch()`-ing `data.json` — so it keeps working opened directly via
`file://`, per this module's own docstring.

**2026-10 update:** the marts now live in shard files under
`docs/dashboard/data/` (core, one per regulation scope, and the three
largest marts on their own), and `data.json` holds every other key plus
`mart_files`, the index of those shards. The feed is still complete and
scriptable, as several files instead of one. See `docs/dashboard.md`'s
"Payload split".

### 33. GitHub Releases with packaged artifacts — DONE

- **Size**: S
- **Value**: Consumption today is `git clone` or raw URLs. A zipped release
  package with checksums makes versions citable and verifiable — and
  `releases/` already has everything needed.
- **Blocked by**: nothing (pairs naturally with #35)
- **Touches**: `pipelines/release/build.py`, `.github/workflows/`

Shipped as new `.github/workflows/publish-release.yml`, triggered by the
commit that adds a new `releases/manifests/manifest-<version>.json` to
`main` (diffing `github.event.before`/`after` for added manifest files)
rather than a git-tag push — this repo has never tagged dataset versions,
and inventing that convention just to satisfy a workflow trigger would
have been a bigger change than this item asked for. For each new version
it zips `releases/data/<version>/` (CSVs + `images/`) together with
`manifest.json` and `CHANGELOG.md` — matching `CLAUDE.md`'s "Release
package" contents exactly — writes a `sha256sum` checksum file, and
publishes both as a GitHub Release tagged `data-v<version>` via `gh
release create` (no third-party action needed; `gh` is preinstalled on
GitHub-hosted runners). Also exposed as `workflow_dispatch` with a
`version` input, to (re-)publish a specific version on demand — deletes
and recreates the release/tag first for idempotency on rerun. Verified
end-to-end against the real `releases/data/0.2.0/` (330 files, 11MB zip)
with a stubbed `gh`: the zip contents and computed checksum both came out
correct; a synthetic git-history test also confirmed the added-manifest
diff logic picks up exactly the new version(s) in a push, not
already-published ones.

### 34. Pokémon Profile empty state — RESOLVED, current behavior kept

- **Size**: S
- **Value**: The third open `docs/todo.md` M6 backlog item.
- **Blocked by**: nothing
- **Touches**: `pipelines/dashboard/static/app.js`

The existing item notes the current behavior — defaulting to the
highest-usage Pokémon — may actually be preferable to an empty state.
Decide before building.

Decided: keep defaulting to the highest-usage Pokémon, no code change.
Every other tab in this dashboard shows ranked content immediately on
open (Overview's Top 12, Usage's leaderboard, Team Builder's legal-pool
picker) per the "Ordering convention" — a blank Profile panel on first
load would be the one tab asking a visitor to act before showing them
anything. `.empty-state` is still used for the genuine empty case (a
stale selection resolving to no matching row). Documented in
`docs/design-system.md`'s new "Default selection, not an empty state
(Pokémon Profile)" subsection so this reads as a decision, not an
unaddressed gap.

---

## Section 3 — Platform, quality, and ops

Separated from the analytics list so it doesn't dilute it. These are
verified gaps, not speculative hardening. Items #36 and #38 were the two
with real correctness consequences; both are now done.

### 35. CI workflow — DONE

- **Size**: M
- **Value**: `make check` (lint + test + dbt build + validate) exists and
  nothing runs it automatically. There is no `.github/` directory at all.
- **Blocked by**: nothing
- **Touches**: new `.github/workflows/`

("No `.github/` directory at all" was already stale by the time this was
picked up — `scheduled-extraction.yml`/`deploy-dashboard.yml` exist — but
neither ran lint/test/dbt-build/validate on a push or PR, so the core gap
this item describes was real.) Shipped as new `.github/workflows/ci.yml`,
triggered on every PR and push to `main`. `lint`/`test` always run (pure
Python, no network dependency). `dbt-build`/`validate` need
`data/staging/*.csv`, which is gitignored and not committed — rather than
re-running extraction on every push (hitting OP.GG/PokéBase/MunchStats
repeatedly, which the extractors' own docstrings already flag an
unverified rate-limit/ToS posture for under `scheduled-extraction.yml`'s
daily cadence, let alone per-push), CI restores the same `actions/cache`
entry `scheduled-extraction.yml` populates (read-only, via
`actions/cache/restore`) and runs `dbt-build`/`validate` against that; on
a fresh fork with no scheduled run yet, that step degrades to a skipped
no-op rather than failing the job. This was caught firsthand: PR #40 (the
one that shipped backlog items #8/#10/#12/#13/#14) had zero CI checks run
against it before this item existed.

### 35b. CI skips dbt when the restored cache predates the commit — DONE

Follow-up to #35, found the hard way: the PR that added the RK9 and
Limitless sources red-failed CI with three opaque dbt errors ("No files
found that match the pattern `../data/staging/limitless/*.csv`",
"Referenced column `event_format` not found in FROM clause") even though
`make check` passed locally against real data.

Nothing was wrong with the code. CI deliberately never extracts: it
restores the `actions/cache` entry `scheduled-extraction.yml` populates and
runs dbt against that, so the data it sees is always as old as the last
scheduled run. Any PR that adds a source or a staging column is therefore
*guaranteed* to build against snapshots that predate it — a structural
false failure that would have hit every future source addition, and one
that resolves on its own once the nightly cron repopulates the cache.

`ci.yml` already intended to skip rather than fail here; it just only
recognised the total-miss case (a fresh fork with no cache at all). New
`pipelines/schema_contracts.staging_contract_mismatches()` compares the
restored snapshots against the tracked `data/staging/*.schema.json`
contracts — reusing #41's existing contract loader rather than adding a
second notion of what a staging source looks like — and CI now skips with
an explanation when they disagree. Covered by seven unit tests, including
the exact missing-source and missing-column shapes that failed.

### 36. Fix vacuously-passing coverage tests — DONE

- **Size**: S
- **Value**: A correctness hole in the release gate. All four
  `assert_*_coverage.sql` tests return `10000` bps (100%) when the source
  has zero rows — so a total upstream outage that yields an empty CSV
  **passes every gate and can be released**.
- **Blocked by**: nothing
- **Touches**: `dbt/tests/singular/assert_*_coverage.sql`

Each test's zero-row branch now reports `0` bps instead of `10000`, so an
empty source fails the gate instead of passing it vacuously. Verified the
branch can only trigger for a genuinely empty (but present) snapshot file —
a missing one makes DuckDB's external-source glob raise an `IO Error`
before the query runs at all — so this doesn't newly break a fresh clone
with no extraction yet, only a real "extraction ran and returned nothing"
outage. Pairs with #40, which is still open.

### 37. Derive the validation report from dbt's manifest — DONE

- **Size**: M
- **Value**: `pipelines/validate/report.py` maps tests via four hardcoded
  dicts covering 30 of dbt's 32 singular tests. Two —
  `assert_archetype_pokemon_map_resolves_to_pokemon` and
  `assert_duplicate_key_archetype_pokemon_map` — run on every build but
  appear in no report section, so they **can never block a release**. Any
  new test is invisible to the gate until someone remembers to edit
  `report.py`.
- **Blocked by**: nothing
- **Touches**: `pipelines/validate/report.py`,
  `reports/validation/validation_report.template.json`

The real gap was larger than the two named tests: `ability_detail`,
`item_detail`, and `move_detail`'s duplicate-key tests were invisible too
(five tests total, all added after the four dicts were last touched) —
exactly the "any new test is invisible until someone remembers to edit
report.py" failure mode this item describes, caught in the wild rather
than hypothetically. Fixed by removing the four dicts entirely: every
singular test SQL file now declares its own `{{ config(meta={category:
..., ...}) }}` (`dbt/tests/singular/*.sql`), and `report.py`'s
`build_report` iterates every test node in the manifest and buckets it by
`meta.category` instead of a name lookup. A test with no recognized
category lands in a new `uncategorized_checks` section (still eligible to
block a release on failure) rather than disappearing — closing the gap
for good, not just for these five tests. Verified against a real `dbt
build` + `extract all` pass: all 13 duplicate-key tables (the previously
-invisible four included) and all 9 referential-integrity checks now
appear in `validation_report.json` with real pass/fail status, and
`uncategorized_checks` is empty.

### 38. Don't swallow the `dbt build` return code — DONE

- **Size**: S
- **Value**: The other correctness hole. `subprocess.run(["dbt", "build"])`
  at `pipelines/cli.py:46` discards its exit status. The comment correctly
  justifies this for *test* failures, but a compile or connection error also
  exits non-zero **without writing fresh `run_results.json`** — so
  `validate` silently reshapes the previous run's artifacts and can report a
  pass on a build that never ran.
- **Blocked by**: nothing
- **Touches**: `pipelines/cli.py:41-52`

`_run_validate` now captures the exit code, treats anything outside
`{0, 1}` as a crash it returns directly (no report generated), and — even
within `{0, 1}` — refuses to reshape `run_results.json` unless its mtime
shows it was actually rewritten by this invocation, catching the compile/
connection-error case the ratio-based gates couldn't see. Also fixed the two
nits noted here: the subprocess call is now `uv run dbt build` (matches the
Makefile), and the no-op list copy is gone. See `docs/todo.md`'s "Platform
hardening" section.

### 39. Source freshness gate — DONE

- **Size**: S
- **Value**: Nothing checks whether a snapshot is stale. The pipeline will
  happily validate and release six-month-old data with every gate green.
- **Blocked by**: nothing
- **Touches**: `dbt/models/staging/_sources.yml`,
  `pipelines/validate/report.py`

No `loaded_at_field` or `freshness:` block is configured anywhere, though
every row already carries `extracted_at_utc`.

Shipped: `_sources.yml`'s seven scheduled sources (PokéAPI + its three
detail feeds, OP.GG, MunchStats, PokéBase — Bulbagarden stays exempt,
it's deliberately on-demand-only) each gained a `freshness:` block
(`warn_after`/`error_after` mirroring `docs/dataset-spec.md`'s weekly/daily
cadences, doubled so one missed scheduled run warns rather than errors)
and a `loaded_at_field` casting `extracted_at_utc` to a timestamp (dbt's
freshness macro needs a real datetime, not the plain ISO-8601 string the
column actually is). `pipelines/cli.py`'s `_run_validate` now also runs
`dbt source freshness` (a separate command from `dbt build`) before
generating the report; `report.py`'s new `build_freshness_checks` reshapes
`target/sources.json` into a `freshness_checks` section, folding dbt's
"error" status into `release_blocking_findings` the same way any other
failing check is, while "warn" stays non-blocking. Verified against a real
`extract all` + `dbt source freshness` run: all seven sources report
`pass` with real `max_loaded_at`/age values in `validation_report.json`.

### 40. Row-count anomaly detection — DONE

- **Size**: M
- **Value**: Every current gate is a ratio or a duplicate count, so a source
  silently dropping from 106,000 rows to 500 passes all of them. Volume
  baselines catch the partial-outage case that #36 catches only in the total
  case.
- **Blocked by**: nothing, though #1's history makes baselines far easier
- **Touches**: `dbt/tests/singular/`, `pipelines/validate/report.py`

Shipped as a new dbt *generic* test — this project's first, per #42's own
observation that none existed — `dbt/macros/test_row_count_anomaly.sql`,
applied to each of the seven scheduled sources' `data_tests:` in
`_sources.yml` (same set freshness already covers; Bulbagarden stays
exempt for the same on-demand reason). It compares the latest
`snapshot_date`'s row count against the immediately preceding one (using
the append-only history #1/#2 already shipped) and fails below 50% of that
baseline; fewer than two snapshots (fresh clone, or a source extracted
only once) passes rather than failing vacuously, since there's no baseline
yet to call an anomaly against — a different case from #36's "present but
empty" fix, not a regression of it. Wired into
`pipelines/validate/report.py` as a new `row_count_anomaly_checks`
category (no hardcoded dict, following #37's meta.category pattern) and
`reports/validation/validation_report.template.json`. Verified against a
synthetic two-snapshot fixture (`dbt test -s
source_row_count_anomaly_staging_pokeapi_`): a 300→50 row drop fails at
1667bps, a 300→280 normal fluctuation passes, and a single-snapshot source
passes vacuously — plus a new `test_report.py` unit test for the
report-shaping side.

### 41. Schema-drift enforcement — DONE

- **Size**: M
- **Value**: The `data/staging/*.schema.json` and `data/normalized/*.schema.json`
  contracts are described as the durable tracked contract for each source —
  but they are documentation only. **No code loads or asserts against
  them**, and every `stg_*` model is a bare `select *`, so an upstream
  column rename propagates silently or surfaces as a confusing downstream
  error.
- **Blocked by**: nothing
- **Touches**: `data/**/*.schema.json`, `dbt/models/staging/`, `tests/`

Shipped as two layers, matching the two contract directories this entry
names. New shared `pipelines/schema_contracts.py` (`schema_field_names`,
`csv_header`) is the one place both layers load a `*.schema.json`
contract's declared field-name list. **Staging layer**: new
`tests/unit/extract/test_schema_contracts.py` asserts every one of the
five extractors' `FIELDNAMES` (plus PokéAPI's three detail-feed
`MOVE_FIELDNAMES`/`ABILITY_FIELDNAMES`/`ITEM_FIELDNAMES` constants) exactly
matches its `data/staging/<subdir>.schema.json` contract — a pure
code-level check needing no live data, so it runs on every `make test`/CI
push and catches the "code and docs drifted apart" mistake immediately,
before anything downstream. **Normalized layer**: new
`pipelines/validate/report.py`'s `build_schema_drift_checks` compares each
`data/normalized/<entity>.csv`'s real header (post-`dbt build`) against its
`data/normalized/<entity>.schema.json` contract, wired into `build_report`
as a new `schema_drift_checks` report section and into
`release_blocking_findings` the same way any other failing gate is — a
missing CSV (fresh clone, or an unextracted source like `pokemon_asset`
before Bulbagarden runs) reports `skipped`, not `fail`, since there's no
drift to detect against data that doesn't exist yet. Verified against real
data: a full `extract` + `dbt build` + `validate` run reports all 11
present normalized entities `pass` and `pokemon_asset` correctly
`skipped` (Bulbagarden wasn't extracted this pass), with
`release_blocking_findings` empty.

The RSC-scraping risk this entry specifically named (`opgg.py`/`pokebase.py`'s
hand-rolled string markers) turns out to fail loud already, not silent —
`_extract_pokemon_payloads` raises `ValueError` if the marker or bracket
structure it scans for ever goes missing, and a genuine upstream JSON-key
rename (e.g. `stats["hp"]`) would raise `KeyError` the same way. The real
silent-drift risk this item closes is narrower but still real: our own
`FIELDNAMES`/`schema.json` pair (or a normalized model's `select` list)
drifting out of sync with each other through an ordinary code edit, which
neither layer's tests caught before this pass.

### 42. Mart tests — DONE

- **Size**: M
- **Value**: All 32 singular tests target normalized and seed models. **Zero
  tests exist on any of the ten marts** — the layer the dashboard actually
  reads.
- **Blocked by**: nothing
- **Touches**: `dbt/tests/singular/`, `dbt/models/marts/schema.yml`

Took the "generics would cover it in one line" path this entry itself
suggested, applied to all 21 marts that exist by the time this was picked
up (not ten -- the mart layer grew across several other backlog items
before this one landed). Every mart now carries `not_null` on its grain
column(s) plus a uniqueness check on its real primary key: dbt's built-in
`unique` for the 8 marts with a genuine single-column grain
(`pokemon_champions_profile`, `pokemon_speed_tiers`, etc.), and a new
generic test, `dbt/macros/test_unique_combination_of_columns.sql`, for the
13 marts with a real composite grain (e.g. `pokemon_usage_summary`'s
`(pokemon_key, event_tier)`, `pokemon_team_core_usage`'s `(pokemon_key,
partner_pokemon_key)`) -- the standard `unique_combination_of_columns`
pattern (the same one dbt-utils ships), reimplemented directly rather than
adding a package dependency for one macro. This is this project's second
generic test (the first was backlog #40's `row_count_anomaly`), so the
"not a single generic test" observation this entry originally made no
longer holds at all.

Tagged `meta.category: mart_quality`, following #37's mechanism, and
wired into `pipelines/validate/report.py` as a new `mart_quality_checks`
report section -- but deliberately **excluded** from
`release_blocking_findings`, unlike every other category: marts branch off
the normalized layer for dashboard-facing output and aren't part of the
release package (`CLAUDE.md`'s "Repository structure"), so a mart-quality
failure should be visible and actionable without blocking
`pipelines.cli release`. New `tests/unit/validate/test_report.py` cases
cover both the categorization and the never-blocks guarantee directly.

Verified against real data, and this real run caught a real, previously
-latent bug, not a hypothetical: `dbt build` against the actual warehouse
initially failed with a DuckDB CSV parse error on `player_signature_pokemon
.csv` (a `unique_combination_of_columns` test was the first query ever to
read that mart's *full* row width back into DuckDB) -- `read_csv`'s
`auto_detect` sniffer only samples the first ~20,480 rows to guess the CSV
dialect, and the first quoted comma in a player name ("Wyatt Thibodeaux,
Jr.") didn't appear until row 34,569, so it wrongly concluded no quote
character was needed at all. A single-column `not_null` test against the
same view didn't trip it (confirmed: the optimizer can prune that down to
one column without validating full row arity), so this was a real gap
only a multi-column test could have caught. Fixed at the source, not
worked around in the test: `dbt_project.yml`'s `marts`/`normalized` model
configs now pin `csv_read_options: {quote: '"', escape: '"'}` (Python's
`csv.DictWriter` and dbt-duckdb's own CSV writer both already always use
`"`, so this was never actually a value that needed sniffing) while
leaving delimiter/header/type detection on `auto_detect`. Confirmed fixed
directly against the same file with `read_csv(..., quote=chr(34),
escape=chr(34))`, then via a real, clean `dbt build` (147 pass, 0 mart
test failures) and `pipelines.cli validate` (54 mart_quality_checks, all
`pass`, `release_blocking_findings` empty). The same latent risk existed
for `normalized/*.csv` too (e.g. `tournament_team.player_name`) even
though nothing had tripped it yet -- fixed there in the same config change
rather than only patching the mart that happened to surface it first.

### 43. Extractor resilience — DONE (retry/backoff; rate limiting still open)

- **Size**: M
- **Value**: No retry, backoff, or rate limiting anywhere. `pokeapi.py`
  fires roughly 1,350 sequential unthrottled requests and a single
  `raise_for_status()` anywhere aborts the run with no output at all.
  Becomes materially more important once #3 runs extraction unattended.
- **Blocked by**: nothing
- **Touches**: all five `pipelines/extract/*.py`

Shipped as a new shared `pipelines/extract/http.py`, `get_with_retry`:
retries a transient failure (connection error, timeout, or a 5xx response)
up to three times with exponential backoff (2s, 4s), and fails immediately
on a 4xx — retrying a client error just burns the backoff window on a
request that will never succeed. Applied to every raw `session.get(...)`
call in all five extractors, including the two that had none at all
before this pass: `pokeapi.py`'s `_fetch_pokemon_list`/`_fetch_pokemon`
(the ~1,350-sequential-request path this entry specifically named) and
`opgg.py`/`pokebase.py`'s page-scrape fetch, `munchstats.py`'s JSON fetch,
and `bulbagarden.py`'s API calls and binary image download. `pokeapi.py`'s
move/ability/item detail lookups (`_fetch_resource_or_none`) already had a
bespoke, near-identical retry loop from an earlier pass; that loop is now
deleted in favor of calling the shared helper, so there's exactly one
retry implementation instead of two. New `tests/unit/extract/test_http.py`
covers the helper directly (retry-then-succeed, exhausts-then-raises,
fails-fast on 4xx, exponential delay sequence), and each of the five
extractors' existing test suites gained one retry-then-succeed regression
test using the same flaky-response pattern the pre-existing PokéAPI
move/ability/item tests already used. What this entry's value statement
also named but this pass didn't build: proactive rate limiting (throttling
request *cadence*, not just reacting to failures after the fact) — a
distinct, smaller follow-up, not folded in here since retry/backoff was
the change with the real "whole run aborts" failure mode behind it.

### 44. Incremental extraction — DONE

- **Size**: M
- **Value**: MunchStats refetches all 31 tournaments and ~106k rows every
  run even though historical events never change. Wasteful now, actively
  painful under #3's scheduled cadence.
- **Blocked by**: nothing (design alongside #1)
- **Touches**: `pipelines/extract/munchstats.py`, others as applicable

Followed Bulbagarden's sha1-based `skip_existing` pattern as this entry
suggested, adapted to what MunchStats actually offers: there's no
per-tournament content hash, so `extract`'s new `previous_snapshot_path`
parameter (wired up in `pipelines/cli.py`'s `_run_extract`, munchstats-only,
via the already-existing `_latest_snapshot_path` helper) still always
re-fetches each tournament's cheap `metadata.json`, and only skips
re-fetching the heavy `players.json` (the bulk of every run's ~106k rows)
when that tournament's `(name, date, type)` signature is unchanged from
what's already cached in the previous dated snapshot. Reused rows are
re-stamped with the current run's `extracted_at_utc`/`dataset_version`,
matching `bulbagarden.py`'s "every row reflects this extraction run"
convention for its own skipped-download rows. Verified against real data,
not just the new unit tests (`tests/unit/extract/test_munchstats.py`):
re-running `extract munchstats` same-day against a freshly-extracted
snapshot reproduced the identical 106,134 rows in 11 seconds (down from
the original run's 63 live requests fetching ~37MB), confirming every
tournament's roster data was correctly reused rather than silently
dropped or duplicated.

Conditional requests (ETag / If-Modified-Since) for the two scraped
sources (OP.GG/PokéBase) are lower value than this was: both are already a
single request each, so there's no comparable "N heavy fetches down to
near-zero" win available there.

### 45. `pipelines/cli.py` test coverage — DONE

- **Size**: S
- **Value**: 74 unit tests cover the extractors, release, render, dashboard,
  and validation modules. The CLI — the only entry point to all of them —
  has **zero tests**. Argument parsing, subcommand dispatch, and both
  exit-code paths are entirely unexercised.
- **Blocked by**: nothing
- **Touches**: new `tests/unit/test_cli.py`

`tests/unit/test_cli.py` already existed (added alongside backlog #38's
fix) with 16 tests covering the snapshot-path helpers, `extract`
orchestration (including `all`), `dataset_version` defaulting/override, and
all four `validate` exit-code paths. This pass closed the remaining gap: 11
new tests cover `main()`'s argument-parsing/dispatch for `release` (version
plus repeatable `--known-limitation`, defaulting to `[]`, and the
required-`--version` `SystemExit(2)` path), `render-card` (`--team-id` and
`--spec` each dispatch correctly, plus both the missing-both and
both-given `SystemExit(2)` mutual-exclusivity paths), and `build-dashboard`
(default `None`/`True` kwargs, and all four overrides including
`--no-fetch-icons`). 27 tests total in the file now, all passing.

Related, still true: there is no `conftest.py` or shared fixture module
anywhere under `tests/`, so each file re-declares its own helpers.

### 46. Dashboard JS duplication check — DONE, and it immediately caught a real bug

- **Size**: S
- **Value**: `pipelines/dashboard/static/app.js` and the committed
  `docs/dashboard/app.js` are byte-identical copies with nothing enforcing
  it. Editing the wrong one produces a published site that silently
  disagrees with its source.
- **Blocked by**: nothing
- **Touches**: `tests/`, or a `make` target

Shipped as `tests/unit/dashboard/test_static_duplication.py`, comparing
the three static scripts (`app.js`/`matchup.js`/`teams.js`) directly
against their committed `docs/dashboard/` copies (independent of
`build()`'s own copy step, so it also catches a hand-edit of the published
copy). This was not a hypothetical: the first run **failed for real** —
`pipelines/dashboard/static/app.js` had moved on through two more commits
(`00ef4d2`, `313acd2` — sub-tabs, icon-only type badges, a sortable moves
table) past the last time `docs/dashboard/app.js` was actually
republished, so the live GitHub Pages dashboard was missing real, already
-built UI features. Fixed by rerunning `make dashboard` and committing the
regenerated `docs/dashboard/`, which now passes the new test.

### 47. `sprites.py` rebuild ordering constraint — DONE

- **Size**: S
- **Value**: `copy_sprites` deliberately `rmtree`s the output `images/`
  directory (`pipelines/dashboard/sprites.py:58-61`) to stop stale sprites
  accumulating — reasonable in isolation, but it means any asset written to
  `images/` *before* it in a build gets wiped. Today's call order happens to
  be safe; nothing guarantees it stays that way.
- **Blocked by**: nothing
- **Touches**: `pipelines/dashboard/sprites.py`, `build.py`

Prune stale files by name rather than nuking the directory, or make the
ordering constraint explicit and tested.

Took the first option: `copy_sprites` no longer `rmtree`s `images/` at
all. It now only unlinks the top-level `*.png` files it itself owns
(sprites live flat as `images/<pokemon_key>.png`), leaving sibling
subdirectories (`images/icons/`, `images/reference_teams/`, populated by
other `build.py` steps) untouched regardless of call order — the ordering
constraint is now moot rather than merely documented. New regression test
(`test_copy_sprites_does_not_clobber_sibling_asset_subdirectories`)
pre-populates an icons subdirectory before calling `copy_sprites` and
asserts it survives; the existing stale-sprite-cleanup test
(`test_copy_sprites_clears_stale_files_across_rebuilds`) still passes
unchanged.

### 48. Extraction run metadata and structured logging — DONE

- **Size**: M
- **Value**: `reports/validation/extraction_summary.json` reports per-source
  request success rates and row counts — and is a **hand-written static
  file dated 2026-07-19** that no code generates. There is no run history,
  no structured logging, and failures surface only as an unhandled
  traceback.
- **Blocked by**: nothing
- **Touches**: `pipelines/extract/`, `reports/validation/`

Shipped as three pieces. `pipelines/extract/http.py` gained `RequestStats`
and a `track_requests()` context manager: since every extractor's raw HTTP
calls already funnel through the one `get_with_retry` chokepoint (#43),
that's instrumented directly rather than touching each extractor module —
one `get_with_retry` call is one logical "attempted" request regardless of
how many raw retry attempts it took internally. New
`pipelines/extract/summary.py` computes each source's `rows_written`
(counting the written CSV) and `required_field_null_rate` (only over
fields the matching `data/staging/<subdir>.schema.json` marks `required:
true`, matching the old file's own convention of not penalizing
known-optional blanks like OP.GG's `pokemon_id`) and `update()`s
`reports/validation/extraction_summary.json` by merging just the
just-run source's entry into the existing document — a single-source
`extract <source>` run no longer wipes out what's known about every other
source. `pipelines/cli.py`'s new `_run_tracked_extract` wraps every
extraction call in `track_requests()` and calls `summary.update()`
regardless of success; on an extractor exception it now prints a
structured one-line error and returns a controlled exit code instead of
letting a raw traceback propagate, matching `_run_validate`'s existing
catch-log-return convention. PokéAPI's move/ability/item detail fetches
(previously invisible — the old hand-written file only ever had one merged
"PokéAPI" entry) each get their own entry now, correctly distinguishing
"PokéAPI" (1,352 requests) from "PokéAPI (move detail)" (569 requests,
1 genuinely 404'd — an unresolvable move name the extractor already
gracefully skips) etc.

Verified against real, freshly-run extractions, not synthetic fixtures —
and this real run caught a genuine bug in #44's just-shipped
implementation, not a hypothetical: `extract munchstats`'s real
`requests_attempted` came back as 90, not the ~32 the #44 write-up
expected, because live MunchStats indexes both VGC events *and*
same-venue TCG events (a fact invisible to #44's own row-count/md5-based
verification, since a TCG tournament's `players.json` reports players
whose `team` list is always empty, so it silently contributes zero rows
either way — content-only verification couldn't tell full-refetch and
correctly-cached apart). Fixed in the same pass: `metadata.json`'s own
`teams_scraped` count tells `munchstats.py` upfront, with no
`players.json` fetch and no cache needed at all, that a tournament will
contribute zero rows (`teams_scraped: 0`). A real re-run afterward
confirmed `requests_attempted` at the true minimum, 61 (1 index + 60
metadata, zero `players.json` fetches — all 31 real VGC tournaments
correctly cache-hit, all 29 TCG ones correctly skipped via
`teams_scraped`), with the same 106,134 real rows preserved. This is the
concrete case for why this item's own value statement is true: content-
equality checks couldn't see this waste at all; the structured request
counts this item adds surfaced it immediately. `reports/validation/
extraction_summary.json` itself is now a real, current, code-generated
document for four of five sources (Bulbagarden was never in the old
hand-written file either and wasn't re-extracted in this pass; it gets a
real entry the first time someone runs `extract bulbagarden` after this
change, same as any other source).

### 49. Bps-based validation-report metrics read as 0 on a passing check — DONE

- **Size**: S
- **Value**: A real, previously-undetected correctness gap in the
  validation report and every release manifest's `quality_checks` block —
  discovered in this pass while verifying #29/#30 against a real
  `extract all` + `dbt build` + `validate` run, not a hypothetical.
- **Blocked by**: nothing
- **Touches**: `pipelines/validate/report.py` (`_ratio_from_bps`),
  `dbt/tests/singular/*.sql`'s `fail_calc`-based tests

Every coverage/null-rate/row-count-anomaly check reports its ratio via a
`fail_calc` override in basis points (the `assert_opgg_legal_pool_coverage.
sql`-style pattern documented in `report.py`'s own module docstring).
`_ratio_from_bps` assumes dbt's `run_results.json` always carries that
computed value in `failures`, regardless of pass/fail — true when a check
fails, **false when it passes**: dbt-core's `TestRunner.build_test_run_
result` (`dbt/task/test.py`) hardcodes `failures = 0` on the `TestStatus.
Pass` branch and only assigns `result.failures` (the real fail_calc value)
on the `Fail`/`Warn` branches. Confirmed directly against a real run: every
passing coverage/null-rate/row-count-anomaly check in a real `validation_
report.json` shows `metric_value: 0.0` (e.g. `opgg_legal_pool_coverage`
status `pass` but metric `0.0`, not the real ~0.95+), even though the
gating decision itself (`status`) is unaffected and correctly computed
dbt-side — **no release has ever shipped on a false pass**, but every
published manifest's `quality_checks` numbers for these checks have been
wrong since the ratio pattern was introduced.

Fixed as this entry's own "not a one-line fix" note described: a new
`_recompute_bps_ratio` in `report.py` re-executes each bps test's own
`compiled_code` (already present per-result in `run_results.json`,
confirmed by reading dbt-core's `RunResultOutput`/`process_run_result`
directly) against `dbt/data/warehouse.duckdb`, wrapped in the same
`fail_calc` expression the manifest's `node.config.fail_calc` already
declares (`select {fail_calc} as value from ({compiled_code}) as t`) —
deterministic and correct regardless of pass/fail, since the underlying
data hasn't changed since dbt itself ran that query moments earlier. The
"careful handling of relative `external_location` paths" caveat this entry
flagged was real and caught empirically, not just anticipated: a `source()`
reference compiles to a literal, relative CSV glob path (e.g.
`'../data/staging/opgg_champions/*.csv'`), resolved against dbt's own
working directory (`dbt/`) at query time — running the recompute query
from the repo root silently read zero rows instead of erroring, rather
than raising something obviously wrong. Fixed by temporarily `chdir`-ing
into the warehouse's parent `dbt/` directory for the duration of the
recompute query. Falls back to the old `_ratio_from_bps(result)` behavior
whenever recompute isn't possible (no warehouse file, no compiled_code/
fail_calc on the node, or the recompute query itself errors), so report
generation degrades gracefully rather than raising. Verified against a
real `extract all` + `dbt build` + `validate` run: `opgg_legal_pool_
coverage` now reports `0.9842` (previously `0.0`), `pokebase_legal_pool_
coverage` `0.9871`, `bulbagarden_sprite_coverage` `0.883`,
`tournament_team_member_mapping_coverage` `0.9995` — all matching the real
figures already documented elsewhere in this file and `docs/todo.md`
(e.g. "98.4%, 312/317") that this bug had been silently contradicting in
the machine-readable report the whole time. `null_rate_checks` correctly
still show `0.0` — confirmed against the warehouse directly that the real
null rate for these tables genuinely is zero, not a residual bug. New
regression tests in `tests/unit/validate/test_report.py` cover the
recompute-recovers-the-true-value case (using a result with `failures: 0`/
`status: "pass"`, i.e. the exact shape dbt itself produces on this bug),
each fallback path, and the relative-source-path resolution specifically
(a synthetic `dbt/` + `data/staging/` layout under `tmp_path`, not just the
happy-path same-directory fixture, since that's the case that silently
produced a wrong-but-plausible answer rather than an obvious error).
`duckdb` is now also an explicit `pyproject.toml` dependency (`report.py`
imports it directly) rather than an implicit transitive one via
`dbt-duckdb`.

---

## Section 4 — Known documentation debt

Not full backlog entries — these are drift and belong to `.claude/loop.md`'s
tech-debt loop, listed here only so they're written down somewhere.

**All eight items below are now fixed** (2026-08-02 pass):

- ~~`docs/prd.md` still names Chart.js as the resolved dashboard stack~~ —
  checked and this was already stale itself: `docs/prd.md`'s "Open
  questions" section already documents Chart.js's removal in the broadcast
  redesign (`docs/design-system.md`'s "6-wide grid" section). No edit
  needed; this entry no longer describes real drift.
- ~~`docs/todo.md`'s release-readiness header says `0.1.0` is the published
  version~~ — now says `0.2.0` (the current latest), noting `0.1.0` was the
  first release.
- ~~`docs/todo.md`'s null-rate item says "all eight" core tables pass~~ — now
  says "all nine," with a note that `pokemon_asset` joined the core entity
  list in Phase 4.
- ~~`docs/dataset-spec.md`'s trailing "Next implementation task" section
  describes repository scaffolding completed long ago~~ — replaced with a
  "Current status" section pointing at `todo.md`/`backlog.md` for what's
  actually still open.
- ~~`dbt/analyses/README.md` still attributes the degenerate legal-pool query
  to OP.GG's null `regulation_code`~~ — now correctly attributes it to
  Blocker A (only one `snapshot_date` so far), with a note that
  `regulation_code` itself is real now.
- ~~`.claude/loop.md`'s "Why a loop" section claims "Phase 1+ ingestion/
  normalization logic is still unwritten"~~ — now states that Phases 1-4
  and M6 are implemented and published, and that the loop's role has
  shifted from initial build-out to backlog/hardening/upkeep work.
- ~~`docs/design-system.md:415-416` has a sentence mangled mid-edit~~ — fixed
  to read "...needs a battle-log source — neither an in-scope nor a
  deferred source (Limitless VGC, Victory Road) is confirmed to provide
  one." (the debt note's own line numbers had already drifted from the
  original edit; found by searching for the mangled text instead).
- ~~`docs/dataset-spec.md`'s phased roadmap names only three phases~~ — now
  names Phase 4 and M6 too, with a pointer to `CLAUDE.md`'s "Repository
  purpose" for how each layers on the last.

One item on this list was **not** prose drift and got separate attention —
now fixed: `releases/manifests/manifest-0.2.0.json` had
`"known_limitations": []`, while all three limitations recorded in
`manifest-0.1.0.json` — PokéBase's missing removal signal, the all-zero stat
deltas, and the excluded ambiguous form mappings — remain true in 0.2.0 (the
`--known-limitation` flags were simply never passed when 0.2.0 was cut).
Corrected directly in `manifest-0.2.0.json` and `CHANGELOG-0.2.0.md`,
carrying forward the same three limitations and extending the ambiguous
-form-mapping one to also cover Bulbagarden's own excluded 'Mega Meowstic'
sprite title (new in 0.2.0, same underlying ambiguity). Quality-check
`metric_value`s in the same manifest still read `0.0` on every passing
check — a separate, pre-existing artifact of backlog #49's bug (fixed in
`report.py` after 0.2.0 was published) — left as-is since recomputing the
true historical ratios would need the exact 0.2.0 warehouse snapshot, which
no longer exists.

---

## 2026-08-04, dashboard graphics & accuracy pass

A design pass on the dashboard, focused on Pokémon graphics fidelity and
on making the dataset's own accuracy visible. Not drawn from the numbered
backlog above — every unblocked item there was already done — so this is
recorded here rather than as item resolutions.

**Shipped:**

1. **High-resolution art as a second `pokemon_asset` image kind.** Every
   sprite in this repo was a 128×128 Bulbagarden menu icon, displayed at up
   to 128 CSS px (256 device px on HiDPI) with pixelation deliberately
   disabled — so every hero slot was a visibly blurred upscale.
   `pokemon_asset` now carries a `home_render` kind (PokéAPI HOME renders,
   512×512) beside `menu_sprite`, with its own `>=95%` coverage gate;
   measured coverage is **317/317 = 100%**. Its primary key became the
   composite `<pokemon_key>::<image_kind>`.

   The enabling detail: **no new mapping seed was needed.** PokéAPI's
   sprite repository is keyed by each form's own resource id (`10034` for
   `charizard-mega-x`, not species `6`), and `pipelines/extract/pokeapi.py`
   already recorded exactly that as `source_record_id`.

2. **Teams drawn as six Pokémon.** Top Teams rendered a six-Pokémon team as
   its first slot's sprite alone — a correctness problem, not a cosmetic
   one, since two teams sharing a lead were visually identical.
   `teamCompositionHtml()` plus `renderGrid6xn`'s new `iconHtmlFn` option
   now render the whole roster, in both Top Teams and Converged lists.

3. **Type color accents**, reusing `pipelines/render/template.py`'s existing
   18-entry `TYPE_COLORS` map — emitted into `:root` at build time rather
   than copied, so the dashboard and the team-card renderer stay one
   palette. Applied automatically to any Pokémon-keyed `.grid-6xn` tile.

4. **A Data & Sources tab.** The dashboard surfaced no provenance at all,
   in a repo whose first stated convention is that provenance is mandatory.
   It now reports per-source extraction health, all 48 release gates, image
   coverage, cross-source roster agreement (wiring
   `roster_source_agreement`, which had been built and tested but unread),
   and the standing caveats that apply to figures elsewhere on the page.

5. **A Converged lists view** over `team_list`/`team_list_member` — the
   Limitless layer, which had zero mart and zero dashboard reach. Ranked by
   how many distinct players independently fielded the same six Pokémon
   (top composition: 9 players), with the day-2-cut-only caveat displayed.

6. **The payload split.** `index.html` inlined the entire payload, making it
   an **8.18 MB** file whose first paint blocked on parsing all of it,
   beside an identical 8.14 MB `data.json`. The marts now live only in
   `data.json`, fetched on first use; `index.html` is **~140 KB**. Whole
   site: 22 MB → 14 MB, *including* 4.9 MB of newly added hero art.

7. **Country flags** from ISO 3166-1 alpha-2 codes as Unicode
   regional-indicator pairs — no asset, no network. Deliberately strict: a
   malformed code renders as text rather than a guessed flag.

8. **Hygiene:** `images/icons/items/` is now pruned by name like `images/`
   already was (151 committed files → 78 referenced); doc drift fixed
   (`build.py`'s stale "Chart.js via CDN", "seven tabs" → nine, "~250
   sprites" → 312, the signature floor comment's 3 → 2, and
   `docs/dashboard.md`'s incomplete committed-files list).

**Not a future-work candidate:**

- **Tera-type analytics.** Champions does not currently have the Tera
  mechanic. The apparent 82.8% coverage came from standard VGC rows outside
  this dataset's scope; Champions-scoped coverage is 0%. The experimental
  mart was removed under backlog #10 and should be reconsidered only if the
  Champions format adds Tera.
