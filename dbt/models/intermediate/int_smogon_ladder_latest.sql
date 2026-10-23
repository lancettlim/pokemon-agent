-- The current point-in-time stg_smogon_ladder snapshot.
select *
from {{ ref('stg_smogon_ladder') }}
where snapshot_date = (select max(snapshot_date) from {{ ref('stg_smogon_ladder') }})
