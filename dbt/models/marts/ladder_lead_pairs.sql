{{ config(location='../data/marts/ladder_lead_pairs.csv') }}
-- The pairs Showdown ladder players lead with (docs/upgrade-plan-2027q2.md,
-- S3; laundry list #27), from sampled replays: how often each pair opens a
-- battle and how often that side wins. Every sampled battle counts (the
-- leads are always on the field); win rates read decided battles. A side
-- that opened with one Pokémon is left out. The Showdown ladder population
-- only, never tournament data. A Mega counts with its base Pokémon.
-- variant 'all' pools Bo1 and Bo3. The 50 most common pairs per regulation
-- and variant.
with leads as (
  select
    replay_id,
    side,
    regulation_code,
    variant,
    any_value(result) as result,
    any_value(is_decided) as is_decided,
    min(pokemon_key) as pokemon_key_1,
    max(pokemon_key) as pokemon_key_2,
    count(*) as keyed_leads
  from {{ ref('int_ladder_battle_pokemon') }}
  where led and lead_count = 2
  group by replay_id, side, regulation_code, variant
),
scoped as (
  select *, variant as variant_scope from leads
  union all
  select *, 'all' as variant_scope from leads
),
totals as (
  select regulation_code, variant_scope, count(*) as sides
  from scoped
  group by all
),
pairs as (
  select
    regulation_code,
    variant_scope,
    pokemon_key_1,
    pokemon_key_2,
    count(*) as sides_led,
    count(*) filter (where is_decided) as decided,
    count(*) filter (where is_decided and result = 'win') as wins
  from scoped
  -- Both leads resolved to a Pokémon, and two different ones.
  where keyed_leads = 2 and pokemon_key_1 is not null and pokemon_key_1 != pokemon_key_2
  group by all
),
ranked as (
  select
    pairs.*,
    totals.sides,
    row_number() over (
      partition by pairs.regulation_code, pairs.variant_scope
      order by pairs.sides_led desc, pairs.pokemon_key_1, pairs.pokemon_key_2
    ) as pair_rank
  from pairs
  inner join totals using (regulation_code, variant_scope)
)
select
  regulation_code,
  variant_scope as variant,
  pokemon_key_1,
  pokemon_key_2,
  sides_led,
  round(sides_led::double / sides, 4) as lead_share,
  decided,
  wins,
  round(wins::double / nullif(decided, 0), 4) as win_rate,
  pair_rank,
  'Pokémon Showdown replays' as source_name,
  'https://replay.pokemonshowdown.com' as source_url
from ranked
where pair_rank <= 50
order by regulation_code, variant, pair_rank
