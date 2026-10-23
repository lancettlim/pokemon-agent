{{ config(location='../data/marts/pokemon_move_usage.csv') }}
-- Move drill-down (docs/todo.md's Phase 3 tier/record/item follow-up item;
-- docs/prd.md's "Drill-down by Pokémon, team core, move, and item usage"):
-- usage count per Pokémon x move, unnesting tournament_team_member's
-- pipe-delimited moves list, restricted to the current legal pool and to
-- roster slots that reported a move list.
--
-- move_share is usage_count's fraction of that Pokémon's own total move
-- rows (dashboard "percentages, not raw counts" ask), the same
-- share-of-own-total pattern pokemon_usage_summary.usage_share and
-- pokemon_item_usage.item_share use.
--
-- move_type/power/accuracy/category/priority/pp/short_effect are joined
-- from move_detail (PokéAPI move detail) for the Pokémon Profile's Moves
-- section and the Matchup tab's damage calculator; all nullable when that
-- lookup didn't resolve.
--
-- regulation_scope (docs/upgrade-plan-2026q4.md, A3): one partition per
-- Champions regulation ("m-a", "m-b", "m-c", ...) plus the roll-up 'all',
-- each computed and ranked independently, via int_champions_roster_scoped.
with counted as (
  select
    member.regulation_scope,
    member.pokemon_key,
    trim(move.move_name) as move_name,
    count(*) as usage_count
  from {{ ref('int_champions_roster_scoped') }} member
  inner join {{ ref('pokemon_stat_champions') }} champions
    on champions.pokemon_key = member.pokemon_key
    and champions.is_legal = true
  , unnest(string_split(member.moves, '|')) as move(move_name)
  where member.moves is not null
  group by member.regulation_scope, member.pokemon_key, trim(move.move_name)
)
select
  counted.regulation_scope,
  counted.pokemon_key,
  counted.move_name,
  move_detail.move_type,
  move_detail.power,
  move_detail.accuracy,
  move_detail.category,
  move_detail.priority,
  move_detail.pp,
  move_detail.short_effect,
  counted.usage_count,
  round(
    counted.usage_count::double / sum(counted.usage_count) over (partition by counted.regulation_scope, counted.pokemon_key),
    4
  ) as move_share,
  row_number() over (
    partition by counted.regulation_scope, counted.pokemon_key
    order by counted.usage_count desc, counted.move_name
  ) as usage_rank
from counted
left join {{ ref('move_detail') }} move_detail
  on move_detail.move_name = counted.move_name
order by counted.regulation_scope, counted.pokemon_key, counted.usage_count desc
