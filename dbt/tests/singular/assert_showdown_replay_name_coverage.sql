-- Warn: >=99% of the Pokémon shown at team preview in the sampled Showdown
-- replays (docs/upgrade-plan-2027q2.md, S3) resolve to a pokemon_key, by
-- slot. A mart check, not a release gate: replays feed the ladder marts
-- only. An unmapped name drops out of the bring rates; the fix is a row in
-- dbt/seeds/smogon_name_to_pokeapi_form.csv. 98.9% resolved on the first
-- sample before cosmetic patterns were mapped, 100% after.
--
-- Zero staged rows reports 0 coverage and fails, as the other coverage
-- gates do, rather than passing vacuously.
{{ config(severity='warn', fail_calc='max(coverage_bps)', warn_if='<9900', meta={'category': 'mart_quality', 'table_name': 'ladder_bring_rate'}) }}
select
  case
    when count(*) = 0 then 0
    else round(count(pokemon_key)::double / count(*) * 10000)::integer
  end as coverage_bps
from {{ ref('int_ladder_battle_pokemon') }}
