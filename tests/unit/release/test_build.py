import csv
import json

import pytest

from pipelines.release import build


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _passing_validation_report():
    return {
        "dataset_version": "0.1.0",
        "generated_at_utc": "2026-01-01T00:00:00Z",
        "coverage_checks": [
            {
                "check_name": "opgg_legal_pool_coverage",
                "description": "d",
                "threshold": ">=0.95",
                "metric_value": 0.98,
                "status": "pass",
            },
            {
                "check_name": "tournament_team_member_mapping_coverage",
                "description": "d",
                "threshold": ">=0.90",
                "metric_value": 0.99,
                "status": "pass",
            },
        ],
        "null_rate_checks": [
            {"table_name": t, "metric_value": 0.0, "threshold": "<=0.01", "status": "pass"}
            for t in build.TABLES
        ],
        "duplicate_key_checks": [
            {
                "table_name": t,
                "primary_key": pk,
                "duplicate_count": 0,
                "status": "pass",
            }
            for t, pk in build.TABLES.items()
        ],
        "referential_integrity_checks": [
            {"check_name": "some_check", "status": "pass", "violation_count": 0}
        ],
        "release_blocking_findings": [],
    }


def _populate_normalized_and_staging(tmp_path, *, include_missing_asset=False):
    normalized_dir = tmp_path / "normalized"
    staging_dir = tmp_path / "staging"
    asset_cache_dir = tmp_path / "assets" / "bulbagarden"
    artwork_cache_dir = tmp_path / "assets" / "pokeapi_artwork"
    for table_name, primary_key in build.TABLES.items():
        if table_name == "pokemon_asset":
            # pokemon_asset rows need a real local_cache_path so
            # _copy_referenced_images has something to copy. Both image
            # kinds are represented so the per-kind cache routing and
            # images/<image_kind>/ layout are exercised rather than assumed.
            rows = [
                {
                    primary_key: "k1::menu_sprite",
                    "image_kind": "menu_sprite",
                    "local_cache_path": "0001.png",
                },
                {
                    primary_key: "k2::menu_sprite",
                    "image_kind": "menu_sprite",
                    "local_cache_path": "0002.png",
                },
                {
                    primary_key: "k1::home_render",
                    "image_kind": "home_render",
                    "local_cache_path": "k1.png",
                },
            ]
            if include_missing_asset:
                # References a cache file that was never downloaded/was
                # pruned (coverage gate is only >=85%, not 100%).
                rows.append(
                    {
                        primary_key: "k3::menu_sprite",
                        "image_kind": "menu_sprite",
                        "local_cache_path": "0003.png",
                    }
                )
        else:
            rows = [{primary_key: "k1"}, {primary_key: "k2"}]
        _write_csv(normalized_dir / f"{table_name}.csv", rows)
    asset_cache_dir.mkdir(parents=True, exist_ok=True)
    (asset_cache_dir / "0001.png").write_bytes(b"fake-png-1")
    (asset_cache_dir / "0002.png").write_bytes(b"fake-png-2")
    artwork_cache_dir.mkdir(parents=True, exist_ok=True)
    (artwork_cache_dir / "k1.png").write_bytes(b"fake-render-1")
    # Staging is date-partitioned per source (backlog.md #1), so each
    # source is a directory of YYYY-MM-DD.csv snapshots, not a flat file.
    # Two snapshots for pokeapi so the "newest wins" resolution is exercised
    # rather than assumed.
    _write_csv(
        staging_dir / "pokeapi" / "2026-01-01.csv",
        [{"extracted_at_utc": "2026-01-01T00:00:00Z", "pokemon_id": "1"}],
    )
    _write_csv(
        staging_dir / "pokeapi" / "2026-01-02.csv",
        [
            {"extracted_at_utc": "2026-01-02T00:00:00Z", "pokemon_id": "1"},
            {"extracted_at_utc": "2026-01-02T00:00:00Z", "pokemon_id": "2"},
        ],
    )
    _write_csv(
        staging_dir / "opgg_champions" / "2026-01-01.csv",
        [{"extracted_at_utc": "2026-01-01T01:00:00Z", "pokemon_id": "1"}],
    )
    _write_csv(
        staging_dir / "munchstats" / "2026-01-01.csv",
        [{"extracted_at_utc": "2026-01-01T02:00:00Z", "event_id": "e1"}],
    )
    _write_csv(
        staging_dir / "pokebase" / "2026-01-01.csv",
        [{"extracted_at_utc": "2026-01-01T03:00:00Z", "pokemon_id": "1"}],
    )
    _write_csv(
        staging_dir / "bulbagarden" / "2026-01-01.csv",
        [
            {
                "extracted_at_utc": "2026-01-01T04:00:00Z",
                "bulbagarden_title": "File:Menu CP 0001.png",
            }
        ],
    )
    _write_csv(
        staging_dir / "rk9_pairings" / "2026-01-01.csv",
        [{"extracted_at_utc": "2026-01-01T05:00:00Z", "event_id": "e1"}],
    )
    _write_csv(
        staging_dir / "limitless" / "2026-01-01.csv",
        [{"extracted_at_utc": "2026-01-01T06:00:00Z", "limitless_team_id": "1"}],
    )
    return normalized_dir, staging_dir, asset_cache_dir, artwork_cache_dir


def test_build_raises_when_validation_report_missing(tmp_path):
    with pytest.raises(build.ReleaseBlockedError, match="not found"):
        build.build(
            "0.1.0",
            validation_report_path=tmp_path / "missing.json",
            normalized_dir=tmp_path / "normalized",
            staging_dir=tmp_path / "staging",
            releases_data_dir=tmp_path / "releases" / "data",
            manifests_dir=tmp_path / "releases" / "manifests",
            changelogs_dir=tmp_path / "releases" / "changelogs",
        )


def test_build_raises_when_gates_failing(tmp_path):
    report = _passing_validation_report()
    report["release_blocking_findings"] = ["pokemon: status=fail"]
    report_path = tmp_path / "validation_report.json"
    report_path.write_text(json.dumps(report))

    with pytest.raises(build.ReleaseBlockedError, match="pokemon: status=fail"):
        build.build(
            "0.1.0",
            validation_report_path=report_path,
            normalized_dir=tmp_path / "normalized",
            staging_dir=tmp_path / "staging",
            releases_data_dir=tmp_path / "releases" / "data",
            manifests_dir=tmp_path / "releases" / "manifests",
            changelogs_dir=tmp_path / "releases" / "changelogs",
        )


def test_build_writes_manifest_changelog_and_copies_tables(tmp_path):
    report_path = tmp_path / "validation_report.json"
    report_path.write_text(json.dumps(_passing_validation_report()))
    normalized_dir, staging_dir, asset_cache_dir, artwork_cache_dir = (
        _populate_normalized_and_staging(tmp_path)
    )
    releases_data_dir = tmp_path / "releases" / "data"
    manifests_dir = tmp_path / "releases" / "manifests"
    changelogs_dir = tmp_path / "releases" / "changelogs"

    manifest = build.build(
        "0.1.0",
        known_limitations=["example limitation"],
        validation_report_path=report_path,
        normalized_dir=normalized_dir,
        staging_dir=staging_dir,
        releases_data_dir=releases_data_dir,
        manifests_dir=manifests_dir,
        changelogs_dir=changelogs_dir,
        asset_cache_dir=asset_cache_dir,
        artwork_cache_dir=artwork_cache_dir,
    )

    assert manifest["dataset_version"] == "0.1.0"
    assert manifest["known_limitations"] == ["example limitation"]
    assert len(manifest["tables"]) == len(build.TABLES)
    # Two rows per table, except pokemon_asset: it carries one row per
    # Pokémon per image_kind, and the fixture gives k1 both kinds.
    assert all(
        t["row_count"] == (3 if t["table_name"] == "pokemon_asset" else 2)
        for t in manifest["tables"]
    )
    assert {s["source_name"] for s in manifest["sources"]} == set(build.SOURCES)
    # Each source's row count/timestamp comes from its NEWEST dated snapshot,
    # not the first or an arbitrary one: pokeapi has two, and the later one
    # has two rows.
    pokeapi_source = next(s for s in manifest["sources"] if s["source_name"] == "PokéAPI")
    assert pokeapi_source["record_count"] == 2
    assert pokeapi_source["extracted_at_utc"] == "2026-01-02T00:00:00Z"
    assert manifest["images"] == {
        "count": 3,
        "missing": 0,
        "directory": "images/",
        "by_image_kind": {"home_render": 1, "menu_sprite": 2},
    }

    for table_name in build.TABLES:
        assert (releases_data_dir / "0.1.0" / f"{table_name}.csv").exists()

    # Laid out per image_kind, sourced from that kind's own cache dir.
    images_dir = releases_data_dir / "0.1.0" / "images"
    assert (images_dir / "menu_sprite" / "0001.png").read_bytes() == b"fake-png-1"
    assert (images_dir / "menu_sprite" / "0002.png").read_bytes() == b"fake-png-2"
    assert (images_dir / "home_render" / "k1.png").read_bytes() == b"fake-render-1"

    manifest_path = manifests_dir / "manifest-0.1.0.json"
    assert manifest_path.exists()
    assert json.loads(manifest_path.read_text()) == manifest

    changelog_path = changelogs_dir / "CHANGELOG-0.1.0.md"
    assert changelog_path.exists()
    changelog_text = changelog_path.read_text()
    assert "dataset_version 0.1.0" in changelog_text
    assert "example limitation" in changelog_text
    assert "{VERSION}" not in changelog_text


def test_build_skips_missing_cached_images(tmp_path):
    report_path = tmp_path / "validation_report.json"
    report_path.write_text(json.dumps(_passing_validation_report()))
    normalized_dir, staging_dir, asset_cache_dir, artwork_cache_dir = (
        _populate_normalized_and_staging(tmp_path, include_missing_asset=True)
    )
    releases_data_dir = tmp_path / "releases" / "data"

    manifest = build.build(
        "0.1.0",
        validation_report_path=report_path,
        normalized_dir=normalized_dir,
        staging_dir=staging_dir,
        releases_data_dir=releases_data_dir,
        manifests_dir=tmp_path / "releases" / "manifests",
        changelogs_dir=tmp_path / "releases" / "changelogs",
        asset_cache_dir=asset_cache_dir,
        artwork_cache_dir=artwork_cache_dir,
    )

    assert manifest["images"] == {
        "count": 3,
        "missing": 1,
        "directory": "images/",
        "by_image_kind": {"home_render": 1, "menu_sprite": 2},
    }
    images_dir = releases_data_dir / "0.1.0" / "images"
    assert (images_dir / "menu_sprite" / "0001.png").exists()
    assert (images_dir / "menu_sprite" / "0002.png").exists()
    assert not (images_dir / "menu_sprite" / "0003.png").exists()


def test_build_quality_checks_reflect_report(tmp_path):
    report = _passing_validation_report()
    report_path = tmp_path / "validation_report.json"
    report_path.write_text(json.dumps(report))
    normalized_dir, staging_dir, asset_cache_dir, artwork_cache_dir = (
        _populate_normalized_and_staging(tmp_path)
    )

    manifest = build.build(
        "0.2.0",
        validation_report_path=report_path,
        normalized_dir=normalized_dir,
        staging_dir=staging_dir,
        releases_data_dir=tmp_path / "releases" / "data",
        manifests_dir=tmp_path / "releases" / "manifests",
        changelogs_dir=tmp_path / "releases" / "changelogs",
        asset_cache_dir=asset_cache_dir,
        artwork_cache_dir=artwork_cache_dir,
    )

    checks_by_name = {c["check_name"]: c for c in manifest["quality_checks"]}
    assert checks_by_name["opgg_legal_pool_coverage"]["metric_value"] == 0.98
    assert checks_by_name["required_field_null_rate"]["status"] == "pass"
    assert checks_by_name["duplicate_primary_key_violations"]["metric_value"] == 0
    assert checks_by_name["referential_integrity"]["status"] == "pass"


def test_build_sources_handles_a_source_that_was_never_extracted(tmp_path):
    """A source directory that doesn't exist yet (fresh clone, or a source
    like Bulbagarden that only runs on demand) must report zero records
    rather than raising -- the release gate decides what may ship, not an
    incidental FileNotFoundError here."""
    staging_dir = tmp_path / "staging"
    _write_csv(
        staging_dir / "pokeapi" / "2026-01-01.csv",
        [{"extracted_at_utc": "2026-01-01T00:00:00Z", "pokemon_id": "1"}],
    )

    sources = build._build_sources(staging_dir)

    by_name = {s["source_name"]: s for s in sources}
    assert by_name["PokéAPI"]["record_count"] == 1
    for name in build.SOURCES:
        if name != "PokéAPI":
            assert by_name[name]["record_count"] == 0
            assert by_name[name]["extracted_at_utc"] is None


def test_build_packages_a_release_asset_and_records_it(tmp_path):
    """docs/upgrade-plan-2027q1.md, D1: from 0.4.0 the package is a GitHub
    Release asset; the committed manifest records its file and checksum."""
    import hashlib
    import zipfile

    report_path = tmp_path / "validation_report.json"
    report_path.write_text(json.dumps(_passing_validation_report()))
    normalized_dir, staging_dir, asset_cache_dir, artwork_cache_dir = (
        _populate_normalized_and_staging(tmp_path)
    )
    manifests_dir = tmp_path / "releases" / "manifests"
    packages_dir = tmp_path / "releases" / "packages"

    manifest = build.build(
        "0.4.0",
        notes=["Releases before 0.4.0 exclude Reg M-B and M-C events."],
        validation_report_path=report_path,
        normalized_dir=normalized_dir,
        staging_dir=staging_dir,
        releases_data_dir=tmp_path / "releases" / "data",
        manifests_dir=manifests_dir,
        changelogs_dir=tmp_path / "releases" / "changelogs",
        asset_cache_dir=asset_cache_dir,
        artwork_cache_dir=artwork_cache_dir,
        package=True,
        packages_dir=packages_dir,
    )

    package = manifest["package"]
    zip_path = packages_dir / "pokemon-champions-dataset-0.4.0.zip"
    assert package["file_name"] == zip_path.name
    assert package["sha256"] == hashlib.sha256(zip_path.read_bytes()).hexdigest()
    assert package["size_bytes"] == zip_path.stat().st_size
    assert package["release_tag"] == "data-v0.4.0"
    assert package["url"].endswith("/releases/download/data-v0.4.0/" + zip_path.name)
    checksum = (packages_dir / "pokemon-champions-dataset-0.4.0.sha256").read_text()
    assert checksum == f"{package['sha256']}  {zip_path.name}\n"
    assert json.loads((manifests_dir / "manifest-0.4.0.json").read_text())["package"] == package

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        prefix = "pokemon-champions-dataset-0.4.0/"
        assert prefix + "manifest.json" in names
        assert prefix + "CHANGELOG.md" in names
        assert all(prefix + f"{table}.csv" in names for table in build.TABLES)
        assert prefix + "images/menu_sprite/0001.png" in names
        changelog = archive.read(prefix + "CHANGELOG.md").decode()
        assert "## Notes" in changelog and "exclude Reg M-B and M-C" in changelog
