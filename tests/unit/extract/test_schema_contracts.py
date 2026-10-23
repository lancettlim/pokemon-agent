"""Backlog #41: every extractor's FIELDNAMES must match the field list its
data/staging/<subdir>.schema.json contract declares -- name-for-name, in
the same order -- so a code change that adds/renames/drops a staging
column can't drift silently out of sync with the documented contract.
This is the staging half of schema-drift enforcement; see
tests/unit/validate/test_report.py for the normalized-layer half (checked
against a real dbt build's CSV output, not just the extractor code)."""

import json
from pathlib import Path

import pytest

from pipelines.cli import _EXTRACTORS
from pipelines.extract import pokeapi, smogon_ladder
from pipelines.schema_contracts import schema_field_names, staging_contract_mismatches

REPO_ROOT = Path(__file__).resolve().parents[3]
STAGING_SCHEMA_DIR = REPO_ROOT / "data" / "staging"

# Derived from pipelines/cli.py's _EXTRACTORS (source -> staging
# subdirectory) rather than restated here: a hand-maintained copy silently
# stops covering any extractor added after it was last edited, which is the
# same failure mode backlog #37 removed from the validation report.
_EXTRACTOR_SCHEMAS = [(module, subdir) for module, subdir in _EXTRACTORS.values()]


@pytest.mark.parametrize(
    "module,schema_stem", _EXTRACTOR_SCHEMAS, ids=[stem for _, stem in _EXTRACTOR_SCHEMAS]
)
def test_extractor_fieldnames_match_schema_contract(module, schema_stem):
    schema_path = STAGING_SCHEMA_DIR / f"{schema_stem}.schema.json"

    assert module.FIELDNAMES == schema_field_names(schema_path)


@pytest.mark.parametrize(
    "module_fieldnames,schema_stem",
    [
        (pokeapi.MOVE_FIELDNAMES, "pokeapi_move"),
        (pokeapi.ABILITY_FIELDNAMES, "pokeapi_ability"),
        (pokeapi.ITEM_FIELDNAMES, "pokeapi_item"),
        (pokeapi.ARTWORK_FIELDNAMES, "pokeapi_artwork"),
        (pokeapi.NAMES_FIELDNAMES, "pokeapi_names"),
        (smogon_ladder.COUNTER_FIELDNAMES, "smogon_ladder_counters"),
        (smogon_ladder.SPREAD_FIELDNAMES, "smogon_ladder_spreads"),
    ],
    ids=[
        "pokeapi_move",
        "pokeapi_ability",
        "pokeapi_item",
        "pokeapi_artwork",
        "pokeapi_names",
        "smogon_ladder_counters",
        "smogon_ladder_spreads",
    ],
)
def test_pokeapi_detail_fieldnames_match_schema_contract(module_fieldnames, schema_stem):
    schema_path = STAGING_SCHEMA_DIR / f"{schema_stem}.schema.json"

    assert module_fieldnames == schema_field_names(schema_path)


# --- staging_contract_mismatches: the CI cache-staleness check ---
#
# CI never extracts; it runs dbt against the actions/cache entry the
# scheduled extraction populates, which is always as old as the last
# scheduled run. A PR that adds a source or a staging column therefore
# builds against snapshots that predate it. These cases must be
# *recognisable* so CI can skip with an explanation rather than red-fail on
# an opaque dbt error (see .github/workflows/ci.yml).


def _staging_fixture(tmp_path, sources):
    """sources: {name: (contract_fields, snapshot_header or None)}."""
    for name, (fields, header) in sources.items():
        (tmp_path / f"{name}.schema.json").write_text(
            json.dumps({"fields": [{"name": f} for f in fields]}), encoding="utf-8"
        )
        if header is None:
            continue
        snapshot = tmp_path / name / "2026-01-01.csv"
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(",".join(header) + "\n", encoding="utf-8")
    return tmp_path


def test_no_mismatches_when_every_source_matches_its_contract(tmp_path):
    staging = _staging_fixture(
        tmp_path,
        {"alpha": (["a", "b"], ["a", "b"]), "beta": (["c"], ["c"])},
    )

    assert staging_contract_mismatches(staging) == []


def test_reports_a_source_added_since_the_cache_was_built(tmp_path):
    staging = _staging_fixture(
        tmp_path,
        {"alpha": (["a"], ["a"]), "brand_new": (["a"], None)},
    )

    mismatches = staging_contract_mismatches(staging)

    assert len(mismatches) == 1
    assert "brand_new" in mismatches[0]
    assert "no staged snapshot" in mismatches[0]


def test_reports_a_column_added_since_the_cache_was_built(tmp_path):
    # The exact shape that broke CI on the event_format change.
    staging = _staging_fixture(tmp_path, {"alpha": (["a", "b", "new_col"], ["a", "b"])})

    mismatches = staging_contract_mismatches(staging)

    assert len(mismatches) == 1
    assert "missing ['new_col']" in mismatches[0]


def test_reports_a_column_dropped_from_the_contract(tmp_path):
    staging = _staging_fixture(tmp_path, {"alpha": (["a"], ["a", "removed"])})

    assert "unexpected ['removed']" in staging_contract_mismatches(staging)[0]


def test_reports_reordered_columns(tmp_path):
    staging = _staging_fixture(tmp_path, {"alpha": (["a", "b"], ["b", "a"])})

    assert "column order differs" in staging_contract_mismatches(staging)[0]


def test_checks_the_newest_snapshot_not_an_older_one(tmp_path):
    # dbt's staging models union every retained snapshot, so an older
    # narrower snapshot alongside a current one is real drift -- but the
    # newest is what says whether the cache has caught up.
    staging = _staging_fixture(tmp_path, {"alpha": (["a", "b"], ["a"])})
    (staging / "alpha" / "2026-06-01.csv").write_text("a,b\n", encoding="utf-8")

    assert staging_contract_mismatches(staging) == []


def test_real_repo_staging_contracts_are_all_covered_by_a_schema_file(tmp_path):
    # Guards the naming assumption the check depends on: every staging
    # subdirectory pipelines/cli.py writes to has a matching
    # <name>.schema.json beside it.
    for _module, subdir in _EXTRACTOR_SCHEMAS:
        assert (STAGING_SCHEMA_DIR / f"{subdir}.schema.json").exists()
