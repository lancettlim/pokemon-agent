"""The Data section's table cards and data dictionary
(docs/upgrade-plan-2027q1.md, D2), generated at build time from the dbt
schema files and the newest release manifest, so they can't drift from
the marts and tables they describe.

- mart_dictionary(): one entry per mart the site serves -- its
  description, grain, columns (with descriptions where schema.yml has
  them), row count and the JSON shard it ships in.
- release_tables(): the newest release's tables -- description, primary
  key, row count and where to download them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MARTS_SCHEMA_PATH = REPO_ROOT / "dbt" / "models" / "marts" / "schema.yml"
NORMALIZED_SCHEMA_PATH = REPO_ROOT / "dbt" / "models" / "normalized" / "schema.yml"
DEFAULT_MANIFESTS_DIR = REPO_ROOT / "releases" / "manifests"
# Pre-0.4.0 releases are committed files (docs/dataset-spec.md's
# "Distribution"), downloadable one CSV at a time from the repository.
RAW_RELEASE_BASE = "https://raw.githubusercontent.com/lancettlim/pokemon-agent/main/releases/data"

# Payload entries pipelines/dashboard/data.py derives rather than reading
# from a dbt mart, described here since no schema.yml covers them.
DERIVED_DESCRIPTIONS = {
    "tournament_top_cut_teams": (
        "Top-16 finishes from tournament_team_results, derived at build time for "
        "Top Teams, event pages and a profile's Teams view."
    ),
    "player_index": (
        "One row per player, derived at build time from tournament_team_results: "
        "name and country as the source spells them, teams on record (one per "
        "event), best finish and regulations played."
    ),
}


# schema.yml descriptions often end "See data/normalized/<table>.schema.json."
# or "Written to data/marts/<table>.csv." -- pointers for maintainers, not
# readers of the site (docs/upgrade-plan-2027q1.md, U4).
_REPO_POINTER = re.compile(r"\s*(See|Written to) [\w./<>-]+\.(schema\.json|csv)\.?")


def _squash(text: str | None) -> str:
    return _REPO_POINTER.sub("", " ".join(str(text or "").split())).strip()


def load_schema_models(path: Path) -> dict[str, dict[str, Any]]:
    """{model_name: {"description", "grain", "columns": {name: description}}}
    from a dbt schema.yml. The grain is the model's
    unique_combination_of_columns test, or a column with a `unique` test.
    Missing or unparseable file -> {}."""
    if not path.exists():
        return {}
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    models: dict[str, dict[str, Any]] = {}
    for model in document.get("models") or []:
        grain: list[str] = []
        for test in model.get("data_tests") or []:
            if isinstance(test, dict) and "unique_combination_of_columns" in test:
                spec = test["unique_combination_of_columns"] or {}
                arguments = spec.get("arguments") or spec
                grain = list(arguments.get("combination_of_columns") or [])
        columns: dict[str, str] = {}
        for column in model.get("columns") or []:
            columns[column["name"]] = _squash(column.get("description"))
            for test in column.get("data_tests") or []:
                if test == "unique" or (isinstance(test, dict) and "unique" in test):
                    grain = grain or [column["name"]]
        models[model["name"]] = {
            "description": _squash(model.get("description")),
            "grain": grain,
            "columns": columns,
        }
    return models


def _shard_for(name: str, rows: list[dict[str, Any]], mart_files: dict[str, Any]) -> str | None:
    if name in (mart_files.get("build_only") or []):
        # Summarised into the page at build time; no shard carries it.
        return None
    if name in (mart_files.get("on_demand") or {}):
        return mart_files["on_demand"][name]
    if rows and "regulation_scope" in rows[0]:
        return "data/scope-<regulation>.json"
    return mart_files.get("core")


def mart_dictionary(
    marts: dict[str, list[dict[str, Any]]],
    mart_files: dict[str, Any],
    schema_path: Path = MARTS_SCHEMA_PATH,
    hidden_columns: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """One entry per mart in the payload, alphabetically. Columns are the
    fields the site's copy actually carries (minus `hidden_columns`, the
    display names shard files drop), described from schema.yml where it has
    a description."""
    schema = load_schema_models(schema_path)
    entries = []
    for name in sorted(marts):
        rows = marts[name] or []
        model = schema.get(name, {})
        fields = [k for k in (rows[0].keys() if rows else model.get("columns", {}).keys())]
        fields = [f for f in fields if f not in hidden_columns]
        entries.append(
            {
                "table": name,
                "description": model.get("description") or DERIVED_DESCRIPTIONS.get(name, ""),
                "grain": "|".join(model.get("grain") or []),
                "columns": [
                    {"name": f, "description": (model.get("columns") or {}).get(f, "")}
                    for f in fields
                ],
                "row_count": len(rows),
                "shard": _shard_for(name, rows, mart_files),
                "source": "dbt mart" if name in schema else "derived at build",
            }
        )
    return entries


def _version_key(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError:
        return (0,)


def release_tables(
    manifests_dir: Path = DEFAULT_MANIFESTS_DIR,
    schema_path: Path = NORMALIZED_SCHEMA_PATH,
) -> list[dict[str, Any]]:
    """The newest release's tables, one row each, with where to get them:
    the Release asset for 0.4.0 on (its manifest's `package` block), or the
    committed CSV before that. [] when nothing has been released."""
    manifests = []
    for path in manifests_dir.glob("manifest-*.json"):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if manifest.get("dataset_version"):
            manifests.append(manifest)
    if not manifests:
        return []
    newest = max(manifests, key=lambda m: _version_key(m["dataset_version"]))
    version = newest["dataset_version"]
    package = newest.get("package") or {}
    schema = load_schema_models(schema_path)
    return [
        {
            "table_name": table["table_name"],
            "file_name": table.get("file_name"),
            "primary_key": table.get("primary_key"),
            "row_count": table.get("row_count"),
            "description": (schema.get(table["table_name"]) or {}).get("description", ""),
            "dataset_version": version,
            "published_at_utc": newest.get("published_at_utc"),
            "download_url": package.get("url")
            or f"{RAW_RELEASE_BASE}/{version}/{table.get('file_name')}",
            "download_kind": "release package (zip)" if package else "CSV",
        }
        for table in newest.get("tables") or []
    ]
