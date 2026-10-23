-- One row per Pokémon on a normalized tournament team, mapping
-- stg_munchstats.pokemon_name to pokemon_key/pokemon_id via the
-- munchstats_name_to_pokeapi_form seed (dataset-spec.md's MunchStats
-- mapping rule: "Map roster Pokémon names to canonical pokemon_id and
-- pokemon_key"). Rows whose name doesn't resolve are dropped — per
-- dataset-spec.md, unmapped rows must not ship in release outputs.
--
-- Online team sheets (docs/upgrade-plan-2027q2.md, S1) follow, already
-- resolved by int_limitless_play_mapped.
select
  source.source_record_id as team_member_id,
  source.team_id,
  source.event_id,
  pokemon.pokemon_key,
  pokemon.pokemon_id,
  source.slot_number,
  source.item_name,
  source.ability,
  source.tera_type,
  source.nature,
  source.moves,
  source.source_name,
  source.source_url,
  source.source_record_id,
  source.extracted_at_utc,
  source.dataset_version
from {{ ref('int_munchstats_deduped') }} source
inner join {{ ref('munchstats_name_to_pokeapi_form') }} seed_map
  on seed_map.munchstats_pokemon_name = source.pokemon_name
inner join {{ ref('pokemon') }} pokemon
  on pokemon.form_name = seed_map.pokeapi_form_name
union all
select
  source_record_id as team_member_id,
  team_id,
  event_id,
  pokemon_key,
  pokemon_id,
  slot_number,
  item_name,
  ability,
  tera_type,
  nature,
  moves,
  source_name,
  source_url,
  source_record_id,
  extracted_at_utc,
  dataset_version
from {{ ref('int_limitless_play_mapped') }}
