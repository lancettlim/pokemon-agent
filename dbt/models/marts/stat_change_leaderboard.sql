{{ config(location='../data/marts/stat_change_leaderboard.csv') }}
-- Dashboard-ready trend table (docs/todo.md's "dashboard-ready trend
-- tables (usage, legality, stat changes)"): pokemon_stat_delta reshaped
-- with a gainer/loser direction flag and a rank within that direction, so
-- a dashboard can slice straight to "top N gainers" / "top N losers"
-- without recomputing window functions client-side.
select
  pokemon_key,
  stat_total_delta,
  case when stat_total_delta >= 0 then 'gainer' else 'loser' end as direction,
  case
    when stat_total_delta >= 0
      then row_number() over (order by stat_total_delta desc, pokemon_key)
    else row_number() over (order by stat_total_delta asc, pokemon_key)
  end as rank_within_direction
from {{ ref('pokemon_stat_delta') }}
order by direction, rank_within_direction
