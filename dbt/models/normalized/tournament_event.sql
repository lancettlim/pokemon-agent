-- Normalized tournament metadata from MunchStats: one row per event_id.
--
-- event_format is what separates Champions events from the standard VGC
-- events MunchStats indexes alongside them. It matters more than it looks:
-- without it every usage and win-rate mart silently blends two different
-- games. It also explains the "~17% nature coverage" this repo documented
-- as a MunchStats data gap -- Champions team sheets report nature and the
-- format has no Tera mechanic, standard VGC is the exact reverse, and
-- Champions events are 17.2% of staged roster slots. Measured, not
-- inferred: nature coverage is 100% within Champions and 0% outside it.
-- event_name/event_date/source_name/source_url are constant across a given
-- event's roster rows in stg_munchstats, so distinct collapses them safely.
--
-- regulation_code is the Champions regulation set the event was played
-- under ("m-a", "m-b", "m-c"), resolved exactly from event_format through
-- the champions_regulations seed. It is null for standard-VGC events, which
-- have no Champions regulation. assert_champions_formats_registered fails
-- the build if a Champions-format event resolves to no regulation.
with events as (
  select distinct
    event_id,
    event_name,
    event_date,
    event_tier,
    event_format,
    source_name,
    source_url,
    extracted_at_utc,
    dataset_version
  from {{ ref('int_munchstats_deduped') }}
)
select
  events.event_id,
  events.event_name,
  events.event_date,
  events.event_tier,
  events.event_format,
  regulation.regulation_code,
  events.source_name,
  events.source_url,
  events.event_id as source_record_id,
  events.extracted_at_utc,
  events.dataset_version
from events
left join {{ ref('champions_regulations') }} regulation
  on regulation.munchstats_format = events.event_format
