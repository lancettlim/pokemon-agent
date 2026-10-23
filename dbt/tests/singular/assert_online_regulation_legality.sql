-- Gate: >=95% of Limitless online team-sheet slots are Pokémon legal in the
-- regulation their tournament resolved to (docs/upgrade-plan-2027q2.md,
-- S1), checked per regulation, the worst one reported.
--
-- This guards int_limitless_play_mapped's regulation resolution. Online
-- organisers choose a format label by hand and keep the old one after a
-- rollover: before the label-lag rule, 31 September tournaments labelled
-- "M-B" put 25% of their slots on Pokémon M-B doesn't allow (Rillaboom on
-- half their teams), and those games would have been reported as M-B.
-- Correctly resolved data sits at 98.7-99.9%: the remainder are form names
-- the legality snapshot spells differently (Meowstic's female Mega), the
-- same 0.1% the official events show, and the odd off-format pick at an
-- event that really was played under an old label. The bar is the one
-- int_limitless_play_mapped uses to keep an old label (95%), so an event
-- that rule keeps can't fail this gate; mislabelled events sit at 67-85%.
--
-- Legality is each regulation's newest legality_snapshot. Zero online slots
-- reports 0 and fails, like the coverage gates.
-- fail_calc reports basis points (100% = 10000 bps); see
-- assert_limitless_slug_mapping_coverage.sql.
{{ config(fail_calc='coalesce(min(legal_bps), 0)', error_if='<9500', warn_if='<9500', meta={'category': 'coverage', 'check_name': 'online_regulation_legality', 'description': 'Share of Limitless online team-sheet slots legal in their resolved regulation (worst regulation)', 'threshold': '>=0.95'}) }}
with latest_legality as (
  select regulation_code, pokemon_key, is_legal
  from {{ ref('legality_snapshot') }}
  qualify snapshot_date = max(snapshot_date) over (partition by regulation_code)
),
online_slots as (
  select roster.regulation_code, roster.pokemon_key
  from {{ ref('int_champions_roster') }} roster
  where roster.population = 'online'
)
select
  online_slots.regulation_code,
  round(
    count(*) filter (where latest_legality.is_legal)::double / count(*) * 10000
  )::integer as legal_bps
from online_slots
left join latest_legality
  on latest_legality.regulation_code = online_slots.regulation_code
  and latest_legality.pokemon_key = online_slots.pokemon_key
group by online_slots.regulation_code
