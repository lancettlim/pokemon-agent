{{ config(location='../data/marts/ladder_stat_point_spreads.csv') }}
-- The Stat Point spreads Showdown ladder players ran (docs/upgrade-plan-
-- 2027q2.md, S2, decision D3): per regulation, ladder, rating cutoff and
-- Pokémon, its most-run nature and spread, with share the spread's share of
-- all that Pokémon's spreads in the file.
--
-- Ladder only. Official team sheets publish ability, item, nature and
-- moves and no spreads, so these never enter a tournament entity, a team
-- sheet or the Builder's sets, and every consumer labels them "Showdown
-- ladder; tournament sheets don't publish spreads". Champions' Stat Points
-- are 66 per Pokémon, at most 32 in one stat
-- (assert_ladder_stat_points_bounded).
select
  spreads.regulation_code,
  spreads.month,
  spreads.variant,
  spreads.cutoff,
  spreads.battles,
  names.pokemon_key,
  spreads.nature,
  spreads.sp_hp,
  spreads.sp_atk,
  spreads.sp_def,
  spreads.sp_spa,
  spreads.sp_spd,
  spreads.sp_spe,
  round(spreads.share, 4) as share,
  row_number() over (
    partition by spreads.regulation_code, spreads.variant, spreads.cutoff, names.pokemon_key
    order by spreads.weight desc, spreads.source_record_id
  ) as spread_rank,
  spreads.source_name,
  spreads.source_url
from {{ ref('int_smogon_ladder_spreads_latest') }} spreads
inner join {{ ref('int_smogon_ladder_names') }} names
  on names.smogon_name = spreads.pokemon_name
where names.pokemon_key is not null
order by spreads.regulation_code, spreads.variant, spreads.cutoff desc, names.pokemon_key, spread_rank
