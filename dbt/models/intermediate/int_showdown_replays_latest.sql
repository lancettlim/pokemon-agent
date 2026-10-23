-- The current point-in-time stg_showdown_replays snapshot.
select *
from {{ ref('stg_showdown_replays') }}
where snapshot_date = (select max(snapshot_date) from {{ ref('stg_showdown_replays') }})
