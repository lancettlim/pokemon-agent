-- The current point-in-time stg_limitless_play_upcoming snapshot.
select *
from {{ ref('stg_limitless_play_upcoming') }}
where snapshot_date = (select max(snapshot_date) from {{ ref('stg_limitless_play_upcoming') }})
