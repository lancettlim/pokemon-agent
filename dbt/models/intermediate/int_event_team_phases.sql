-- How far each official team got (docs/upgrade-plan-2027q2.md, E1): one
-- row per team at an event with phase data (int_event_phases), saying
-- whether it reached Day 2 and the top cut. A team reached a phase when it
-- played any Masters round from that phase's first round on; a team that
-- never appears in the pairings (an unresolved roster) has no row, so a
-- phase's share is over the teams the pairings account for.
with appearances as (
  select event_id, round_number, team_id_1 as team_id
  from {{ ref('tournament_match') }}
  where division = 'Masters' and team_id_1 is not null
  union all
  select event_id, round_number, team_id_2 as team_id
  from {{ ref('tournament_match') }}
  where division = 'Masters' and team_id_2 is not null
)
select
  appearances.event_id,
  appearances.team_id,
  coalesce(
    bool_or(appearances.round_number >= phases.day2_start_round), false
  ) as reached_day2,
  coalesce(
    bool_or(appearances.round_number >= phases.top_cut_start_round), false
  ) as reached_top_cut,
  max(appearances.round_number) as last_round_played,
  any_value(phases.day2_start_round) is not null as event_has_day2,
  any_value(phases.top_cut_start_round) is not null as event_has_top_cut
from appearances
inner join {{ ref('int_event_phases') }} phases
  on phases.event_id = appearances.event_id
group by appearances.event_id, appearances.team_id
