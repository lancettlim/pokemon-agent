{{ config(location='../data/marts/team_mega_count.csv') }}
-- How many Mega Stones a team carries (docs/upgrade-plan-2027q2.md, E3):
-- the share of teams with zero, one, two (or, rarely, more) Mega forms on
-- their sheet, per regulation scope and per event, the second half of the
-- Mega usage panel. Same two grains as mega_stone_usage (scope_kind
-- 'regulation' with a null event_id, or 'event').
with team_megas as (
  select
    regulation_scope,
    event_id,
    regulation_code,
    team_id,
    count(*) filter (where pokemon_key like '%-mega%') as mega_count
  from {{ ref('int_champions_roster_scoped') }}
  group by regulation_scope, event_id, regulation_code, team_id
),
by_scope as (
  select
    'regulation' as scope_kind,
    regulation_scope as scope_code,
    cast(null as varchar) as event_id,
    mega_count,
    count(*) as team_count
  from team_megas
  group by regulation_scope, mega_count
),
by_event as (
  select
    'event' as scope_kind,
    regulation_code as scope_code,
    event_id,
    mega_count,
    count(*) as team_count
  from team_megas
  where regulation_scope != 'all'
  group by regulation_code, event_id, mega_count
)
select
  *,
  round(
    team_count::double / sum(team_count) over (partition by scope_kind, scope_code, event_id),
    4
  ) as team_share
from (
  select * from by_scope
  union all
  select * from by_event
)
order by scope_kind, scope_code, event_id, mega_count
