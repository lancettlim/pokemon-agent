-- One row per Pokémon a side showed at team preview in a sampled Showdown
-- ladder battle (docs/upgrade-plan-2027q2.md, S3; docs/roadmap.md, Phase
-- 4's `battle_pokemon` grain): whether it entered the battle, led, or Mega
-- Evolved, and how its side did. Names are the preview's, so a Mega counts
-- with its base Pokémon; pokemon_key comes from int_smogon_ladder_names.
with team as (
  select
    sides.replay_id,
    sides.side,
    sides.regulation_code,
    sides.variant,
    sides.result,
    sides.is_complete_side,
    sides.brought,
    sides.leads,
    sides.mega_evolved,
    sides.lead_count,
    unnest(string_split(sides.team, '|')) as showdown_name,
    generate_subscripts(string_split(sides.team, '|'), 1) as slot
  from {{ ref('int_ladder_battle_side') }} sides
)
select
  team.replay_id,
  team.side,
  team.slot,
  team.regulation_code,
  team.variant,
  team.showdown_name,
  names.pokemon_key,
  list_contains(string_split(coalesce(team.brought, ''), '|'), team.showdown_name) as was_brought,
  list_contains(string_split(coalesce(team.leads, ''), '|'), team.showdown_name) as led,
  list_contains(string_split(coalesce(team.mega_evolved, ''), '|'), team.showdown_name) as mega_evolved,
  team.lead_count,
  team.result,
  battles.is_decided,
  battles.is_complete
from team
inner join {{ ref('int_ladder_battle') }} battles
  on battles.replay_id = team.replay_id
left join {{ ref('int_smogon_ladder_names') }} names
  on names.smogon_name = team.showdown_name
