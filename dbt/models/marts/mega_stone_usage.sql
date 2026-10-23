{{ config(location='../data/marts/mega_stone_usage.csv') }}
-- Which Mega Stones teams carry (docs/upgrade-plan-2027q2.md, E3): every
-- recap of a Champions event publishes this table, and the roster already
-- holds it, because a Mega holder is recorded as its Mega form
-- (charizard-mega-y holding Charizardite Y).
--
-- Two grains in one table, told apart by scope_kind:
--   'regulation'  one row per (scope_code, Mega form), over every Champions
--                 team in the scope ("m-c", ..., or 'all'); event_id is
--                 null.
--   'event'       one row per (event, Mega form), over that event's teams;
--                 scope_code is the event's regulation.
-- The column is scope_code, not regulation_scope, on purpose: an event
-- page shows an event of any regulation, so the page must not narrow these
-- rows to its own regulation the way it narrows regulation_scope marts.
-- team_share is team_count over scope_team_count, the same unit as
-- pokemon_usage_summary.team_share. item_name is the stone most often
-- held by that form (a form has one stone, so this is a label).
with megas as (
  select *
  from {{ ref('int_champions_roster_scoped') }}
  where pokemon_key like '%-mega%'
),
scope_teams as (
  select regulation_scope, count(distinct team_id) as scope_team_count
  from {{ ref('int_champions_roster_scoped') }}
  group by regulation_scope
),
event_teams as (
  select event_id, any_value(regulation_code) as regulation_code, count(distinct team_id) as scope_team_count
  from {{ ref('int_champions_roster_official') }}
  group by event_id
),
by_scope as (
  select
    'regulation' as scope_kind,
    megas.regulation_scope as scope_code,
    cast(null as varchar) as event_id,
    megas.pokemon_key,
    mode(megas.item_name) as item_name,
    count(distinct megas.team_id) as team_count,
    scope_teams.scope_team_count
  from megas
  inner join scope_teams using (regulation_scope)
  group by megas.regulation_scope, megas.pokemon_key, scope_teams.scope_team_count
),
by_event as (
  select
    'event' as scope_kind,
    event_teams.regulation_code as scope_code,
    megas.event_id,
    megas.pokemon_key,
    mode(megas.item_name) as item_name,
    count(distinct megas.team_id) as team_count,
    event_teams.scope_team_count
  from megas
  inner join event_teams using (event_id)
  -- Official events only: one row per event, from its own base scope.
  where megas.regulation_scope = megas.regulation_code
  group by event_teams.regulation_code, megas.event_id, megas.pokemon_key, event_teams.scope_team_count
)
select
  *,
  round(team_count::double / scope_team_count, 4) as team_share,
  row_number() over (
    partition by scope_kind, scope_code, event_id order by team_count desc, pokemon_key
  ) as usage_rank
from (
  select * from by_scope
  union all
  select * from by_event
)
order by scope_kind, scope_code, event_id, usage_rank
