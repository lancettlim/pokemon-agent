{{ config(location='../data/marts/pokemon_localised_names.csv') }}
-- Each Pokémon's name in Japanese, Spanish, French and German
-- (docs/upgrade-plan-2027q2.md, Q4), for the dashboard's name-language
-- switch: one row per pokemon_key and language. Names only; numbers and
-- copy stay in English, and Portuguese uses the English names, as the
-- Brazilian games do. name_rule says whether PokéAPI published the name or
-- pipelines/extract/pokeapi.py's localised_name composed it.
select
  pokemon.pokemon_key,
  names.language,
  names.localised_name,
  names.name_rule
from {{ ref('int_pokeapi_names_latest') }} names
inner join {{ ref('pokemon') }} pokemon
  on pokemon.form_name = names.form_name
order by pokemon.pokemon_key, names.language
