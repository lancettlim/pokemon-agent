# Local queries

The fastest way to answer an ad-hoc question against this dataset is to
query the DuckDB warehouse directly — no dashboard, no notebook server, no
new dependency. `dbt/data/warehouse.duckdb` already holds every normalized
table and every mart as a real, queryable relation (dbt's `external`
materialization backs each one by its CSV under `data/normalized/` or
`data/marts/`, so the warehouse file and the CSVs stay in sync automatically
on every `dbt build`).

This is backlog item #28: for a single user, a short recipe plus a few
starter queries beats building a notebook server or a new dashboard tab —
several marts below (team synergy, placement-weighted usage, build
concentration, cross-source roster agreement) aren't wired into the
dashboard UI yet at all, so this is currently the *only* way to see their
output.

Note on scope: every usage/win-rate mart is now restricted to Pokémon
Champions events. MunchStats indexes standard VGC events alongside
Champions ones, and until `event_format` was captured these tables mixed
the two — see `dbt/models/intermediate/int_champions_roster.sql`.

## Prerequisites

The warehouse file is a build artifact (gitignored, like everything under
`data/`), not something checked into the repo. Build it once with:

```
make dbt-build
```

(or `make refresh` if `data/staging/` is empty too — see this repo's
`CLAUDE.md` for the full extract → build chain). Every query below assumes
you're running from the `dbt/` directory, since the warehouse's external
tables are registered with paths relative to it (`profiles.yml`'s
`external_root`).

## Opening the warehouse

**DuckDB CLI** (if you have the `duckdb` binary installed):

```
cd dbt
duckdb data/warehouse.duckdb
```

**Python**, using the `duckdb` package already in this project's
dependencies:

```
cd dbt
uv run python3
>>> import duckdb
>>> con = duckdb.connect("data/warehouse.duckdb", read_only=True)
>>> con.sql("select * from pokemon_usage_summary limit 5").show()
```

`read_only=True` is worth keeping as a habit: it lets you open the file
alongside a `dbt build` running in another terminal without lock
contention.

To see every table available, including intermediate/staging models not
meant to be queried directly:

```sql
select table_name from information_schema.tables where table_schema = 'main' order by 1;
```

The ten-ish tables named `pokemon_*_usage`, `pokemon_*_summary`,
`pokemon_team_*`, and similar under `data/marts/*.csv` are the ones meant
for this kind of ad-hoc querying; `stg_*`/`int_*` are intermediate layers
worth ignoring unless you're debugging the models themselves.

## Starter queries

Regulation-sensitive marts (usage, win rate, items/abilities/moves, cores,
synergy, profile, speed tiers, top teams) carry a `regulation_scope`
column: one partition per regulation (`'m-a'`, `'m-b'`, `'m-c'`, ...) plus
`'all'` across every Champions regulation. Always filter on it, or each
Pokémon is counted once per scope. `pokemon_regulation_movers` compares
each regulation with the one before it.

Each of these was run against a real, freshly-extracted snapshot to
confirm it returns non-degenerate results — not just checked for syntax.

**Top 10 most-used Pokémon in Reg M-C:**

```sql
select pokemon_key, usage_count, round(usage_share * 100, 1) as usage_pct, usage_rank
from pokemon_usage_summary
where event_tier is null        -- the overall row, not a per-tier breakout
  and regulation_scope = 'm-c'  -- or 'all' for every Champions regulation
order by usage_rank
limit 10;
```

**Biggest risers from M-B to M-C** (team counts are the sample size):

```sql
select pokemon_key, round(previous_usage_share * 100, 1) as mb_pct,
       round(usage_share * 100, 1) as mc_pct, is_new_to_format,
       team_count, previous_team_count
from pokemon_regulation_movers
where regulation_code = 'm-c'
order by usage_share_delta desc
limit 10;
```

**Win rate leaders, ranked by statistical confidence (Wilson lower bound)
rather than raw win rate** — this is what fixed the KPI card in backlog
#13: a 100%-over-3-matches outlier no longer beats a well-established
50%-over-thousands-of-matches Pokémon:

```sql
select pokemon_key, total_wins, total_losses,
       round(win_rate * 100, 1) as win_rate_pct,
       round(wilson_lower_bound * 100, 1) as wilson_lb_pct
from pokemon_win_rate_summary
where regulation_scope = 'all'
order by wilson_rank
limit 10;
```

**Genuine teammate synergy, not just "both are popular"** (lift > 1 means
the pair appears together more than their individual usage rates would
predict; filtered to pairs seen together often enough for the ratio to be
meaningful):

```sql
select pokemon_key, partner_pokemon_key, pair_team_count, round(lift, 2) as lift
from pokemon_team_synergy
where regulation_scope = 'all'
  and pair_team_count >= 20
order by lift desc
limit 10;
```

**Head-to-head matchups for one Pokémon** (swap the `pokemon_key`; see
`pokemon.csv` or `pokemon_usage_summary` for valid keys). Read this as
*team vs team* — see `pokemon_head_to_head`'s schema.yml entry:

```sql
select opponent_pokemon_key, matches_played, round(win_rate * 100, 1) as win_pct
from pokemon_head_to_head
where pokemon_key = 'incineroar' and matches_played >= 30
order by wilson_lower_bound desc
limit 10;
```

**Do the two roster sources agree?** — MunchStats and Limitless read
independently, compared per event:

```sql
select event_name, covered_players, exact_agreement_rate, slot_agreement_rate
from roster_source_agreement
order by covered_players desc;
```

**"Popular" vs. "actually good"** — top-cut usage share and a continuous
placement-weighted score, both distinct from raw usage:

```sql
select pokemon_key, top_cut_usage_count, round(weighted_usage_share * 100, 2) as weighted_pct
from pokemon_placement_weighted_usage
order by placement_weighted_score desc
limit 10;
```

**Item/ability concentration** — a low Herfindahl-Hirschman Index means a
Pokémon's item or ability choice is genuinely contested across the
tournament field, not locked into one "correct" build:

```sql
select pokemon_key, item_count, round(item_hhi, 3) as item_hhi
from pokemon_build_concentration
where item_count > 1
order by item_hhi asc
limit 10;
```

**Usage scoped to one regulation's legal pool** (swap the `regulation_code`;
see `legality_summary_by_regulation` for valid codes):

```sql
select pokemon_key, usage_count, usage_rank
from pokemon_usage_by_regulation
where regulation_code = 'm-a'
order by usage_rank
limit 10;
```

## More examples

`dbt/analyses/` holds three more example queries (canonical-vs-Champions
stat deltas, most-used legal Pokémon, legal-pool changes by regulation)
written against the normalized layer rather than the marts above — see
`dbt/analyses/README.md` for what each one validates and its current
known-degenerate caveats (a rebalance and multiple snapshots, respectively,
haven't happened yet). Those are dbt "analyses": compile them with
`dbt compile --select <name>` and run the output from
`target/compiled/pokemon_champions/analyses/` the same way as above, or
just copy the SQL directly into your own session.
