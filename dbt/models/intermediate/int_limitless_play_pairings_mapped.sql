-- Limitless online-tournament pairings, resolved to the online teams in
-- int_limitless_play_mapped (docs/upgrade-plan-2027q2.md, S1). A handle
-- whose list the organiser didn't publish has no team, so its team id
-- stays null: the match is still a real result, as an RK9 pairing against
-- an unrostered player is.
--
-- The API reports the winner as a handle, "0" for a tie and "-1" for no
-- result; a pairing with no second player is a bye, which has no winning
-- team (the platform names player 1 the winner of a bye). Phase 1 is
-- Swiss and later phases are the top cut. is_complete follows the outcome:
-- a decided game, a tie or a bye, never a pairing with no result.
with teams as (
  select distinct tournament_id, player_handle, team_id, player_id
  from {{ ref('int_limitless_play_mapped') }}
)
select
  'LP-' || pairings.tournament_id as event_id,
  pairings.tournament_id,
  pairings.phase,
  pairings.round_number,
  pairings.table_number,
  pairings.player1_handle,
  nullif(pairings.player2_handle, '') as player2_handle,
  player1.player_id as player_id_1,
  player1.team_id as team_id_1,
  player2.player_id as player_id_2,
  player2.team_id as team_id_2,
  case
    when nullif(pairings.player2_handle, '') is null then 'bye'
    when pairings.winner_handle = pairings.player1_handle then 'player1_win'
    when pairings.winner_handle = pairings.player2_handle then 'player2_win'
    when pairings.winner_handle = '0' then 'tie'
    else 'no_result'
  end as outcome,
  case
    when nullif(pairings.player2_handle, '') is null then null
    when pairings.winner_handle = pairings.player1_handle then player1.team_id
    when pairings.winner_handle = pairings.player2_handle then player2.team_id
  end as winner_team_id,
  nullif(pairings.player2_handle, '') is null
    or pairings.winner_handle in (pairings.player1_handle, pairings.player2_handle, '0')
    as is_complete,
  pairings.source_name,
  pairings.source_url,
  pairings.source_record_id,
  pairings.extracted_at_utc,
  pairings.dataset_version
from {{ ref('int_limitless_play_pairings_latest') }} pairings
inner join (select distinct tournament_id from teams) covered
  on covered.tournament_id = pairings.tournament_id
left join teams player1
  on player1.tournament_id = pairings.tournament_id
  and player1.player_handle = pairings.player1_handle
left join teams player2
  on player2.tournament_id = pairings.tournament_id
  and player2.player_handle = pairings.player2_handle
