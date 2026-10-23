{{ config(location='../data/marts/detected_archetype_team_membership.csv') }}
-- Experimental team-to-archetype assignments. A team matches an archetype
-- when it contains at least one of that archetype group's qualifying core
-- triples. The strongest match is primary. One secondary/hybrid assignment
-- is retained only when its score is within 90% of the primary score, so a
-- team is not forced into a single identity when two cores describe it
-- almost equally well.
with legal_members as (
  select distinct team_id, pokemon_key
  from {{ ref('int_champions_roster_official') }}
),
team_triples as (
  select
    a.team_id,
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
matches as (
  select
    triples.team_id,
    candidate.archetype_key,
    max(candidate.candidate_score) as match_score,
    count(*) as matched_candidate_count
  from team_triples triples
  inner join {{ ref('detected_archetype_candidates') }} candidate
    on candidate.pokemon_key_a = triples.pokemon_key_a
    and candidate.pokemon_key_b = triples.pokemon_key_b
    and candidate.pokemon_key_c = triples.pokemon_key_c
  group by triples.team_id, candidate.archetype_key
),
ranked as (
  select
    *,
    row_number() over (
      partition by team_id
      order by match_score desc, archetype_key
    ) as assignment_rank,
    max(match_score) over (partition by team_id) as primary_score
  from matches
)
select
  team_id || '::' || assignment_rank as archetype_assignment_key,
  team_id,
  archetype_key,
  round(match_score, 4) as match_score,
  matched_candidate_count,
  assignment_rank,
  round(match_score / primary_score, 4) as relative_score,
  case when assignment_rank = 1 then 'primary' else 'secondary' end as assignment_type
from ranked
where assignment_rank = 1
  or (assignment_rank = 2 and match_score >= primary_score * 0.9)
order by team_id, assignment_rank
