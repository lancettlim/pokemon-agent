{{ config(location='../data/marts/pokemon_usage_by_country.csv') }}
-- Country-grain half of backlog.md #7 ("which regions favor which
-- archetypes"): usage x player_country cross-tab, mirroring
-- pokemon_usage_by_regulation's usage-x-dimension pattern (backlog.md
-- #12) rather than pokemon_usage_summary's event_tier rows-plus-overall
-- shape, since there's no meaningful "overall" row here beyond what
-- pokemon_usage_summary already reports.
--
-- usage_share is usage_count's fraction of total roster appearances within
-- the same player_country partition -- "what does this region actually
-- play," not a raw count dominated by whichever country fielded the most
-- teams. Restricted to the current legal pool and to roster rows with a
-- reported player_country (tournament_team.player_country is optional --
-- not every MunchStats player row reports it).
--
-- team_share (docs/upgrade-plan-2027q2.md, V1): the share of the
-- country's teams that brought the Pokémon, over country_team_count.
with country_teams as (
  select team.player_country, count(distinct member.team_id) as country_team_count
  from {{ ref('int_champions_roster_official') }} member
  inner join {{ ref('tournament_team') }} team
    on team.team_id = member.team_id
  where team.player_country is not null and team.player_country != ''
  group by team.player_country
),
counted as (
  select
    member.pokemon_key,
    team.player_country,
    count(*) as usage_count
  from {{ ref('int_champions_roster_official') }} member
  inner join {{ ref('pokemon_stat_champions') }} champions
    on champions.pokemon_key = member.pokemon_key
    and champions.is_legal = true
  inner join {{ ref('tournament_team') }} team
    on team.team_id = member.team_id
  where team.player_country is not null and team.player_country != ''
  group by member.pokemon_key, team.player_country
)
select
  counted.pokemon_key,
  counted.player_country,
  counted.usage_count,
  round(
    counted.usage_count::double / sum(counted.usage_count) over (partition by counted.player_country),
    4
  ) as usage_share,
  round(counted.usage_count::double / country_teams.country_team_count, 4) as team_share,
  country_teams.country_team_count,
  row_number() over (
    partition by counted.player_country order by counted.usage_count desc, counted.pokemon_key
  ) as country_usage_rank
from counted
inner join country_teams
  on country_teams.player_country = counted.player_country
