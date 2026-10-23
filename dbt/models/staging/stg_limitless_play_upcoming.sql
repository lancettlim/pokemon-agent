-- Full history of raw Limitless upcoming online-tournament snapshots
-- (docs/upgrade-plan-2027q2.md, list #31).
select
  *,
  cast(extracted_at_utc as date) as snapshot_date
from {{ source('staging', 'limitless_play_upcoming') }}
