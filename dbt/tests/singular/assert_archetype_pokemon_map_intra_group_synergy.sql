-- Backlog #15's softer intermediate step: archetype_pokemon_map is a
-- curated, NOT-sourced seed (dbt/seeds/schema.yml) -- someone's editorial
-- judgment about which Pokémon belong to which archetype, not derived
-- from real co-occurrence data. Rather than replacing it outright with
-- full clustering (a bigger, separate ask this item also names), this
-- flags -- doesn't fail the build over -- archetypes whose curated
-- members don't actually show above-chance real team synergy with each
-- other, using pokemon_team_synergy's lift (backlog #9) as the "observed
-- cluster" signal to compare against.
--
-- Per archetype: avg_intra_group_lift averages pokemon_team_synergy.lift
-- across every unordered pair of the archetype's own curated members
-- (lift is symmetric, so averaging both mirrored directions doesn't skew
-- it). A pair that has never co-occurred on a real tournament team at all
-- has no pokemon_team_synergy row -- left join preserves that pair as
-- NULL rather than silently dropping it, so an archetype whose members
-- simply never appear together doesn't get treated the same as one with
-- no data at all.
--
-- drift_status:
--   insufficient_data  -- fewer than 2 curated members: no pair exists to judge
--   no_observed_pairs  -- every curated pair has zero real co-occurrence
--   drifted            -- avg lift <= 1.0: real co-occurrence is no better
--                          than chance would predict
--   aligned            -- avg lift > 1.0: members really do pair up more
--                          than their individual popularity would predict
--
-- severity=warn (this test's own config, not meta.category): a curated
-- archetype not matching observed data is real signal worth surfacing,
-- not a data-quality defect that should fail `dbt build`/CI the way an
-- actual duplicate key or referential-integrity violation would.
{{ config(
    severity='warn',
    meta={'category': 'archetype_drift', 'check_name': 'archetype_pokemon_map_intra_group_synergy'}
) }}

with map as (
  select archetype_key, pokemon_key
  from {{ ref('archetype_pokemon_map') }}
),
archetypes as (
  select distinct archetype_key from map
),
-- Every ordered pair within an archetype (a member paired with each other
-- member, both directions -- pokemon_team_synergy is mirrored the same
-- way). A single-member archetype contributes no rows here at all, which
-- is exactly what `scored`'s left join from `archetypes` (not from this
-- CTE) needs to correctly report pair_count = 0 for it below, rather than
-- that archetype silently vanishing from the result entirely.
pairs as (
  select a.archetype_key, a.pokemon_key, b.pokemon_key as partner_pokemon_key
  from map a
  inner join map b
    on b.archetype_key = a.archetype_key
    and b.pokemon_key != a.pokemon_key
),
scored as (
  select
    archetypes.archetype_key,
    count(pairs.pokemon_key) as pair_count,
    round(avg(synergy.lift), 4) as avg_intra_group_lift
  from archetypes
  left join pairs
    on pairs.archetype_key = archetypes.archetype_key
  left join {{ ref('pokemon_team_synergy') }} synergy
    on synergy.pokemon_key = pairs.pokemon_key
    and synergy.partner_pokemon_key = pairs.partner_pokemon_key
    and synergy.regulation_scope = 'all'
  group by archetypes.archetype_key
),
with_status as (
  select
    archetype_key,
    pair_count,
    avg_intra_group_lift,
    case
      when pair_count = 0 then 'insufficient_data'
      when avg_intra_group_lift is null then 'no_observed_pairs'
      when avg_intra_group_lift <= 1.0 then 'drifted'
      else 'aligned'
    end as drift_status
  from scored
)
select *
from with_status
where drift_status in ('drifted', 'no_observed_pairs')
