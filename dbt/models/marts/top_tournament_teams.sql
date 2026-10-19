{{ config(location='../data/marts/top_tournament_teams.csv') }}
-- Top Teams tab's leaderboard feed (docs/design-system.md's "Top teams"
-- ask): one row per tournament_team with a reported win/loss record,
-- ranked by win_rate, with its event context and full roster (all
-- reported member Pokémon, not filtered to the current legal pool -- a
-- team's roster is a historical fact, and filtering members out would
-- misrepresent what was actually played). This is real, sourced
-- MunchStats data, distinct from the curated, hand-authored Pro Team
-- Gallery (data/reference_teams/reference_teams.json) the same tab also
-- surfaces -- see docs/dashboard.md's "Pro Team Gallery" section.
--
-- Capped to the top 100 by win_rate (`limit 100` below): MunchStats
-- reports tens of thousands of individual teams, but the dashboard only
-- ever surfaces the top ~18 in a .grid-6xn tile grid with no table tier
-- underneath (docs/design-system.md's "Top Teams" section) -- shipping
-- every team into the page's baked-in JSON (window.DASHBOARD_DATA) would
-- bloat every visitor's page load for rows nothing in the UI ever reads.
-- 100 leaves headroom for a future detail-table tier without the
-- unbounded-row-count cost.
-- regulation_scope (docs/upgrade-plan-2026q4.md, A3): the top 100 teams
-- per regulation plus the top 100 across all Champions regulations. A
-- team belongs to exactly one regulation (its event's), so it appears in
-- at most two scopes. Ties on win_rate now break on wins, then team_id,
-- so the ranking is deterministic.
with member_rosters as (
  select
    team_id,
    string_agg(pokemon_key, '|' order by slot_number) as pokemon_keys
  from {{ ref('int_champions_roster') }}
  group by team_id
),
teams as (
  select
    team.team_id,
    event.event_name,
    event.event_tier,
    event.event_date,
    event.regulation_code,
    team.player_name,
    team.player_country,
    team.placement,
    team.record_wins,
    team.record_losses,
    round(
      team.record_wins::double / nullif(team.record_wins + team.record_losses, 0),
      4
    ) as win_rate,
    roster.pokemon_keys
  from {{ ref('tournament_team') }} team
  inner join {{ ref('tournament_event') }} event
    on event.event_id = team.event_id
  inner join member_rosters roster
    on roster.team_id = team.team_id
  where team.record_wins is not null
    and team.record_losses is not null
    and (team.record_wins + team.record_losses) > 0
),
scoped as (
  select regulation_code as regulation_scope, * from teams
  union all
  select 'all' as regulation_scope, * from teams
),
ranked as (
  select
    *,
    row_number() over (
      partition by regulation_scope
      order by win_rate desc, record_wins desc, team_id
    ) as team_rank
  from scoped
)
select
  regulation_scope,
  team_id,
  event_name,
  event_tier,
  event_date,
  player_name,
  player_country,
  placement,
  record_wins,
  record_losses,
  win_rate,
  pokemon_keys,
  team_rank
from ranked
where team_rank <= 100
order by regulation_scope, team_rank
