-- Warn: >=99% of the latest Smogon ladder snapshot's usage rows resolve to
-- a pokemon_key (docs/upgrade-plan-2027q2.md, S2). A mart check, not a
-- release gate: ladder data feeds the ladder marts only, never a release
-- entity, so an unmapped name drops that Pokémon from the ladder lens
-- rather than stopping a release. int_smogon_ladder_names
-- resolved 333 of 333 names when the source was added; a new Mega or form
-- Showdown names differently from PokéAPI is the expected failure, fixed
-- with a row in dbt/seeds/smogon_name_to_pokeapi_form.csv.
--
-- Zero staged rows reports 0 coverage and fails, as the other coverage
-- gates do, rather than passing vacuously.
-- fail_calc reports basis points (100% = 10000 bps); see
-- assert_limitless_slug_mapping_coverage.sql.
{{ config(severity='warn', fail_calc='max(coverage_bps)', warn_if='<9900', meta={'category': 'mart_quality', 'table_name': 'ladder_pokemon_usage'}) }}
select
  case
    when count(*) = 0 then 0
    else round(count(names.pokemon_key)::double / count(*) * 10000)::integer
  end as coverage_bps
from {{ ref('int_smogon_ladder_latest') }} ladder
left join {{ ref('int_smogon_ladder_names') }} names
  on names.smogon_name = ladder.pokemon_name
