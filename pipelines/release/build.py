"""Assemble a versioned release package under releases/, per
docs/dataset-spec.md's "Release package" section: one CSV per core entity
plus manifest.json and CHANGELOG.md.

From 0.4.0 the package is distributed only as a GitHub Release asset
(docs/upgrade-plan-2027q1.md, D1): `package=True` zips it into
releases/packages/ with a sha256 checksum and records both in the
manifest's `package` block, and .github/workflows/cut-release.yml uploads
the zip. Only the manifest and changelog are committed;
releases/data/<version>/ and releases/packages/ are gitignored for new
versions, so a release no longer adds ~50MB to git.

Gated on reports/validation/validation_report.json: a release is refused
(ReleaseBlockedError) unless that report exists and reports zero
release_blocking_findings, per CLAUDE.md's "Don't ship ungated data" and
dataset-spec.md's "Any unmapped or low-confidence rows must be documented
in the manifest and excluded from release tables unless explicitly
approved." Run `pipelines.cli validate` (dbt build + report generation)
before publishing.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipelines.validate.report import REPORT_PATH

REPO_ROOT = Path(__file__).resolve().parents[2]
NORMALIZED_DIR = REPO_ROOT / "data" / "normalized"
STAGING_DIR = REPO_ROOT / "data" / "staging"
RELEASES_DATA_DIR = REPO_ROOT / "releases" / "data"
MANIFESTS_DIR = REPO_ROOT / "releases" / "manifests"
CHANGELOGS_DIR = REPO_ROOT / "releases" / "changelogs"
PACKAGES_DIR = REPO_ROOT / "releases" / "packages"
# Where cut-release.yml publishes a version's package: the GitHub Release
# tagged data-v<version>.
RELEASE_DOWNLOAD_BASE = "https://github.com/lancettlim/pokemon-agent/releases/download"
PACKAGE_PREFIX = "pokemon-champions-dataset"
DEFAULT_ASSET_CACHE_DIR = REPO_ROOT / "data" / "assets" / "bulbagarden"
DEFAULT_ARTWORK_CACHE_DIR = REPO_ROOT / "data" / "assets" / "pokeapi_artwork"
IMAGES_SUBDIR = "images"

# table_name -> primary_key for the nine core release entities
# (docs/dataset-spec.md's entity dictionary) shipped as
# releases/data/<version>/*.csv. Kept here rather than derived from
# report.py's test-driven categorization (backlog #37): this is "which
# entities does the release package ship," a fixed product decision, not
# "which dbt tests exist" -- the two happen to overlap for these twelve tables
# today, but report.py's duplicate_key_checks now also covers non-release
# reference tables (ability_detail, item_detail, move_detail,
# archetype_pokemon_map) that don't belong in this list.
TABLES: dict[str, str] = {
    "pokemon": "pokemon_key",
    "pokemon_stat_canonical": "pokemon_stat_canonical_key",
    "pokemon_stat_champions": "pokemon_stat_champions_key",
    "pokemon_stat_delta": "pokemon_stat_delta_key",
    "legality_snapshot": "legality_snapshot_key",
    "tournament_event": "event_id",
    "tournament_team": "team_id",
    "tournament_team_member": "team_member_id",
    "tournament_match": "match_id",
    "team_list": "team_list_id",
    "team_list_member": "team_list_member_id",
    "pokemon_asset": "pokemon_asset_key",
}

# source_name -> (source_url, staging subdirectory), matching
# releases/manifests/manifest.template.json's sources array. The value is a
# per-source *directory* under data/staging/, not a flat CSV filename:
# backlog.md #1 moved staging to date-partitioned data/staging/<source>/
# <date>.csv snapshots, and this mapping still pointed at the pre-#1 flat
# paths -- so _build_sources raised FileNotFoundError for every source. It
# went unnoticed because no release had been cut since that change.
SOURCES: dict[str, tuple[str, str]] = {
    "PokéAPI": ("https://github.com/PokeAPI/pokeapi", "pokeapi"),
    "OP.GG Pokémon Champions": ("https://op.gg/pokemon-champions/pokedex", "opgg_champions"),
    "MunchStats": ("https://github.com/PizzaTimeJoshua/munchstats", "munchstats"),
    "PokéBase": ("https://pokebase.app/pokemon-champions/pokemon", "pokebase"),
    "Bulbagarden Archives": ("https://archives.bulbagarden.net/w/api.php", "bulbagarden"),
    "RK9.gg": ("https://rk9.gg", "rk9_pairings"),
    "Limitless VGC": ("https://limitlessvgc.com", "limitless"),
}

CHANGELOG_TEMPLATE = (REPO_ROOT / "releases" / "changelogs" / "CHANGELOG.template.md").read_text()


class ReleaseBlockedError(RuntimeError):
    """Raised when the validation report is missing or reports failing gates."""


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _load_validation_report(validation_report_path: Path) -> dict[str, Any]:
    if not validation_report_path.exists():
        raise ReleaseBlockedError(
            f"{validation_report_path} not found — run `pipelines.cli validate` "
            "(or `make validate`) before publishing a release"
        )
    report = json.loads(validation_report_path.read_text())
    findings = report["release_blocking_findings"]
    if findings:
        raise ReleaseBlockedError(f"Cannot publish release: gates failing: {findings}")
    return report


def _latest_snapshot(staging_dir: Path, staging_subdir: str) -> Path | None:
    """Newest dated snapshot for a source, or None if it has never been
    extracted. Filenames are YYYY-MM-DD.csv, so lexicographic order is
    chronological -- the same convention pipelines/cli.py's own
    _latest_snapshot_path uses."""
    source_dir = staging_dir / staging_subdir
    if not source_dir.is_dir():
        return None
    snapshots = sorted(source_dir.glob("*.csv"))
    return snapshots[-1] if snapshots else None


def _build_sources(staging_dir: Path) -> list[dict[str, Any]]:
    sources = []
    for source_name, (source_url, staging_subdir) in SOURCES.items():
        snapshot = _latest_snapshot(staging_dir, staging_subdir)
        rows = _read_csv_rows(snapshot) if snapshot is not None else []
        sources.append(
            {
                "source_name": source_name,
                "source_url": source_url,
                "extracted_at_utc": rows[0]["extracted_at_utc"] if rows else None,
                "record_count": len(rows),
            }
        )
    return sources


def _copy_tables(normalized_dir: Path, dest_dir: Path) -> list[dict[str, Any]]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    tables = []
    for table_name, primary_key in TABLES.items():
        src = normalized_dir / f"{table_name}.csv"
        dest = dest_dir / f"{table_name}.csv"
        shutil.copyfile(src, dest)
        tables.append(
            {
                "table_name": table_name,
                "file_name": dest.name,
                "primary_key": primary_key,
                "row_count": len(_read_csv_rows(dest)),
            }
        )
    return tables


def _copy_referenced_images(
    dest_dir: Path,
    *,
    asset_cache_dir: Path = DEFAULT_ASSET_CACHE_DIR,
    artwork_cache_dir: Path = DEFAULT_ARTWORK_CACHE_DIR,
) -> dict[str, Any]:
    """Copy every file pokemon_asset.csv's local_cache_path column
    references from the local extractor caches into dest_dir/images/, so the
    release package is self-contained. dest_dir is the release's own
    per-version directory (releases_data_dir/<dataset_version>), and
    pokemon_asset.csv must already be present there (i.e. this runs after
    _copy_tables). Returns the manifest's "images" block.

    Files are laid out under one subdirectory per image_kind
    (images/menu_sprite/, images/home_render/) rather than flat. The two
    kinds come from different caches and have independent naming
    conventions -- Bulbagarden's National-Dex-style "0006-Mega X.png"
    against PokéAPI's form slug "charizard-mega-x.png" -- so a flat
    directory would mix two schemes with no way to tell which asset a
    consumer is looking at. Rows with no image_kind are treated as
    menu_sprite, which is what every row was before high-resolution artwork
    was added.
    """
    pokemon_asset_rows = _read_csv_rows(dest_dir / "pokemon_asset.csv")
    images_dir = dest_dir / IMAGES_SUBDIR
    images_dir.mkdir(parents=True, exist_ok=True)
    cache_dir_by_kind = {
        "menu_sprite": asset_cache_dir,
        "home_render": artwork_cache_dir,
    }
    copied = 0
    missing = 0
    by_kind: dict[str, int] = {}
    for row in pokemon_asset_rows:
        local_cache_path = row["local_cache_path"]
        image_kind = row.get("image_kind") or "menu_sprite"
        cache_dir = cache_dir_by_kind.get(image_kind)
        if cache_dir is None:
            missing += 1
            print(
                f"warning: pokemon_asset row has unknown image_kind {image_kind!r}, skipping: "
                f"{local_cache_path}",
                file=sys.stderr,
            )
            continue
        src = cache_dir / local_cache_path
        if not src.exists():
            missing += 1
            print(
                f"warning: pokemon_asset image not found in cache, skipping: {src}",
                file=sys.stderr,
            )
            continue
        dest = images_dir / image_kind / local_cache_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        copied += 1
        by_kind[image_kind] = by_kind.get(image_kind, 0) + 1
    return {
        "count": copied,
        "missing": missing,
        "directory": f"{IMAGES_SUBDIR}/",
        "by_image_kind": dict(sorted(by_kind.items())),
    }


def _build_quality_checks(validation_report: dict[str, Any]) -> list[dict[str, Any]]:
    checks = []
    for coverage_check in validation_report["coverage_checks"]:
        checks.append(
            {
                "check_name": coverage_check["check_name"],
                "status": coverage_check["status"],
                "metric_value": coverage_check["metric_value"],
                "threshold": coverage_check["threshold"],
            }
        )

    null_rate_checks = validation_report["null_rate_checks"]
    null_rate_values = [
        c["metric_value"] for c in null_rate_checks if c["metric_value"] is not None
    ]
    checks.append(
        {
            "check_name": "required_field_null_rate",
            "status": "pass" if all(c["status"] == "pass" for c in null_rate_checks) else "fail",
            "metric_value": max(null_rate_values) if null_rate_values else None,
            "threshold": "<=0.01",
        }
    )

    duplicate_checks = validation_report["duplicate_key_checks"]
    duplicate_counts = [
        c["duplicate_count"] for c in duplicate_checks if c["duplicate_count"] is not None
    ]
    checks.append(
        {
            "check_name": "duplicate_primary_key_violations",
            "status": "pass" if all(c["status"] == "pass" for c in duplicate_checks) else "fail",
            "metric_value": sum(duplicate_counts) if duplicate_counts else None,
            "threshold": "=0",
        }
    )

    referential_checks = validation_report["referential_integrity_checks"]
    violation_counts = [
        c["violation_count"] for c in referential_checks if c["violation_count"] is not None
    ]
    checks.append(
        {
            "check_name": "referential_integrity",
            "status": "pass" if all(c["status"] == "pass" for c in referential_checks) else "fail",
            "metric_value": sum(violation_counts) if violation_counts else None,
            "threshold": "all resolve",
        }
    )
    return checks


def package_release(
    dataset_version: str,
    *,
    release_dir: Path,
    manifest_path: Path,
    changelog_path: Path,
    packages_dir: Path = PACKAGES_DIR,
) -> dict[str, Any]:
    """Zip a built release (its CSVs and images, plus manifest.json and
    CHANGELOG.md) into packages_dir/<prefix>-<version>.zip under a
    <prefix>-<version>/ folder, write a sha256sum-style checksum file next
    to it, and return the manifest's `package` block. The same layout
    publish-release.yml has always produced."""
    name = f"{PACKAGE_PREFIX}-{dataset_version}"
    packages_dir.mkdir(parents=True, exist_ok=True)
    zip_path = packages_dir / f"{name}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(release_dir.rglob("*")):
            if path.is_file():
                archive.write(path, f"{name}/{path.relative_to(release_dir).as_posix()}")
        archive.write(manifest_path, f"{name}/manifest.json")
        if changelog_path.exists():
            archive.write(changelog_path, f"{name}/CHANGELOG.md")
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (packages_dir / f"{name}.sha256").write_text(f"{digest}  {zip_path.name}\n")
    tag = f"data-v{dataset_version}"
    return {
        "file_name": zip_path.name,
        "sha256": digest,
        "size_bytes": zip_path.stat().st_size,
        "release_tag": tag,
        "url": f"{RELEASE_DOWNLOAD_BASE}/{tag}/{zip_path.name}",
    }


def _write_changelog(
    path: Path,
    *,
    dataset_version: str,
    published_at_utc: str,
    sources: list[dict[str, Any]],
    known_limitations: list[str],
    notes: list[str] | None = None,
) -> None:
    source_by_name = {s["source_name"]: s for s in sources}
    text = (
        CHANGELOG_TEMPLATE.replace("{VERSION}", dataset_version)
        .replace("{PUBLISHED_AT_UTC}", published_at_utc)
        .replace("{POKEAPI_EXTRACTED_AT_UTC}", str(source_by_name["PokéAPI"]["extracted_at_utc"]))
        .replace(
            "{OPGG_EXTRACTED_AT_UTC}",
            str(source_by_name["OP.GG Pokémon Champions"]["extracted_at_utc"]),
        )
        .replace(
            "{MUNCHSTATS_EXTRACTED_AT_UTC}", str(source_by_name["MunchStats"]["extracted_at_utc"])
        )
        .replace("{POKEBASE_EXTRACTED_AT_UTC}", str(source_by_name["PokéBase"]["extracted_at_utc"]))
        .replace(
            "{BULBAGARDEN_EXTRACTED_AT_UTC}",
            str(source_by_name["Bulbagarden Archives"]["extracted_at_utc"]),
        )
    )
    limitations_block = (
        "\n".join(f"- {item}" for item in known_limitations) if known_limitations else "- None"
    )
    text = text.replace(
        "### New\n\n- {describe any newly identified coverage gaps or low-confidence mappings}",
        f"### New\n\n{limitations_block}",
    )
    if notes:
        text = text.rstrip("\n") + "\n\n## Notes\n\n" + "\n".join(f"- {n}" for n in notes) + "\n"
    path.write_text(text)


def build(
    dataset_version: str,
    *,
    known_limitations: list[str] | None = None,
    validation_report_path: Path = REPORT_PATH,
    normalized_dir: Path = NORMALIZED_DIR,
    staging_dir: Path = STAGING_DIR,
    releases_data_dir: Path = RELEASES_DATA_DIR,
    manifests_dir: Path = MANIFESTS_DIR,
    changelogs_dir: Path = CHANGELOGS_DIR,
    asset_cache_dir: Path = DEFAULT_ASSET_CACHE_DIR,
    artwork_cache_dir: Path = DEFAULT_ARTWORK_CACHE_DIR,
    notes: list[str] | None = None,
    package: bool = False,
    packages_dir: Path = PACKAGES_DIR,
) -> dict[str, Any]:
    """Build a versioned release package: copies data/normalized/*.csv to
    releases/data/<dataset_version>/, copies the images pokemon_asset.csv
    references into releases/data/<dataset_version>/images/<image_kind>/,
    and writes releases/manifests/manifest-<dataset_version>.json and
    releases/changelogs/CHANGELOG-<dataset_version>.md.

    Raises ReleaseBlockedError if reports/validation/validation_report.json
    is missing or reports any release_blocking_findings.

    package=True also zips the package for a GitHub Release (see
    package_release) and adds its `package` block to the committed
    manifest. The copy of manifest.json inside the zip is written before
    the zip exists, so it carries no `package` block of its own.
    """
    validation_report = _load_validation_report(validation_report_path)

    published_at_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    sources = _build_sources(staging_dir)
    release_dir = releases_data_dir / dataset_version
    tables = _copy_tables(normalized_dir, release_dir)
    images = _copy_referenced_images(
        release_dir, asset_cache_dir=asset_cache_dir, artwork_cache_dir=artwork_cache_dir
    )
    quality_checks = _build_quality_checks(validation_report)

    manifest = {
        "dataset_version": dataset_version,
        "published_at_utc": published_at_utc,
        "sources": sources,
        "tables": tables,
        "images": images,
        "quality_checks": quality_checks,
        "known_limitations": known_limitations or [],
    }

    manifests_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifests_dir / f"manifest-{dataset_version}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    changelogs_dir.mkdir(parents=True, exist_ok=True)
    changelog_path = changelogs_dir / f"CHANGELOG-{dataset_version}.md"
    _write_changelog(
        changelog_path,
        dataset_version=dataset_version,
        published_at_utc=published_at_utc,
        sources=sources,
        known_limitations=known_limitations or [],
        notes=notes,
    )

    if package:
        manifest["package"] = package_release(
            dataset_version,
            release_dir=release_dir,
            manifest_path=manifest_path,
            changelog_path=changelog_path,
            packages_dir=packages_dir,
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    return manifest
