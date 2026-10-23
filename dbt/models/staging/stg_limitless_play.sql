-- Full history of raw Limitless online-tournament staging snapshots
-- (docs/upgrade-plan-2027q2.md, S1). See stg_pokeapi.sql's header for the
-- snapshot_date/history-vs-latest design.
select
  *,
  cast(extracted_at_utc as date) as snapshot_date
from {{ source('staging', 'limitless_play') }}
