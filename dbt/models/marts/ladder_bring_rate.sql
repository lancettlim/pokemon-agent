{{ config(location='../data/marts/ladder_bring_rate.csv') }}
-- Which of its team a Pokémon is brought from (docs/upgrade-plan-2027q2.md,
-- S3; laundry list #27), from sampled Showdown ladder replays: how often it
-- is shown at team preview, brought, led, and how its side does when it is
-- brought versus left at home. The Showdown ladder population only: no
-- official event is played on Showdown, and this is never tournament data.
--
-- Shown at preview and led read every sampled battle. Brought, benched and
-- their win rates read complete battles only (both sides revealed all the
-- Pokémon they brought, int_ladder_battle): elsewhere a Pokémon brought
-- but never sent in looks benched, which happens most on the winning side
-- and would flatter the benched win rate. Win rates read decided battles.
-- A Mega counts with its base Pokémon (team preview hides the stone).
-- variant 'all' pools Bo1 and Bo3.
with pokemon as (
  select *, variant as variant_scope from {{ ref('int_ladder_battle_pokemon') }}
  where pokemon_key is not null
  union all
  select *, 'all' as variant_scope from {{ ref('int_ladder_battle_pokemon') }}
  where pokemon_key is not null
),
battles as (
  select regulation_code, variant as variant_scope, is_complete, side_count
  from {{ ref('int_ladder_battle') }}
  union all
  select regulation_code, 'all', is_complete, side_count
  from {{ ref('int_ladder_battle') }}
),
totals as (
  select
    regulation_code,
    variant_scope,
    sum(side_count) as sides,
    sum(side_count) filter (where is_complete) as complete_sides
  from battles
  group by all
),
per_pokemon as (
  select
    regulation_code,
    variant_scope,
    pokemon_key,
    -- Two sides can show the same Pokémon; each side counts.
    count(*) as shown,
    count(*) filter (where led) as led,
    count(*) filter (where is_complete) as complete_shown,
    count(*) filter (where is_complete and was_brought) as brought,
    count(*) filter (where is_complete and was_brought and is_decided) as brought_decided,
    count(*) filter (where is_complete and was_brought and is_decided and result = 'win') as wins_brought,
    count(*) filter (where is_complete and not was_brought and is_decided) as benched_decided,
    count(*) filter (where is_complete and not was_brought and is_decided and result = 'win') as wins_benched,
    count(*) filter (where mega_evolved) as mega_evolved
  from pokemon
  group by all
)
select
  per_pokemon.regulation_code,
  per_pokemon.variant_scope as variant,
  per_pokemon.pokemon_key,
  totals.sides // 2 as battles,
  coalesce(totals.complete_sides, 0) // 2 as complete_battles,
  per_pokemon.shown,
  round(per_pokemon.shown::double / totals.sides, 4) as shown_share,
  per_pokemon.led,
  round(per_pokemon.led::double / per_pokemon.shown, 4) as lead_rate,
  per_pokemon.complete_shown,
  per_pokemon.brought,
  round(per_pokemon.brought::double / nullif(per_pokemon.complete_shown, 0), 4) as bring_rate,
  per_pokemon.brought_decided,
  per_pokemon.wins_brought,
  round(per_pokemon.wins_brought::double / nullif(per_pokemon.brought_decided, 0), 4) as win_rate_brought,
  per_pokemon.benched_decided,
  per_pokemon.wins_benched,
  round(per_pokemon.wins_benched::double / nullif(per_pokemon.benched_decided, 0), 4) as win_rate_benched,
  per_pokemon.mega_evolved,
  row_number() over (
    partition by per_pokemon.regulation_code, per_pokemon.variant_scope
    order by per_pokemon.shown desc, per_pokemon.pokemon_key
  ) as shown_rank,
  'Pokémon Showdown replays' as source_name,
  'https://replay.pokemonshowdown.com' as source_url
from per_pokemon
inner join totals
  on totals.regulation_code = per_pokemon.regulation_code
  and totals.variant_scope = per_pokemon.variant_scope
order by regulation_code, variant, shown_rank
