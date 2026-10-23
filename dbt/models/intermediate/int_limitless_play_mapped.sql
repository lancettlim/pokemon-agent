-- Limitless online-tournament team-sheet slots, resolved to canonical
-- pokemon_key and to a Champions regulation (docs/upgrade-plan-2027q2.md,
-- S1).
--
-- The platform uses the same species slugs as limitlessvgc.com, so the
-- same two seeds resolve them: limitless_slug_to_pokeapi_form, then
-- limitless_mega_item_to_pokeapi_form for a base species holding its Mega
-- Stone (Limitless lists "Charizard" + "Charizardite Y", the dataset keys
-- the evolved form). Online players bring a wider pool than official top
-- cuts, so a slug the seed doesn't list falls back to the PokéAPI form of
-- the same name: int_limitless_mapped.sql documents that Limitless slugs
-- follow PokéAPI's form names (78 of 83 matched outright), and the seed
-- exists for the exceptions, which it still decides. A slug resolving to
-- neither is dropped, per docs/dataset-spec.md.
--
-- Mega Stones are typed by hand online ("salamencite", " Lucarionite Z"),
-- so the item matches case- and space-insensitively, and a stone the seed
-- doesn't list (the seed was built from official top cuts: no Meganiumite,
-- Hawluchanite, Slowbronite, ...) still resolves when it is the slot's own
-- species' stone -- its first five letters match the slug -- and PokéAPI
-- has the "<slug>-mega[-x|-y|-z]" form. Without this, 1,044 online Mega
-- holders read as their base form. A typo or another species' stone keeps
-- the base form.
--
-- Limitless leaves a dropped player's placing blank, and placement is a
-- required tournament_team field. A drop is placed after every finisher of
-- its tournament, by record (more wins, then fewer losses, then handle for
-- a stable order) -- how RK9's standings rank a drop -- and
-- placement_is_derived says so.
--
-- regulation_code comes from the champions_regulations seed's
-- limitless_play_format ("M-C"), matched case-insensitively. Organisers
-- pick the label by hand and keep the old one for weeks after a rollover:
-- 31 tournaments labelled "M-B" ran in September 2026, after M-C began,
-- 29 of them plainly M-C (named so, with Rillaboom, legal only in M-C, on
-- half their teams; 67-85% of their slots legal in M-B), 2 genuinely M-B
-- (98-99%). So a tournament dated after its label's regulation ended keeps
-- the label only when at least 95% of its slots are legal under it, and
-- otherwise takes the regulation in force on its date. A label for a set
-- that hasn't started yet is kept: those are early games of the new
-- format. assert_online_regulation_legality checks the result against the
-- legal pools.
--
-- Identity keys carry an "LP-" prefix so an online event, team or player
-- can never collide with an RK9 or MunchStats id: handles are not legal
-- names and never join official identities.
with players as (
  select distinct
    tournament_id,
    player_handle,
    try_cast(nullif(cast(placement as varchar), '') as integer) as placement,
    try_cast(record_wins as integer) as record_wins,
    try_cast(record_losses as integer) as record_losses
  from {{ ref('int_limitless_play_latest') }}
),
placed as (
  select
    tournament_id,
    player_handle,
    placement is null as placement_is_derived,
    coalesce(
      placement,
      max(placement) over (partition by tournament_id)
        + row_number() over (
          partition by tournament_id, placement is null
          order by record_wins desc nulls last, record_losses asc nulls last, player_handle
        ),
      row_number() over (
        partition by tournament_id
        order by record_wins desc nulls last, record_losses asc nulls last, player_handle
      )
    ) as placement
  from players
),
slots as (
  select
    'LP-' || source.tournament_id as event_id,
    source.tournament_id,
    source.tournament_name,
    cast(source.tournament_date as date) as event_date,
    source.tournament_format,
    label_regulation.regulation_code as label_regulation_code,
    cast(source.tournament_date as date) >= label_regulation.end_date as label_has_ended,
    dated_regulation.regulation_code as dated_regulation_code,
    source.player_count,
    'LP-' || source.tournament_id || '-' || source.player_handle as team_id,
    'LP-' || source.player_handle as player_id,
    source.player_handle,
    source.player_name,
    nullif(source.player_country, '') as player_country,
    placed.placement,
    placed.placement_is_derived,
    source.record_wins,
    source.record_losses,
    source.record_ties,
    source.dropped,
    source.slot_number,
    source.pokemon_slug,
    pokemon.pokemon_key,
    pokemon.pokemon_id,
    nullif(source.item_name, '') as item_name,
    nullif(source.ability, '') as ability,
    nullif(source.tera_type, '') as tera_type,
    nullif(source.nature, '') as nature,
    nullif(source.moves, '') as moves,
    source.source_name,
    source.source_url,
    source.source_record_id,
    source.extracted_at_utc,
    source.dataset_version
  from {{ ref('int_limitless_play_latest') }} source
  inner join placed
    on placed.tournament_id = source.tournament_id
    and placed.player_handle = source.player_handle
  inner join {{ ref('champions_regulations') }} label_regulation
    on upper(label_regulation.limitless_play_format) = upper(source.tournament_format)
  left join {{ ref('champions_regulations') }} dated_regulation
    on cast(source.tournament_date as date) >= dated_regulation.start_date
    and cast(source.tournament_date as date) < dated_regulation.end_date
  left join {{ ref('limitless_slug_to_pokeapi_form') }} seed_map
    on seed_map.limitless_pokemon_slug = source.pokemon_slug
  left join {{ ref('limitless_mega_item_to_pokeapi_form') }} mega_map
    on mega_map.limitless_pokemon_slug = source.pokemon_slug
    and lower(trim(mega_map.item_name)) = lower(trim(source.item_name))
  left join {{ ref('pokemon') }} mega_rule
    on mega_map.pokeapi_form_name is null
    and regexp_matches(lower(trim(source.item_name)), '^[a-z]+ite( [xyz])?$')
    and left(lower(trim(source.item_name)), 5) = left(source.pokemon_slug, 5)
    and mega_rule.form_name = source.pokemon_slug || '-mega'
      || coalesce('-' || nullif(regexp_extract(lower(trim(source.item_name)), ' ([xyz])$', 1), ''), '')
  inner join {{ ref('pokemon') }} pokemon
    on pokemon.form_name = coalesce(
      mega_map.pokeapi_form_name,
      mega_rule.form_name,
      seed_map.pokeapi_form_name,
      source.pokemon_slug
    )
),
latest_legality as (
  select regulation_code, pokemon_key, is_legal
  from {{ ref('legality_snapshot') }}
  qualify snapshot_date = max(snapshot_date) over (partition by regulation_code)
),
-- Share of each tournament's slots legal under its own label.
label_fit as (
  select
    slots.tournament_id,
    avg(case when latest_legality.is_legal then 1.0 else 0.0 end) as label_legal_share
  from slots
  left join latest_legality
    on latest_legality.regulation_code = slots.label_regulation_code
    and latest_legality.pokemon_key = slots.pokemon_key
  group by slots.tournament_id
)
select
  slots.* exclude (label_regulation_code, label_has_ended, dated_regulation_code),
  case
    when slots.label_has_ended and label_fit.label_legal_share < 0.95
      then coalesce(slots.dated_regulation_code, slots.label_regulation_code)
    else slots.label_regulation_code
  end as regulation_code
from slots
inner join label_fit
  on label_fit.tournament_id = slots.tournament_id
