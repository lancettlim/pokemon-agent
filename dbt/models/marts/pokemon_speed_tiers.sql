{{ config(location='../data/marts/pokemon_speed_tiers.csv') }}
-- Speed-tier bracket mart (backlog.md #16): the Speed Tiers tab has only
-- ever shown flat base speed, but who actually moves first is decided by
-- *modified* Speed under the format's common competitive scenarios --
-- a +1/+2 stat-stage boost, a Choice Scarf, or a team-wide Tailwind (and
-- a scarfed Pokémon under its own team's Tailwind, a common real
-- combination). One row per currently legal Pokémon, built on top of
-- pokemon_champions_profile's max_investment_speed (Level 50, 252 EVs, a
-- beneficial nature, 31 IV -- see that model's schema.yml entry for the
-- documented convention and formula).
--
-- The stage/item multipliers themselves (+1 stage and Choice Scarf are
-- both x1.5; +2 stage and Tailwind are both x2.0; a scarfed Pokémon under
-- Tailwind is x3.0) are universal, fixed game-mechanics constants, not
-- per-Pokémon extracted facts -- the same treatment schema.yml already
-- gives app.js's SPEED_TIERS bucketing thresholds and matchup.js's
-- TYPE_CHART/weather-boost multipliers, so they're applied here as plain
-- multiplication rather than sourced from anywhere. plus_one_speed and
-- scarf_speed (likewise plus_two_speed and tailwind_speed) are
-- numerically identical but kept as separate, distinctly-named columns:
-- "is my Pokémon fast enough after a Rock Polish" and "is my Pokémon fast
-- enough scarfed" are different real questions a Team Builder / Speed
-- Tiers view needs to answer even when the arithmetic happens to match.
--
-- regulation_scope passes through from pokemon_champions_profile: speeds
-- are identical in every scope, usage/win rate are per scope.
select
  regulation_scope,
  pokemon_key,
  type_1,
  type_2,
  speed as base_speed,
  max_investment_speed,
  floor(max_investment_speed * 1.5) as plus_one_speed,
  floor(max_investment_speed * 1.5) as scarf_speed,
  floor(max_investment_speed * 2.0) as plus_two_speed,
  floor(max_investment_speed * 2.0) as tailwind_speed,
  floor(max_investment_speed * 3.0) as scarf_tailwind_speed,
  usage_count,
  usage_share,
  win_rate,
  record_count
from {{ ref('pokemon_champions_profile') }}
order by regulation_scope, max_investment_speed desc
