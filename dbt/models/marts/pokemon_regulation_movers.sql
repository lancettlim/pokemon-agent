{{ config(location='../data/marts/pokemon_regulation_movers.csv') }}
-- "What changed" feed (docs/upgrade-plan-2026q4.md, A4): each Pokémon's
-- usage and win rate in a regulation next to the same figures in the
-- regulation before it, for every consecutive pair in the
-- champions_regulations seed (M-A -> M-B, M-B -> M-C, ...).
--
-- backlog.md #18 (meta-shift view) was archived because it waited on
-- extraction-snapshot history. This needs none: it compares two cohorts of
-- events that are already in the data, grouped by
-- tournament_event.regulation_code.
--
-- One row per (regulation_code, pokemon_key) for every Pokémon used in
-- either regulation of the pair. Deltas are null when one side has no
-- data, and is_new_to_format marks Pokémon not legal in the previous
-- regulation (legality_snapshot). team_count/previous_team_count carry the
-- sample size so the UI can show it and hold back deltas a thin regulation
-- can't support: an early-season regulation can have a handful of events.
with regulation_order as (
  select
    regulation_code,
    lag(regulation_code) over (order by start_date) as previous_regulation_code
  from {{ ref('champions_regulations') }}
),
team_counts as (
  select regulation_code, count(distinct team_id) as team_count
  from {{ ref('int_champions_roster') }}
  group by regulation_code
),
usage as (
  select regulation_scope as regulation_code, pokemon_key, usage_count, usage_share, team_share, usage_rank
  from {{ ref('pokemon_usage_summary') }}
  where event_tier is null and regulation_scope != 'all'
),
win as (
  select regulation_scope as regulation_code, pokemon_key, win_rate, wilson_lower_bound, record_count
  from {{ ref('pokemon_win_rate_summary') }}
  where regulation_scope != 'all'
),
latest_legality as (
  select regulation_code, pokemon_key
  from {{ ref('legality_snapshot') }}
  where is_legal = true
    and snapshot_date = (select max(snapshot_date) from {{ ref('legality_snapshot') }})
),
pairs as (
  select regulation_order.regulation_code, regulation_order.previous_regulation_code, keys.pokemon_key
  from regulation_order
  inner join (
    select regulation_code, pokemon_key from usage
  ) keys
    on keys.regulation_code in (regulation_order.regulation_code, regulation_order.previous_regulation_code)
  where regulation_order.previous_regulation_code is not null
  group by 1, 2, 3
)
select
  pairs.regulation_code,
  pairs.previous_regulation_code,
  pairs.pokemon_key,
  coalesce(current_usage.usage_count, 0) as usage_count,
  coalesce(current_usage.usage_share, 0) as usage_share,
  current_usage.usage_rank,
  coalesce(previous_usage.usage_count, 0) as previous_usage_count,
  coalesce(previous_usage.usage_share, 0) as previous_usage_share,
  previous_usage.usage_rank as previous_usage_rank,
  round(coalesce(current_usage.usage_share, 0) - coalesce(previous_usage.usage_share, 0), 4)
    as usage_share_delta,
  -- Team share (docs/upgrade-plan-2027q2.md, V1), the headline the "What
  -- changed" panel reports; the slot-share columns above stay for
  -- tooltips and local queries.
  coalesce(current_usage.team_share, 0) as team_share,
  coalesce(previous_usage.team_share, 0) as previous_team_share,
  round(coalesce(current_usage.team_share, 0) - coalesce(previous_usage.team_share, 0), 4)
    as team_share_delta,
  previous_usage.usage_rank - current_usage.usage_rank as rank_change,
  current_win.win_rate,
  previous_win.win_rate as previous_win_rate,
  round(current_win.win_rate - previous_win.win_rate, 4) as win_rate_delta,
  current_win.record_count,
  previous_win.record_count as previous_record_count,
  previous_legal.pokemon_key is null as is_new_to_format,
  coalesce(current_teams.team_count, 0) as team_count,
  coalesce(previous_teams.team_count, 0) as previous_team_count
from pairs
left join usage current_usage
  on current_usage.regulation_code = pairs.regulation_code
  and current_usage.pokemon_key = pairs.pokemon_key
left join usage previous_usage
  on previous_usage.regulation_code = pairs.previous_regulation_code
  and previous_usage.pokemon_key = pairs.pokemon_key
left join win current_win
  on current_win.regulation_code = pairs.regulation_code
  and current_win.pokemon_key = pairs.pokemon_key
left join win previous_win
  on previous_win.regulation_code = pairs.previous_regulation_code
  and previous_win.pokemon_key = pairs.pokemon_key
left join latest_legality previous_legal
  on previous_legal.regulation_code = pairs.previous_regulation_code
  and previous_legal.pokemon_key = pairs.pokemon_key
left join team_counts current_teams
  on current_teams.regulation_code = pairs.regulation_code
left join team_counts previous_teams
  on previous_teams.regulation_code = pairs.previous_regulation_code
order by pairs.regulation_code, usage_share_delta desc
