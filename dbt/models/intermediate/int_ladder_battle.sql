-- One row per sampled Showdown ladder battle (docs/upgrade-plan-2027q2.md,
-- S3; docs/roadmap.md, Phase 4's `battle` grain). is_complete: both sides
-- revealed all the Pokémon they brought, the battles bring rates and
-- win-when-brought figures read; is_decided: someone won (no tie).
select
  replays.replay_id,
  any_value(replays.format_id) as format_id,
  any_value(replays.regulation_code) as regulation_code,
  any_value(replays.variant) as variant,
  any_value(replays.uploaded_at_utc) as uploaded_at_utc,
  any_value(try_cast(nullif(cast(replays.rating as varchar), '') as integer)) as rating,
  any_value(cast(replays.turns as integer)) as turns,
  max(case when replays.result = 'win' then replays.side end) as winner_side,
  bool_and(replays.result != 'tie') as is_decided,
  bool_and(sides.is_complete_side) as is_complete,
  count(*) as side_count,
  any_value(replays.source_name) as source_name,
  any_value(replays.extracted_at_utc) as extracted_at_utc,
  any_value(replays.dataset_version) as dataset_version
from {{ ref('int_showdown_replays_latest') }} replays
inner join {{ ref('int_ladder_battle_side') }} sides
  on sides.replay_id = replays.replay_id
  and sides.side = replays.side
group by replays.replay_id
