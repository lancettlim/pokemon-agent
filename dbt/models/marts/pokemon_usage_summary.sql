{{ config(location='../data/marts/pokemon_usage_summary.csv') }}
-- Flat analytical export (docs/todo.md's Phase 3 "Publish flat analytical
-- exports and summary aggregates" item): total tournament-roster usage per
-- Pokémon, restricted to the current legal pool, ranked descending.
--
-- event_tier is an optional filter dimension (docs/todo.md's "tournament-
-- tier filtering" follow-up): every Pokémon gets one overall row
-- (event_tier is null) plus one row per tournament tier it appears in,
-- each ranked within its own event_tier partition — so the overall
-- ranking is unaffected by adding the per-tier breakdown.
--
-- usage_share is usage_count's fraction of total roster appearances within
-- the same event_tier partition (dashboard "include percentage usage"
-- ask): a Pokémon's share of the meta, not just a raw count, so the
-- Usage tab can rank and label leaders by percentage the same way
-- pokemon_win_rate_summary already does for win_rate.
--
-- regulation_scope (docs/upgrade-plan-2026q4.md, A3): one partition per
-- Champions regulation ("m-a", "m-b", "m-c", ...) plus the roll-up 'all',
-- each computed and ranked independently, via int_champions_roster_scoped.
with overall as (
  select
    member.regulation_scope,
    member.pokemon_key,
    cast(null as varchar) as event_tier,
    count(*) as usage_count
  from {{ ref('int_champions_roster_scoped') }} member
  inner join {{ ref('pokemon_stat_champions') }} champions
    on champions.pokemon_key = member.pokemon_key
    and champions.is_legal = true
  group by member.regulation_scope, member.pokemon_key
),
by_tier as (
  select
    member.regulation_scope,
    member.pokemon_key,
    event.event_tier,
    count(*) as usage_count
  from {{ ref('int_champions_roster_scoped') }} member
  inner join {{ ref('pokemon_stat_champions') }} champions
    on champions.pokemon_key = member.pokemon_key
    and champions.is_legal = true
  inner join {{ ref('tournament_event') }} event
    on event.event_id = member.event_id
  where event.event_tier is not null
  group by member.regulation_scope, member.pokemon_key, event.event_tier
)
select
  regulation_scope,
  pokemon_key,
  event_tier,
  usage_count,
  round(
    usage_count::double / sum(usage_count) over (partition by regulation_scope, event_tier),
    4
  ) as usage_share,
  row_number() over (partition by regulation_scope, event_tier order by usage_count desc) as usage_rank
from (
  select * from overall
  union all
  select * from by_tier
)
