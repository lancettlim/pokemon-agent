-- Full history of raw Showdown ladder replay snapshots (docs/upgrade-plan-
-- 2027q2.md, S3). Each snapshot already holds every battle kept, so the
-- latest one is the whole sample.
select
  *,
  cast(extracted_at_utc as date) as snapshot_date
from {{ source('staging', 'showdown_replays') }}
