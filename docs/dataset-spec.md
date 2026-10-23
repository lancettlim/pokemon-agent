# V1 Dataset Spec

This document is the authoritative v1 dataset artifact plan, distinct from
the repository-level overview in `README.md`.

## Immediate objective

- **Decision**: move from docs-only research to a documented v1 data artifact
  spec that can be executed in phases.
- **Near-term output**: a reproducible, versioned dataset package with
  canonical stats, Champions deltas, legality snapshots, and tournament usage
  records.

## V1 scope (selected high-confidence sources)

The v1 scope covers four sources from `data-sources.md`:

1. **PokéAPI** (canonical base data)
2. **OP.GG Pokémon Champions** (format-specific legal pool and rebalanced data)
3. **MunchStats** (structured tournament roster/usage data)
4. **PokéBase app** (per-regulation legal-pool membership)

PokéBase was originally deferred ("defer until regulation-specific
restrictions are needed beyond the OP.GG legal pool snapshot") but was
pulled into v1 once that need became concrete: OP.GG's Champions Pokédex
page publishes only a single regulation-agnostic legal pool, so
`legality_snapshot.regulation_code` — a locked required field — had no
in-scope source and was permanently null. PokéBase's page embeds real,
per-Pokémon regulation-set membership and turned out to be scriptable the
same way OP.GG is (see `pipelines/extract/pokebase.py`'s docstring), so it
now supplies `legality_snapshot` directly; OP.GG remains the source for
`pokemon_stat_champions`'s stats and overall legal-pool flag.

These four sources provide strong coverage of canonical values, format
modifications, regulation-aware legality, and real competitive usage while
keeping ingestion complexity manageable for v1.

## Formerly deferred sources — resolved 2026-08-03

Both sources previously listed here have been resolved, and neither
resolution matched its deferral reason (see `docs/backlog.md` #25/#26):

- **Limitless VGC** — **now in scope.** Deferred "until historical event
  coverage expansion," which turned out to be the wrong reason to want it:
  it does not extend Champions history at all (only three Champions-format
  events exist anywhere, and MunchStats already had all three), and per
  event it is narrower, publishing the day-2 cut only. It was brought in
  for a different, real value: canonical shared team-list identity (one
  team id reused across every player and event that fielded that
  composition, which MunchStats cannot express) and an independent second
  reading of the same rosters to cross-validate against. Feeds `team_list`
  and `team_list_member`.
- **Victory Road** — **will not be ingested; the data does not exist.**
  Deferred "until detailed moveset/EV enrichment is prioritized." When it
  was prioritized, the EV half proved unavailable from any source:
  official tournament team sheets — RK9's own, which every source in this
  catalog ultimately derives from — publish ability, held item, nature and
  moves and nothing else. Verified directly against RK9's and Limitless'
  team-list pages: no EV or IV data on either. The moveset half was
  already covered by MunchStats and Limitless at 100% for Champions
  events. Treat tournament EV/IV spreads as structurally unavailable
  rather than pending. (Victory Road is also unreachable from this
  project's egress — see `docs/data-sources.md` — but that is incidental to
  the conclusion.) The Showdown ladder's Stat Point spreads, added
  2026-10-23 (see "Added sources"), don't change this: they are what ladder
  players ran, a different population, and never enter a tournament
  entity.

## Added sources (post-v1)

- **RK9.gg** — added 2026-08-03 to supply match-level head-to-head results
  (`tournament_match`). RK9 is the tournament software the events run on and
  the upstream MunchStats already scrapes for rosters; it publishes
  round-by-round pairings over plain HTTP, and reuses the same event ids
  MunchStats does, so no event-level mapping is needed. See
  `docs/data-sources.md` for the extraction technique and
  `docs/backlog.md` #27 for why this was previously believed impossible.
- **Limitless online tournaments** (`play.limitlesstcg.com/api`) — added
  2026-10-21 (`docs/upgrade-plan-2027q2.md`, S1, decision D1). Hundreds of
  grassroots Champions events run on Limitless' online platform every
  regulation, each with full team sheets, W-L-T records and round-by-round
  pairings: about three times the official sample, and data for a new
  regulation within days of its start. They join `tournament_event`,
  `tournament_team`, `tournament_team_member` and `tournament_match` as
  **their own population**, `event_tier = 'Online'`, with every id prefixed
  `LP-` so it can never collide with an RK9 or MunchStats id. Players are
  Limitless handles, not legal names: online teams never join official
  identities, and no player-level output covers them. Official figures stay
  exactly what they were: every unscoped roster-derived mart reads
  `int_champions_roster_official`, and population-aware marts give online
  events their own `regulation_scope` values (`m-c:online`, `all:online`)
  plus `:combined` scopes for both together (see "Key rules"). Events under
  16 players and Monotype events are skipped. See `docs/data-sources.md`
  §9 for the API, and `pipelines/extract/limitless_play.py`.
- **Smogon usage statistics** (`smogon.com/stats`) — added 2026-10-23
  (`docs/upgrade-plan-2027q2.md`, S2, decisions D2 and D3). Smogon's
  monthly statistics for Pokémon Showdown's Champions ladder, per
  registered regulation (the file is named by the registry's
  `munchstats_format`), Bo1 and Bo3, at rating cutoffs 1760 and 0. Three
  staging tables come from the same files: usage per Pokémon
  (`smogon_ladder`), checks and counters (`smogon_ladder_counters`: per
  pair, how often the Pokémon was KO'd or switched out, from the battle
  logs) and Stat Point spreads (`smogon_ladder_spreads`). The ladder is
  **its own population**, anyone on Showdown weighted toward the
  strongest players, and **feeds no release entity**: it lands in three
  marts only (`ladder_pokemon_usage`, `ladder_checks_counters`,
  `ladder_stat_point_spreads`), shown beside tournament figures and never
  added to them. Its spreads are the one place Stat Points appear (D3):
  tournament team sheets publish none, so they never enter a tournament
  entity, a team sheet or the Builder's sets. See `docs/data-sources.md`
  §10 and `pipelines/extract/smogon_ladder.py`.

## Image asset source (Phase 4 addition)

A fifth source, **Bulbagarden Archives**, was added after v1's initial four-
source scope to supply Pokémon sprite images: PokéAPI's own sprite bundle
(referenced in `data-sources.md`'s PokéAPI entry) is stale for the newest
Pokémon relevant to the Champions format, and Bulbagarden Archives'
"Champions menu sprites" wiki category has the missing art. This is purely
additive — it feeds the new `pokemon_asset` entity below and doesn't change
any of the four core sources' scope, mapping rules, or refresh cadence.
Type/item icons used only by card rendering (not a dataset entity) come
from PokéAPI's community sprites GitHub repo instead — see
`pipelines/render/assets.py`.

## Target v1 schema and data contract

### Entity dictionary

- `pokemon`
  - **Purpose**: canonical identity table for Pokémon and form references used by
    all downstream entities
  - **Primary key**: `pokemon_key`
  - **Join keys**: `pokemon_id`, `form_name`
  - **Required fields**: `pokemon_key`, `pokemon_id`, `pokemon_name`,
    `form_name`, `type_1`, `source_name`, `source_url`, `source_record_id`,
    `extracted_at_utc`, `dataset_version`
  - **Optional fields**: `type_2` (secondary Pokémon type; nullable for
    single-type Pokémon). Added in the dashboard competitive-UX pass: read
    off the same PokéAPI `/pokemon/{form}` payload `pokemon_stat_canonical`
    already fetches (`payload["types"]`), so no new HTTP call was needed —
    see `pipelines/extract/pokeapi.py`'s docstring. Powers the dashboard's
    Pokémon Profile type badge and Matchup tab (type effectiveness, damage
    calculator).
- `pokemon_stat_canonical`
  - **Purpose**: canonical PokéAPI stat snapshot
  - **Primary key**: `pokemon_stat_canonical_key`
  - **Join keys**: `pokemon_key`, `pokemon_id`
  - **Required fields**: `pokemon_stat_canonical_key`, `pokemon_key`,
    `pokemon_id`, `hp`, `attack`, `defense`, `sp_attack`, `sp_defense`,
    `speed`, `stat_total`, `source_name`, `source_url`, `source_record_id`,
    `extracted_at_utc`, `dataset_version`
- `pokemon_stat_champions`
  - **Purpose**: Champions-format stat snapshot from OP.GG
  - **Primary key**: `pokemon_stat_champions_key`
  - **Join keys**: `pokemon_key`, `pokemon_id`
  - **Required fields**: `pokemon_stat_champions_key`, `pokemon_key`,
    `pokemon_id`, `hp`, `attack`, `defense`, `sp_attack`, `sp_defense`,
    `speed`, `stat_total`, `is_legal`, `source_name`, `source_url`,
    `source_record_id`, `extracted_at_utc`, `dataset_version`
- `pokemon_stat_delta`
  - **Purpose**: derived canonical-vs-Champions stat change output
  - **Primary key**: `pokemon_stat_delta_key`
  - **Join keys**: `pokemon_key`, `pokemon_id`
  - **Required fields**: `pokemon_stat_delta_key`, `pokemon_key`, `pokemon_id`,
    `hp_delta`, `attack_delta`, `defense_delta`, `sp_attack_delta`,
    `sp_defense_delta`, `speed_delta`, `stat_total_delta`,
    `canonical_dataset_version`, `champions_dataset_version`, `source_name`,
    `source_url`, `extracted_at_utc`, `dataset_version`
- `legality_snapshot`
  - **Purpose**: time-sliced, regulation-aware legal status for the
    Champions pool, sourced from PokéBase (see "PokéBase" below)
  - **Primary key**: `legality_snapshot_key`
  - **Join keys**: `pokemon_key`, `pokemon_id`, `regulation_code`, `snapshot_date`
  - **Required fields**: `legality_snapshot_key`, `pokemon_key`, `pokemon_id`,
    `regulation_code`, `is_legal`, `snapshot_date`, `source_name`,
    `source_url`, `source_record_id`, `extracted_at_utc`, `dataset_version`
- `tournament_event`
  - **Purpose**: normalized tournament metadata from MunchStats
  - **Primary key**: `event_id`
  - **Join keys**: `event_id`
  - **Required fields**: `event_id`, `event_name`, `event_date`, `source_name`,
    `source_url`, `source_record_id`, `extracted_at_utc`, `dataset_version`
  - **Optional fields**: `event_tier` (tournament tier: Worlds/
    International/Special/Regional from MunchStats — nullable since
    MunchStats doesn't report it for every event — or `Online` for a
    Limitless online tournament, which is always set), `event_format`
    (MunchStats format string, or Limitless' online label such as `M-C`),
    `regulation_code` (Champions regulation set, e.g. `m-c`, resolved
    from `event_format` via `dbt/seeds/champions_regulations.csv`'s
    `munchstats_format` or `limitless_play_format`; null only for
    standard-VGC events. Every Champions-format event must resolve,
    enforced by `assert_champions_formats_registered`. An online event
    dated after its label's regulation ended, with fewer than 95% of its
    slots legal under the label, takes the regulation in force on its date
    instead, because organisers keep old labels after a rollover;
    `assert_online_regulation_legality` checks the result)
  - **Populations**: `event_tier = 'Online'` marks the online population
    (`LP-<tournament id>` event ids). Consumers must not blend it into
    official figures unless they say so; the marts' `regulation_scope`
    values carry the split (see "Key rules")
- `tournament_team`
  - **Purpose**: team-level tournament metadata
  - **Primary key**: `team_id`
  - **Join keys**: `event_id`, `player_id`, `team_id`
  - **Required fields**: `team_id`, `event_id`, `player_id`, `player_name`,
    `placement`, `source_name`, `source_url`, `source_record_id`,
    `extracted_at_utc`, `dataset_version`
  - **Optional fields**: `player_country` (two-letter code, e.g. "IT" —
    nullable since MunchStats doesn't report it for every player),
    `record_wins`, `record_losses` (win-rate proxy — nullable since
    MunchStats doesn't report a record for every player)
  - **Online teams**: `LP-<tournament>-<handle>`, one per player per
    online tournament whose sheet was published; `player_id` is
    `LP-<handle>`, a Limitless handle that never joins an official
    identity. Limitless leaves a dropped player's placing blank (about a
    quarter of online teams), so `placement` places a drop after every
    finisher of its tournament, by record, as RK9's standings rank one
    (`int_limitless_play_mapped.placement_is_derived` marks them)
- `tournament_team_member`
  - **Purpose**: one row per Pokémon on a normalized tournament team
  - **Primary key**: `team_member_id`
  - **Join keys**: `team_id`, `event_id`, `pokemon_key`, `pokemon_id`
  - **Required fields**: `team_member_id`, `team_id`, `event_id`, `pokemon_key`,
    `pokemon_id`, `slot_number`, `source_name`, `source_url`,
    `source_record_id`, `extracted_at_utc`, `dataset_version`
  - **Optional fields**: `item_name`, `ability`, `tera_type`, `nature`,
    `moves` (pipe-delimited) — nullable since MunchStats doesn't report a
    full build for every roster slot
- `tournament_match`
  - **Purpose**: match-level head-to-head results — who faced whom, in
    which round, and who won — sourced from RK9 pairings. Added
    2026-08-03 (`docs/backlog.md` #27)
  - **Primary key**: `match_id`
  - **Join keys**: `event_id`, `team_id_1`, `team_id_2`, `winner_team_id`
  - **Required fields**: `match_id`, `event_id`, `division`,
    `round_number`, `outcome`, `is_complete`, `source_name`, `source_url`,
    `source_record_id`, `extracted_at_utc`, `dataset_version`
  - **Optional fields**: `table_number` (a bye is assigned none);
    `player_id_1`/`team_id_1`/`player_id_2`/`team_id_2` (null for a bye's
    absent opponent, for the Junior/Senior divisions, which MunchStats
    does not scrape rosters for, and for an online player whose sheet the
    organiser didn't publish); `winner_team_id` (null for a tie or bye)
  - **Divisions**: `Masters`/`Senior`/`Junior` from RK9; `Online` for a
    Limitless online pairing, whose `outcome` can also be `no_result`
    (the platform recorded none; `is_complete` false)
  - **Grain caveat, which every consumer must state**: an outcome is *team
    vs team*, not Pokémon vs Pokémon. No source publishes a per-battle log
    naming which four of a team's six Pokémon were brought or which
    defeated which
- `team_list`
  - **Purpose**: canonical team-composition identity, reused across the
    players and events that fielded it, sourced from Limitless VGC. Added
    2026-08-03 (`docs/backlog.md` #26)
  - **Primary key**: `team_list_id`
  - **Join keys**: `team_list_id`, `first_seen_event_id`
  - **Required fields**: `team_list_id`, `tournament_count`,
    `player_count`, `best_placement`, `first_seen_date`,
    `first_seen_tournament_id`, `regulation_set`, `source_name`,
    `source_url`, `source_record_id`, `extracted_at_utc`,
    `dataset_version`
  - **Optional fields**: `first_seen_event_id` (blank if the Limitless
    tournament page carries no RK9 link)
  - **Coverage caveat**: Limitless publishes team lists for the day-2 cut
    only (156 of 1,096 players at NAIC 2026), so this is a top-cut view
- `team_list_member`
  - **Purpose**: one row per Pokémon on a canonical team list, with the
    build the published team sheet carries
  - **Primary key**: `team_list_member_id`
  - **Join keys**: `team_list_id`, `pokemon_key`, `pokemon_id`
  - **Required fields**: `team_list_member_id`, `team_list_id`,
    `pokemon_key`, `pokemon_id`, `slot_number`, `source_name`,
    `source_url`, `source_record_id`, `extracted_at_utc`,
    `dataset_version`
  - **Optional fields**: `item_name` (empty when a Pokémon deliberately
    holds nothing), `ability`, `nature`, `moves` (pipe-delimited)
  - **No EV/IV fields, permanently**: official team sheets do not publish
    them — see "Formerly deferred sources" above
- `pokemon_asset`
  - **Purpose**: image manifest for Pokémon/form references, in two kinds
    (see `image_kind` below)
  - **Primary key**: `pokemon_asset_key`, the composite
    `<pokemon_key>::<image_kind>`. `pokemon_key` alone is deliberately
    **not** unique here — each Pokémon carries one row per image kind. (v1
    scoped this entity to one menu sprite per form, which made the two
    equivalent; the hero-art addition below is what separated them.)
  - **Join keys**: `pokemon_key`, `pokemon_id`
  - **`image_kind`** — one of:
    - `menu_sprite`: 128x128, Bulbagarden Archives. The dense-UI asset,
      correct at table-cell size, cached under `data/assets/bulbagarden/`.
    - `home_render`: 512x512, PokéAPI's sprite repository
      (`sprites/pokemon/other/home/<resource_id>.png`). The hero asset,
      cached under `data/assets/pokeapi_artwork/`. Added because upscaling
      a 128px menu sprite into the dashboard's 96px/128px hero slots
      visibly blurs, worse again on HiDPI displays.
  - **Required fields**: `pokemon_asset_key`, `pokemon_key`, `image_kind`,
    `local_cache_path`, `sha1`, `width`, `height`, `source_name`,
    `source_url`, `source_record_id`, `extracted_at_utc`, `dataset_version`
  - **Optional fields**: `pokemon_id` (nullable only if a future source
    can't supply it directly; both kinds always resolve it — Bulbagarden
    via the mapping seed, PokéAPI artwork by joining its own form slug
    straight to `pokemon.form_name`)
  - **Release layout**: images ship under
    `releases/data/<version>/images/<image_kind>/`, one subdirectory per
    kind, because the two kinds use unrelated file-naming conventions
    (Bulbagarden's `0006-Mega X.png` against PokéAPI's
    `charizard-mega-x.png`) and a flat directory would mix them with no way
    to tell which asset a consumer is looking at.

Three more entities were added in the dashboard competitive-UX pass, all
sourced from PokéAPI, scoped to move/ability/item names actually reported
in `tournament_team_member` (`data/staging/munchstats.csv`'s
`moves`/`ability`/`item_name` fields) rather than PokéAPI's full catalog.
**These are dashboard-support reference/lookup tables, not release-gated
core v1 entities** — they don't join to `pokemon_key` and aren't part of
the versioned release package (`releases/data/<version>/`); they still
carry full provenance per this repo's "provenance is mandatory"
convention, just outside the v1 scope-at-a-glance list above. A future
pass may decide to promote them into the release package once their
value there (vs. as dashboard-only support data) is clearer.

- `move_detail`
  - **Purpose**: move reference detail (type/power/accuracy/category/
    priority/pp/short_effect) for the dashboard's Pokémon Profile move
    descriptions and Matchup-tab damage calculator
  - **Primary key**: `move_name`
  - **Required fields**: `move_name`, `move_type`, `category`, `priority`,
    `pp`, `source_name`, `source_url`, `source_record_id`,
    `extracted_at_utc`, `dataset_version`
  - **Optional fields**: `power`, `accuracy` (null for status/variable-
    power/always-hit moves), `short_effect`
- `ability_detail`
  - **Purpose**: ability reference detail (short_effect) for the
    dashboard's Pokémon Profile ability descriptions
  - **Primary key**: `ability_name`
  - **Required fields**: `ability_name`, `source_name`, `source_url`,
    `source_record_id`, `extracted_at_utc`, `dataset_version`
  - **Optional fields**: `short_effect`
- `item_detail`
  - **Purpose**: held-item reference detail (short_effect) for the
    dashboard's Pokémon Profile item descriptions
  - **Primary key**: `item_name`
  - **Required fields**: `item_name`, `source_name`, `source_url`,
    `source_record_id`, `extracted_at_utc`, `dataset_version`
  - **Optional fields**: `short_effect`

### Locked required fields

- **Identity**: `pokemon_id`, `pokemon_name`, `form_name`
- **Stat context**: `hp`, `attack`, `defense`, `sp_attack`, `sp_defense`,
  `speed`, `stat_total`
- **Legality context**: `regulation_code`, `is_legal`, `snapshot_date`
- **Tournament context**: `event_id`, `event_name`, `event_date`, `player_id`,
  `team_id`, `placement`
- **Lineage/provenance**: `source_name`, `source_url`, `extracted_at_utc`,
  `source_record_id`, `dataset_version`

### Key rules

- `pokemon_key` is the normalized cross-source identifier for one
  Pokémon/form record.
- `pokemon_id` stores the canonical Pokédex identifier used as the preferred
  mapping key across sources.
- Derived tables must retain enough identifiers to trace both upstream records
  and published release versions.
- Rows that cannot be mapped to a stable `pokemon_key` may remain in staging but
  must not ship in release outputs without an explicit confidence override.
- **Populations** (`docs/upgrade-plan-2027q2.md`, S1): official events
  (MunchStats/RK9) and Limitless online events are never blended by
  default. `int_champions_roster` carries a `population` column
  (`official`/`online`); unscoped roster-derived marts read
  `int_champions_roster_official`; regulation-scoped marts read
  `int_champions_roster_scoped`, whose `regulation_scope` is the
  regulation code for official rows (`m-c`, `all`, unchanged), suffixed
  `:online` for online rows (`m-c:online`, `all:online`), and `:combined`
  for both together, which exists only for a regulation with online rows.
  Player-level marts are official-only (`scope_population = 'official'`).

### Refresh policy

- **PokéAPI**: weekly scheduled refresh (identity/stat rows and the
  move/ability/item detail tables; high-resolution artwork is on-demand —
  see "PokéAPI high-resolution artwork" below)
- **OP.GG Pokémon Champions**: daily change check, publish on change detection
- **MunchStats**: daily check with publish after new tournament/event detection
- **Event weekends**: an event dated from the day before to three days
  ago is live: MunchStats and RK9 fetch it again on every run instead of
  reusing their cached copy, and `.github/workflows/event-weekend.yml`
  rebuilds and publishes the dashboard hourly while one is
  (`docs/upgrade-plan-2027q2.md`, E4)
- **Limitless online tournaments**: daily. The lookback is the regulation
  in force; a tournament more than two days old that the previous
  snapshot holds is reused rather than re-fetched (the API allows 50
  requests per 5 minutes without a key, so a first backfill of a
  regulation takes about an hour and later runs a few minutes)
- **Smogon usage statistics**: published monthly, extracted daily. Each
  regulation's month is the newest one it was in force for at least half
  of (a new regulation's first, partial month until a full one exists); a
  month the previous snapshot holds is reused, so a daily run costs a few
  listing requests and a new month lands the day it is published
- **Versioning rule**: publish `dataset_version` on every successful refresh
  cycle with changelog notes for schema or major row-count shifts
- **Snapshot history**: `python -m pipelines.cli extract <source>` writes
  each run to a date-partitioned CSV under `data/staging/<source>/<date>.csv`
  rather than overwriting a single file, pruned to a bounded number of
  retained snapshots per source (see `pipelines/cli.py`'s
  `_RETENTION_COUNTS`). Each `dbt/models/staging/stg_*.sql` model unions
  every retained snapshot with a `snapshot_date` dimension, so extraction
  history is queryable directly from staging; a parallel
  `dbt/models/intermediate/int_*_latest.sql` selector per source filters
  back down to the current point-in-time snapshot that `models/normalized/`
  is built from, so the normalized entities' primary-key and referential-
  integrity contracts are unaffected by staging now holding multiple
  snapshots.

### Provenance rules

- Every record must include source metadata and extraction timestamp.
- Derived tables (for example deltas) must preserve upstream source references.
- Records without traceable source identity are excluded from release outputs.

## Release package

Each v1 release must publish a versioned package with:

- `pokemon.csv`
- `pokemon_stat_canonical.csv`
- `pokemon_stat_champions.csv`
- `pokemon_stat_delta.csv`
- `legality_snapshot.csv`
- `tournament_event.csv`
- `tournament_team.csv`
- `tournament_team_member.csv`
- `pokemon_asset.csv`
- `images/` — the sprite files referenced by `pokemon_asset.csv`'s
  `local_cache_path` values, copied from the local asset cache at release
  time so the release package is self-contained (see
  `pipelines/release/build.py`). These are Nintendo/Game Freak-owned
  artwork mirrored via a fan wiki; `releases/data/README.md` carries a
  redistribution-posture disclaimer alongside this directory.
- `manifest.json`
- `CHANGELOG.md`

### Distribution (from 0.4.0)

From `dataset_version 0.4.0` the package is distributed **only as a GitHub
Release asset**, not as files in the repository (docs/upgrade-plan-2027q1.md,
D1). `.github/workflows/cut-release.yml` (run by hand with the new version)
extracts every source stamped with that version, runs the release gates,
builds the package, zips it as `pokemon-champions-dataset-<version>.zip`
with a `.sha256` checksum, publishes both as the `data-v<version>` GitHub
Release, and opens a pull request committing only:

- `releases/manifests/manifest-<version>.json`, whose `package` block
  names the asset (`file_name`, `url`, `release_tag`, `size_bytes`,
  `sha256`), so the committed metadata identifies the exact published
  bytes; and
- `releases/changelogs/CHANGELOG-<version>.md`.

`releases/data/<version>/` and `releases/packages/` are gitignored for new
versions. Releases `0.1.0`–`0.3.0` keep their committed
`releases/data/<version>/` directories, and `publish-release.yml` can still
re-publish them. The zip's own `manifest.json` is written before the zip
exists, so it carries every field above except `package`.

**Compatibility note:** releases before `0.4.0` exclude every Reg M-B and
M-C event (the Champions format was pinned to Reg M-A until 2026-10); their
usage-derived figures describe M-A only. `0.4.0`'s changelog says so.

### Manifest contents

`manifest.json` must include:

- `dataset_version`
- `published_at_utc`
- `sources` with per-source name, URL, extraction timestamp, and record counts
- `tables` with row counts, primary key definitions, and file names
- `quality_checks` with pass/fail status and metric values
- `known_limitations`
- `package` (from `0.4.0`): the Release asset's file name, URL, tag, size
  and sha256

### Dataset version semantics

- Use semantic-style dataset versions: `MAJOR.MINOR.PATCH`
- Increment **MAJOR** for breaking schema changes
- Increment **MINOR** for new tables, fields, or materially expanded coverage
- Increment **PATCH** for refresh-only releases with no schema changes

### Changelog expectations

Every release entry must summarize:

- source refresh dates
- schema changes
- major row-count changes
- newly known limitations or resolved limitations

## Source-specific extraction contracts

### PokéAPI

- **Records to capture**
  - Pokémon/form identity rows, including `type_1`/`type_2`
  - Base stat rows for all Pokémon in the mapped Champions pool
  - Move/ability/item reference detail (`move_detail`/`ability_detail`/
    `item_detail` — dashboard competitive-UX pass), scoped to names
    actually reported in `tournament_team_member`
- **Refresh cadence**
  - Weekly scheduled refresh
- **Mapping rules**
  - Treat PokéAPI numeric IDs as the canonical `pokemon_id`
  - Normalize form naming into the shared `form_name` convention
  - Move/ability/item names are matched to PokéAPI resource slugs via a
    lowercase/hyphenate transform (`pipelines/extract/pokeapi.py`'s
    `_slugify`); a name that doesn't slug the same way is skipped rather
    than mismapped
- **Known risks**
  - Form-name mismatches between canonical and format-specific sources
  - Multi-form species that need explicit mapping rather than name-only joins
  - A move/ability/item name PokéAPI doesn't recognize under the
    `_slugify` transform simply won't resolve — no fuzzy matching

### OP.GG Pokémon Champions

- **Records to capture**
  - Legal pool membership
  - Rebalanced stat values for each listed Pokémon/form
- **Refresh cadence**
  - Daily change detection; publish only when the legal pool or stats change
- **Mapping rules**
  - Join to canonical records by numeric ID where available
  - Fall back to controlled name/form mappings when direct ID mapping is absent
- **Known risks**
  - HTML structure volatility
  - Custom form labels that may not match canonical naming

### MunchStats

- **Records to capture**
  - Tournament metadata
  - Team metadata
  - Team-member Pokémon rows
- **Refresh cadence**
  - Daily check with publish after new event detection
- **Mapping rules**
  - Preserve upstream event and roster identifiers as `source_record_id`
  - Map roster Pokémon names to canonical `pokemon_id` and `pokemon_key`
- **Known risks**
  - Incomplete tournament coverage
  - Roster naming inconsistencies that reduce automated match confidence

### PokéBase

- **Records to capture**
  - Per-regulation legal-pool membership for the Champions format
    (`legality_snapshot`'s sole source — see "V1 scope" above for why OP.GG
    doesn't cover this)
- **Refresh cadence**
  - Daily change detection; publish only on regulation or legal-pool change
- **Mapping rules**
  - Use PokéBase's own `nationalNumber` directly as `pokemon_id` (correct
    for Mega/regional/alternate forms too, unlike OP.GG's fabricated
    per-form ids)
  - Join to canonical records by form slug, which already matches PokéAPI's
    own form-naming convention for the large majority of entries; fall back
    to controlled name/form mappings (PokéAPI's designated default variety
    per species) for the remainder
- **Known risks**
  - HTML structure volatility
  - Only positive (legal) regulation membership is published — there's no
    explicit "removed from this regulation" signal, so a Pokémon's absence
    from a snapshot isn't distinguishable from "not yet observed" versus
    "confirmed illegal"

### Bulbagarden Archives

- **Records to capture**
  - Champions-menu sprite image manifest (Category:Champions_menu_sprites):
    one row per image, with its local cache path and resolved CDN metadata
- **Refresh cadence**
  - Infrequent / on-demand — sprite art doesn't change once posted, unlike
    OP.GG's daily change detection
- **Mapping rules**
  - Parse each title's Pokédex number and form descriptor, then resolve to
    `pokemon_key` via the `bulbagarden_title_to_pokeapi_form` mapping seed
    (see `dbt/seeds/schema.yml` for the exact reconciliation rules)
  - Several species have many visually distinct Bulbagarden titles but only
    one PokéAPI form/variety (Vivillon's wing patterns, Florges's colors,
    Furfrou's trims, Alcremie's cream flavors, Pyroar's cosmetic female
    sprite); these are deliberately deduped onto a single `pokemon_asset`
    row per `pokemon_key`, matching how `pokemon_stat_champions` already
    dedupes OP.GG's analogous cosmetic duplicates
- **Known risks**
  - Category membership or file-naming convention could change without
    notice
  - Sustained/scheduled automated access rate-limiting or ToS posture not
    independently verified beyond a one-off extract

### PokéAPI localised names

A third PokéAPI path (`docs/upgrade-plan-2027q2.md`, Q4), from PokéAPI's
own source CSVs on GitHub rather than its JSON API: five files
(`languages`, `pokemon`, `pokemon_forms`, `pokemon_species_names`,
`pokemon_form_names`) instead of about 600 calls.

- **Records to capture**
  - Each form's name in Japanese, Spanish, French and German
    (`data/staging/pokeapi_names.schema.json`), with the rule that
    produced it
- **Scope**
  - Every form the same run's pokeapi snapshot holds; weekly, with it
- **Composition**
  - PokéAPI has every species' localised name but full form names only
    unevenly (French and Japanese Megas, a few Spanish and German ones), so
    `pipelines/extract/pokeapi.py`'s `localised_name` composes the rest
    from the species name and each language's convention ("Méga-Dracaufeu
    Y", "Hisui-Arkani", "ウインディ（ヒスイのすがた）"). About ten Champions-pool
    rows fall back to an English form label in Spanish or German
- **Feeds** `pokemon_localised_names`, a mart, not a release entity; the
  dashboard's name-language switch. Portuguese uses the English names, as
  the Brazilian games do

### PokéAPI high-resolution artwork

A second PokéAPI extraction path, distinct from the identity/stat one above
because it reads the project's sprite *repository* on GitHub rather than its
JSON API.

- **Records to capture**
  - One 512x512 Pokémon HOME render per form, with its local cache path,
    locally-computed sha1 and PNG-header dimensions
- **Scope**
  - Restricted to the forms that already have a Bulbagarden Champions menu
    sprite, read from the `bulbagarden_title_to_pokeapi_form` seed — that
    category *is* the Champions pool, so the two image kinds cover exactly
    the same Pokémon rather than drifting apart. Roughly 317 forms against
    PokéAPI's full ~1,350.
- **Refresh cadence**
  - Infrequent / on-demand, same as Bulbagarden: a published render never
    changes
- **Mapping rules**
  - No mapping seed is needed or used. The sprite repository is keyed by
    each form's *own* PokéAPI resource id (`10034` for `charizard-mega-x`,
    not the species Dex number `6`), which the identity extractor already
    records as `source_record_id`; the artwork manifest's `form_name` is
    PokéAPI's own form slug, which joins straight to `pokemon.form_name`.
- **Known risks**
  - Not every form has a published HOME render; a missing one is skipped
    rather than fabricated, so the gap surfaces as the `home_render`
    coverage gate rather than as a failed run
  - The repository publishes no checksum, so unlike Bulbagarden there is no
    upstream sha1 to re-verify a cached file against
  - Artwork is Nintendo/Game Freak-owned and is redistributed under the same
    known-limitation disclaimer as the Bulbagarden sprites, not a cleared
    right

### Confidence requirements

- OP.GG legal-pool mapping coverage must reach at least 95% before release.
- Tournament team-member mapping coverage must reach at least 90% before
  release.
- PokéBase legal-pool mapping coverage must reach at least 95% before
  release.
- Bulbagarden sprite mapping coverage must reach at least 85% before
  release (lower than OP.GG/PokéBase's 95% because `pokemon_asset`'s
  primary key is `pokemon_key`, not `bulbagarden_title` — the cosmetic-
  duplicate dedup above legitimately lowers this row-count ratio without
  indicating a real mapping gap; real measured coverage at seed-build time
  was 317/359 titles, 88.3%).
- Any unmapped or low-confidence rows must be documented in the manifest and
  excluded from release tables unless explicitly approved.
- Smogon ladder names should resolve to a `pokemon_key` for at least 99%
  of usage rows (`assert_smogon_ladder_name_coverage`, 333 of 333 names
  when the source was added). It is a mart check, not a release gate:
  ladder data feeds no release entity, so an unmapped name drops that
  Pokémon from the ladder views rather than stopping a release.

## Phased execution roadmap

v1 delivery was sequenced into three phases — **ingestion**, **normalization**,
and **analytics/dashboard outputs**. Two post-v1 phases followed the same
pattern: **Phase 4** (visual assets and card rendering, on top of the
normalized dataset) and **M6** (a static analytics dashboard, on top of the
Phase 3 marts) — see `CLAUDE.md`'s "Repository purpose" for how each layers
on the last. See `todo.md` for the task-level checklist and current status
of every phase.

## Validation and release gates

- **Coverage**
  - `>=95%` of OP.GG legal pool mapped to canonical `pokemon_id`
  - `>=90%` of targeted tournament records mapped to normalized team tables
  - `>=95%` of PokéBase legal-pool rows mapped to canonical `pokemon_id`
  - `>=85%` of Bulbagarden sprite titles mapped to `pokemon_asset`
    `menu_sprite` rows
  - `>=85%` of staged Limitless online team-sheet slots mapped to a
    `pokemon_key` (`assert_limitless_play_slug_mapping_coverage`), the
    same bar as limitlessvgc.com's slugs, which the platform shares
  - `>=95%` of each regulation's online team-sheet slots legal in it
    (`assert_online_regulation_legality`), which catches a mislabelled
    online event (67–85%); correctly resolved data sits at 98.7–99.9%
  - `>=95%` of `pokemon_asset` `menu_sprite` rows also having a
    `home_render` row. The threshold is higher than Bulbagarden's 85%
    because none of what justifies that lower floor applies: that gate's
    denominator is raw file titles, several of which collapse onto one
    `pokemon_key` by design (Vivillon patterns, Florges colors, Furfrou
    trims, Alcremie flavors). Both sides of this ratio are already
    per-`pokemon_key`, so a shortfall here is a real missing render rather
    than a dedup artifact.
- **Null-rate gate**
  - Required-field null rate must be `<=1%` for every core table
- **Duplicate-key gate**
  - Duplicate primary-key violations must equal `0`
- **Referential-integrity gate**
  - `pokemon_stat_*` rows must resolve to `pokemon`
  - `legality_snapshot` rows must resolve to `pokemon`
  - `tournament_team` rows must resolve to `tournament_event`
  - `tournament_team_member` rows must resolve to both `tournament_team` and
    `pokemon`
  - `pokemon_asset` rows must resolve to `pokemon`

The v1 definition-of-done checklist that tracks these gates, plus export and
example-query validation, lives in `todo.md`.

## Current status

Repository scaffolding, Phases 1-4, and M6 are all implemented, and
`dataset_version 0.2.0` has been published (see `CLAUDE.md`'s "Repository
purpose"). For outstanding work, see `docs/todo.md`'s open items and
`docs/backlog.md`'s uncommitted wish list.
