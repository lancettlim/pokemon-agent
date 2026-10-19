{{ config(location='../data/marts/pokemon_set_variants.csv') }}
-- Real sets (docs/upgrade-plan-2027q1.md, P1): the item, ability, nature
-- and four moves that actually appeared together on one team sheet,
-- counted per Pokémon. This replaces the profile's old "most common set",
-- which took the modal item, ability, nature and each move slot
-- independently and so could describe a set nobody ran.
--
-- Two levels, one row each:
--   set_level = 'full'  the exact item + ability + nature + 4-move set
--                       (moves sorted alphabetically, pipe-delimited).
--   set_level = 'core'  item + ability + the set's 3 most common moves
--                       (by this Pokémon's own move usage in the scope),
--                       with nature dropped, so near-identical sets that
--                       differ in one flex move still cluster.
--
-- Only roster slots with a complete sheet count toward a set (an item, an
-- ability, a nature and exactly four moves). share_of_pokemon divides by
-- every roster slot of the Pokémon in the scope, complete or not, so the
-- shares of one Pokémon's sets sum to at most 1 at each level.
--
-- win_rate and a 95% Wilson lower bound come from the W-L records of the
-- teams that ran the set (record_count of them reported one). set_rank
-- orders by team_count, then Wilson bound; only the top 5 per Pokémon,
-- scope and level are kept, since the long tail is one-off sets.
-- example_team_id is one team that ran the set verbatim.
--
-- regulation_scope: one partition per Champions regulation plus 'all',
-- via int_champions_roster_scoped.
with legal_slots as (
  select member.*
  from {{ ref('int_champions_roster_scoped') }} member
  inner join {{ ref('pokemon_stat_champions') }} champions
    on champions.pokemon_key = member.pokemon_key
    and champions.is_legal = true
),
pokemon_totals as (
  select regulation_scope, pokemon_key, count(*) as pokemon_slot_count
  from legal_slots
  group by regulation_scope, pokemon_key
),
complete_slots as (
  select
    regulation_scope,
    pokemon_key,
    team_id,
    item_name,
    ability,
    nature,
    list_sort(list_transform(string_split(moves, '|'), x -> trim(x))) as move_list,
    record_wins,
    record_losses
  from legal_slots
  where item_name is not null
    and ability is not null
    and nature is not null
    and moves is not null
    and len(string_split(moves, '|')) = 4
),
move_ranks as (
  select regulation_scope, pokemon_key, move_name, usage_rank
  from {{ ref('pokemon_move_usage') }}
),
slot_moves as (
  select
    slots.regulation_scope,
    slots.pokemon_key,
    slots.team_id,
    unnest(slots.move_list) as move_name
  from complete_slots slots
),
slot_core_moves as (
  select
    slot_moves.regulation_scope,
    slot_moves.pokemon_key,
    slot_moves.team_id,
    list_sort(list(slot_moves.move_name)) as core_move_list
  from (
    select
      slot_moves.*,
      row_number() over (
        partition by slot_moves.regulation_scope, slot_moves.pokemon_key, slot_moves.team_id
        order by move_ranks.usage_rank nulls last, slot_moves.move_name
      ) as move_order
    from slot_moves
    left join move_ranks
      on move_ranks.regulation_scope = slot_moves.regulation_scope
      and move_ranks.pokemon_key = slot_moves.pokemon_key
      and move_ranks.move_name = slot_moves.move_name
  ) slot_moves
  where move_order <= 3
  group by slot_moves.regulation_scope, slot_moves.pokemon_key, slot_moves.team_id
),
full_sets as (
  select
    regulation_scope,
    pokemon_key,
    'full' as set_level,
    item_name,
    ability,
    nature,
    array_to_string(move_list, '|') as moves,
    count(*) as team_count,
    sum(record_wins) as total_wins,
    sum(record_losses) as total_losses,
    count(*) filter (where record_wins is not null and record_losses is not null) as record_count,
    min(team_id) as example_team_id
  from complete_slots
  group by regulation_scope, pokemon_key, item_name, ability, nature, array_to_string(move_list, '|')
),
core_sets as (
  select
    slots.regulation_scope,
    slots.pokemon_key,
    'core' as set_level,
    slots.item_name,
    slots.ability,
    cast(null as varchar) as nature,
    array_to_string(core.core_move_list, '|') as moves,
    count(*) as team_count,
    sum(slots.record_wins) as total_wins,
    sum(slots.record_losses) as total_losses,
    count(*) filter (
      where slots.record_wins is not null and slots.record_losses is not null
    ) as record_count,
    min(slots.team_id) as example_team_id
  from complete_slots slots
  inner join slot_core_moves core
    on core.regulation_scope = slots.regulation_scope
    and core.pokemon_key = slots.pokemon_key
    and core.team_id = slots.team_id
  group by
    slots.regulation_scope,
    slots.pokemon_key,
    slots.item_name,
    slots.ability,
    array_to_string(core.core_move_list, '|')
),
all_sets as (
  select * from full_sets
  union all
  select * from core_sets
),
scored as (
  select
    all_sets.*,
    totals.pokemon_slot_count,
    round(all_sets.total_wins::double / nullif(all_sets.total_wins + all_sets.total_losses, 0), 4)
      as win_rate,
    all_sets.total_wins::double / nullif(all_sets.total_wins + all_sets.total_losses, 0)
      as win_rate_raw
  from all_sets
  inner join pokemon_totals totals
    on totals.regulation_scope = all_sets.regulation_scope
    and totals.pokemon_key = all_sets.pokemon_key
),
-- z = 1.96, the same Wilson score lower bound pokemon_win_rate_summary uses.
bounded as (
  select
    *,
    case
      when record_count > 0 and win_rate_raw is not null then
        (
          (win_rate_raw + (1.96 * 1.96) / (2 * record_count))
          - 1.96 * sqrt(
            (win_rate_raw * (1 - win_rate_raw) + (1.96 * 1.96) / (4 * record_count)) / record_count
          )
        ) / (1 + (1.96 * 1.96) / record_count)
    end as wilson_lower_bound_raw
  from scored
),
ranked as (
  select
    *,
    row_number() over (
      partition by regulation_scope, pokemon_key, set_level
      order by team_count desc, wilson_lower_bound_raw desc nulls last, moves, item_name
    ) as set_rank
  from bounded
)
select
  regulation_scope,
  pokemon_key,
  set_level,
  set_rank,
  item_name,
  ability,
  nature,
  moves,
  team_count,
  pokemon_slot_count,
  round(team_count::double / pokemon_slot_count, 4) as share_of_pokemon,
  total_wins,
  total_losses,
  record_count,
  win_rate,
  round(greatest(wilson_lower_bound_raw, 0), 4) as wilson_lower_bound,
  example_team_id
from ranked
where set_rank <= 5
order by regulation_scope, pokemon_key, set_level, set_rank
