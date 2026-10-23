-- The current point-in-time stg_pokeapi_names snapshot.
select *
from {{ ref('stg_pokeapi_names') }}
where snapshot_date = (select max(snapshot_date) from {{ ref('stg_pokeapi_names') }})
