-- Full history of PokéAPI localised-name snapshots
-- (docs/upgrade-plan-2027q2.md, Q4).
select
  *,
  cast(extracted_at_utc as date) as snapshot_date
from {{ source('staging', 'pokeapi_names') }}
