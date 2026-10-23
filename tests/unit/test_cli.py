import csv
import os
import subprocess
import time

import pytest

from pipelines import cli


def _write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_dated_snapshot_path_is_source_subdir_slash_date(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "STAGING_DIR", tmp_path)

    path = cli._dated_snapshot_path("pokeapi", "2026-07-30")

    assert path == tmp_path / "pokeapi" / "2026-07-30.csv"


def test_latest_snapshot_path_picks_most_recent_date(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "STAGING_DIR", tmp_path)
    source_dir = tmp_path / "munchstats"
    for date_str in ("2026-07-01", "2026-07-15", "2026-07-08"):
        _write_csv(source_dir / f"{date_str}.csv", [], ["a"])

    assert cli._latest_snapshot_path("munchstats") == source_dir / "2026-07-15.csv"


def test_latest_snapshot_path_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "STAGING_DIR", tmp_path)

    assert cli._latest_snapshot_path("munchstats") is None


def test_prune_old_snapshots_keeps_only_the_newest(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "STAGING_DIR", tmp_path)
    source_dir = tmp_path / "bulbagarden"
    dates = [f"2026-01-{day:02d}" for day in range(1, 13)]  # 12 snapshots
    for date_str in dates:
        _write_csv(source_dir / f"{date_str}.csv", [], ["a"])

    cli._prune_old_snapshots("bulbagarden")  # retention count is 10

    remaining = sorted(p.stem for p in source_dir.glob("*.csv"))
    assert remaining == dates[-10:]


def test_prune_old_snapshots_no_op_under_retention(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "STAGING_DIR", tmp_path)
    source_dir = tmp_path / "pokebase"
    _write_csv(source_dir / "2026-07-30.csv", [], ["a"])

    cli._prune_old_snapshots("pokebase")

    assert [p.name for p in source_dir.glob("*.csv")] == ["2026-07-30.csv"]


def test_referenced_move_ability_item_names_reads_latest_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "STAGING_DIR", tmp_path)
    fieldnames = ["ability", "item_name", "moves"]
    _write_csv(
        tmp_path / "munchstats" / "2026-07-01.csv",
        [{"ability": "Stale Ability", "item_name": "Stale Item", "moves": "Stale Move"}],
        fieldnames,
    )
    _write_csv(
        tmp_path / "munchstats" / "2026-07-15.csv",
        [{"ability": "Intimidate", "item_name": "Choice Band", "moves": "Flare Blitz|Earthquake"}],
        fieldnames,
    )

    moves, abilities, items = cli._referenced_move_ability_item_names()

    assert moves == {"Flare Blitz", "Earthquake"}
    assert abilities == {"Intimidate"}
    assert items == {"Choice Band"}


def test_referenced_move_ability_item_names_empty_when_no_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "STAGING_DIR", tmp_path)

    assert cli._referenced_move_ability_item_names() == (set(), set(), set())


def _stub_extraction_summary(monkeypatch):
    """Replace extraction_summary.update with a recording no-op so cli
    tests never write to the real reports/validation/extraction_summary.json."""
    calls = []
    monkeypatch.setattr(
        cli.extraction_summary,
        "update",
        lambda result, *, dataset_version: calls.append((result, dataset_version)) or {},
    )
    return calls


class _RecordingExtractor:
    def __init__(self):
        self.calls = []

    def extract(self, output_path, *, dataset_version=None, session=None):
        self.calls.append((output_path, dataset_version))
        _write_csv(output_path, [], ["a"])


def test_run_extract_writes_dated_snapshot_and_prunes(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "STAGING_DIR", tmp_path)
    _stub_extraction_summary(monkeypatch)
    fake = _RecordingExtractor()
    monkeypatch.setattr(cli, "_EXTRACTORS", {"fake": (fake, "fake_source")})
    monkeypatch.setattr(cli, "_RETENTION_COUNTS", {"fake_source": 2})
    monkeypatch.setattr(cli, "_snapshot_date", lambda: "2026-07-30")

    exit_code = cli._run_extract("fake", "1.2.3")

    assert exit_code == 0
    assert fake.calls == [(tmp_path / "fake_source" / "2026-07-30.csv", "1.2.3")]
    assert (tmp_path / "fake_source" / "2026-07-30.csv").exists()


class _RecordingMunchstatsExtractor:
    def __init__(self):
        self.calls = []

    def extract(
        self, output_path, *, dataset_version=None, session=None, previous_snapshot_path=None
    ):
        self.calls.append((output_path, dataset_version, previous_snapshot_path))
        _write_csv(output_path, [], ["a"])


def test_run_extract_munchstats_passes_previous_snapshot_path(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "STAGING_DIR", tmp_path)
    _stub_extraction_summary(monkeypatch)
    previous_path = tmp_path / "munchstats" / "2026-07-29.csv"
    _write_csv(previous_path, [], ["a"])
    fake = _RecordingMunchstatsExtractor()
    monkeypatch.setattr(cli, "_EXTRACTORS", {"munchstats": (fake, "munchstats")})
    monkeypatch.setattr(cli, "_RETENTION_COUNTS", {"munchstats": 7})
    monkeypatch.setattr(cli, "_snapshot_date", lambda: "2026-07-30")

    exit_code = cli._run_extract("munchstats", "1.2.3")

    assert exit_code == 0
    assert fake.calls == [(tmp_path / "munchstats" / "2026-07-30.csv", "1.2.3", previous_path)]


def test_run_extract_rk9_passes_previous_snapshot_path(tmp_path, monkeypatch):
    # rk9 shares munchstats' incremental path: a concluded event's pairings
    # never change, so the previous snapshot is reused rather than re-fetched.
    # It also re-fetches events still running (docs/upgrade-plan-2027q2.md,
    # E4), read off the newest MunchStats snapshot.
    monkeypatch.setattr(cli, "STAGING_DIR", tmp_path)
    _stub_extraction_summary(monkeypatch)
    previous_path = tmp_path / "rk9_pairings" / "2026-07-29.csv"
    _write_csv(previous_path, [], ["a"])

    class _RecordingRk9Extractor(_RecordingMunchstatsExtractor):
        def extract(self, output_path, *, refresh_event_ids=(), **kwargs):
            self.refresh = list(refresh_event_ids)
            super().extract(output_path, **kwargs)

    fake = _RecordingRk9Extractor()
    monkeypatch.setattr(cli, "_EXTRACTORS", {"rk9": (fake, "rk9_pairings")})
    monkeypatch.setattr(cli, "_RETENTION_COUNTS", {"rk9_pairings": 7})
    monkeypatch.setattr(cli, "_snapshot_date", lambda: "2026-07-30")
    monkeypatch.setattr(cli, "live_event_ids", lambda: ["LIVE"])

    exit_code = cli._run_extract("rk9", "1.2.3")

    assert exit_code == 0
    assert fake.calls == [(tmp_path / "rk9_pairings" / "2026-07-30.csv", "1.2.3", previous_path)]
    assert fake.refresh == ["LIVE"]


def test_run_extract_other_sources_do_not_receive_previous_snapshot_path(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "STAGING_DIR", tmp_path)
    _stub_extraction_summary(monkeypatch)
    fake = _RecordingExtractor()
    monkeypatch.setattr(cli, "_EXTRACTORS", {"fake": (fake, "fake_source")})
    monkeypatch.setattr(cli, "_RETENTION_COUNTS", {"fake_source": 2})
    monkeypatch.setattr(cli, "_snapshot_date", lambda: "2026-07-30")

    exit_code = cli._run_extract("fake", "1.2.3")

    assert exit_code == 0
    assert fake.calls == [(tmp_path / "fake_source" / "2026-07-30.csv", "1.2.3")]


def test_run_extract_all_runs_every_source_in_order(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "STAGING_DIR", tmp_path)
    _stub_extraction_summary(monkeypatch)
    call_order = []

    class _Recorder:
        def __init__(self, name):
            self._name = name

        def extract(self, output_path, *, dataset_version=None, session=None):
            call_order.append(self._name)
            _write_csv(output_path, [], ["a"])

    monkeypatch.setattr(
        cli,
        "_EXTRACTORS",
        {
            "first": (_Recorder("first"), "first_dir"),
            "second": (_Recorder("second"), "second_dir"),
        },
    )
    monkeypatch.setattr(cli, "_RETENTION_COUNTS", {"first_dir": 5, "second_dir": 5})

    exit_code = cli._run_extract("all", "1.2.3")

    assert exit_code == 0
    assert call_order == ["first", "second"]


def test_run_extract_updates_extraction_summary_with_source_name(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "STAGING_DIR", tmp_path)
    calls = _stub_extraction_summary(monkeypatch)
    fake = _RecordingExtractor()
    monkeypatch.setattr(cli, "_EXTRACTORS", {"fake": (fake, "fake_source")})
    monkeypatch.setattr(cli, "_RETENTION_COUNTS", {"fake_source": 2})
    monkeypatch.setattr(cli, "_snapshot_date", lambda: "2026-07-30")

    exit_code = cli._run_extract("fake", "1.2.3")

    assert exit_code == 0
    assert len(calls) == 1
    result, dataset_version = calls[0]
    assert result.staging_subdir == "fake_source"
    assert result.output_path == tmp_path / "fake_source" / "2026-07-30.csv"
    assert result.error is None
    assert dataset_version == "1.2.3"


def test_run_extract_catches_extractor_exception_and_returns_error_code(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "STAGING_DIR", tmp_path)
    calls = _stub_extraction_summary(monkeypatch)

    class _FailingExtractor:
        def extract(self, output_path, *, dataset_version=None, session=None):
            raise RuntimeError("upstream is down")

    monkeypatch.setattr(cli, "_EXTRACTORS", {"fake": (_FailingExtractor(), "fake_source")})
    monkeypatch.setattr(cli, "_RETENTION_COUNTS", {"fake_source": 2})
    monkeypatch.setattr(cli, "_snapshot_date", lambda: "2026-07-30")

    exit_code = cli._run_extract("fake", "1.2.3")

    assert exit_code == 1
    assert len(calls) == 1
    result, _ = calls[0]
    assert result.error == "RuntimeError: upstream is down"
    assert "upstream is down" in capsys.readouterr().err


def test_main_extract_defaults_dataset_version_to_latest_published(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli.versioning, "latest_published_version", lambda: "0.9.9")
    monkeypatch.setattr(
        cli,
        "_run_extract",
        lambda source, dataset_version: (
            captured.update(source=source, dataset_version=dataset_version) or 0
        ),
    )

    exit_code = cli.main(["extract", "pokeapi"])

    assert exit_code == 0
    assert captured == {"source": "pokeapi", "dataset_version": "0.9.9"}


def test_main_extract_dataset_version_override(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        cli,
        "_run_extract",
        lambda source, dataset_version: (
            captured.update(source=source, dataset_version=dataset_version) or 0
        ),
    )

    exit_code = cli.main(["extract", "opgg", "--dataset-version", "9.9.9"])

    assert exit_code == 0
    assert captured == {"source": "opgg", "dataset_version": "9.9.9"}


def _run_results_path(dbt_project_dir):
    return dbt_project_dir / "target" / "run_results.json"


def test_run_validate_passes_when_gates_clean(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "DBT_PROJECT_DIR", tmp_path)

    def fake_run(cmd, cwd, **_kwargs):
        _run_results_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
        _run_results_path(tmp_path).write_text("{}")
        return subprocess.CompletedProcess(cmd, returncode=0)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(cli.report, "generate", lambda: {"release_blocking_findings": []})

    assert cli._run_validate() == 0


def test_run_validate_fails_when_gates_report_findings(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "DBT_PROJECT_DIR", tmp_path)

    def fake_run(cmd, cwd, **_kwargs):
        _run_results_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
        _run_results_path(tmp_path).write_text("{}")
        return subprocess.CompletedProcess(cmd, returncode=1)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(
        cli.report, "generate", lambda: {"release_blocking_findings": ["pokemon: status=fail"]}
    )

    assert cli._run_validate() == 1


def test_run_validate_propagates_unexpected_dbt_crash_code(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "DBT_PROJECT_DIR", tmp_path)
    calls = []

    def fake_run(cmd, cwd, **_kwargs):
        return subprocess.CompletedProcess(cmd, returncode=2)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(cli.report, "generate", lambda: calls.append("called"))

    assert cli._run_validate() == 2
    assert calls == []


def test_run_validate_refuses_stale_run_results_after_compile_error(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "DBT_PROJECT_DIR", tmp_path)
    stale_path = _run_results_path(tmp_path)
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_text("{}")
    # Back-date the stale artifact so it predates _run_validate's start time,
    # simulating a compile/connection error that exits 1 without rewriting it.
    old_time = time.time() - 3600
    os.utime(stale_path, (old_time, old_time))
    calls = []

    def fake_run(cmd, cwd, **_kwargs):
        return subprocess.CompletedProcess(cmd, returncode=1)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(cli.report, "generate", lambda: calls.append("called"))

    assert cli._run_validate() == 1
    assert calls == []


def _sources_path(dbt_project_dir):
    return dbt_project_dir / "target" / "sources.json"


def test_run_validate_runs_source_freshness_and_still_passes(tmp_path, monkeypatch):
    """backlog.md #39: validate must also invoke `dbt source freshness`
    (a separate command from `dbt build`), and a fresh, all-pass
    sources.json must not block validation."""
    monkeypatch.setattr(cli, "DBT_PROJECT_DIR", tmp_path)
    calls = []

    def fake_run(cmd, cwd, **_kwargs):
        calls.append(cmd)
        if cmd[-2:] == ["source", "freshness"]:
            _sources_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
            _sources_path(tmp_path).write_text("{}")
        else:
            _run_results_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
            _run_results_path(tmp_path).write_text("{}")
        return subprocess.CompletedProcess(cmd, returncode=0)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(cli.report, "generate", lambda: {"release_blocking_findings": []})

    assert cli._run_validate() == 0
    assert calls == [
        ["uv", "run", "dbt", "build"],
        ["uv", "run", "dbt", "source", "freshness"],
    ]


def test_run_validate_proceeds_when_source_freshness_produces_no_artifact(tmp_path, monkeypatch):
    """If `dbt source freshness` doesn't write a fresh sources.json (e.g. a
    compile error in the sources.yml freshness config), validate should
    still proceed -- freshness is an additional gate, not a hard
    prerequisite for the rest of the report."""
    monkeypatch.setattr(cli, "DBT_PROJECT_DIR", tmp_path)

    def fake_run(cmd, cwd, **_kwargs):
        if cmd[-2:] == ["source", "freshness"]:
            return subprocess.CompletedProcess(cmd, returncode=2)
        _run_results_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
        _run_results_path(tmp_path).write_text("{}")
        return subprocess.CompletedProcess(cmd, returncode=0)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(cli.report, "generate", lambda: {"release_blocking_findings": []})

    assert cli._run_validate() == 0
    assert not _sources_path(tmp_path).exists()


def test_main_extract_accepts_all_choice(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        cli, "_run_extract", lambda source, dataset_version: captured.update(source=source) or 0
    )

    exit_code = cli.main(["extract", "all", "--dataset-version", "1.0.0"])

    assert exit_code == 0
    assert captured == {"source": "all"}


def test_main_release_dispatches_version_and_known_limitations(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        cli,
        "_run_release",
        lambda dataset_version, known_limitations, notes, package: (
            captured.update(
                dataset_version=dataset_version,
                known_limitations=known_limitations,
                notes=notes,
                package=package,
            )
            or 0
        ),
    )

    exit_code = cli.main(
        [
            "release",
            "--version",
            "0.3.0",
            "--known-limitation",
            "no removal signal",
            "--known-limitation",
            "zero stat deltas",
        ]
    )

    assert exit_code == 0
    assert captured == {
        "dataset_version": "0.3.0",
        "known_limitations": ["no removal signal", "zero stat deltas"],
        "notes": [],
        "package": False,
    }


def test_main_release_defaults_known_limitations_to_empty_list(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        cli,
        "_run_release",
        lambda dataset_version, known_limitations, notes, package: (
            captured.update(
                dataset_version=dataset_version,
                known_limitations=known_limitations,
                notes=notes,
                package=package,
            )
            or 0
        ),
    )

    exit_code = cli.main(["release", "--version", "0.3.0"])

    assert exit_code == 0
    assert captured == {
        "dataset_version": "0.3.0",
        "known_limitations": [],
        "notes": [],
        "package": False,
    }


def test_main_release_passes_notes_and_package(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        cli,
        "_run_release",
        lambda dataset_version, known_limitations, notes, package: (
            captured.update(notes=notes, package=package) or 0
        ),
    )
    exit_code = cli.main(
        ["release", "--version", "0.4.0", "--note", "pre-0.4.0 excludes M-B/M-C", "--package"]
    )
    assert exit_code == 0
    assert captured == {"notes": ["pre-0.4.0 excludes M-B/M-C"], "package": True}


def test_main_release_requires_version(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["release"])

    assert exc_info.value.code == 2
    assert "--version" in capsys.readouterr().err


def test_main_render_card_dispatches_with_team_id(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        cli,
        "_run_render_card",
        lambda team_id, spec_path, output_path: (
            captured.update(team_id=team_id, spec_path=spec_path, output_path=output_path) or 0
        ),
    )

    exit_code = cli.main(["render-card", "--team-id", "abc123", "--output", "card.png"])

    assert exit_code == 0
    assert captured == {
        "team_id": "abc123",
        "spec_path": None,
        "output_path": cli.Path("card.png"),
    }


def test_main_render_card_dispatches_with_spec(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        cli,
        "_run_render_card",
        lambda team_id, spec_path, output_path: (
            captured.update(team_id=team_id, spec_path=spec_path, output_path=output_path) or 0
        ),
    )

    exit_code = cli.main(["render-card", "--spec", "team.json", "--output", "card.png"])

    assert exit_code == 0
    assert captured == {
        "team_id": None,
        "spec_path": cli.Path("team.json"),
        "output_path": cli.Path("card.png"),
    }


def test_main_render_card_requires_team_id_or_spec(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["render-card", "--output", "card.png"])

    assert exc_info.value.code == 2
    assert "required" in capsys.readouterr().err.lower()


def test_main_render_card_rejects_both_team_id_and_spec(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "render-card",
                "--team-id",
                "abc123",
                "--spec",
                "team.json",
                "--output",
                "card.png",
            ]
        )

    assert exc_info.value.code == 2
    assert "not allowed with" in capsys.readouterr().err.lower()


def test_main_build_dashboard_dispatches_with_defaults(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        cli,
        "_run_build_dashboard",
        lambda marts_dir, normalized_dir, output_dir, fetch_icons: (
            captured.update(
                marts_dir=marts_dir,
                normalized_dir=normalized_dir,
                output_dir=output_dir,
                fetch_icons=fetch_icons,
            )
            or 0
        ),
    )

    exit_code = cli.main(["build-dashboard"])

    assert exit_code == 0
    assert captured == {
        "marts_dir": None,
        "normalized_dir": None,
        "output_dir": None,
        "fetch_icons": True,
    }


def test_main_build_dashboard_dispatches_with_overrides_and_no_fetch_icons(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        cli,
        "_run_build_dashboard",
        lambda marts_dir, normalized_dir, output_dir, fetch_icons: (
            captured.update(
                marts_dir=marts_dir,
                normalized_dir=normalized_dir,
                output_dir=output_dir,
                fetch_icons=fetch_icons,
            )
            or 0
        ),
    )

    exit_code = cli.main(
        [
            "build-dashboard",
            "--marts-dir",
            "custom/marts",
            "--normalized-dir",
            "custom/normalized",
            "--output-dir",
            "custom/out",
            "--no-fetch-icons",
        ]
    )

    assert exit_code == 0
    assert captured == {
        "marts_dir": cli.Path("custom/marts"),
        "normalized_dir": cli.Path("custom/normalized"),
        "output_dir": cli.Path("custom/out"),
        "fetch_icons": False,
    }


def test_live_event_ids_reads_the_newest_munchstats_snapshot(tmp_path, monkeypatch):
    # docs/upgrade-plan-2027q2.md, E4: the event-weekend workflow asks this
    # before it spends a rebuild, and rk9 re-fetches these events.
    from datetime import date

    monkeypatch.setattr(cli, "STAGING_DIR", tmp_path)
    fields = ["event_id", "event_date"]
    _write_csv(
        tmp_path / "munchstats" / "2026-12-06.csv",
        [
            {"event_id": "LIVE", "event_date": "2026-12-05"},
            {"event_id": "LIVE", "event_date": "2026-12-05"},
            {"event_id": "OLD", "event_date": "2026-10-09"},
        ],
        fields,
    )
    assert cli.live_event_ids(date(2026, 12, 6)) == ["LIVE"]
    assert cli.live_event_ids(date(2026, 12, 20)) == []
