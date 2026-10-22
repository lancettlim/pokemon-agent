{{ config(location='../data/marts/tournament_team_sheets.csv') }}
-- Full team sheets (item, ability, nature and moves per slot) for the
-- teams the site lets a reader copy or load into the Builder
-- (docs/upgrade-plan-2027q1.md, C1, C2, P4, P5): every top-16 finish at a
-- Champions event, plus every team on the top_tournament_teams
-- leaderboard. One row per team x roster slot.
--
-- Bounded on purpose. Every Champions team sheet would be tens of
-- thousands of rows that no view displays in full; the top cut is what
-- event pages, Top Teams and the starter-team strip show. Roster
-- composition for every other team stays in tournament_team_results.
--
-- No EV/IV columns: official team sheets publish ability, held item,
-- nature and moves and nothing more.
with selected_teams as (
  select distinct team_id
  from {{ ref('int_champions_roster_official') }}
  where placement <= 16
  union
  select distinct team_id
  from {{ ref('top_tournament_teams') }}
)
select
  roster.team_id,
  roster.slot_number,
  roster.pokemon_key,
  roster.item_name,
  roster.ability,
  roster.nature,
  roster.moves
from {{ ref('int_champions_roster_official') }} roster
inner join selected_teams
  on selected_teams.team_id = roster.team_id
order by roster.team_id, roster.slot_number
