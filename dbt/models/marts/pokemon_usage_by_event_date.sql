{{ config(location='../data/marts/pokemon_usage_by_event_date.csv') }}
-- Usage over time from tournament_event.event_date (backlog.md #6): real
-- meta-over-time WITHOUT waiting on Blocker A (multi-snapshot extraction
-- history) -- events already carry dates spanning the tournament history,
-- so usage trends can be computed across events rather than across
-- extraction snapshots. Semantically distinct from a snapshot-date trend:
-- this shows how usage shifted across tournaments actually played, not
-- across when this dataset happened to be re-extracted.
--
-- usage_share/usage_rank are computed within each event_date partition
-- (mirroring pokemon_usage_summary's event_tier partitioning), so a
-- Pokémon's share reflects its standing among that date's tournaments
-- specifically.
--
-- team_share (docs/upgrade-plan-2027q2.md, V1): the share of that date's
-- teams that brought the Pokémon.
with date_teams as (
  select event.event_date, count(distinct member.team_id) as team_count
  from {{ ref('int_champions_roster_official') }} member
  inner join {{ ref('tournament_event') }} event
    on event.event_id = member.event_id
  where event.event_date is not null
  group by event.event_date
),
counted as (
  select
    member.pokemon_key,
    event.event_date,
    count(*) as usage_count
  from {{ ref('int_champions_roster_official') }} member
  inner join {{ ref('pokemon_stat_champions') }} champions
    on champions.pokemon_key = member.pokemon_key
    and champions.is_legal = true
  inner join {{ ref('tournament_event') }} event
    on event.event_id = member.event_id
  where event.event_date is not null
  group by member.pokemon_key, event.event_date
)
select
  counted.pokemon_key,
  counted.event_date,
  counted.usage_count,
  round(
    counted.usage_count::double / sum(counted.usage_count) over (partition by counted.event_date),
    4
  ) as usage_share,
  round(counted.usage_count::double / date_teams.team_count, 4) as team_share,
  row_number() over (partition by counted.event_date order by counted.usage_count desc, counted.pokemon_key) as usage_rank
from counted
inner join date_teams
  on date_teams.event_date = counted.event_date
order by counted.event_date, counted.usage_count desc
