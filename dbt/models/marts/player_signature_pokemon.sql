{{ config(location='../data/marts/player_signature_pokemon.csv') }}
-- Player-grain half of backlog.md #7 ("does this player have a signature
-- Pokémon," across their full history rather than the single-team grain
-- top_tournament_teams already reports): one row per player_id x
-- pokemon_key they've fielded, restricted to the current legal pool.
--
-- player_id is a deterministic hash of (player_name, player_country) --
-- see pipelines/extract/munchstats.py's _player_id -- so grouping by all
-- three together is safe: every row sharing a player_id shares the same
-- name/country. player_usage_share is this Pokémon's fraction of the
-- player's own total legal-pool roster appearances across every team of
-- theirs on record; player_pokemon_rank orders a player's own picks, so
-- rank 1 is their signature Pokémon. player_team_count (distinct teams
-- this player has fielded at all) is exposed alongside the rank as a
-- sample-size signal -- a "signature" claim from a player with only one
-- or two recorded teams is much weaker evidence than one from a player
-- with dozens.
with player_totals as (
  select
    team.player_id,
    team.player_name,
    team.player_country,
    count(distinct team.team_id) as player_team_count,
    count(*) as player_total_appearances
  from {{ ref('int_champions_roster_official') }} member
  inner join {{ ref('pokemon_stat_champions') }} champions
    on champions.pokemon_key = member.pokemon_key
    and champions.is_legal = true
  inner join {{ ref('tournament_team') }} team
    on team.team_id = member.team_id
  where team.player_id is not null and team.player_id != ''
  group by team.player_id, team.player_name, team.player_country
),
player_pokemon as (
  select
    team.player_id,
    member.pokemon_key,
    count(*) as usage_count
  from {{ ref('int_champions_roster_official') }} member
  inner join {{ ref('pokemon_stat_champions') }} champions
    on champions.pokemon_key = member.pokemon_key
    and champions.is_legal = true
  inner join {{ ref('tournament_team') }} team
    on team.team_id = member.team_id
  where team.player_id is not null and team.player_id != ''
  group by team.player_id, member.pokemon_key
)
select
  totals.player_id,
  totals.player_name,
  totals.player_country,
  totals.player_team_count,
  pokemon.pokemon_key,
  pokemon.usage_count,
  round(pokemon.usage_count::double / totals.player_total_appearances, 4)
    as player_usage_share,
  row_number() over (
    partition by totals.player_id order by pokemon.usage_count desc, pokemon.pokemon_key
  ) as player_pokemon_rank
from player_pokemon pokemon
inner join player_totals totals
  on totals.player_id = pokemon.player_id
