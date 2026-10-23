-- Warn: every Pokémon in the latest legality snapshot's legal pool has a
-- name in each of the four languages (docs/upgrade-plan-2027q2.md, Q4).
-- All of them did when the names were added; a new form PokéAPI doesn't
-- know yet shows here, and the page falls back to its English name.
{{ config(severity='warn', meta={'category': 'mart_quality', 'table_name': 'pokemon_localised_names'}) }}
with legal as (
  select distinct pokemon_key
  from {{ ref('legality_snapshot') }}
  where is_legal = true
    and snapshot_date = (select max(snapshot_date) from {{ ref('legality_snapshot') }})
),
expected as (
  select legal.pokemon_key, language.language
  from legal
  cross join (values ('ja'), ('es'), ('fr'), ('de')) as language(language)
)
select expected.*
from expected
left join {{ ref('pokemon_localised_names') }} names
  on names.pokemon_key = expected.pokemon_key
  and names.language = expected.language
where names.pokemon_key is null
