-- Every Showdown display name in the latest Smogon ladder snapshot
-- (docs/upgrade-plan-2027q2.md, S2) resolved to a pokemon_key. Showdown
-- names are the ones MunchStats uses, so munchstats_name_to_pokeapi_form
-- resolves most of them; a name only the ladder has falls back to the slug
-- rule that seed was built with (lowercase, apostrophes and periods
-- dropped, spaces to hyphens: "Farfetch'd" -> "farfetchd", "Mr. Mime" ->
-- "mr-mime"), and smogon_name_to_pokeapi_form overrides the two that rule
-- gets wrong (a bare "Gourgeist", and "Meowstic-M-Mega"). A name none of
-- them resolves is left unmapped; assert_smogon_ladder_name_coverage
-- watches the share.
with names as (
  select distinct pokemon_name as smogon_name from {{ ref('int_smogon_ladder_latest') }}
  union
  select distinct counter_name from {{ ref('int_smogon_ladder_counters_latest') }}
  union
  select distinct pokemon_name from {{ ref('int_smogon_ladder_counters_latest') }}
  union
  select distinct pokemon_name from {{ ref('int_smogon_ladder_spreads_latest') }}
),
resolved as (
  select
    names.smogon_name,
    coalesce(
      smogon_seed.pokeapi_form_name,
      munchstats_seed.pokeapi_form_name,
      regexp_replace(
        lower(replace(replace(trim(names.smogon_name), '''', ''), '.', '')), '\s+', '-', 'g'
      )
    ) as form_name
  from names
  left join {{ ref('smogon_name_to_pokeapi_form') }} smogon_seed
    on smogon_seed.smogon_pokemon_name = names.smogon_name
  left join {{ ref('munchstats_name_to_pokeapi_form') }} munchstats_seed
    on munchstats_seed.munchstats_pokemon_name = names.smogon_name
)
select
  resolved.smogon_name,
  pokemon.pokemon_key,
  pokemon.pokemon_name
from resolved
left join {{ ref('pokemon') }} pokemon
  on pokemon.form_name = resolved.form_name
