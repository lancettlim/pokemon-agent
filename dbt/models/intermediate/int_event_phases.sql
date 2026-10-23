-- The phase structure of each official event, from RK9's Masters pairings
-- (docs/upgrade-plan-2027q2.md, E1 and E2): which round Day 2 starts and
-- which round the single-elimination top cut starts. One row per event.
-- Online events are excluded: their pairings carry no Day 2.
--
-- Neither is published as a field, so both are read off the round
-- structure, the same way a player reads a pairings page:
--
--   top_cut_start_round  the first of the trailing run of rounds where
--     each round has twice the tables of the next, nobody who lost plays
--     again and everybody who won does, ending in a one-table final. A
--     Swiss round never has that property: someone at 1-1 can still make
--     the cut. Recife's Day 2 had two 16-table Swiss rounds before a
--     top 16; Louisville cut to a top 32. While an event is still running,
--     the last round counts when it is a power-of-two table count under
--     half the round before it (a quarterfinal in progress).
--   day2_start_round  the first round with under half the tables of the
--     round before (Day 1's cut drops about 500 tables to about 80), when
--     that is before the top cut. A small event that goes straight from
--     Swiss into its top cut has no Day 2.
--
-- Measured on every Champions event with pairings so far: Day 2 starts at
-- round 9 everywhere, and the top cut is a 16-slot bracket (32 at
-- Louisville). It admits everyone with a qualifying record and pads the
-- bracket with byes for the top seeds, so top_cut_size counts players,
-- not slots: 13 players in a 16-slot bracket is common.
with matches as (
  select *
  from {{ ref('tournament_match') }}
  where division = 'Masters'
),
rounds as (
  select
    event_id,
    round_number,
    count(*) as table_count,
    count(*) filter (where outcome = 'bye') as bye_count
  from matches
  group by event_id, round_number
),
sides as (
  select
    event_id,
    round_number,
    player_id_1 as player_id,
    case outcome when 'player1_win' then 'W' when 'player2_win' then 'L' end as result
  from matches
  where player_id_1 is not null
  union all
  select
    event_id,
    round_number,
    player_id_2 as player_id,
    case outcome when 'player2_win' then 'W' when 'player1_win' then 'L' end as result
  from matches
  where player_id_2 is not null
),
continuity as (
  -- Per round: how many of its losers play the next round, and how many
  -- of its winners don't.
  select
    this_round.event_id,
    this_round.round_number,
    count(*) filter (where this_round.result = 'L' and next_round.player_id is not null)
      as losers_continuing,
    count(*) filter (where this_round.result = 'W' and next_round.player_id is null)
      as winners_missing
  from sides this_round
  left join (select distinct event_id, round_number, player_id from sides) next_round
    on next_round.event_id = this_round.event_id
    and next_round.round_number = this_round.round_number + 1
    and next_round.player_id = this_round.player_id
  group by this_round.event_id, this_round.round_number
),
shaped as (
  select
    rounds.event_id,
    rounds.round_number,
    rounds.table_count,
    rounds.bye_count,
    lag(rounds.table_count) over w as previous_tables,
    lead(rounds.table_count) over w as next_tables,
    max(rounds.round_number) over (partition by rounds.event_id) as last_round,
    continuity.losers_continuing,
    continuity.winners_missing
  from rounds
  left join continuity
    on continuity.event_id = rounds.event_id
    and continuity.round_number = rounds.round_number
  window w as (partition by rounds.event_id order by rounds.round_number)
),
classified as (
  select
    *,
    case
      when round_number = last_round
        then table_count in (1, 2, 4, 8, 16, 32)
          and (previous_tables is null or previous_tables >= 2 * table_count)
      else table_count = 2 * next_tables
        and coalesce(losers_continuing, 0) = 0
        and coalesce(winners_missing, 0) = 0
    end as is_elimination,
    previous_tables is not null and table_count < 0.5 * previous_tables as is_cut
  from shaped
),
top_cut as (
  select
    event_id,
    coalesce(max(round_number) filter (where not is_elimination), 0) + 1 as top_cut_start_round,
    max(last_round) as last_round
  from classified
  group by event_id
),
events as (
  select
    top_cut.event_id,
    top_cut.last_round,
    case
      when top_cut.top_cut_start_round <= top_cut.last_round then top_cut.top_cut_start_round
    end as top_cut_start_round
  from top_cut
)
select
  events.event_id,
  events.last_round,
  (
    select min(classified.round_number)
    from classified
    where classified.event_id = events.event_id
      and classified.is_cut
      and classified.round_number < coalesce(events.top_cut_start_round, events.last_round + 1)
  ) as day2_start_round,
  events.top_cut_start_round,
  -- Players in the top cut's first round: every slot but the byes.
  (
    select 2 * classified.table_count - classified.bye_count
    from classified
    where classified.event_id = events.event_id
      and classified.round_number = events.top_cut_start_round
  ) as top_cut_size,
  -- Slots in that round's bracket: 16 for a 16-player bracket.
  (
    select 2 * classified.table_count
    from classified
    where classified.event_id = events.event_id
      and classified.round_number = events.top_cut_start_round
  ) as bracket_size
from events
inner join {{ ref('tournament_event') }} event
  on event.event_id = events.event_id
where event.regulation_code is not null
  and coalesce(event.event_tier, '') != 'Online'
