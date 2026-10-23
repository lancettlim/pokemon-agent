-- Warn: ladder bring, lead and win rates (docs/upgrade-plan-2027q2.md, S3)
-- are shares, and a Pokémon is never brought or led more often than it is
-- shown at preview.
{{ config(severity='warn', meta={'category': 'mart_quality', 'table_name': 'ladder_bring_rate'}) }}
select *
from {{ ref('ladder_bring_rate') }}
where brought > complete_shown
  or led > shown
  or complete_shown > shown
  or greatest(shown_share, lead_rate, coalesce(bring_rate, 0), coalesce(win_rate_brought, 0), coalesce(win_rate_benched, 0)) > 1
  or least(shown_share, lead_rate, coalesce(bring_rate, 0), coalesce(win_rate_brought, 0), coalesce(win_rate_benched, 0)) < 0
