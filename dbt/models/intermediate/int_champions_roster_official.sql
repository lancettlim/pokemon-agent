-- The official population of int_champions_roster: Champions events from
-- MunchStats and RK9, without Limitless online events
-- (docs/upgrade-plan-2027q2.md, S1). Every unscoped roster-derived mart
-- reads this, so its figures stay exactly the official ones; marts that
-- report per population read int_champions_roster_scoped instead.
select *
from {{ ref('int_champions_roster') }}
where population = 'official'
