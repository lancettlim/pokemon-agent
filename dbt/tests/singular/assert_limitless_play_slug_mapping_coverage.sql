-- Gate: >=85% of staged Limitless online team-sheet slots resolve to a
-- pokemon_key (docs/upgrade-plan-2027q2.md, S1). The online platform uses
-- limitlessvgc.com's slugs and the same seeds, so it gets
-- assert_limitless_slug_mapping_coverage.sql's bar. Online players bring a
-- wider pool than official top cuts, which is why
-- int_limitless_play_mapped falls back to the PokéAPI form of the same
-- name; a slug neither resolves is dropped, and this gate catches the day
-- that stops being rare.
--
-- Zero staged rows reports 0 coverage and fails, as the other coverage
-- gates do, rather than passing vacuously.
-- fail_calc reports basis points (100% = 10000 bps); see
-- assert_limitless_slug_mapping_coverage.sql.
{{ config(fail_calc='max(coverage_bps)', error_if='<8500', warn_if='<8500', meta={'category': 'coverage', 'check_name': 'limitless_play_slug_mapping_coverage', 'description': 'Share of staged Limitless online team-sheet slots resolved to a canonical pokemon_key', 'threshold': '>=0.85'}) }}
select
  case
    when total.slot_count = 0 then 0
    else round(mapped.slot_count::double / total.slot_count * 10000)::integer
  end as coverage_bps
from (
  select count(*) as slot_count
  from {{ ref('int_limitless_play_latest') }}
) total
cross join (
  select count(*) as slot_count
  from {{ ref('int_limitless_play_mapped') }}
) mapped
