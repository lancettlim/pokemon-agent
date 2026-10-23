{{ config(location='../data/marts/team_list_convergence.csv') }}
-- Top Teams tab's "Converged lists" feed: one row per canonical Limitless
-- team-list id, ranked by how many distinct players fielded that same
-- six-Pokémon composition. Answers a question no other mart does -- not
-- "which Pokémon were popular" but "which whole *compositions* did the
-- field independently converge on".
--
-- Champions scoping: this deliberately does NOT read
-- int_champions_roster, and that is not a bypass of the rule in CLAUDE.md.
-- That gate exists because MunchStats indexes standard VGC events
-- alongside Champions ones, so a roster mart must filter by
-- event_format. Limitless is extracted Champions-only (its regulation_set
-- filter reads the champions_regulations seed) -- and this mart's grain is
-- team_list_member, a different table with no event_format column to
-- filter on. Scoping is a property of the source here, not of a filter.
--
-- Coverage caveat, surfaced in the UI rather than only recorded here:
-- Limitless publishes the day-2 cut only, roughly 93 distinct Pokémon
-- across ~2,150 member rows against 203 in the full Champions roster. This
-- is a view of what converged at the top of the field, not of the meta.
with member_rosters as (
  select
    team_list_id,
    string_agg(pokemon_key, '|' order by slot_number) as pokemon_keys,
    count(*) as roster_size
  from {{ ref('team_list_member') }}
  group by team_list_id
)
select
  list.team_list_id,
  list.player_count,
  list.tournament_count,
  list.best_placement,
  list.first_seen_date,
  list.regulation_set,
  roster.pokemon_keys,
  roster.roster_size,
  row_number() over (
    order by list.player_count desc, list.tournament_count desc, list.best_placement asc, list.team_list_id
  ) as convergence_rank
from {{ ref('team_list') }} list
inner join member_rosters roster
  on roster.team_list_id = list.team_list_id
order by convergence_rank
