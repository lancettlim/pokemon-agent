{{ config(location='../data/marts/pokemon_placement_weighted_usage.csv') }}
-- Placement-weighted usage (backlog.md #8): distinguishes "popular" from
-- "successful" -- raw pokemon_usage_summary.usage_count treats a
-- last-place team's roster slot the same as a tournament winner's, which
-- flatters crowd-favorite picks and hides quiet top-cut staples.
--
-- Two views, both derived from tournament_team.placement (always reported,
-- lower is better -- 1 is first place):
--   - top_cut_usage_count/top_cut_usage_share: appearances on a team that
--     placed 1-8 ("top cut", the standard VGC/Champions cutoff for a
--     tournament's single-elimination bracket) -- a hard cutoff view.
--   - placement_weighted_score/weighted_usage_share: a continuously
--     weighted view using an inverse-placement weight (1/placement) per
--     appearance, so a 1st-place finish counts far more than a 200th, with
--     no cutoff discontinuity.
--
-- regulation_scope (docs/upgrade-plan-2026q4.md, A3): one partition per
-- Champions regulation ("m-a", "m-b", "m-c", ...) plus the roll-up 'all',
-- each computed and ranked independently, via int_champions_roster_scoped.
--
-- top_cut_team_share/weighted_team_share (docs/upgrade-plan-2027q2.md,
-- V1) are the same two views over teams instead of roster slots: the share
-- of top-8 teams that brought the Pokémon, and its teams' summed
-- 1/placement weight over every placed team's.
with placed_teams as (
  select distinct member.regulation_scope, member.team_id, team.placement
  from {{ ref('int_champions_roster_scoped') }} member
  inner join {{ ref('tournament_team') }} team
    on team.team_id = member.team_id
  where team.placement is not null
    and team.placement > 0
),
team_weights as (
  select
    regulation_scope,
    count(*) filter (where placement <= 8) as top_cut_team_count,
    sum(1.0 / placement) as total_team_weight
  from placed_teams
  group by regulation_scope
),
legal_appearances as (
  select member.regulation_scope, member.pokemon_key, team.placement
  from {{ ref('int_champions_roster_scoped') }} member
  inner join {{ ref('tournament_team') }} team
    on team.team_id = member.team_id
  inner join {{ ref('pokemon_stat_champions') }} champions
    on champions.pokemon_key = member.pokemon_key
    and champions.is_legal = true
  where team.placement is not null
    and team.placement > 0
),
per_pokemon as (
  select
    regulation_scope,
    pokemon_key,
    count(*) as usage_count,
    sum(case when placement <= 8 then 1 else 0 end) as top_cut_usage_count,
    sum(1.0 / placement) as placement_weighted_score
  from legal_appearances
  group by regulation_scope, pokemon_key
)
select
  regulation_scope,
  pokemon_key,
  usage_count,
  top_cut_usage_count,
  round(
    top_cut_usage_count::double / nullif(sum(top_cut_usage_count) over (partition by regulation_scope), 0),
    4
  ) as top_cut_usage_share,
  round(placement_weighted_score, 4) as placement_weighted_score,
  round(
    placement_weighted_score / nullif(sum(placement_weighted_score) over (partition by regulation_scope), 0),
    4
  ) as weighted_usage_share,
  round(top_cut_usage_count::double / nullif(team_weights.top_cut_team_count, 0), 4)
    as top_cut_team_share,
  round(placement_weighted_score / nullif(team_weights.total_team_weight, 0), 4)
    as weighted_team_share,
  row_number() over (partition by regulation_scope order by placement_weighted_score desc) as weighted_usage_rank
from per_pokemon
inner join team_weights using (regulation_scope)
order by regulation_scope, placement_weighted_score desc
