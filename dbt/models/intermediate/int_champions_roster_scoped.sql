-- int_champions_roster with a regulation_scope dimension, for marts that
-- report per regulation (docs/upgrade-plan-2026q4.md, A3).
--
-- Every roster row appears twice: once under its own regulation_code
-- ("m-a", "m-b", "m-c", ...) and once under the roll-up scope 'all'. A mart
-- that groups by regulation_scope then yields one partition per regulation
-- plus an all-Champions partition, each ranked independently, without
-- every mart repeating the union. The 'all' partition is exactly what these
-- marts reported before the dimension existed.
--
-- Populations (docs/upgrade-plan-2027q2.md, S1): official rows keep the
-- scopes above ("m-c", 'all'), so every official figure is unchanged.
-- Limitless online rows get their own, suffixed ":online" ("m-c:online",
-- "all:online"), and both together ":combined" -- the dashboard's
-- Official / Online / All switch. A mart that groups by regulation_scope
-- gets all three without knowing they exist; scope_population names which
-- one a row belongs to, for a mart that should only report one (player
-- records are official-only: handles never join official identities).
--
-- A ":combined" scope exists only for a regulation with online rows, and
-- 'all:combined' only once any exist: without online data it would repeat
-- the official partition row for row.
with online_regulations as (
  select distinct regulation_code
  from {{ ref('int_champions_roster') }}
  where population = 'online'
)
select
  roster.*,
  case roster.population when 'official' then roster.regulation_code
    else roster.regulation_code || ':online' end as regulation_scope,
  roster.population as scope_population
from {{ ref('int_champions_roster') }} roster
union all
select
  roster.*,
  case roster.population when 'official' then 'all' else 'all:online' end as regulation_scope,
  roster.population as scope_population
from {{ ref('int_champions_roster') }} roster
union all
select
  roster.*,
  roster.regulation_code || ':combined' as regulation_scope,
  'combined' as scope_population
from {{ ref('int_champions_roster') }} roster
where roster.regulation_code in (select regulation_code from online_regulations)
union all
select
  roster.*,
  'all:combined' as regulation_scope,
  'combined' as scope_population
from {{ ref('int_champions_roster') }} roster
where exists (select 1 from online_regulations)
