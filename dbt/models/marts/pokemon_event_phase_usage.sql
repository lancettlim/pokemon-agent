{{ config(location='../data/marts/pokemon_event_phase_usage.csv') }}
-- Day 2 conversion (docs/upgrade-plan-2027q2.md, E1), VGC's classic stat:
-- a Pokémon's share of the whole field against its share of the teams
-- that reached Day 2 (or the top cut), and the ratio between them.
-- Official events with RK9 pairings only (int_event_team_phases).
--
-- Two grains, told apart by scope_kind, as in mega_stone_usage:
--   'event'       one row per (event, phase, Pokémon); scope_code is the
--                 event's regulation.
--   'regulation'  one row per (scope_code, phase, Pokémon) over every
--                 event in the scope ("m-c", ..., or 'all') that had the
--                 phase, so the field it is compared with is the same
--                 events' field.
--
-- phase is 'day2' or 'top_cut'. phase_team_count is the phase's n and
-- field_team_count the field's n at the same events; conversion is
-- team_share / field_team_share (1.0 = converted at its field rate).
-- is_reliable follows the "What changed" panel's floor
-- (pipelines/dashboard/data.py's MIN_MOVER_TEAMS): both sides need 100
-- teams, which an event's top cut never has. Consumers show counts but
-- hold back the ratio when it is false.
with teams as (
  select
    roster.event_id,
    roster.regulation_code,
    roster.team_id,
    roster.pokemon_key,
    phases.reached_day2,
    phases.reached_top_cut,
    phases.event_has_day2,
    phases.event_has_top_cut
  from {{ ref('int_champions_roster_official') }} roster
  inner join {{ ref('int_event_team_phases') }} phases
    on phases.team_id = roster.team_id
),
phased as (
  select *, 'day2' as phase, reached_day2 as in_phase, event_has_day2 as has_phase
  from teams
  union all
  select *, 'top_cut' as phase, reached_top_cut as in_phase, event_has_top_cut as has_phase
  from teams
),
scoped as (
  select 'event' as scope_kind, regulation_code as scope_code, event_id as grain_event_id, *
  from phased
  where has_phase
  union all
  select 'regulation' as scope_kind, regulation_code as scope_code, null as grain_event_id, *
  from phased
  where has_phase
  union all
  select 'regulation' as scope_kind, 'all' as scope_code, null as grain_event_id, *
  from phased
  where has_phase
),
totals as (
  select
    scope_kind,
    scope_code,
    grain_event_id,
    phase,
    count(distinct team_id) as field_team_count,
    count(distinct team_id) filter (where in_phase) as phase_team_count
  from scoped
  group by scope_kind, scope_code, grain_event_id, phase
),
usage as (
  select
    scope_kind,
    scope_code,
    grain_event_id,
    phase,
    pokemon_key,
    count(distinct team_id) as field_usage_count,
    count(distinct team_id) filter (where in_phase) as team_count
  from scoped
  group by scope_kind, scope_code, grain_event_id, phase, pokemon_key
)
select
  usage.scope_kind,
  usage.scope_code,
  usage.grain_event_id as event_id,
  usage.phase,
  usage.pokemon_key,
  usage.team_count,
  totals.phase_team_count,
  round(usage.team_count::double / nullif(totals.phase_team_count, 0), 4) as team_share,
  usage.field_usage_count,
  totals.field_team_count,
  round(usage.field_usage_count::double / nullif(totals.field_team_count, 0), 4)
    as field_team_share,
  round(
    (usage.team_count::double / nullif(totals.phase_team_count, 0))
    / nullif(usage.field_usage_count::double / nullif(totals.field_team_count, 0), 0),
    3
  ) as conversion,
  totals.phase_team_count >= 100 and totals.field_team_count >= 100 as is_reliable,
  row_number() over (
    partition by usage.scope_kind, usage.scope_code, usage.grain_event_id, usage.phase
    order by usage.team_count desc, usage.field_usage_count desc, usage.pokemon_key
  ) as usage_rank
from usage
inner join totals
  on totals.scope_kind = usage.scope_kind
  and totals.scope_code = usage.scope_code
  and totals.grain_event_id is not distinct from usage.grain_event_id
  and totals.phase = usage.phase
where totals.phase_team_count > 0
