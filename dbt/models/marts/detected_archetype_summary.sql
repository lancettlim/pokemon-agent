{{ config(location='../data/marts/detected_archetype_summary.csv') }}
-- Dashboard-facing summary of experimental data-derived archetypes. Usage
-- and performance use primary assignments only so hybrid teams are not
-- double-counted; secondary assignments remain available in
-- detected_archetype_team_membership for analysis.
with primary_assignments as (
  select *
  from {{ ref('detected_archetype_team_membership') }}
  where assignment_rank = 1
),
team_context as (
  select
    team_id,
    min(player_id) as player_id,
    min(event_id) as event_id,
    min(placement) as placement,
    min(record_wins) as record_wins,
    min(record_losses) as record_losses
  from {{ ref('int_champions_roster_official') }}
  group by team_id
),
total_teams as (
  select count(*) as total_teams from team_context
),
anchors as (
  select distinct
    archetype_key,
    anchor_candidate_key,
    anchor_pokemon_key_a as pokemon_key_a,
    anchor_pokemon_key_b as pokemon_key_b,
    anchor_pokemon_key_c as pokemon_key_c
  from {{ ref('detected_archetype_candidates') }}
),
candidate_counts as (
  select archetype_key, count(*) as candidate_count
  from {{ ref('detected_archetype_candidates') }}
  group by archetype_key
),
assigned as (
  select membership.archetype_key, context.*
  from primary_assignments membership
  inner join team_context context on context.team_id = membership.team_id
),
summary as (
  select
    assigned.archetype_key,
    count(*) as team_count,
    count(distinct player_id) as player_count,
    count(distinct event_id) as event_count,
    sum(record_wins) as total_wins,
    sum(record_losses) as total_losses,
    avg(placement) as avg_placement
  from assigned
  group by assigned.archetype_key
),
extension_counts as (
  select
    assigned.archetype_key,
    member.pokemon_key,
    count(distinct assigned.team_id) as extension_team_count
  from assigned
  inner join {{ ref('int_champions_roster_official') }} member
    on member.team_id = assigned.team_id
  inner join anchors on anchors.archetype_key = assigned.archetype_key
  where member.pokemon_key not in (
    anchors.pokemon_key_a, anchors.pokemon_key_b, anchors.pokemon_key_c
  )
  group by assigned.archetype_key, member.pokemon_key
),
ranked_extensions as (
  select
    *,
    row_number() over (
      partition by archetype_key
      order by extension_team_count desc, pokemon_key
    ) as extension_rank
  from extension_counts
)
select
  summary.archetype_key,
  anchors.anchor_candidate_key,
  anchors.pokemon_key_a,
  anchors.pokemon_key_b,
  anchors.pokemon_key_c,
  candidate_counts.candidate_count,
  summary.team_count,
  summary.player_count,
  summary.event_count,
  round(summary.team_count::double / total_teams.total_teams, 4) as team_share,
  summary.total_wins,
  summary.total_losses,
  round(summary.total_wins::double / nullif(summary.total_wins + summary.total_losses, 0), 4)
    as win_rate,
  round(summary.avg_placement, 2) as avg_placement,
  extension.pokemon_key as top_extension_pokemon_key,
  extension.extension_team_count,
  round(extension.extension_team_count::double / summary.team_count, 4)
    as top_extension_share,
  case
    when summary.event_count >= 2 and summary.team_count >= 10 then 'cross-event'
    when summary.team_count >= 10 then 'single-event'
    else 'emerging'
  end as stability_label,
  row_number() over (
    order by summary.team_count desc, summary.player_count desc, summary.archetype_key
  ) as archetype_rank
from summary
cross join total_teams
inner join anchors on anchors.archetype_key = summary.archetype_key
inner join candidate_counts on candidate_counts.archetype_key = summary.archetype_key
left join ranked_extensions extension
  on extension.archetype_key = summary.archetype_key
  and extension.extension_rank = 1
order by archetype_rank
