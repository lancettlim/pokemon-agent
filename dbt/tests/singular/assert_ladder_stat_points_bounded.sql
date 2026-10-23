-- Warn: every ladder spread fits Champions' Stat Points, 66 per Pokémon and
-- at most 32 in one stat (docs/upgrade-plan-2027q2.md, S2). A row outside
-- them means Smogon's spread format changed or the extractor misread it.
{{ config(severity='warn', meta={'category': 'mart_quality', 'table_name': 'ladder_stat_point_spreads'}) }}
select *
from {{ ref('ladder_stat_point_spreads') }}
where sp_hp + sp_atk + sp_def + sp_spa + sp_spd + sp_spe > 66
  or greatest(sp_hp, sp_atk, sp_def, sp_spa, sp_spd, sp_spe) > 32
  or least(sp_hp, sp_atk, sp_def, sp_spa, sp_spd, sp_spe) < 0
