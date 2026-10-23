{{ config(location='../data/marts/ladder_checks_counters.csv') }}
-- Showdown ladder checks and counters (docs/upgrade-plan-2027q2.md, S2):
-- for each Pokémon, the opponents that most often KO it or force it out,
-- read from the battle logs of every rated ladder battle in the
-- regulation's month. The only Pokémon-vs-Pokémon battle signal any source
-- publishes; tournament data is team vs team, and this is never presented
-- as tournament data.
--
-- ko_or_switch_rate is the share of the pair's encounters in which
-- pokemon_key (not the counter) was KO'd or switched out; score is
-- Smogon's own ranking, ko_or_switch_rate minus four standard deviations,
-- so a high rate measured on few encounters ranks lower. A Pokémon's mirror
-- match is dropped.
--
-- Read from the all-ratings (cutoff 0) files only: Smogon lists a pair
-- only above about 20 encounters, and at 1760 encounters are weighted by
-- rating, so those files carry almost none (see
-- pipelines/extract/smogon_ladder.py).
with counters as (
  select
    counters.regulation_code,
    counters.month,
    counters.variant,
    counters.cutoff,
    counters.battles,
    pokemon.pokemon_key,
    counter.pokemon_key as counter_pokemon_key,
    counters.encounters,
    counters.ko_or_switch_rate,
    counters.std_dev,
    counters.source_name,
    counters.source_url
  from {{ ref('int_smogon_ladder_counters_latest') }} counters
  inner join {{ ref('int_smogon_ladder_names') }} pokemon
    on pokemon.smogon_name = counters.pokemon_name
  inner join {{ ref('int_smogon_ladder_names') }} counter
    on counter.smogon_name = counters.counter_name
  where counters.cutoff = 0
    and pokemon.pokemon_key is not null
    and counter.pokemon_key is not null
    and pokemon.pokemon_key != counter.pokemon_key
)
select
  regulation_code,
  month,
  variant,
  cutoff,
  battles,
  pokemon_key,
  counter_pokemon_key,
  round(encounters)::integer as encounters,
  round(ko_or_switch_rate, 4) as ko_or_switch_rate,
  round(std_dev, 4) as std_dev,
  round(ko_or_switch_rate - 4 * std_dev, 4) as score,
  row_number() over (
    partition by regulation_code, variant, pokemon_key
    order by ko_or_switch_rate - 4 * std_dev desc, counter_pokemon_key
  ) as counter_rank,
  source_name,
  source_url
from counters
order by regulation_code, variant, pokemon_key, counter_rank
