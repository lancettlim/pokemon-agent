{{ config(location='../data/marts/pokemon_archetype_usage.csv') }}
-- Archetype Explorer member-level drill-down: joins the curated
-- dbt/seeds/archetype_pokemon_map.csv seed to real usage/win-rate data so
-- each archetype's members are shown with actual tournament performance,
-- not just curated membership. usage_share/win_rate/record_count are
-- nullable -- a curated member may not have any recorded tournament
-- appearances yet, mirroring pokemon_champions_profile's nullable-usage
-- convention.
select
  map.archetype_key,
  map.archetype_name,
  map.pokemon_key,
  usage.usage_share,
  win.win_rate,
  win.record_count,
  row_number() over (
    partition by map.archetype_key
    order by usage.usage_share desc nulls last
  ) as member_rank
from {{ ref('archetype_pokemon_map') }} map
left join (
  select * from {{ ref('pokemon_usage_summary') }}
  where event_tier is null and regulation_scope = 'all'
) usage
  on usage.pokemon_key = map.pokemon_key
left join {{ ref('pokemon_win_rate_summary') }} win
  on win.pokemon_key = map.pokemon_key
  and win.regulation_scope = 'all'
order by map.archetype_key, member_rank
