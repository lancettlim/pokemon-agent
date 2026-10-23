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
--
-- team_share (docs/upgrade-plan-2027q2.md, V1) is the headline metric:
-- the share of *teams* in the partition that brought the Pokémon,
-- usage_count / scope_team_count. A Pokémon appears at most once per team
-- (species clause), so usage_count is also its team count. It is the unit
-- the official usage card, Pikalytics and Smogon report, and reads about
-- 6x usage_share, which divides by roster slots instead (six per team):
-- Rillaboom on 1,958 of 3,770 M-C teams is 51.9% of teams, 8.7% of slots.
-- scope_team_count counts every team in the partition, including any
-- whose members fall outside the current legal pool.
with team_totals as (
  select regulation_scope, cast(null as varchar) as event_tier, count(distinct team_id) as scope_team_count
  from {{ ref('int_champions_roster_scoped') }}
  group by regulation_scope
  union all
  select member.regulation_scope, event.event_tier, count(distinct member.team_id) as scope_team_count
  from {{ ref('int_champions_roster_scoped') }} member
  inner join {{ ref('tournament_event') }} event
    on event.event_id = member.event_id
  where event.event_tier is not null
  group by member.regulation_scope, event.event_tier
),
overall as (
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
  usage.regulation_scope,
  usage.pokemon_key,
  usage.event_tier,
  usage.usage_count,
  round(
    usage.usage_count::double / sum(usage.usage_count) over (partition by usage.regulation_scope, usage.event_tier),
    4
  ) as usage_share,
  round(usage.usage_count::double / team_totals.scope_team_count, 4) as team_share,
  team_totals.scope_team_count,
  row_number() over (partition by usage.regulation_scope, usage.event_tier order by usage.usage_count desc, usage.pokemon_key) as usage_rank
from (
  select * from overall
  union all
  select * from by_tier
) usage
inner join team_totals
  on team_totals.regulation_scope = usage.regulation_scope
  and team_totals.event_tier is not distinct from usage.event_tier
