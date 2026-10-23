{{ config(location='../data/marts/pokemon_win_rate_summary.csv') }}
-- Win-rate-proxy KPI (docs/todo.md's Phase 3 tier/record/item follow-up
-- item; docs/prd.md's "KPI overview cards (usage, win-rate proxies, ...)"):
-- aggregates each team's reported win/loss record across every roster slot
-- that included the Pokémon, restricted to the current legal pool and to
-- teams MunchStats actually reported a record for.
--
-- wilson_lower_bound (backlog.md #13) is the lower bound of a 95% Wilson
-- score confidence interval on win_rate, using record_count as the sample
-- size. Fixes the ordering a raw win_rate ranking gets wrong: a 100% win
-- rate over 3 recorded matches currently outranks 62% over 200, even
-- though the latter is the far more reliable number. wilson_rank orders by
-- this instead of raw win_rate; win_rate/record_count stay as reported so
-- consumers that want the raw proxy still have it.
--
-- regulation_scope (docs/upgrade-plan-2026q4.md, A3): one partition per
-- Champions regulation ("m-a", "m-b", "m-c", ...) plus the roll-up 'all',
-- each computed and ranked independently, via int_champions_roster_scoped.
with agg as (
  select
    member.regulation_scope,
    member.pokemon_key,
    sum(team.record_wins) as total_wins,
    sum(team.record_losses) as total_losses,
    round(
      sum(team.record_wins)::double
        / nullif(sum(team.record_wins) + sum(team.record_losses), 0),
      4
    ) as win_rate,
    count(*) as record_count
  from {{ ref('int_champions_roster_scoped') }} member
  inner join {{ ref('tournament_team') }} team
    on team.team_id = member.team_id
  inner join {{ ref('pokemon_stat_champions') }} champions
    on champions.pokemon_key = member.pokemon_key
    and champions.is_legal = true
  where team.record_wins is not null
    and team.record_losses is not null
  group by member.regulation_scope, member.pokemon_key
),
-- z = 1.96 (95% confidence). Wilson score lower bound:
-- (phat + z^2/(2n) - z*sqrt((phat*(1-phat) + z^2/(4n)) / n)) / (1 + z^2/n)
scored as (
  select
    *,
    (
      (win_rate + (1.96 * 1.96) / (2 * record_count))
      - 1.96 * sqrt((win_rate * (1 - win_rate) + (1.96 * 1.96) / (4 * record_count)) / record_count)
    ) / (1 + (1.96 * 1.96) / record_count) as wilson_lower_bound_raw
  from agg
)
select
  regulation_scope,
  pokemon_key,
  total_wins,
  total_losses,
  win_rate,
  record_count,
  round(greatest(wilson_lower_bound_raw, 0), 4) as wilson_lower_bound,
  row_number() over (partition by regulation_scope order by wilson_lower_bound_raw desc, pokemon_key) as wilson_rank
from scored
order by regulation_scope, wilson_lower_bound desc
