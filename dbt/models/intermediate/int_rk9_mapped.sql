-- Resolves each side of an RK9 pairing to this dataset's own player/team
-- identity, so match outcomes can be joined to rosters.
--
-- No mapping seed is needed here, unlike the OP.GG/PokéBase/MunchStats/
-- Bulbagarden Pokémon-name seeds: RK9 and MunchStats are the same
-- underlying data (MunchStats scrapes RK9), so `event_id` matches exactly
-- and players match on their own reported (name, country). Verified against
-- real data: 1003/1007 = 99.6% of NAIC 2026 round-5 Masters pairing slots
-- resolve to a MunchStats roster player. The join key is lower/trimmed
-- rather than raw so incidental casing or padding on either feed doesn't
-- drop an otherwise-exact match.
--
-- A (name, country) two entrants share is left unresolved rather than
-- guessed (docs/upgrade-plan-2027q2.md, E2): it shows up as the same name
-- twice in one round, or twice on the roster. Before this, both Noah
-- Gardners (US) at Indianapolis 2026 resolved to the one who made top 16,
-- whose bracket path then showed two round-1 matches, and head-to-head
-- credited his team with the other's results; three events had such a
-- pair. Only Masters pairings resolve: MunchStats has no Junior or Senior
-- rosters, so a junior sharing a Masters player's name would otherwise
-- take their team.
--
-- Unresolved players are kept with a null team_id, not dropped: the
-- residual is real (players who dropped before submitting a team list, and
-- the Junior/Senior divisions, which MunchStats does not scrape at all), and
-- assert_rk9_pairing_mapping_coverage.sql can only measure the mapping rate
-- if the misses survive to be counted.

with pairings as (
  select * from {{ ref('int_rk9_latest') }}
),

-- (event, name, country) keys two entrants share, from either side.
pairing_names as (
  select event_id, division, round_number,
    lower(trim(player1_name)) as player_join_key,
    lower(trim(player1_country)) as country_join_key
  from pairings
  union all
  select event_id, division, round_number,
    lower(trim(player2_name)), lower(trim(player2_country))
  from pairings
  where nullif(trim(player2_name), '') is not null
),
ambiguous_names as (
  select distinct event_id, player_join_key, country_join_key
  from pairing_names
  where division = 'Masters'
  group by event_id, division, round_number, player_join_key, country_join_key
  having count(*) > 1
  union
  select event_id, lower(trim(player_name)), lower(trim(player_country))
  from {{ ref('int_munchstats_deduped') }}
  group by event_id, lower(trim(player_name)), lower(trim(player_country))
  having count(distinct player_id) > 1
),

-- One row per (event, player). A roster has six slots per player, so this
-- collapses them; a name two players share is excluded above.
roster_players as (
  select
    event_id,
    lower(trim(player_name)) as player_join_key,
    lower(trim(player_country)) as country_join_key,
    player_id,
    team_id
  from (
    select
      event_id,
      player_name,
      player_country,
      player_id,
      team_id,
      row_number() over (
        partition by event_id, lower(trim(player_name)), lower(trim(player_country))
        order by team_id asc
      ) as _rn
    from {{ ref('int_munchstats_deduped') }}
  ) deduped
  where _rn = 1
    and not exists (
      select 1
      from ambiguous_names
      where ambiguous_names.event_id = deduped.event_id
        and ambiguous_names.player_join_key = lower(trim(deduped.player_name))
        and ambiguous_names.country_join_key = lower(trim(deduped.player_country))
    )
)

select
  pairings.event_id,
  pairings.pod_id,
  pairings.division,
  pairings.round_number,
  pairings.table_number,
  pairings.outcome,
  pairings.is_complete,
  pairings.player1_name,
  pairings.player1_country,
  pairings.player2_name,
  pairings.player2_country,
  player1.player_id as player_id_1,
  player1.team_id as team_id_1,
  player2.player_id as player_id_2,
  player2.team_id as team_id_2,
  case pairings.outcome
    when 'player1_win' then player1.team_id
    when 'player2_win' then player2.team_id
    else null
  end as winner_team_id,
  pairings.source_name,
  pairings.source_url,
  pairings.source_record_id,
  pairings.extracted_at_utc,
  pairings.dataset_version
from pairings
left join roster_players as player1
  on pairings.division = 'Masters'
  and player1.event_id = pairings.event_id
  and player1.player_join_key = lower(trim(pairings.player1_name))
  and player1.country_join_key = lower(trim(pairings.player1_country))
left join roster_players as player2
  on pairings.division = 'Masters'
  and player2.event_id = pairings.event_id
  and player2.player_join_key = lower(trim(pairings.player2_name))
  and player2.country_join_key = lower(trim(pairings.player2_country))
