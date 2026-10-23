{{ config(location='../data/marts/pokemon_head_to_head.csv') }}
-- Real head-to-head records, built on tournament_match (backlog.md #27).
--
-- Grain and its honest limit: one row per (pokemon_key,
-- opponent_pokemon_key), counting matches where a team fielding the first
-- Pokémon faced a team fielding the second. RK9 publishes no per-battle log
-- naming which Pokémon were actually brought (VGC brings 4 of 6) or which
-- beat which, so this measures *team* outcomes attributed to every Pokémon
-- on the roster -- "teams with A beat teams with B this often", not "A
-- beats B". Every consumer of this mart must say so; see
-- dbt/models/marts/schema.yml.
--
-- Pairs are mirrored (A-vs-B and B-vs-A both present) so a lookup by
-- pokemon_key alone returns that Pokémon's full opponent list, matching
-- pokemon_team_core_usage's existing convention for partner pairs.
--
-- regulation_scope (docs/plan-synergy-checks-graph.md, G1): one partition
-- per Champions regulation plus the roll-up 'all', via
-- int_champions_roster_scoped. A match takes its event's regulation (both
-- teams of a match come from the same event, so the opponent's roster is
-- read in the scope of the side's own team). Before this, a matchup from
-- M-A showed up on an M-C page -- the blending the regulation registry
-- exists to stop.
--
-- Scoped to Masters (the only division with rosters, see
-- assert_rk9_pairing_mapping_coverage.sql), to decided matches (a tie or
-- bye has no winner to attribute), and to the current legal pool.
--
-- wilson_lower_bound reuses pokemon_win_rate_summary.sql's 95% Wilson score
-- formula (backlog.md #13). It matters more here than there: head-to-head
-- counts are far smaller than aggregate ones, so a raw win_rate ranking is
-- dominated by 1-0 records without it.
with decided as (
  select
    match_id,
    team_id_1,
    team_id_2,
    winner_team_id
  from {{ ref('tournament_match') }}
  where division = 'Masters'
    and outcome in ('player1_win', 'player2_win')
    and team_id_1 is not null
    and team_id_2 is not null
    and winner_team_id is not null
),

-- Legal-pool roster membership, one row per (scope, team, Pokémon).
-- distinct guards against a team that fielded the same Pokémon in two
-- slots inflating its own pair counts. scoped_team_key folds scope and
-- team into one join key: joining the two roster sides on
-- regulation_scope as a separate predicate let the planner pair every
-- roster row with every other in the same scope before filtering by team,
-- which ran DuckDB out of temp space.
roster as (
  select distinct
    member.regulation_scope,
    member.team_id,
    member.regulation_scope || ':' || member.team_id as scoped_team_key,
    member.pokemon_key
  from {{ ref('int_champions_roster_scoped') }} member
  inner join {{ ref('pokemon_stat_champions') }} champions
    on champions.pokemon_key = member.pokemon_key
    and champions.is_legal = true
),

scoped_teams as (
  select distinct regulation_scope, team_id from roster
),

-- Each decided match contributes both directions, once per scope its
-- teams belong to (their own regulation and 'all').
sides as (
  select
    decided.match_id,
    decided.team_id_1 as own_team_id,
    decided.team_id_2 as opponent_team_id,
    decided.winner_team_id
  from decided
  union all
  select
    decided.match_id,
    decided.team_id_2 as own_team_id,
    decided.team_id_1 as opponent_team_id,
    decided.winner_team_id
  from decided
),

scoped_sides as (
  select
    scoped_teams.regulation_scope,
    scoped_teams.regulation_scope || ':' || sides.own_team_id as own_key,
    scoped_teams.regulation_scope || ':' || sides.opponent_team_id as opponent_key,
    case when sides.winner_team_id = sides.own_team_id then 1 else 0 end as is_win
  from sides
  inner join scoped_teams
    on scoped_teams.team_id = sides.own_team_id
),

pairs as (
  select
    scoped_sides.regulation_scope,
    own_roster.pokemon_key,
    opponent_roster.pokemon_key as opponent_pokemon_key,
    scoped_sides.is_win
  from scoped_sides
  inner join roster as own_roster
    on own_roster.scoped_team_key = scoped_sides.own_key
  inner join roster as opponent_roster
    on opponent_roster.scoped_team_key = scoped_sides.opponent_key
),

agg as (
  select
    regulation_scope,
    pokemon_key,
    opponent_pokemon_key,
    count(*) as matches_played,
    sum(is_win) as wins,
    count(*) - sum(is_win) as losses,
    round(sum(is_win)::double / count(*), 4) as win_rate
  from pairs
  group by regulation_scope, pokemon_key, opponent_pokemon_key
),

-- z = 1.96 (95% confidence), same Wilson score lower bound
-- pokemon_win_rate_summary.sql documents.
scored as (
  select
    *,
    (
      (win_rate + (1.96 * 1.96) / (2 * matches_played))
      - 1.96 * sqrt(
        (win_rate * (1 - win_rate) + (1.96 * 1.96) / (4 * matches_played)) / matches_played
      )
    ) / (1 + (1.96 * 1.96) / matches_played) as wilson_lower_bound_raw
  from agg
)

select
  regulation_scope,
  pokemon_key,
  opponent_pokemon_key,
  matches_played,
  wins,
  losses,
  win_rate,
  round(greatest(wilson_lower_bound_raw, 0), 4) as wilson_lower_bound,
  row_number() over (
    partition by regulation_scope, pokemon_key
    order by wilson_lower_bound_raw desc, matches_played desc, opponent_pokemon_key asc
  ) as matchup_rank
from scored
order by regulation_scope, pokemon_key, matchup_rank
