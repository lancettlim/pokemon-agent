-- Gate: >=90% of tournament records mapped to normalized team tables (docs/dataset-spec.md).
-- MunchStats rows only: tournament_team_member also holds Limitless online
-- slots (docs/upgrade-plan-2027q2.md, S1), which have their own gate
-- (assert_limitless_play_slug_mapping_coverage) and would otherwise let
-- this ratio pass with most MunchStats rows unmapped.
-- Zero staged rows reports 0 coverage (fails the gate) rather than passing
-- vacuously: the source's external_location glob (_sources.yml) errors out
-- before this query ever runs if no snapshot file exists at all, so a
-- zero-row result here only happens when a snapshot file exists but is
-- empty -- exactly the total-upstream-outage case this gate exists to catch
-- (docs/backlog.md #36).
-- fail_calc must resolve to an integer (dbt's run-results schema requires it), so this
-- reports coverage in basis points (100% = 10000 bps); pipelines/validate/report.py
-- divides by 10000 to recover the ratio for the report's metric_value.
{{ config(fail_calc='max(coverage_bps)', error_if='<9000', warn_if='<9000', meta={'category': 'coverage', 'check_name': 'tournament_team_member_mapping_coverage', 'description': 'Share of tournament roster rows mapped to normalized team tables', 'threshold': '>=0.90'}) }}
select
  case
    when count(*) = 0 then 0
    else round((
      select count(*) from {{ ref('tournament_team_member') }} where source_name = 'MunchStats'
    )::double / count(*) * 10000)::integer
  end as coverage_bps
from {{ source('staging', 'munchstats') }}
