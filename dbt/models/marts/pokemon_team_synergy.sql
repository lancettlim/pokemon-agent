{{ config(location='../data/marts/pokemon_team_synergy.csv') }}
-- Team synergy beyond raw co-occurrence (backlog.md #9): pokemon_team_
-- core_usage reports how often two Pokémon appear together, which mostly
-- just re-ranks the individually popular ones. This mart adds lift -- the
-- ratio of a pair's observed team co-occurrence rate to the co-occurrence
-- rate you'd expect if the two Pokémon were paired independently of their
-- individual popularity:
--
--   lift(A, B) = P(A and B) / (P(A) * P(B))
--              = (pair_team_count / total_teams)
--                / ((team_count_a / total_teams) * (team_count_b / total_teams))
--
-- lift > 1 means the pair appears together more than chance given how
-- popular each Pokémon is individually -- a genuine pairing, not just two
-- popular Pokémon coincidentally sharing rosters. lift < 1 means they're
-- paired together less than their individual popularity would predict.
--
-- Built on top of pokemon_team_core_usage's already-mirrored pairs (both
-- anchor directions) rather than re-deriving the pairwise team self-join,
-- plus a small marginal (how many distinct teams include this Pokémon at
-- all) and total-team-count aggregate.
--
-- CAVEAT: lift is noisy for low pair_team_count (a pair seen together
-- twice against a Pokémon that's individually rare can produce an
-- extreme lift value) -- pair_team_count is exposed alongside lift so
-- consumers can apply their own confidence floor, the same pattern
-- pokemon_win_rate_summary's record_count/wilson_lower_bound pairing
-- uses.
--
-- Confidence (docs/plan-synergy-checks-graph.md, G3): expected_pair_team_
-- count is the number of shared teams independence predicts (team_count_a
-- * team_count_b / total_teams), and synergy_z is the Poisson z score of
-- the observed count against it, (observed - expected) / sqrt(expected).
-- Lift says how strong a pairing is; synergy_z says how sure we are of it,
-- which is what the synergy graph caps each node's edges by.
--
-- regulation_scope (docs/upgrade-plan-2026q4.md, A3): one partition per
-- Champions regulation ("m-a", "m-b", "m-c", ...) plus the roll-up 'all',
-- each computed and ranked independently, via int_champions_roster_scoped.
with legal_members as (
  select distinct member.regulation_scope, member.team_id, member.pokemon_key
  from {{ ref('int_champions_roster_scoped') }} member
  inner join {{ ref('pokemon_stat_champions') }} champions
    on champions.pokemon_key = member.pokemon_key
    and champions.is_legal = true
),
total_teams as (
  select regulation_scope, count(distinct team_id) as total_teams
  from legal_members
  group by regulation_scope
),
marginal as (
  select regulation_scope, pokemon_key, count(distinct team_id) as team_count
  from legal_members
  group by regulation_scope, pokemon_key
),
scored as (
  select
    core.regulation_scope,
    core.pokemon_key,
    core.partner_pokemon_key,
    core.co_occurrence_count as pair_team_count,
    (core.co_occurrence_count::double * total_teams.total_teams)
      / (marginal_a.team_count * marginal_b.team_count) as lift_raw,
    (marginal_a.team_count::double * marginal_b.team_count) / total_teams.total_teams
      as expected_raw
  from {{ ref('pokemon_team_core_usage') }} core
  inner join total_teams on total_teams.regulation_scope = core.regulation_scope
  inner join marginal marginal_a
    on marginal_a.pokemon_key = core.pokemon_key
    and marginal_a.regulation_scope = core.regulation_scope
  inner join marginal marginal_b
    on marginal_b.pokemon_key = core.partner_pokemon_key
    and marginal_b.regulation_scope = core.regulation_scope
)
select
  regulation_scope,
  pokemon_key,
  partner_pokemon_key,
  pair_team_count,
  round(lift_raw, 4) as lift,
  round(expected_raw, 4) as expected_pair_team_count,
  round((pair_team_count - expected_raw) / sqrt(expected_raw), 4) as synergy_z,
  row_number() over (partition by regulation_scope, pokemon_key order by lift_raw desc) as lift_rank
from scored
order by regulation_scope, pokemon_key, lift desc
