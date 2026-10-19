-- Gate: every Champions-format event MunchStats indexes must resolve to a
-- row in the champions_regulations seed (docs/upgrade-plan-2026q4.md, A1).
--
-- This is the drift alarm for a new regulation set. The pipeline used to
-- pin Champions to the single Reg M-A format. When M-B (the 2026 World
-- Championships) and then M-C appeared upstream, they were silently
-- filtered out for four months because nothing noticed a Champions format
-- it didn't recognise. MunchStats is extracted unfiltered (standard VGC
-- included), so a new `gen9champions*` format reaches staging the day it
-- is indexed, and this test fails until the seed gains a row for it.
-- Each failing row names the unregistered format.
{{ config(meta={'category': 'referential_integrity', 'check_name': 'champions_formats_registered'}) }}
select distinct event.event_format
from {{ ref('tournament_event') }} event
where event.event_format like 'gen9champions%'
  and event.regulation_code is null
