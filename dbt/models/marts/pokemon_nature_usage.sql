{{ config(location='../data/marts/pokemon_nature_usage.csv') }}
-- Nature drill-down for the Pokémon Profile's "most common set" card
-- (docs/upgrade-plan-2026q4.md, B4): usage count and nature_share (that
-- count's fraction of the Pokémon's own roster slots with a reported
-- nature) per Pokémon x nature, restricted to the current legal pool and
-- ranked within each Pokémon. Champions team sheets report nature for
-- every slot, so within Champions this is complete; there is still no EV
-- or IV data anywhere (see CLAUDE.md).
--
-- regulation_scope (docs/upgrade-plan-2026q4.md, A3): one partition per
-- Champions regulation ("m-a", "m-b", "m-c", ...) plus the roll-up 'all',
-- each computed and ranked independently, via int_champions_roster_scoped.
with counted as (
  select
    member.regulation_scope,
    member.pokemon_key,
    member.nature,
    count(*) as usage_count
  from {{ ref('int_champions_roster_scoped') }} member
  inner join {{ ref('pokemon_stat_champions') }} champions
    on champions.pokemon_key = member.pokemon_key
    and champions.is_legal = true
  where member.nature is not null
  group by member.regulation_scope, member.pokemon_key, member.nature
)
select
  regulation_scope,
  pokemon_key,
  nature,
  usage_count,
  round(
    usage_count::double / sum(usage_count) over (partition by regulation_scope, pokemon_key),
    4
  ) as nature_share,
  row_number() over (
    partition by regulation_scope, pokemon_key
    order by usage_count desc, nature
  ) as usage_rank
from counted
order by regulation_scope, pokemon_key, usage_count desc
