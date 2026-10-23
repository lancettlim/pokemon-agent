-- The current point-in-time stg_smogon_ladder_counters snapshot.
select *
from {{ ref('stg_smogon_ladder_counters') }}
where snapshot_date = (select max(snapshot_date) from {{ ref('stg_smogon_ladder_counters') }})
