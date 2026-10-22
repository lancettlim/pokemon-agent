{{ config(location='../data/marts/tournament_event_summary.csv') }}
-- One row per Champions event (docs/upgrade-plan-2027q1.md, C1 and U2):
-- the event index, each event page's header, and the "5 events · 3,770
-- teams" sample-size KPI all read this, so the page always says how much
-- data a figure rests on.
--
-- Event grain, so it carries the event's own regulation_code rather than a
-- regulation_scope partition: an event belongs to exactly one regulation,
-- and the 'all' scope is simply every row.
--
-- team_count counts teams with at least one Champions roster row;
-- recorded_team_count those with a reported W-L record. match_count is
-- decided Masters matches from RK9 pairings (0 where RK9 has no pairings
-- for the event). The winner columns come from the placement-1 team, and
-- are null for an event whose standings aren't published yet.
-- pairings_url is the RK9 pairings page the rk9 extractor reads, set only
-- when RK9 published pairings for the event.
with teams as (
  select
    roster.event_id,
    roster.team_id,
    any_value(roster.player_id) as player_id,
    any_value(roster.player_name) as player_name,
    any_value(roster.player_country) as player_country,
    any_value(roster.placement) as placement,
    any_value(roster.record_wins) as record_wins,
    any_value(roster.record_losses) as record_losses,
    string_agg(roster.pokemon_key, '|' order by roster.slot_number) as pokemon_keys
  from {{ ref('int_champions_roster_official') }} roster
  group by roster.event_id, roster.team_id
),
team_counts as (
  select
    event_id,
    count(*) as team_count,
    count(distinct player_id) as player_count,
    count(*) filter (where record_wins is not null and record_losses is not null) as recorded_team_count
  from teams
  group by event_id
),
winners as (
  select
    event_id,
    team_id as winner_team_id,
    player_name as winner_player_name,
    player_country as winner_player_country,
    record_wins as winner_record_wins,
    record_losses as winner_record_losses,
    pokemon_keys as winner_pokemon_keys,
    row_number() over (partition by event_id order by team_id) as tie_rank
  from teams
  where placement = 1
),
matches as (
  select event_id, count(*) as match_count
  from {{ ref('tournament_match') }}
  where division = 'Masters'
    and outcome in ('player1_win', 'player2_win')
  group by event_id
)
select
  event.event_id,
  event.event_name,
  event.event_date,
  event.event_tier,
  event.regulation_code,
  team_counts.team_count,
  team_counts.player_count,
  team_counts.recorded_team_count,
  coalesce(matches.match_count, 0) as match_count,
  winners.winner_team_id,
  winners.winner_player_name,
  winners.winner_player_country,
  winners.winner_record_wins,
  winners.winner_record_losses,
  winners.winner_pokemon_keys,
  event.source_name,
  event.source_url,
  case
    when matches.match_count > 0 then 'https://rk9.gg/pairings/' || event.event_id
  end as pairings_url,
  row_number() over (
    partition by event.regulation_code
    order by event.event_date desc, event.event_id
  ) as recency_rank
from {{ ref('tournament_event') }} event
inner join team_counts
  on team_counts.event_id = event.event_id
left join winners
  on winners.event_id = event.event_id
  and winners.tie_rank = 1
left join matches
  on matches.event_id = event.event_id
where event.regulation_code is not null
order by event.event_date desc, event.event_id
