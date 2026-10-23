{{ config(location='../data/marts/online_upcoming_events.csv') }}
-- Upcoming Limitless online tournaments (docs/upgrade-plan-2027q2.md, list
-- #31): the newest snapshot's list, from the moment it was read on. The
-- dashboard shows them in the visitor's own time zone and drops any that
-- have started since. Organiser-run events, a different population from
-- official ones; no player appears here.
select
  upcoming.tournament_id,
  upcoming.tournament_name,
  upcoming.regulation_code,
  upcoming.tournament_format,
  -- ISO-8601 with a Z, which every browser's Date parses (DuckDB's own
  -- timestamptz text, "2026-10-23 12:00:00+00", isn't in every one).
  strftime(timezone('UTC', cast(upcoming.starts_at_utc as timestamptz)), '%Y-%m-%dT%H:%M:%SZ') as starts_at_utc,
  case upcoming.platform
    when 'SWITCH' then 'Switch'
    when 'SIM' then 'Showdown'
    else upcoming.platform
  end as platform,
  upcoming.organizer_name,
  cast(upcoming.registrations as integer) as registrations,
  cast(upcoming.player_cap as integer) as player_cap,
  cast(upcoming.registration_open as boolean) as registration_open,
  upcoming.source_name,
  upcoming.source_url,
  upcoming.source_record_id,
  strftime(timezone('UTC', cast(upcoming.extracted_at_utc as timestamptz)), '%Y-%m-%dT%H:%M:%SZ') as extracted_at_utc,
  upcoming.dataset_version
from {{ ref('int_limitless_play_upcoming_latest') }} upcoming
where cast(upcoming.starts_at_utc as timestamptz) >= cast(upcoming.extracted_at_utc as timestamptz) - interval 3 hour
order by starts_at_utc, tournament_id
