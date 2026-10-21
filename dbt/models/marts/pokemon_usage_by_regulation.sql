{{ config(location='../data/marts/pokemon_usage_by_regulation.csv') }}
-- Usage x regulation cross-tab (backlog.md #12): for each regulation, every
-- Pokémon legal under it, with its usage *in events played under that
-- regulation* (0 if it was legal but never brought).
--
-- This used to be a stand-in: tournament_event carried no regulation_code,
-- so the mart cross-joined all-time usage against each regulation's legal
-- pool, and "usage in M-B" really meant "all-time usage of Pokémon legal in
-- M-B". tournament_event.regulation_code now exists (resolved through the
-- champions_regulations seed), and pokemon_usage_summary is partitioned by
-- regulation_scope, so this is the real temporal slice
-- (docs/upgrade-plan-2026q4.md, A2).
--
-- usage_share/usage_rank are computed within each regulation_code, so a
-- share is that Pokémon's standing in that regulation's own events.
-- team_share (docs/upgrade-plan-2027q2.md, V1) is the share of the
-- regulation's teams that brought it, the headline metric.
with regulation_usage as (
  select regulation_scope as regulation_code, pokemon_key, usage_count
  from {{ ref('pokemon_usage_summary') }}
  where event_tier is null
    and regulation_scope != 'all'
),
regulation_teams as (
  select regulation_code, count(distinct team_id) as team_count
  from {{ ref('int_champions_roster') }}
  group by regulation_code
),
latest_snapshot as (
  select max(snapshot_date) as snapshot_date
  from {{ ref('legality_snapshot') }}
),
legal_by_regulation as (
  select ls.regulation_code, ls.pokemon_key
  from {{ ref('legality_snapshot') }} ls
  inner join latest_snapshot
    on latest_snapshot.snapshot_date = ls.snapshot_date
  where ls.is_legal = true
),
joined as (
  select
    legal_by_regulation.regulation_code,
    legal_by_regulation.pokemon_key,
    coalesce(regulation_usage.usage_count, 0) as usage_count
  from legal_by_regulation
  left join regulation_usage
    on regulation_usage.pokemon_key = legal_by_regulation.pokemon_key
    and regulation_usage.regulation_code = legal_by_regulation.regulation_code
),
-- win_rate/record_count (docs/upgrade-plan-2027q1.md, P2): the same
-- regulation's pokemon_win_rate_summary partition, so the Pokémon
-- profile's per-regulation trend can show usage and win rate side by side
-- with its sample size. Null where the Pokémon has no recorded results in
-- that regulation.
win as (
  select regulation_scope as regulation_code, pokemon_key, win_rate, record_count
  from {{ ref('pokemon_win_rate_summary') }}
  where regulation_scope != 'all'
)
select
  joined.regulation_code,
  joined.pokemon_key,
  joined.usage_count,
  round(
    joined.usage_count::double / nullif(sum(joined.usage_count) over (partition by joined.regulation_code), 0),
    4
  ) as usage_share,
  round(joined.usage_count::double / nullif(regulation_teams.team_count, 0), 4) as team_share,
  row_number() over (
    partition by joined.regulation_code order by joined.usage_count desc, joined.pokemon_key
  ) as usage_rank,
  win.win_rate,
  win.record_count
from joined
left join win
  on win.regulation_code = joined.regulation_code
  and win.pokemon_key = joined.pokemon_key
left join regulation_teams
  on regulation_teams.regulation_code = joined.regulation_code
order by joined.regulation_code, joined.usage_count desc
