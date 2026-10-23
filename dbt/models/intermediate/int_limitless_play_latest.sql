-- The current point-in-time stg_limitless_play snapshot, so a multi-snapshot
-- staging history doesn't change downstream key contracts.
select *
from {{ ref('stg_limitless_play') }}
where snapshot_date = (select max(snapshot_date) from {{ ref('stg_limitless_play') }})
