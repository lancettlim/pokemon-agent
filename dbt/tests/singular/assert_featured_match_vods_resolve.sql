-- Every curated "Watch on stream" link (featured_match_vods, docs/upgrade-
-- plan-2027q2.md S5) names a real top-cut match and a YouTube watch URL. A
-- row that matches no match would never show, so a typo in the seed's event,
-- round or table fails here instead of going quietly missing.
{{ config(meta={'category': 'mart_quality', 'table_name': 'tournament_top_cut_matches'}) }}
select vods.*
from {{ ref('featured_match_vods') }} vods
left join {{ ref('tournament_top_cut_matches') }} matches
  on matches.event_id = vods.event_id
  and matches.round_number = vods.round_number
  and matches.table_number = vods.table_number
where matches.match_id is null
  or not regexp_full_match(vods.url, 'https://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{11}')
  or vods.t < 0
