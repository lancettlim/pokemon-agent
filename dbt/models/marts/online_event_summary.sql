{{ config(location='../data/marts/online_event_summary.csv') }}
-- One row per Limitless online tournament (docs/upgrade-plan-2027q2.md,
-- S1): the Events tab's online list, which links each one to its page on
-- play.limitlesstcg.com instead of an event page of ours. Online events are
-- their own population, so they stay out of tournament_event_summary (the
-- official event index and its sample-size KPI) entirely.
--
-- registered_player_count is the platform's own entrant count;
-- team_count is the players whose team sheet the organiser published,
-- which is what every online usage figure rests on. match_count is decided
-- pairings, Swiss and top cut. The winner columns come from the
-- placement-1 team and are null when the winner's list wasn't published,
-- or when the platform shares first place (some organisers rank Swiss-only
-- events in groups): winner_count says how many teams hold placing 1, and
-- naming one of them would be a guess.
with teams as (
  select
    roster.event_id,
    roster.team_id,
    any_value(roster.player_name) as player_name,
    any_value(roster.player_country) as player_country,
    any_value(roster.placement) as placement,
    any_value(roster.record_wins) as record_wins,
    any_value(roster.record_losses) as record_losses,
    string_agg(roster.pokemon_key, '|' order by roster.slot_number) as pokemon_keys
  from {{ ref('int_champions_roster') }} roster
  where roster.population = 'online'
  group by roster.event_id, roster.team_id
),
team_counts as (
  select event_id, count(*) as team_count
  from teams
  group by event_id
),
winners as (
  select
    event_id,
    player_name as winner_player_name,
    player_country as winner_player_country,
    record_wins as winner_record_wins,
    record_losses as winner_record_losses,
    pokemon_keys as winner_pokemon_keys,
    count(*) over (partition by event_id) as winner_count
  from teams
  where placement = 1
),
registered as (
  select event_id, max(player_count) as registered_player_count
  from {{ ref('int_limitless_play_mapped') }}
  group by event_id
),
matches as (
  select event_id, count(*) as match_count
  from {{ ref('tournament_match') }}
  where division = 'Online'
    and outcome in ('player1_win', 'player2_win')
  group by event_id
)
select
  event.event_id,
  event.event_name,
  event.event_date,
  event.regulation_code,
  registered.registered_player_count,
  team_counts.team_count,
  coalesce(matches.match_count, 0) as match_count,
  coalesce(shared.winner_count, 0) as winner_count,
  winners.winner_player_name,
  winners.winner_player_country,
  winners.winner_record_wins,
  winners.winner_record_losses,
  winners.winner_pokemon_keys,
  event.source_name,
  event.source_url,
  row_number() over (
    partition by event.regulation_code
    order by event.event_date desc, event.event_id
  ) as recency_rank
from {{ ref('tournament_event') }} event
inner join team_counts
  on team_counts.event_id = event.event_id
left join registered
  on registered.event_id = event.event_id
left join (select distinct event_id, winner_count from winners) shared
  on shared.event_id = event.event_id
left join winners
  on winners.event_id = event.event_id
  and winners.winner_count = 1
left join matches
  on matches.event_id = event.event_id
where event.event_tier = 'Online'
order by event.event_date desc, event.event_id
