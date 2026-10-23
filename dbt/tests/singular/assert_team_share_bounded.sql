{{ config(meta={'category': 'mart_quality', 'table_name': 'pokemon_usage_summary'}) }}
-- docs/upgrade-plan-2027q2.md, V1: team share is a share of teams, and a
-- Pokémon appears at most once per team, so it can never exceed 1. A
-- value above 1 means a denominator counted something other than the
-- partition's teams (or a team carried a Pokémon twice).
select 'pokemon_usage_summary' as mart, regulation_scope as scope, pokemon_key, team_share
from {{ ref('pokemon_usage_summary') }}
where team_share < 0 or team_share > 1
union all
select 'pokemon_usage_by_regulation', regulation_code, pokemon_key, team_share
from {{ ref('pokemon_usage_by_regulation') }}
where team_share < 0 or team_share > 1
union all
select 'pokemon_event_usage_vs_regulation', event_id, pokemon_key, event_team_share
from {{ ref('pokemon_event_usage_vs_regulation') }}
where event_team_share < 0 or event_team_share > 1
union all
select 'pokemon_usage_by_event_date', cast(event_date as varchar), pokemon_key, team_share
from {{ ref('pokemon_usage_by_event_date') }}
where team_share < 0 or team_share > 1
union all
select 'pokemon_usage_by_country', player_country, pokemon_key, team_share
from {{ ref('pokemon_usage_by_country') }}
where team_share < 0 or team_share > 1
