{{ config(location='../data/marts/ladder_pokemon_usage.csv') }}
-- Showdown ladder usage per Pokémon (docs/upgrade-plan-2027q2.md, S2,
-- decision D2), one row per regulation, ladder (Bo1/Bo3), rating cutoff
-- and Pokémon, from Smogon's monthly statistics for the regulation's month
-- (pipelines/extract/smogon_ladder.py, pick_month).
--
-- The ladder is its own population: anyone on Showdown, weighted at the
-- 1760 cutoff toward the strongest players. Its usage is a weighted share
-- of teams, so it sits beside tournament team share on the same scale, but
-- the two are never added together. tournament_team_share is the official
-- figure for the same regulation (pokemon_usage_by_regulation), null where
-- the Pokémon was not legal in the latest legality snapshot; ladder_gap is
-- ladder minus tournament, positive where the ladder plays it more.
with ladder as (
  select
    ladder.regulation_code,
    ladder.month,
    ladder.variant,
    ladder.cutoff,
    ladder.battles,
    names.pokemon_key,
    ladder.pokemon_name as ladder_name,
    ladder.raw_count,
    ladder.usage,
    ladder.source_name,
    ladder.source_url
  from {{ ref('int_smogon_ladder_latest') }} ladder
  inner join {{ ref('int_smogon_ladder_names') }} names
    on names.smogon_name = ladder.pokemon_name
  where names.pokemon_key is not null
)
select
  ladder.regulation_code,
  ladder.month,
  ladder.variant,
  ladder.cutoff,
  ladder.battles,
  ladder.pokemon_key,
  ladder.ladder_name,
  ladder.raw_count,
  round(ladder.usage, 4) as ladder_usage,
  row_number() over (
    partition by ladder.regulation_code, ladder.variant, ladder.cutoff
    order by ladder.usage desc, ladder.pokemon_key
  ) as ladder_rank,
  tournament.team_share as tournament_team_share,
  tournament.usage_rank as tournament_rank,
  round(ladder.usage - tournament.team_share, 4) as ladder_gap,
  ladder.source_name,
  ladder.source_url
from ladder
left join {{ ref('pokemon_usage_by_regulation') }} tournament
  on tournament.regulation_code = ladder.regulation_code
  and tournament.pokemon_key = ladder.pokemon_key
order by ladder.regulation_code, ladder.variant, ladder.cutoff desc, ladder_rank
