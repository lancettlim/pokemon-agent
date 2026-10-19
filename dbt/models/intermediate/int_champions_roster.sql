-- Tournament roster slots scoped to the Pokémon Champions format.
--
-- Every mart downstream of tournament rosters reads this rather than
-- tournament_team_member directly, because MunchStats indexes standard VGC
-- events (regulations F/H/I) alongside Champions ones and nothing used to
-- tell them apart -- so "Incineroar's usage" silently averaged two
-- different games with different legal pools and different mechanics.
-- Champions events are only 17.2% of staged roster slots, so this is not a
-- rounding error in the numbers it corrects.
--
-- The same conflation is what produced this repo's long-documented
-- "MunchStats nature coverage is only ~17%" note: that figure is the
-- Champions share of the corpus, not a coverage defect. Within Champions,
-- nature is reported for 100% of slots (and tera_type for 0%, since the
-- format has no Tera mechanic); outside it, exactly the reverse.
--
-- Champions membership comes from the champions_regulations seed, which
-- lists every regulation set. This used to compare against a single
-- hardcoded Reg M-A format, which silently excluded the 2026 World
-- Championships (M-B) and every M-C event.
--
-- Joins team and event alongside the member row so downstream marts get
-- placement/record/tier/date/regulation without repeating the same joins.
select
  member.team_member_id,
  member.team_id,
  member.event_id,
  member.pokemon_key,
  member.pokemon_id,
  member.slot_number,
  member.item_name,
  member.ability,
  member.tera_type,
  member.nature,
  member.moves,
  team.player_id,
  team.player_name,
  team.player_country,
  team.placement,
  team.record_wins,
  team.record_losses,
  event.event_name,
  event.event_date,
  event.event_tier,
  event.event_format,
  event.regulation_code
from {{ ref('tournament_team_member') }} member
inner join {{ ref('tournament_team') }} team
  on team.team_id = member.team_id
inner join {{ ref('tournament_event') }} event
  on event.event_id = team.event_id
where event.regulation_code is not null
