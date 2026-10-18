{{ config(location='../data/marts/pokemon_usage_by_regulation.csv') }}
-- Usage x regulation cross-tab (backlog.md #12): for each regulation, every
-- Pokémon legal under it, with its usage *in events played under that
-- regulation* (0 if it was legal but never brought).
--
-- This used to be a stand-in: tournament_event carried no regulation_code,
-- so the mart cross-joined all-time usage against each regulation's legal
-- pool, and "usage in M-B" really meant "all-time usage of Pokémon legal in
-- M-B". tournament_event.regulation_code now exists (resolved through the
-- champions_regulations seed), and pokemon_usage_summary is partitioned by
-- regulation_scope, so this is the real temporal slice
-- (docs/upgrade-plan-2026q4.md, A2).
--
-- usage_share/usage_rank are computed within each regulation_code, so a
-- share is that Pokémon's standing in that regulation's own events.
with regulation_usage as (
  select regulation_scope as regulation_code, pokemon_key, usage_count
  from {{ ref('pokemon_usage_summary') }}
  where event_tier is null
    and regulation_scope != 'all'
),
latest_snapshot as (
  select max(snapshot_date) as snapshot_date
  from {{ ref('legality_snapshot') }}
),
legal_by_regulation as (
  select ls.regulation_code, ls.pokemon_key
  from {{ ref('legality_snapshot') }} ls
  inner join latest_snapshot
    on latest_snapshot.snapshot_date = ls.snapshot_date
  where ls.is_legal = true
),
joined as (
  select
    legal_by_regulation.regulation_code,
    legal_by_regulation.pokemon_key,
    coalesce(regulation_usage.usage_count, 0) as usage_count
  from legal_by_regulation
  left join regulation_usage
    on regulation_usage.pokemon_key = legal_by_regulation.pokemon_key
    and regulation_usage.regulation_code = legal_by_regulation.regulation_code
)
select
  regulation_code,
  pokemon_key,
  usage_count,
  round(
    usage_count::double / nullif(sum(usage_count) over (partition by regulation_code), 0),
    4
  ) as usage_share,
  row_number() over (partition by regulation_code order by usage_count desc, pokemon_key) as usage_rank
from joined
order by regulation_code, usage_count desc
