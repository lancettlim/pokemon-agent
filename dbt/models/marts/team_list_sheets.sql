{{ config(location='../data/marts/team_list_sheets.csv') }}
-- Full sheets (item, ability, nature, moves per slot) for the converged
-- team lists Top Teams shows (docs/upgrade-plan-2027q1.md, P4): "Use this
-- team" loads one into the Builder with the sets players actually ran.
-- Limited to the 60 most-converged lists; one row per list x slot.
select
  member.team_list_id,
  member.slot_number,
  member.pokemon_key,
  member.item_name,
  member.ability,
  member.nature,
  member.moves
from {{ ref('team_list_member') }} member
inner join {{ ref('team_list_convergence') }} convergence
  on convergence.team_list_id = member.team_list_id
where convergence.convergence_rank <= 60
order by member.team_list_id, member.slot_number
