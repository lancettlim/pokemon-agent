-- Full history of raw Smogon ladder checks and counters snapshots
-- (docs/upgrade-plan-2027q2.md, S2).
select
  *,
  cast(extracted_at_utc as date) as snapshot_date
from {{ source('staging', 'smogon_ladder_counters') }}
