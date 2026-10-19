{{ config(meta={'category': 'mart_quality', 'table_name': 'pokemon_set_variants'}) }}
-- docs/upgrade-plan-2027q1.md, P1: every full set listed must appear
-- verbatim on its example team's sheet -- same Pokémon, item, ability,
-- nature and the same four moves -- so the profile never shows a set
-- nobody ran.
with sheets as (
  select
    team_id,
    pokemon_key,
    item_name,
    ability,
    nature,
    array_to_string(list_sort(list_transform(string_split(moves, '|'), x -> trim(x))), '|') as moves
  from {{ ref('tournament_team_member') }}
)
select sets.*
from {{ ref('pokemon_set_variants') }} sets
left join sheets
  on sheets.team_id = sets.example_team_id
  and sheets.pokemon_key = sets.pokemon_key
  and sheets.item_name = sets.item_name
  and sheets.ability = sets.ability
  and sheets.nature = sets.nature
  and sheets.moves = sets.moves
where sets.set_level = 'full'
  and sheets.team_id is null
