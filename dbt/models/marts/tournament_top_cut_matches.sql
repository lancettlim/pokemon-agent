{{ config(location='../data/marts/tournament_top_cut_matches.csv') }}
-- The single-elimination bracket of each official event with RK9 pairings
-- (docs/upgrade-plan-2027q2.md, E2): one row per top-cut match, from the
-- round int_event_phases finds the top cut starting in. Event pages draw
-- it as scoreboard rows with team strips.
--
-- Team vs team, as every match view here: a row says which team beat
-- which, not which of their Pokémon were brought. round_label names the
-- round by its bracket ("Round of 16", "Quarterfinals", "Semifinals",
-- "Final"); a top seed's bye is a row with outcome 'bye' and no second
-- side. top_cut_size counts players and bracket_size slots.
-- Each side carries the team's player, placement and six Pokémon so the
-- page needs no other mart to draw it.
with teams as (
  select
    team_id,
    any_value(player_id) as player_id,
    any_value(player_name) as player_name,
    any_value(player_country) as player_country,
    any_value(placement) as placement,
    string_agg(pokemon_key, '|' order by slot_number) as pokemon_keys
  from {{ ref('int_champions_roster_official') }}
  group by team_id
),
cut_matches as (
  select
    match.*,
    phases.top_cut_start_round,
    phases.top_cut_size,
    phases.bracket_size,
    count(*) over (partition by match.event_id, match.round_number) as round_tables
  from {{ ref('tournament_match') }} match
  inner join {{ ref('int_event_phases') }} phases
    on phases.event_id = match.event_id
  where match.division = 'Masters'
    and match.round_number >= phases.top_cut_start_round
)
select
  cut_matches.match_id,
  cut_matches.event_id,
  event.regulation_code,
  cut_matches.round_number,
  cut_matches.round_number - cut_matches.top_cut_start_round + 1 as bracket_round,
  cut_matches.top_cut_size,
  cut_matches.bracket_size,
  case cut_matches.round_tables
    when 1 then 'Final'
    when 2 then 'Semifinals'
    when 4 then 'Quarterfinals'
    else 'Round of ' || cast(2 * cut_matches.round_tables as varchar)
  end as round_label,
  cut_matches.table_number,
  cut_matches.team_id_1,
  team1.player_id as player_id_1,
  team1.player_name as player_name_1,
  team1.player_country as player_country_1,
  team1.placement as placement_1,
  team1.pokemon_keys as pokemon_keys_1,
  cut_matches.team_id_2,
  team2.player_id as player_id_2,
  team2.player_name as player_name_2,
  team2.player_country as player_country_2,
  team2.placement as placement_2,
  team2.pokemon_keys as pokemon_keys_2,
  cut_matches.winner_team_id,
  cut_matches.outcome,
  cut_matches.is_complete
from cut_matches
inner join {{ ref('tournament_event') }} event
  on event.event_id = cut_matches.event_id
left join teams team1
  on team1.team_id = cut_matches.team_id_1
left join teams team2
  on team2.team_id = cut_matches.team_id_2
order by cut_matches.event_id, cut_matches.round_number, cut_matches.table_number
