{{ config(location='../data/marts/pokemon_build_concentration.csv') }}
-- Item and build concentration metrics (backlog.md #14): a
-- Herfindahl-Hirschman Index (sum of squared shares) over
-- pokemon_item_usage.item_share and pokemon_ability_usage.ability_share
-- per Pokémon, distinguishing Pokémon with one locked-in optimal build
-- (HHI near 1: usage concentrated on a single item/ability) from ones with
-- genuinely contested choices (HHI near 0: usage spread evenly across
-- several). item_count/ability_count is how many distinct items/abilities
-- were observed at all, so a HHI of 1 with item_count 1 (no contested
-- choice observed) reads differently from a HHI of 1 with item_count > 1
-- (one build has crowded out real alternatives).
--
-- Built on top of pokemon_item_usage/pokemon_ability_usage rather than
-- re-deriving from tournament_team_member directly, so this mart always
-- agrees with the per-item/per-ability shares the Pokémon Profile tab
-- already shows.
--
-- regulation_scope passes through from pokemon_item_usage and
-- pokemon_ability_usage: one HHI per Pokémon per scope.
with item_hhi as (
  select
    regulation_scope,
    pokemon_key,
    round(sum(item_share * item_share), 4) as item_hhi,
    count(*) as item_count
  from {{ ref('pokemon_item_usage') }}
  group by regulation_scope, pokemon_key
),
ability_hhi as (
  select
    regulation_scope,
    pokemon_key,
    round(sum(ability_share * ability_share), 4) as ability_hhi,
    count(*) as ability_count
  from {{ ref('pokemon_ability_usage') }}
  group by regulation_scope, pokemon_key
)
select
  coalesce(item_hhi.regulation_scope, ability_hhi.regulation_scope) as regulation_scope,
  coalesce(item_hhi.pokemon_key, ability_hhi.pokemon_key) as pokemon_key,
  item_hhi.item_hhi,
  item_hhi.item_count,
  ability_hhi.ability_hhi,
  ability_hhi.ability_count
from item_hhi
full outer join ability_hhi
  on ability_hhi.pokemon_key = item_hhi.pokemon_key
  and ability_hhi.regulation_scope = item_hhi.regulation_scope
order by regulation_scope, pokemon_key
