{{ config(location='../data/marts/archetype_matchups.csv') }}
-- Archetype vs archetype records (docs/upgrade-plan-2027q2.md, list #30):
-- for every decided official match whose two teams each have a primary
-- detected archetype, the win for one archetype over the other. One row
-- per (archetype, opponent archetype) with both directions present, so a
-- heatmap reads a row's record against each column. Mirror matches are
-- left out (they are always even).
--
-- Team vs team, like every head-to-head figure: no source says which
-- four Pokémon were brought, and an archetype is a label on the six.
-- Official events only (online pairings carry handles, not the RK9
-- identities detected archetypes are built from).
with primary_archetype as (
  select team_id, archetype_key
  from {{ ref('detected_archetype_team_membership') }}
  where assignment_rank = 1
),
decided as (
  select
    match.match_id,
    side_1.archetype_key as archetype_1,
    side_2.archetype_key as archetype_2,
    case
      when match.winner_team_id = match.team_id_1 then 1
      when match.winner_team_id = match.team_id_2 then 2
    end as winning_side
  from {{ ref('tournament_match') }} match
  inner join {{ ref('tournament_event') }} event
    on event.event_id = match.event_id
  inner join primary_archetype side_1
    on side_1.team_id = match.team_id_1
  inner join primary_archetype side_2
    on side_2.team_id = match.team_id_2
  where coalesce(event.event_tier, '') != 'Online'
    and match.winner_team_id is not null
    and side_1.archetype_key != side_2.archetype_key
),
both_directions as (
  select archetype_1 as archetype_key, archetype_2 as opponent_archetype_key,
    (winning_side = 1)::integer as won
  from decided
  union all
  select archetype_2, archetype_1, (winning_side = 2)::integer
  from decided
)
select
  archetype_key,
  opponent_archetype_key,
  count(*) as matches,
  sum(won) as wins,
  count(*) - sum(won) as losses,
  round(sum(won)::double / count(*), 4) as win_rate
from both_directions
group by archetype_key, opponent_archetype_key
order by archetype_key, matches desc
