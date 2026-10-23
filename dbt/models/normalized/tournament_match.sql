-- One row per played match: who faced whom, in which round, and who won.
-- Sourced from RK9's round-by-round pairings (see
-- pipelines/extract/rk9.py), the tournament software the events run on and
-- the source MunchStats itself scrapes for rosters.
--
-- This is the entity backlog.md #27 recorded as underivable. It is real
-- head-to-head data, but note the grain honestly: an outcome is *team vs
-- team*, not Pokémon vs Pokémon. RK9 publishes no per-battle log naming
-- which Pokémon were brought or which knocked out which, so downstream
-- matchup analysis reads "A's team beat B's team", never "A beat B".
--
-- Byes are kept (outcome = 'bye', team_id_2 null): a bye is a real,
-- scheduled round result that affects a player's record, and dropping it
-- would silently disagree with the win/loss totals tournament_team reports.
--
-- Online pairings (docs/upgrade-plan-2027q2.md, S1) follow with division
-- 'Online'; a pairing the platform reports with no result is kept as
-- 'no_result' with is_complete false. Their key includes both handles:
-- the platform gives byes and no-shows no table number, so a round can
-- list one player against several table-less entries.
select
  md5(
    event_id || ':' || pod_id || ':' || cast(round_number as varchar)
    || ':' || coalesce(cast(table_number as varchar), 'bye')
    || ':' || player1_name
  ) as match_id,
  event_id,
  division,
  round_number,
  table_number,
  player_id_1,
  team_id_1,
  player_id_2,
  team_id_2,
  winner_team_id,
  outcome,
  is_complete,
  source_name,
  source_url,
  source_record_id,
  extracted_at_utc,
  dataset_version
from {{ ref('int_rk9_mapped') }}
union all
select
  md5(
    event_id || ':' || cast(phase as varchar) || ':' || cast(round_number as varchar)
    || ':' || coalesce(cast(table_number as varchar), 'bye') || ':' || player1_handle
    || ':' || coalesce(player2_handle, '')
  ) as match_id,
  event_id,
  'Online' as division,
  round_number,
  table_number,
  player_id_1,
  team_id_1,
  player_id_2,
  team_id_2,
  winner_team_id,
  outcome,
  is_complete,
  source_name,
  source_url,
  source_record_id,
  extracted_at_utc,
  dataset_version
from {{ ref('int_limitless_play_pairings_mapped') }}
