{{ config(location='../data/marts/pokemon_champions_profile.csv') }}
-- Denormalized per-Pokémon profile for the dashboard's Speed Tiers, Team
-- Builder, Pokémon Profile, and Matchup views (docs/todo.md M6 backlog):
-- one row per currently legal Pokémon, combining its Champions-format base
-- stats (speed, for speed-tier ordering), its type_1/type_2 (for the
-- Profile type badge, type/role filters, and the Matchup tab's type
-- effectiveness and damage calculator), and its overall usage/win-rate
-- KPIs, so those views can list/sort/filter the legal pool without joining
-- multiple marts client-side. usage_count/usage_share/win_rate/
-- record_count are nullable — real MunchStats tournament data doesn't
-- cover every legal Pokémon, and a null here means "not yet seen in a
-- recorded roster", not zero.
--
-- max_investment_speed (backlog.md #16) is the Level-50 Speed stat under
-- the standard competitive "max speed investment" convention -- 252 EVs, a
-- beneficial nature, and a perfect (31) IV -- rather than the raw base
-- `speed` stat above, which is what a real team's Speed actually looks
-- like at the format's standard level and is what determines turn order
-- in practice. Exact EVs/nature per real roster entry would need Victory
-- Road's moveset data (backlog.md #25, still deferred); this is the
-- documented simplification that item calls out as the honest interim
-- convention. Formula (Bulbapedia's standard stat formula, Level 50, IV
-- 31, EV 252, nature 1.1x): floor((floor((2*base + 31 + floor(252/4)) *
-- 50/100) + 5) * 1.1), which simplifies exactly (2*base+94 is always
-- even) to floor((base_speed + 52) * 1.1) -- verified against a known
-- reference value: base speed 142 (Dragapult) -> 213.
--
-- regulation_scope (docs/upgrade-plan-2026q4.md, A3): every legal Pokémon
-- gets one row per regulation plus 'all', carrying that scope's usage and
-- win rate (null where it wasn't used). Stats are the same in every scope.
with scopes as (
  select regulation_code as regulation_scope from {{ ref('champions_regulations') }}
  union all
  select 'all'
)
select
  scopes.regulation_scope,
  champions.pokemon_key,
  pokemon.type_1,
  pokemon.type_2,
  champions.hp,
  champions.attack,
  champions.defense,
  champions.sp_attack,
  champions.sp_defense,
  champions.speed,
  floor((champions.speed + 52) * 1.1) as max_investment_speed,
  champions.stat_total,
  usage.usage_count,
  usage.usage_share,
  win.win_rate,
  win.record_count
from {{ ref('pokemon_stat_champions') }} champions
cross join scopes
left join {{ ref('pokemon') }} pokemon
  on pokemon.pokemon_key = champions.pokemon_key
left join (
  select * from {{ ref('pokemon_usage_summary') }} where event_tier is null
) usage
  on usage.pokemon_key = champions.pokemon_key
  and usage.regulation_scope = scopes.regulation_scope
left join {{ ref('pokemon_win_rate_summary') }} win
  on win.pokemon_key = champions.pokemon_key
  and win.regulation_scope = scopes.regulation_scope
where champions.is_legal = true
order by scopes.regulation_scope, champions.speed desc
