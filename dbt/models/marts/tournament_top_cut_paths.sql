{{ config(location='../data/marts/tournament_top_cut_paths.csv') }}
-- Each top-cut team's path through its event (docs/upgrade-plan-2027q2.md,
-- E2): every Masters round it played, Day 1 to the end, with the opponent's
-- player and team and the result. An event page opens it when a player in
-- the bracket is clicked.
--
-- Team vs team: a W says this team beat that one, not which Pokémon won
-- the games. result is W, L, T or Bye. phase is 'Day 1', 'Day 2' or 'Top
-- cut' from int_event_phases (Day 1 throughout for an event with no Day 2).
with teams as (
  select
    team_id,
    any_value(player_name) as player_name,
    any_value(player_country) as player_country,
    any_value(placement) as placement,
    string_agg(pokemon_key, '|' order by slot_number) as pokemon_keys
  from {{ ref('int_champions_roster_official') }}
  group by team_id
),
cut_teams as (
  select event_id, team_id
  from {{ ref('int_event_team_phases') }}
  where reached_top_cut
),
sides as (
  select
    match_id, event_id, round_number, table_number,
    team_id_1 as team_id, team_id_2 as opponent_team_id, outcome,
    case outcome
      when 'player1_win' then 'W' when 'player2_win' then 'L'
      when 'tie' then 'T' when 'bye' then 'Bye'
    end as result
  from {{ ref('tournament_match') }}
  where division = 'Masters' and team_id_1 is not null
  union all
  select
    match_id, event_id, round_number, table_number,
    team_id_2 as team_id, team_id_1 as opponent_team_id, outcome,
    case outcome
      when 'player2_win' then 'W' when 'player1_win' then 'L'
      when 'tie' then 'T'
    end as result
  from {{ ref('tournament_match') }}
  where division = 'Masters' and team_id_2 is not null
)
select
  sides.event_id,
  sides.team_id,
  sides.round_number,
  case
    when sides.round_number >= phases.top_cut_start_round then 'Top cut'
    when sides.round_number >= phases.day2_start_round then 'Day 2'
    else 'Day 1'
  end as phase,
  sides.table_number,
  sides.result,
  sides.opponent_team_id,
  opponent.player_name as opponent_player_name,
  opponent.player_country as opponent_player_country,
  opponent.placement as opponent_placement,
  opponent.pokemon_keys as opponent_pokemon_keys,
  sides.match_id
from sides
inner join cut_teams
  on cut_teams.event_id = sides.event_id
  and cut_teams.team_id = sides.team_id
inner join {{ ref('int_event_phases') }} phases
  on phases.event_id = sides.event_id
left join teams opponent
  on opponent.team_id = sides.opponent_team_id
order by sides.event_id, sides.team_id, sides.round_number
