-- Cross-check (docs/upgrade-plan-2027q2.md, E1): the Day 2 field that
-- int_event_phases reads off RK9's round structure should match the
-- players Limitless VGC publishes team lists for, since Limitless lists
-- the Day 2 cut and nobody else. Measured when this was written: Worlds
-- 2026 57 and 57, NAIC 2026 156 and 156, Turin 135 and 135, Indianapolis
-- 143 and 145 (two Day 2 players without a resolved roster).
--
-- One row per event where they differ by more than five players and 5%.
-- Events Limitless has no lists for are skipped. severity=warn and a mart
-- category: a mismatch says the round-structure rule needs a look (a new
-- event format, say), not that a release must stop.
{{ config(severity='warn', meta={'category': 'mart_quality', 'table_name': 'pokemon_event_phase_usage'}) }}
with derived as (
  select event_id, count(*) filter (where reached_day2) as day2_teams
  from {{ ref('int_event_team_phases') }}
  where event_has_day2
  group by event_id
),
listed as (
  select rk9_event_id as event_id, count(distinct player_name) as listed_players
  from {{ ref('int_limitless_latest') }}
  where rk9_event_id is not null
  group by rk9_event_id
)
select derived.event_id, derived.day2_teams, listed.listed_players
from derived
inner join listed
  on listed.event_id = derived.event_id
where abs(derived.day2_teams - listed.listed_players) > 5
  and abs(derived.day2_teams - listed.listed_players) > 0.05 * listed.listed_players
