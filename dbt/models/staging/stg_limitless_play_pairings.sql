-- Full history of raw Limitless online-tournament pairings snapshots
-- (docs/upgrade-plan-2027q2.md, S1).
select
  *,
  cast(extracted_at_utc as date) as snapshot_date
from {{ source('staging', 'limitless_play_pairings') }}
