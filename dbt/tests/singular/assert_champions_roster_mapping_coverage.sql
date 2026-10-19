-- Gate: >=99% of Champions-format roster slots in the latest MunchStats
-- snapshot resolve to a canonical pokemon_key through
-- munchstats_name_to_pokeapi_form.
--
-- tournament_team_member_mapping_coverage measures every staged slot,
-- standard VGC included, at a 90% bar. Champions events are a minority of
-- that corpus, so a whole new regulation's Megas can go unmapped without
-- moving it: the 2026-10 refresh found 4,245 unmapped Champions slots
-- (Mega Raichu Y alone 1,017, Mega Salamence 946) while that gate still
-- passed. This one is scoped to Champions events, where every slot should
-- map, so new species are caught the day they first appear.
{{ config(fail_calc='max(coverage_bps)', error_if='<9900', warn_if='<9900', meta={'category': 'coverage', 'check_name': 'champions_roster_mapping_coverage', 'description': 'Share of Champions-format MunchStats roster slots resolved to a canonical pokemon_key', 'threshold': '>=0.99'}) }}
with champions_slots as (
  select source.pokemon_name
  from {{ ref('int_munchstats_latest') }} source
  inner join {{ ref('champions_regulations') }} regulation
    on regulation.munchstats_format = source.event_format
)
select
  case
    when count(*) = 0 then 0
    else round(
      count(*) filter (
        where pokemon_name in (select munchstats_pokemon_name from {{ ref('munchstats_name_to_pokeapi_form') }})
      )::double / count(*) * 10000
    )::integer
  end as coverage_bps
from champions_slots
