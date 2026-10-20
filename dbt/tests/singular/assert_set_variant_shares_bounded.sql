{{ config(meta={'category': 'mart_quality', 'table_name': 'pokemon_set_variants'}) }}
-- docs/upgrade-plan-2027q1.md, P1: one Pokémon's set shares can never add
-- up to more than all of its roster slots, at either set level. Only the
-- top 5 sets are kept, so the sum is usually well below 1. The tolerance
-- is the rounding bound: each share is rounded to 4 places, so five of
-- them can overshoot by up to 5 x 0.00005.
select regulation_scope, pokemon_key, set_level, sum(share_of_pokemon) as total_share
from {{ ref('pokemon_set_variants') }}
group by regulation_scope, pokemon_key, set_level
having sum(share_of_pokemon) > 1.00025
