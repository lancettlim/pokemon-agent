{{ config(location='../data/marts/pokemon_team_core_triple_usage.csv') }}
-- Champions-format three-Pokemon team cores. Each six-member team yields
-- C(6, 3) = 20 canonical triples; pokemon_key_a < pokemon_key_b <
-- pokemon_key_c makes the grain explicit and prevents mirrored duplicates.
--
-- triple_lift compares the observed share of teams containing all three
-- Pokemon with the share expected if their individual team appearances
-- were independent. avg_pair_lift/min_pair_lift keep the triple honest:
-- a high three-way score should not hide a constituent pair that never
-- forms a meaningful core. Counts and event/player coverage stay exposed
-- because all lift metrics are noisy at small samples.
with legal_members as (
  select distinct
    member.team_id,
    member.player_id,
    member.event_id,
    member.pokemon_key,
    member.placement,
    member.record_wins,
    member.record_losses
  from {{ ref('int_champions_roster_official') }} member
  inner join {{ ref('pokemon_stat_champions') }} champions
    on champions.pokemon_key = member.pokemon_key
    and champions.is_legal = true
),
triples as (
  select
    a.team_id,
    a.player_id,
    a.event_id,
    a.placement,
    a.record_wins,
    a.record_losses,
    a.pokemon_key as pokemon_key_a,
    b.pokemon_key as pokemon_key_b,
    c.pokemon_key as pokemon_key_c
  from legal_members a
  inner join legal_members b
    on a.team_id = b.team_id
    and a.pokemon_key < b.pokemon_key
  inner join legal_members c
    on a.team_id = c.team_id
    and b.pokemon_key < c.pokemon_key
),
total_teams as (
  select count(distinct team_id) as total_teams from legal_members
),
marginals as (
  select pokemon_key, count(distinct team_id) as team_count
  from legal_members
  group by pokemon_key
),
counted as (
  select
    pokemon_key_a,
    pokemon_key_b,
    pokemon_key_c,
    count(*) as triple_team_count,
    count(distinct player_id) as player_count,
    count(distinct event_id) as event_count,
    sum(record_wins) as total_wins,
    sum(record_losses) as total_losses,
    avg(placement) as avg_placement
  from triples
  group by pokemon_key_a, pokemon_key_b, pokemon_key_c
),
pair_lifts as (
  -- pokemon_team_synergy is mirrored; retain one canonical direction.
  select pokemon_key, partner_pokemon_key, lift
  from {{ ref('pokemon_team_synergy') }}
  where pokemon_key < partner_pokemon_key
    and regulation_scope = 'all'
),
scored as (
  select
    counted.*,
    total_teams.total_teams,
    counted.triple_team_count::double / total_teams.total_teams as triple_team_share_raw,
    (marginal_a.team_count::double / total_teams.total_teams)
      * (marginal_b.team_count::double / total_teams.total_teams)
      * (marginal_c.team_count::double / total_teams.total_teams) as expected_team_share_raw,
    (counted.triple_team_count::double * total_teams.total_teams * total_teams.total_teams)
      / (marginal_a.team_count * marginal_b.team_count * marginal_c.team_count)
      as triple_lift_raw,
    least(pair_ab.lift, pair_ac.lift, pair_bc.lift) as min_pair_lift_raw,
    (pair_ab.lift + pair_ac.lift + pair_bc.lift) / 3.0 as avg_pair_lift_raw
  from counted
  cross join total_teams
  inner join marginals marginal_a on marginal_a.pokemon_key = counted.pokemon_key_a
  inner join marginals marginal_b on marginal_b.pokemon_key = counted.pokemon_key_b
  inner join marginals marginal_c on marginal_c.pokemon_key = counted.pokemon_key_c
  inner join pair_lifts pair_ab
    on pair_ab.pokemon_key = counted.pokemon_key_a
    and pair_ab.partner_pokemon_key = counted.pokemon_key_b
  inner join pair_lifts pair_ac
    on pair_ac.pokemon_key = counted.pokemon_key_a
    and pair_ac.partner_pokemon_key = counted.pokemon_key_c
  inner join pair_lifts pair_bc
    on pair_bc.pokemon_key = counted.pokemon_key_b
    and pair_bc.partner_pokemon_key = counted.pokemon_key_c
)
select
  pokemon_key_a,
  pokemon_key_b,
  pokemon_key_c,
  triple_team_count,
  player_count,
  event_count,
  round(triple_team_share_raw, 4) as triple_team_share,
  round(expected_team_share_raw, 6) as expected_team_share,
  round(triple_lift_raw, 4) as triple_lift,
  round(min_pair_lift_raw, 4) as min_pair_lift,
  round(avg_pair_lift_raw, 4) as avg_pair_lift,
  total_wins,
  total_losses,
  round(total_wins::double / nullif(total_wins + total_losses, 0), 4) as win_rate,
  round(avg_placement, 2) as avg_placement,
  row_number() over (
    order by triple_team_count desc, triple_lift_raw desc,
      pokemon_key_a, pokemon_key_b, pokemon_key_c
  ) as support_rank,
  row_number() over (
    order by triple_lift_raw desc, triple_team_count desc,
      pokemon_key_a, pokemon_key_b, pokemon_key_c
  ) as lift_rank
from scored
order by triple_team_count desc, triple_lift desc
