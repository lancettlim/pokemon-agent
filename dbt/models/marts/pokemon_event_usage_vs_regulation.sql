{{ config(location='../data/marts/pokemon_event_usage_vs_regulation.csv') }}
-- Usage at each Champions event against its regulation's average
-- (docs/upgrade-plan-2027q1.md, C1 and C4). An event page's "over- and
-- under-performers" read event_usage_share - regulation_usage_share, and
-- the event-window filter ("since Frankfurt", "last 3 events") sums
-- usage_count and slot_count over the events in a window.
--
-- One row per event x Pokémon used anywhere in that event's regulation,
-- including Pokémon absent from the event (usage_count 0), so a Pokémon
-- the field dropped at one event still shows as under-performing there.
-- usage shares are of roster slots, the same unit as
-- pokemon_usage_summary.usage_share; the team_share columns are of teams,
-- the headline unit (docs/upgrade-plan-2027q2.md, V1).
-- wins/losses are the reported records of the event's teams that brought
-- the Pokémon. Small events make noisy deltas: consumers should hide them
-- below a minimum event_team_count, as the dashboard does.
with legal_slots as (
  select roster.*
  from {{ ref('int_champions_roster_official') }} roster
  inner join {{ ref('pokemon_stat_champions') }} champions
    on champions.pokemon_key = roster.pokemon_key
    and champions.is_legal = true
),
events as (
  select
    event_id,
    any_value(event_date) as event_date,
    any_value(regulation_code) as regulation_code,
    count(*) as event_slot_count,
    count(distinct team_id) as event_team_count
  from legal_slots
  group by event_id
),
event_usage as (
  select
    event_id,
    pokemon_key,
    count(*) as usage_count,
    sum(record_wins) as total_wins,
    sum(record_losses) as total_losses
  from legal_slots
  group by event_id, pokemon_key
),
regulation_usage as (
  select regulation_scope as regulation_code, pokemon_key, usage_count, usage_share, team_share
  from {{ ref('pokemon_usage_summary') }}
  where event_tier is null
    and regulation_scope in (select regulation_code from {{ ref('champions_regulations') }})
),
grid as (
  select
    events.*,
    regulation_usage.pokemon_key,
    regulation_usage.usage_share as regulation_usage_share,
    regulation_usage.team_share as regulation_team_share
  from events
  inner join regulation_usage
    on regulation_usage.regulation_code = events.regulation_code
)
select
  grid.regulation_code,
  grid.event_id,
  grid.event_date,
  grid.pokemon_key,
  coalesce(event_usage.usage_count, 0) as usage_count,
  grid.event_slot_count,
  grid.event_team_count,
  round(coalesce(event_usage.usage_count, 0)::double / grid.event_slot_count, 4)
    as event_usage_share,
  grid.regulation_usage_share,
  round(
    coalesce(event_usage.usage_count, 0)::double / grid.event_slot_count
      - grid.regulation_usage_share,
    4
  ) as usage_share_delta,
  round(coalesce(event_usage.usage_count, 0)::double / grid.event_team_count, 4)
    as event_team_share,
  grid.regulation_team_share,
  round(
    coalesce(event_usage.usage_count, 0)::double / grid.event_team_count
      - grid.regulation_team_share,
    4
  ) as team_share_delta,
  event_usage.total_wins,
  event_usage.total_losses
from grid
left join event_usage
  on event_usage.event_id = grid.event_id
  and event_usage.pokemon_key = grid.pokemon_key
order by grid.event_date desc, grid.event_id, usage_count desc, grid.pokemon_key
