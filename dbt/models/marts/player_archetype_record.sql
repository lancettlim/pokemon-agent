{{ config(location='../data/marts/player_archetype_record.csv') }}
-- A player's match record against each detected archetype they faced
-- (docs/upgrade-plan-2027q1.md, C3, for opponent prep). Team vs team: the
-- opponent's archetype is their team's primary
-- detected_archetype_team_membership assignment, and a win means the
-- player's team beat that team. No source names the four Pokémon brought
-- to a given game.
--
-- One row per player x regulation x opponent archetype, from decided
-- Masters matches in RK9 pairings. Only rows with at least 2 matches are
-- kept: a single game against an archetype is that game, not a record.
with decided as (
  select event_id, team_id_1, team_id_2, winner_team_id
  from {{ ref('tournament_match') }}
  where division = 'Masters'
    and outcome in ('player1_win', 'player2_win')
    and team_id_1 is not null
    and team_id_2 is not null
    and winner_team_id is not null
),
sides as (
  select event_id, team_id_1 as own_team_id, team_id_2 as opponent_team_id, winner_team_id
  from decided
  union all
  select event_id, team_id_2 as own_team_id, team_id_1 as opponent_team_id, winner_team_id
  from decided
),
teams as (
  select distinct team_id, player_id, regulation_code
  from {{ ref('int_champions_roster') }}
),
archetypes as (
  select team_id, archetype_key
  from {{ ref('detected_archetype_team_membership') }}
  where assignment_type = 'primary'
)
select
  own.player_id,
  own.regulation_code,
  opponent_archetype.archetype_key as opponent_archetype_key,
  -- The archetype's anchor core, so a consumer can name it without the
  -- whole archetype mart.
  any_value(
    summary.pokemon_key_a || '|' || summary.pokemon_key_b || '|' || summary.pokemon_key_c
  ) as opponent_pokemon_keys,
  count(*) as matches_played,
  sum(case when sides.winner_team_id = sides.own_team_id then 1 else 0 end) as wins,
  sum(case when sides.winner_team_id = sides.own_team_id then 0 else 1 end) as losses,
  round(
    sum(case when sides.winner_team_id = sides.own_team_id then 1 else 0 end)::double / count(*),
    4
  ) as win_rate
from sides
inner join teams own
  on own.team_id = sides.own_team_id
inner join archetypes opponent_archetype
  on opponent_archetype.team_id = sides.opponent_team_id
left join {{ ref('detected_archetype_summary') }} summary
  on summary.archetype_key = opponent_archetype.archetype_key
group by own.player_id, own.regulation_code, opponent_archetype.archetype_key
having count(*) >= 2
order by own.player_id, own.regulation_code, matches_played desc
