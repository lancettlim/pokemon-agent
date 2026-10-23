-- Every sampled Showdown ladder battle (docs/upgrade-plan-2027q2.md, S3)
-- reads consistently: two sides, one win and one loss (or a tie on both),
-- no more Pokémon brought than the team size, every brought Pokémon and
-- lead on the team shown at preview, and the leads among those brought.
-- A failure means the extractor misread a log; the battle would skew the
-- bring rates.
{{ config(meta={'category': 'mart_quality', 'table_name': 'ladder_bring_rate'}) }}
with side_checks as (
  select
    replay_id,
    side,
    brought_count > team_size as too_many_brought,
    list_has_all(string_split(team, '|'), string_split(brought, '|')) as brought_on_team,
    list_has_all(string_split(brought, '|'), string_split(leads, '|')) as leads_brought
  from {{ ref('int_ladder_battle_side') }}
),
battle_checks as (
  select
    replay_id,
    count(*) as sides,
    count(*) filter (where result = 'win') as wins,
    count(*) filter (where result = 'loss') as losses,
    count(*) filter (where result = 'tie') as ties
  from {{ ref('int_ladder_battle_side') }}
  group by replay_id
)
select 'side' as grain, replay_id, side as detail
from side_checks
where too_many_brought or not brought_on_team or not leads_brought
union all
select 'battle', replay_id, sides || ' sides, ' || wins || 'W ' || losses || 'L ' || ties || 'T'
from battle_checks
where sides != 2 or not ((wins = 1 and losses = 1) or ties = 2)
