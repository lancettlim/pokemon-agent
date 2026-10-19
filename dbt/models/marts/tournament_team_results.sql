{{ config(location='../data/marts/tournament_team_results.csv') }}
-- One row per Champions tournament team (docs/upgrade-plan-2027q1.md, C1,
-- C2, C3, P2): who brought it, where it finished, its W-L record and its
-- six Pokémon. Event pages read their top 8 from it, Top Teams ranks it by
-- placement within event tier, player pages list a player's events from
-- it, and a Pokémon's profile lists the top-placing teams featuring it.
--
-- Team grain, carrying the event's regulation_code (one regulation per
-- team) rather than a regulation_scope partition.
--
-- is_fully_reported is true when the team sheet lists six Pokémon, each
-- with an item, an ability, a nature and four moves: the teams a reader
-- can copy and play as published. primary_archetype_key is the team's
-- primary detected_archetype_team_membership assignment, null when no
-- qualifying core matched.
--
-- Player names are the sources' own spelling, and nothing here is
-- inferred beyond what the tournament data publishes.
with members as (
  select
    roster.*,
    case
      when roster.item_name is not null
        and roster.ability is not null
        and roster.nature is not null
        and len(string_split(roster.moves, '|')) = 4
        then 1
      else 0
    end as is_complete_slot
  from {{ ref('int_champions_roster') }} roster
),
teams as (
  select
    team_id,
    any_value(event_id) as event_id,
    any_value(event_name) as event_name,
    any_value(event_date) as event_date,
    any_value(event_tier) as event_tier,
    any_value(regulation_code) as regulation_code,
    any_value(player_id) as player_id,
    any_value(player_name) as player_name,
    any_value(player_country) as player_country,
    any_value(placement) as placement,
    any_value(record_wins) as record_wins,
    any_value(record_losses) as record_losses,
    string_agg(pokemon_key, '|' order by slot_number) as pokemon_keys,
    count(*) as roster_size,
    sum(is_complete_slot) as complete_slot_count
  from members
  group by team_id
),
archetypes as (
  select team_id, archetype_key
  from {{ ref('detected_archetype_team_membership') }}
  where assignment_type = 'primary'
),
event_sizes as (
  select event_id, count(*) as event_team_count
  from teams
  group by event_id
)
select
  teams.team_id,
  teams.event_id,
  teams.event_name,
  teams.event_date,
  teams.event_tier,
  teams.regulation_code,
  teams.player_id,
  teams.player_name,
  teams.player_country,
  teams.placement,
  event_sizes.event_team_count,
  teams.record_wins,
  teams.record_losses,
  round(
    teams.record_wins::double / nullif(teams.record_wins + teams.record_losses, 0),
    4
  ) as win_rate,
  teams.pokemon_keys,
  teams.roster_size,
  teams.roster_size = 6 and teams.complete_slot_count = 6 as is_fully_reported,
  archetypes.archetype_key as primary_archetype_key
from teams
inner join event_sizes
  on event_sizes.event_id = teams.event_id
left join archetypes
  on archetypes.team_id = teams.team_id
order by teams.event_date desc, teams.event_id, teams.placement nulls last, teams.team_id
