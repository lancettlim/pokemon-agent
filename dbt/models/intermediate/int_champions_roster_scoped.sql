-- int_champions_roster with a regulation_scope dimension, for marts that
-- report per regulation (docs/upgrade-plan-2026q4.md, A3).
--
-- Every roster row appears twice: once under its own regulation_code
-- ("m-a", "m-b", "m-c", ...) and once under the roll-up scope 'all'. A mart
-- that groups by regulation_scope then yields one partition per regulation
-- plus an all-Champions partition, each ranked independently, without
-- every mart repeating the union. The 'all' partition is exactly what these
-- marts reported before the dimension existed.
select
  roster.*,
  roster.regulation_code as regulation_scope
from {{ ref('int_champions_roster') }} roster
union all
select
  roster.*,
  'all' as regulation_scope
from {{ ref('int_champions_roster') }} roster
