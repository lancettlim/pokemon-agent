-- One row per side of a sampled Showdown ladder battle (docs/upgrade-plan-
-- 2027q2.md, S3; docs/roadmap.md, Phase 4's `battle_side` grain): its
-- result, how many Pokémon it showed and how many entered the battle.
-- A side is complete when every Pokémon it brought was revealed
-- (brought_count = team_size): only then do its benched Pokémon really
-- stay at home rather than wait unrevealed in the back.
select
  replay_id,
  side,
  regulation_code,
  variant,
  result,
  cast(team_size as integer) as team_size,
  team,
  brought,
  leads,
  mega_evolved,
  len(string_split(team, '|')) as team_count,
  case when coalesce(brought, '') = '' then 0 else len(string_split(brought, '|')) end as brought_count,
  case when coalesce(leads, '') = '' then 0 else len(string_split(leads, '|')) end as lead_count,
  coalesce(brought, '') != ''
    and len(string_split(brought, '|')) = cast(team_size as integer) as is_complete_side
from {{ ref('int_showdown_replays_latest') }}
