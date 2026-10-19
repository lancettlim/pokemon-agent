import json

from pipelines.dashboard import dictionary

SCHEMA = """
version: 2
models:
  - name: tournament_team_results
    description: >
      One row per team. Written to data/marts/tournament_team_results.csv.
    data_tests:
      - unique_combination_of_columns:
          arguments:
            combination_of_columns: [event_id, team_id]
    columns:
      - name: team_id
        description: "The team."
      - name: placement
        description: "Final standing. See data/normalized/tournament_team.schema.json."
  - name: tournament_event_summary
    description: "One row per event."
    columns:
      - name: event_id
        description: "The event."
        data_tests: [unique, not_null]
"""


def _schema(tmp_path):
    path = tmp_path / "schema.yml"
    path.write_text(SCHEMA, encoding="utf-8")
    return path


def test_squash_drops_repo_pointers_and_collapses_whitespace():
    assert dictionary._squash("One row\n  per team. Written to data/marts/x.csv.") == (
        "One row per team."
    )
    assert dictionary._squash("Identity. See data/normalized/pokemon.schema.json.") == "Identity."
    assert dictionary._squash(None) == ""


def test_load_schema_models_reads_descriptions_and_grain(tmp_path):
    models = dictionary.load_schema_models(_schema(tmp_path))
    results = models["tournament_team_results"]
    assert results["description"] == "One row per team."
    assert results["grain"] == ["event_id", "team_id"]
    assert results["columns"]["placement"] == "Final standing."
    # A column-level `unique` test is the grain when there's no combination.
    assert models["tournament_event_summary"]["grain"] == ["event_id"]


def test_load_schema_models_tolerates_a_missing_or_broken_file(tmp_path):
    assert dictionary.load_schema_models(tmp_path / "missing.yml") == {}
    broken = tmp_path / "broken.yml"
    broken.write_text("models: [", encoding="utf-8")
    assert dictionary.load_schema_models(broken) == {}


def test_mart_dictionary_lists_served_fields_and_their_shard(tmp_path):
    marts = {
        "tournament_team_results": [{"team_id": "T1", "placement": 1, "pokemon_name": "x"}],
        "pokemon_usage_by_regulation": [{"regulation_scope": "m-c", "pokemon_key": "a"}],
        "tournament_top_cut_teams": [{"team_id": "T1"}],
        "tournament_event_summary": [],
    }
    mart_files = {
        "core": "data/core.json",
        "on_demand": {"tournament_team_results": "data/tournament_team_results.json"},
    }
    entries = dictionary.mart_dictionary(
        marts, mart_files, _schema(tmp_path), hidden_columns=("pokemon_name",)
    )
    by_table = {e["table"]: e for e in entries}
    assert [e["table"] for e in entries] == sorted(marts)

    results = by_table["tournament_team_results"]
    assert [c["name"] for c in results["columns"]] == ["team_id", "placement"]
    assert results["columns"][1]["description"] == "Final standing."
    assert results["grain"] == "event_id|team_id"
    assert results["shard"] == "data/tournament_team_results.json"
    assert results["source"] == "dbt mart"

    assert by_table["pokemon_usage_by_regulation"]["shard"] == "data/scope-<regulation>.json"
    derived = by_table["tournament_top_cut_teams"]
    assert derived["source"] == "derived at build"
    assert derived["description"].startswith("Top-16 finishes")
    # An empty mart still lists the columns schema.yml documents.
    assert [c["name"] for c in by_table["tournament_event_summary"]["columns"]] == ["event_id"]


def _manifest(path, version, package=None):
    manifest = {
        "dataset_version": version,
        "published_at_utc": f"2026-0{version[2]}-01T00:00:00Z",
        "tables": [
            {
                "table_name": "pokemon",
                "file_name": "pokemon.csv",
                "primary_key": "pokemon_key",
                "row_count": 10,
            }
        ],
    }
    if package:
        manifest["package"] = package
    path.write_text(json.dumps(manifest), encoding="utf-8")


def test_release_tables_describe_the_newest_release_and_where_to_get_it(tmp_path):
    schema = tmp_path / "normalized.yml"
    schema.write_text(
        "models:\n  - name: pokemon\n    description: "
        '"Identity table. See data/normalized/pokemon.schema.json."\n',
        encoding="utf-8",
    )
    _manifest(tmp_path / "manifest-0.3.0.json", "0.3.0")
    _manifest(tmp_path / "manifest-0.10.0.json", "0.10.0")
    (tmp_path / "manifest-bad.json").write_text("{", encoding="utf-8")

    rows = dictionary.release_tables(tmp_path, schema)
    # Versions compare numerically, not as strings.
    assert rows[0]["dataset_version"] == "0.10.0"
    assert rows[0]["description"] == "Identity table."
    assert rows[0]["download_kind"] == "CSV"
    assert rows[0]["download_url"] == f"{dictionary.RAW_RELEASE_BASE}/0.10.0/pokemon.csv"

    _manifest(tmp_path / "manifest-0.11.0.json", "0.11.0", package={"url": "https://example/x.zip"})
    rows = dictionary.release_tables(tmp_path, schema)
    assert rows[0]["download_kind"] == "release package (zip)"
    assert rows[0]["download_url"] == "https://example/x.zip"


def test_release_tables_is_empty_before_any_release(tmp_path):
    assert dictionary.release_tables(tmp_path, tmp_path / "none.yml") == []
