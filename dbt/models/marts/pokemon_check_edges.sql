{{ config(location='../data/marts/pokemon_check_edges.csv') }}
-- Check edges for the synergy and checks graph (docs/plan-synergy-checks-
-- graph.md, G2): one row per regulation_scope and ordered pair (A, B),
-- measuring whether teams with A beat teams with B more often than the two
-- teams' overall records predict.
--
-- CAVEAT, repeated from pokemon_head_to_head and to be surfaced wherever
-- this is displayed: the grain is team vs team, NOT Pokémon vs Pokémon.
-- RK9 publishes no per-battle log naming which Pokémon were brought (VGC
-- brings 4 of 6) or which defeated which, so a row reads "teams with A beat
-- teams with B more often than expected", never "A beats B".
--
-- Why a baseline: a raw head-to-head win rate mostly measures A's own
-- strength -- teams with a strong Pokémon beat nearly everyone, so ranking
-- by it orders opponents by how weak they are. The expectation here is
-- log5 from each Pokémon's overall win rate over the same decided matches
-- in the same scope:
--
--   expected = (pA - pA*pB) / (pA + pB - 2*pA*pB)
--
-- and the edge is how far the observed record sits from it, as a binomial
-- z score. (The plan named pokemon_win_rate_summary for pA/pB; that mart
-- reads MunchStats' self-reported records, a different and larger team
-- population than the RK9 pairings this counts, so the baseline is taken
-- from the pairings themselves instead.)
--
-- Mirror contamination: a match where A's team also fields B, or B's team
-- also fields A, is left out, because the effect cancels by construction.
--
-- Evidence: most pairs clear |z| >= 2 by chance alone (thousands of pairs
-- are tested), so each scope gets a Benjamini-Hochberg q value over its
-- unordered pairs. strong = q <= 0.10; suggestive = |z| >= 2 but not
-- strong; none otherwise. The table is antisymmetric: z(A->B) = -z(B->A)
-- (assert_check_edges_antisymmetric).
{% set min_matches = 20 %}
{% set strong_q = 0.10 %}
{% set suggestive_z = 2 %}
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

-- scoped_team_key folds scope and team into one join key, as in
-- pokemon_head_to_head: a separate regulation_scope predicate between the
-- two roster sides lets the planner pair whole scopes before filtering.
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
  -- Official events only, as in pokemon_head_to_head: RK9 pairings exist
  -- only for them.
  where member.scope_population = 'official'
),

-- Teams in a scope, so a side whose team has no legal roster in the scope
-- doesn't count toward any Pokémon's baseline.
scoped_teams as (
  select distinct regulation_scope, team_id from roster
),

sides as (
  select
    decided.match_id,
    decided.team_id_1 as own_team_id,
    decided.team_id_2 as opponent_team_id,
    case when decided.winner_team_id = decided.team_id_1 then 1 else 0 end as is_win
  from decided
  union all
  select
    decided.match_id,
    decided.team_id_2 as own_team_id,
    decided.team_id_1 as opponent_team_id,
    case when decided.winner_team_id = decided.team_id_2 then 1 else 0 end as is_win
  from decided
),

scoped_sides as (
  select
    own_team.regulation_scope,
    own_team.regulation_scope || ':' || sides.own_team_id as own_key,
    own_team.regulation_scope || ':' || sides.opponent_team_id as opponent_key,
    sides.is_win
  from sides
  inner join scoped_teams own_team
    on own_team.team_id = sides.own_team_id
  -- The opponent must have a legal roster in the same scope too.
  inner join (
    select regulation_scope || ':' || team_id as scoped_team_key from scoped_teams
  ) opponent_team
    on opponent_team.scoped_team_key = own_team.regulation_scope || ':' || sides.opponent_team_id
),

-- Each Pokémon's overall record in the scope: every decided match its
-- team played, counted once per side.
baseline as (
  select
    scoped_sides.regulation_scope,
    roster.pokemon_key,
    count(*) as baseline_matches,
    sum(scoped_sides.is_win)::double / count(*) as baseline_win_rate
  from scoped_sides
  inner join roster
    on roster.scoped_team_key = scoped_sides.own_key
  group by scoped_sides.regulation_scope, roster.pokemon_key
),

-- Each team's legal roster as a list, so the mirror filter below is a
-- list lookup rather than a correlated subquery (which the planner turned
-- into a join large enough to exhaust DuckDB's temp space).
team_rosters as (
  select scoped_team_key, list(pokemon_key) as pokemon_keys
  from roster
  group by scoped_team_key
),

side_rosters as (
  select
    scoped_sides.regulation_scope,
    scoped_sides.is_win,
    own.pokemon_keys as own_keys,
    opponent.pokemon_keys as opponent_keys
  from scoped_sides
  inner join team_rosters own
    on own.scoped_team_key = scoped_sides.own_key
  inner join team_rosters opponent
    on opponent.scoped_team_key = scoped_sides.opponent_key
),

own_unnested as (
  select
    regulation_scope,
    is_win,
    own_keys,
    opponent_keys,
    unnest(own_keys) as pokemon_key
  from side_rosters
),

pairs as (
  select
    regulation_scope,
    pokemon_key,
    opponent_pokemon_key,
    is_win
  from (
    select
      regulation_scope,
      is_win,
      own_keys,
      opponent_keys,
      pokemon_key,
      unnest(opponent_keys) as opponent_pokemon_key
    from own_unnested
  ) expanded
  -- Mirror contamination: A's team must not also field B, and B's team
  -- must not also field A. (This also drops A vs A.)
  where not list_contains(own_keys, opponent_pokemon_key)
    and not list_contains(opponent_keys, pokemon_key)
),

agg as (
  select
    regulation_scope,
    pokemon_key,
    opponent_pokemon_key,
    count(*) as matches_played,
    sum(is_win) as wins
  from pairs
  group by regulation_scope, pokemon_key, opponent_pokemon_key
  having count(*) >= {{ min_matches }}
),

expected as (
  select
    agg.*,
    own_base.baseline_win_rate as pokemon_win_rate,
    opponent_base.baseline_win_rate as opponent_win_rate,
    (own_base.baseline_win_rate - own_base.baseline_win_rate * opponent_base.baseline_win_rate)
      / nullif(
        own_base.baseline_win_rate + opponent_base.baseline_win_rate
          - 2 * own_base.baseline_win_rate * opponent_base.baseline_win_rate,
        0
      ) as expected_raw
  from agg
  inner join baseline own_base
    on own_base.regulation_scope = agg.regulation_scope
    and own_base.pokemon_key = agg.pokemon_key
  inner join baseline opponent_base
    on opponent_base.regulation_scope = agg.regulation_scope
    and opponent_base.pokemon_key = agg.opponent_pokemon_key
),

scored as (
  select
    *,
    (wins - matches_played * expected_raw)
      / sqrt(matches_played * expected_raw * (1 - expected_raw)) as z_raw
  from expected
  -- A baseline of exactly 0 or 1 has no variance to measure against.
  where expected_raw > 0 and expected_raw < 1
),

with_p as (
  select
    *,
    least({{ normal_two_sided_p('z_raw') }}, 1.0) as p_raw
  from scored
),

-- Benjamini-Hochberg over each scope's unordered pairs. The table is
-- mirrored, and both directions of a pair share one p value, so the test
-- runs on one canonical direction and the q value is copied to the other.
canonical as (
  select
    regulation_scope,
    pokemon_key,
    opponent_pokemon_key,
    p_raw,
    row_number() over (partition by regulation_scope order by p_raw asc, pokemon_key, opponent_pokemon_key) as p_rank,
    count(*) over (partition by regulation_scope) as tested_pairs
  from with_p
  where pokemon_key < opponent_pokemon_key
),

bh as (
  select
    regulation_scope,
    pokemon_key,
    opponent_pokemon_key,
    tested_pairs,
    least(
      min(p_raw * tested_pairs / p_rank) over (
        partition by regulation_scope
        order by p_rank desc
        rows between unbounded preceding and current row
      ),
      1.0
    ) as q_raw
  from canonical
),

bh_mirrored as (
  select regulation_scope, pokemon_key, opponent_pokemon_key, tested_pairs, q_raw from bh
  union all
  select regulation_scope, opponent_pokemon_key, pokemon_key, tested_pairs, q_raw from bh
)

select
  with_p.regulation_scope,
  with_p.pokemon_key,
  with_p.opponent_pokemon_key,
  with_p.matches_played,
  with_p.wins,
  with_p.matches_played - with_p.wins as losses,
  round(with_p.wins::double / with_p.matches_played, 4) as observed_win_rate,
  round(with_p.pokemon_win_rate, 4) as pokemon_win_rate,
  round(with_p.opponent_win_rate, 4) as opponent_win_rate,
  round(with_p.expected_raw, 4) as expected_win_rate,
  round(with_p.wins::double / with_p.matches_played - with_p.expected_raw, 4) as edge,
  round(with_p.z_raw, 4) as z_score,
  round(with_p.p_raw, 6) as p_value,
  round(bh_mirrored.q_raw, 6) as q_value,
  case
    when bh_mirrored.q_raw <= {{ strong_q }} then 'strong'
    when abs(with_p.z_raw) >= {{ suggestive_z }} then 'suggestive'
    else 'none'
  end as evidence,
  bh_mirrored.tested_pairs,
  {{ min_matches }} as min_matches_threshold
from with_p
inner join bh_mirrored
  on bh_mirrored.regulation_scope = with_p.regulation_scope
  and bh_mirrored.pokemon_key = with_p.pokemon_key
  and bh_mirrored.opponent_pokemon_key = with_p.opponent_pokemon_key
order by with_p.regulation_scope, with_p.pokemon_key, with_p.z_raw desc
