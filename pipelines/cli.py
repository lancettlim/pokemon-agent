"""CLI entry point for the pipelines package.

Subcommands:
    extract <source>   Run one source extractor (pokeapi | opgg | munchstats | rk9 | limitless | pokebase | bulbagarden | all)
    validate           Reshape dbt's test results into a validation report
    release            Publish a versioned release package (gated on validate)
    render-card        Render a team card PNG, from a team_id or an ad-hoc build spec
    build-dashboard    Build the static analytics dashboard site from data/marts/*.csv

Staging snapshots (see `_run_extract` below) are written date-partitioned,
one CSV per source per UTC calendar day, under a per-source subdirectory of
data/staging/ (e.g. data/staging/pokeapi/2026-07-30.csv) rather than a
single file that gets overwritten every run — see backlog.md #1. CSV stays
the format (not Parquet): it matches the existing data/staging/*.schema.json
contracts and needs no new dependency. Retention is pruned per source after
each write via _RETENTION_COUNTS, sized to each source's refresh cadence
(docs/dataset-spec.md) and row volume — munchstats.csv alone runs ~37MB, so
it keeps the fewest snapshots.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from pipelines import versioning
from pipelines.dashboard import build as dashboard_build
from pipelines.extract import (
    bulbagarden,
    limitless,
    limitless_play,
    munchstats,
    opgg,
    pokeapi,
    pokebase,
    rk9,
    showdown_replays,
    smogon_ladder,
)
from pipelines.extract import http as extract_http
from pipelines.extract import summary as extraction_summary
from pipelines.release import build as release_build
from pipelines.render import share_cards, team_card
from pipelines.validate import report

REPO_ROOT = Path(__file__).resolve().parents[1]
DBT_PROJECT_DIR = REPO_ROOT / "dbt"
STAGING_DIR = REPO_ROOT / "data" / "staging"

# source subcommand -> (extractor module, staging subdirectory name).
# Order matters for `extract all`: munchstats must run before pokeapi so
# pokeapi's move/ability/item detail fetch has roster names to scope to
# (see _referenced_move_ability_item_names).
_EXTRACTORS = {
    "munchstats": (munchstats, "munchstats"),
    "rk9": (rk9, "rk9_pairings"),
    "limitless": (limitless, "limitless"),
    # Online tournaments (docs/upgrade-plan-2027q2.md, S1): writes its
    # pairings to limitless_play_pairings too, see _run_limitless_play.
    "limitless_play": (limitless_play, "limitless_play"),
    # Showdown ladder statistics (docs/upgrade-plan-2027q2.md, S2): also
    # writes smogon_ladder_counters and smogon_ladder_spreads, see
    # _run_smogon_ladder.
    "smogon_ladder": (smogon_ladder, "smogon_ladder"),
    # Showdown ladder replays (docs/upgrade-plan-2027q2.md, S3): a capped,
    # paced sample of rated battles, reusing every battle already held.
    "showdown_replays": (showdown_replays, "showdown_replays"),
    "opgg": (opgg, "opgg_champions"),
    "pokebase": (pokebase, "pokebase"),
    "bulbagarden": (bulbagarden, "bulbagarden"),
    "pokeapi": (pokeapi, "pokeapi"),
}

# Snapshots kept per staging subdirectory before older ones are pruned.
# PokéAPI sources refresh weekly (docs/dataset-spec.md) so a year of history
# fits in ~12 snapshots; OP.GG/PokéBase/Bulbagarden refresh daily-or-less and
# are small per-row, so two weeks is cheap; MunchStats also refreshes daily
# but is ~37MB/run, so it keeps the least history of the daily sources.
_RETENTION_COUNTS = {
    "pokeapi": 12,
    "pokeapi_move": 12,
    "pokeapi_ability": 12,
    "pokeapi_item": 12,
    # Artwork refreshes on-demand rather than weekly (a published HOME
    # render never changes), so it keeps the same history as the sprite
    # manifest it sits beside rather than the weekly sources' 12.
    "pokeapi_artwork": 10,
    # Localised names (Q4) refresh with the weekly pokeapi run.
    "pokeapi_names": 12,
    "opgg_champions": 14,
    "munchstats": 7,
    "rk9_pairings": 7,
    "limitless": 14,
    "limitless_play": 14,
    "limitless_play_pairings": 14,
    "limitless_play_upcoming": 14,
    # Smogon publishes monthly and a held month is reused, so a daily run
    # only re-stamps it; three snapshots (~14MB each) cover a missed run.
    "smogon_ladder": 3,
    "smogon_ladder_counters": 3,
    "smogon_ladder_spreads": 3,
    # Each snapshot holds every battle kept (up to 5,000 per format), so a
    # few cover a missed run.
    "showdown_replays": 3,
    "pokebase": 14,
    "bulbagarden": 10,
}

# Static per-staging-subdirectory endpoint descriptions for
# reports/validation/extraction_summary.json (backlog.md #48) -- these
# describe the fixed shape of each API call, not anything that varies
# per-run, so they're recorded here rather than derived at runtime.
# pokeapi_move/pokeapi_ability/pokeapi_item get their own entries (distinct
# from "pokeapi" itself) since they're separate requests made during the
# same `extract pokeapi` invocation.
_ENDPOINTS = {
    "pokeapi": "https://pokeapi.co/api/v2/pokemon/{form_name} "
    "(list from https://pokeapi.co/api/v2/pokemon?limit=5000)",
    "pokeapi_move": "https://pokeapi.co/api/v2/move/{move_name}",
    "pokeapi_ability": "https://pokeapi.co/api/v2/ability/{ability_name}",
    "pokeapi_item": "https://pokeapi.co/api/v2/item/{item_name}",
    "pokeapi_names": "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/"
    "{languages,pokemon,pokemon_forms,pokemon_species_names,pokemon_form_names}.csv",
    "pokeapi_artwork": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/"
    "pokemon/other/home/{pokeapi_resource_id}.png",
    "opgg_champions": "https://op.gg/pokemon-champions/pokedex",
    "munchstats": "https://raw.githubusercontent.com/PizzaTimeJoshua/munchstats/main/"
    "stats/tournaments/",
    "rk9_pairings": "https://rk9.gg/pairings/{event_id}?pod={pod}&rnd={round}",
    "limitless": "https://limitlessvgc.com/tournaments, /tournaments/{id}, /teams/{id}",
    "limitless_play": "https://play.limitlesstcg.com/api/tournaments?game=VGC, "
    "/api/tournaments/{id}/standings",
    "limitless_play_pairings": "https://play.limitlesstcg.com/api/tournaments/{id}/pairings",
    "limitless_play_upcoming": "https://play.limitlesstcg.com/tournaments/upcoming"
    "?game=VGC&format={limitless_play_format}",
    "pokebase": "https://pokebase.app/pokemon-champions/pokemon",
    "smogon_ladder": "https://www.smogon.com/stats/{month}/chaos/{metagame}[bo3]-{cutoff}.json",
    "showdown_replays": "https://replay.pokemonshowdown.com/search.json?format={format_id}"
    "&before={uploadtime}, /{replay_id}.json",
    "bulbagarden": "https://archives.bulbagarden.net/w/api.php (Category:Champions_menu_sprites)",
}

_SOURCE_NAME_SUFFIXES = {
    "pokeapi_move": " (move detail)",
    "pokeapi_ability": " (ability detail)",
    "pokeapi_item": " (item detail)",
    "pokeapi_artwork": " (artwork)",
    "pokeapi_names": " (localised names)",
    "limitless_play_pairings": " (pairings)",
    "limitless_play_upcoming": " (upcoming)",
}


def _snapshot_date() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _dated_snapshot_path(staging_subdir: str, date_str: str) -> Path:
    return STAGING_DIR / staging_subdir / f"{date_str}.csv"


def _latest_snapshot_path(staging_subdir: str) -> Path | None:
    source_dir = STAGING_DIR / staging_subdir
    if not source_dir.exists():
        return None
    snapshots = sorted(source_dir.glob("*.csv"))
    return snapshots[-1] if snapshots else None


def _prune_old_snapshots(staging_subdir: str) -> None:
    """Delete all but the newest `_RETENTION_COUNTS[staging_subdir]` dated
    snapshots. Filenames are `YYYY-MM-DD.csv`, so lexicographic sort order
    is chronological order.
    """
    keep = _RETENTION_COUNTS[staging_subdir]
    source_dir = STAGING_DIR / staging_subdir
    snapshots = sorted(source_dir.glob("*.csv"))
    for stale in snapshots[:-keep]:
        stale.unlink()


def _referenced_move_ability_item_names() -> tuple[set[str], set[str], set[str]]:
    """Read the latest data/staging/munchstats/<date>.csv snapshot for the
    distinct move/ability/item names real tournament rosters reported, so
    `extract pokeapi` can scope its move/ability/item detail fetches to
    names that matter to the dashboard instead of PokéAPI's full catalog.
    Reads the munchstats snapshot directly (not the dbt-normalized
    tournament_team_member table) to avoid a circular dependency on
    `dbt build` running before `extract pokeapi`.
    """
    munchstats_path = _latest_snapshot_path("munchstats")
    if munchstats_path is None:
        return set(), set(), set()

    moves: set[str] = set()
    abilities: set[str] = set()
    items: set[str] = set()
    with munchstats_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("ability"):
                abilities.add(row["ability"])
            if row.get("item_name"):
                items.add(row["item_name"])
            if row.get("moves"):
                moves.update(name.strip() for name in row["moves"].split("|") if name.strip())
    return moves, abilities, items


def _champions_form_resource_ids() -> list[tuple[str, str]]:
    """Resolve the `(form_name, pokeapi_resource_id)` pairs `extract pokeapi`
    should fetch high-resolution artwork for.

    Scoped to the forms that already have a Bulbagarden Champions menu
    sprite, read from the controlled `bulbagarden_title_to_pokeapi_form`
    seed: that category *is* the Champions pool, so this fetches artwork for
    exactly the set `pokemon_asset` already carries a sprite for -- roughly
    317 forms rather than PokéAPI's full ~1,350, and with no chance of the
    two image kinds covering different Pokémon. The seed is read directly
    (not the dbt-built `pokemon_asset` table) to avoid a circular dependency
    on `dbt build` running before `extract pokeapi`, the same reasoning
    _referenced_move_ability_item_names() applies to munchstats.

    The resource id comes from the pokeapi snapshot just written by this
    same invocation, where `extract()` records each form's own PokéAPI id as
    `source_record_id` -- so no extra HTTP lookup and no new mapping seed
    are needed to go from a form slug to the id the sprite repository is
    keyed by.
    """
    seed_path = DBT_PROJECT_DIR / "seeds" / "bulbagarden_title_to_pokeapi_form.csv"
    pokeapi_path = _latest_snapshot_path("pokeapi")
    if not seed_path.exists() or pokeapi_path is None:
        return []

    with seed_path.open(newline="", encoding="utf-8") as fh:
        champions_forms = {
            row["pokeapi_form_name"] for row in csv.DictReader(fh) if row.get("pokeapi_form_name")
        }

    resource_id_by_form: dict[str, str] = {}
    with pokeapi_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("form_name") and row.get("source_record_id"):
                resource_id_by_form[row["form_name"]] = row["source_record_id"]

    return sorted(
        (form_name, resource_id_by_form[form_name])
        for form_name in champions_forms
        if form_name in resource_id_by_form
    )


def _source_display_name(module, staging_subdir: str) -> str:
    base = getattr(module, "SOURCE_NAME", staging_subdir)
    return f"{base}{_SOURCE_NAME_SUFFIXES.get(staging_subdir, '')}"


def _run_tracked_extract(
    *, source_name: str, staging_subdir: str, output_path: Path, dataset_version: str, call
) -> bool:
    """Run `call()` (an extraction into output_path) inside an
    `http.track_requests()` scope, then merge the run's request/row/
    null-rate stats into reports/validation/extraction_summary.json
    (backlog.md #48) regardless of whether the extraction succeeded.

    Returns True on success. On failure, prints a structured one-line
    error (source name + exception) to stderr and returns False instead of
    letting the exception propagate as a raw traceback -- matching
    `_run_validate`'s existing "catch, log, return a code" convention
    rather than crashing the process.
    """
    error = None
    with extract_http.track_requests() as stats:
        try:
            call()
        except Exception as exc:  # noqa: BLE001 -- must catch anything to still write the summary
            error = f"{type(exc).__name__}: {exc}"
        result = extraction_summary.SourceRunResult(
            source_name=source_name,
            endpoint=_ENDPOINTS.get(staging_subdir, ""),
            staging_subdir=staging_subdir,
            output_path=output_path,
            stats=stats,
            error=error,
        )
        extraction_summary.update(result, dataset_version=dataset_version)
    if error is not None:
        print(f"Extraction failed for {source_name} ({staging_subdir}): {error}", file=sys.stderr)
        return False
    return True


def live_event_ids(today=None) -> list[str]:
    """Events running now or just over (munchstats.is_live), from the
    newest MunchStats snapshot: run `extract munchstats` first and a new
    event's date is already in it. Used to re-fetch live RK9 pairings (E4)
    and by `live-events`, which the event-weekend workflow asks before it
    spends a rebuild."""
    path = _latest_snapshot_path("munchstats")
    if path is None:
        return []
    live: dict[str, None] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("event_id") and munchstats.is_live(row.get("event_date"), today):
                live[row["event_id"]] = None
    return list(live)


def _run_limitless_play(dataset_version: str) -> int:
    """Online tournaments in three tracked passes sharing one rate limiter:
    team sheets (limitless_play), then the pairings of the same tournaments
    (limitless_play_pairings), each reusing its previous snapshot for
    settled tournaments, then the upcoming tournaments list
    (limitless_play_upcoming, list #31). The passes carry one extraction
    time, so a run that crosses midnight UTC still lands them under the
    same snapshot date (staging reads snapshot_date from extracted_at_utc)."""
    extracted_at = datetime.now(UTC)
    extracted_at_utc = extracted_at.isoformat()
    date_str = extracted_at.strftime("%Y-%m-%d")
    output_path = _dated_snapshot_path("limitless_play", date_str)
    pairings_path = _dated_snapshot_path("limitless_play_pairings", date_str)
    upcoming_path = _dated_snapshot_path("limitless_play_upcoming", date_str)
    covered: list[dict] = []

    def roster() -> None:
        covered.extend(
            limitless_play.extract(
                output_path,
                dataset_version=dataset_version,
                previous_snapshot_path=_latest_snapshot_path("limitless_play"),
                extracted_at_utc=extracted_at_utc,
            )
        )

    ok = _run_tracked_extract(
        source_name=_source_display_name(limitless_play, "limitless_play"),
        staging_subdir="limitless_play",
        output_path=output_path,
        dataset_version=dataset_version,
        call=roster,
    )
    if not ok:
        return 1
    _prune_old_snapshots("limitless_play")
    previous_pairings = _latest_snapshot_path("limitless_play_pairings")
    ok = _run_tracked_extract(
        source_name=_source_display_name(limitless_play, "limitless_play_pairings"),
        staging_subdir="limitless_play_pairings",
        output_path=pairings_path,
        dataset_version=dataset_version,
        call=lambda: limitless_play.extract_pairings(
            pairings_path,
            covered,
            dataset_version=dataset_version,
            previous_snapshot_path=previous_pairings,
            extracted_at_utc=extracted_at_utc,
        ),
    )
    if not ok:
        return 1
    _prune_old_snapshots("limitless_play_pairings")
    ok = _run_tracked_extract(
        source_name=_source_display_name(limitless_play, "limitless_play_upcoming"),
        staging_subdir="limitless_play_upcoming",
        output_path=upcoming_path,
        dataset_version=dataset_version,
        call=lambda: limitless_play.extract_upcoming(
            upcoming_path, dataset_version=dataset_version, extracted_at_utc=extracted_at_utc
        ),
    )
    if not ok:
        return 1
    _prune_old_snapshots("limitless_play_upcoming")
    return 0


def _run_smogon_ladder(dataset_version: str) -> int:
    """Smogon's ladder statistics: one tracked pass writing usage
    (smogon_ladder), checks and counters (smogon_ladder_counters) and Stat
    Point spreads (smogon_ladder_spreads) from the same files, each reusing
    the previous snapshot's rows for a month it already holds. The
    extraction summary counts the usage table's rows."""
    date_str = _snapshot_date()
    subdirs = ("smogon_ladder", "smogon_ladder_counters", "smogon_ladder_spreads")
    paths = [_dated_snapshot_path(subdir, date_str) for subdir in subdirs]
    previous = tuple(_latest_snapshot_path(subdir) for subdir in subdirs)
    ok = _run_tracked_extract(
        source_name=_source_display_name(smogon_ladder, "smogon_ladder"),
        staging_subdir="smogon_ladder",
        output_path=paths[0],
        dataset_version=dataset_version,
        call=lambda: smogon_ladder.extract(
            *paths, dataset_version=dataset_version, previous_paths=previous
        ),
    )
    if not ok:
        return 1
    for subdir in subdirs:
        _prune_old_snapshots(subdir)
    return 0


def _run_extract(source: str, dataset_version: str) -> int:
    if source == "all":
        for one_source in _EXTRACTORS:
            exit_code = _run_extract(one_source, dataset_version)
            if exit_code != 0:
                return exit_code
        return 0

    if source == "limitless_play":
        return _run_limitless_play(dataset_version)
    if source == "smogon_ladder":
        return _run_smogon_ladder(dataset_version)

    module, staging_subdir = _EXTRACTORS[source]
    date_str = _snapshot_date()
    output_path = _dated_snapshot_path(staging_subdir, date_str)
    extract_kwargs = {}
    if source in ("munchstats", "rk9", "showdown_replays"):
        # backlog.md #44: reuse cached rows for an event that hasn't changed
        # since the previous snapshot, instead of re-fetching everything on
        # every scheduled run. For munchstats that's ~106k roster rows
        # behind a metadata signature check; for rk9 it's every round of a
        # concluded event, whose pairings are immutable once uploaded; for
        # showdown_replays every battle already sampled.
        extract_kwargs["previous_snapshot_path"] = _latest_snapshot_path(staging_subdir)
    if source == "rk9":
        # An event still running is fetched again (E4): its cached pairings
        # stop at whichever round was live when they were cached.
        extract_kwargs["refresh_event_ids"] = live_event_ids()
    ok = _run_tracked_extract(
        source_name=_source_display_name(module, staging_subdir),
        staging_subdir=staging_subdir,
        output_path=output_path,
        dataset_version=dataset_version,
        call=lambda: module.extract(output_path, dataset_version=dataset_version, **extract_kwargs),
    )
    if not ok:
        return 1
    _prune_old_snapshots(staging_subdir)
    if source == "pokeapi":
        # Artwork is scoped to the bulbagarden mapping seed and this run's
        # own pokeapi snapshot, so unlike the move/ability/item detail
        # fetches below it doesn't depend on munchstats having run first --
        # it goes before their early return rather than after it.
        form_resource_ids = _champions_form_resource_ids()
        if not form_resource_ids:
            print(
                "Skipping artwork extraction: no form/resource-id pairs resolved from "
                "dbt/seeds/bulbagarden_title_to_pokeapi_form.csv and the pokeapi snapshot.",
                file=sys.stderr,
            )
        else:
            artwork_output_path = _dated_snapshot_path("pokeapi_artwork", date_str)
            ok = _run_tracked_extract(
                source_name=_source_display_name(pokeapi, "pokeapi_artwork"),
                staging_subdir="pokeapi_artwork",
                output_path=artwork_output_path,
                dataset_version=dataset_version,
                call=lambda: pokeapi.extract_artwork(
                    artwork_output_path, form_resource_ids, dataset_version=dataset_version
                ),
            )
            if not ok:
                return 1
            _prune_old_snapshots("pokeapi_artwork")

        # Localised names (docs/upgrade-plan-2027q2.md, Q4) for every form
        # this run just wrote, from PokéAPI's source CSVs: five requests.
        names_output_path = _dated_snapshot_path("pokeapi_names", date_str)
        with output_path.open(newline="", encoding="utf-8") as fh:
            form_names = [row["form_name"] for row in csv.DictReader(fh) if row.get("form_name")]
        ok = _run_tracked_extract(
            source_name=_source_display_name(pokeapi, "pokeapi_names"),
            staging_subdir="pokeapi_names",
            output_path=names_output_path,
            dataset_version=dataset_version,
            call=lambda: pokeapi.extract_names(
                names_output_path, form_names, dataset_version=dataset_version
            ),
        )
        if not ok:
            return 1
        _prune_old_snapshots("pokeapi_names")

        moves, abilities, items = _referenced_move_ability_item_names()
        if not moves and not abilities and not items:
            print(
                "Skipping move/ability/item detail extraction: "
                "run `extract munchstats` first so there are names to scope to.",
                file=sys.stderr,
            )
            return 0
        for detail_subdir, names, extract_fn in (
            ("pokeapi_move", sorted(moves), pokeapi.extract_moves),
            ("pokeapi_ability", sorted(abilities), pokeapi.extract_abilities),
            ("pokeapi_item", sorted(items), pokeapi.extract_items),
        ):
            detail_output_path = _dated_snapshot_path(detail_subdir, date_str)
            ok = _run_tracked_extract(
                source_name=_source_display_name(pokeapi, detail_subdir),
                staging_subdir=detail_subdir,
                output_path=detail_output_path,
                dataset_version=dataset_version,
                call=lambda extract_fn=extract_fn, detail_output_path=detail_output_path, names=names: (
                    extract_fn(detail_output_path, names, dataset_version=dataset_version)
                ),
            )
            if not ok:
                return 1
            _prune_old_snapshots(detail_subdir)
    return 0


def _run_validate() -> int:
    # dbt build exits non-zero both when a data test fails (an expected
    # outcome here -- a release gate catching bad data) and when a compile
    # or connection error aborts the run before writing a fresh
    # run_results.json. Those two cases must not be treated the same: only
    # the first one has real results worth reshaping into a report. Guard
    # against the second by checking that run_results.json was actually
    # rewritten by this invocation before reading it.
    run_results_path = DBT_PROJECT_DIR / "target" / "run_results.json"
    started_at = time.time()
    result = subprocess.run(["uv", "run", "dbt", "build"], cwd=DBT_PROJECT_DIR, check=False)
    if result.returncode not in (0, 1):
        print(f"dbt build crashed unexpectedly (exit {result.returncode})", file=sys.stderr)
        return result.returncode
    if not run_results_path.exists() or run_results_path.stat().st_mtime < started_at:
        print(
            "dbt build did not produce a fresh run_results.json (likely a compile "
            "or connection error) -- refusing to validate against stale results",
            file=sys.stderr,
        )
        return 1

    # backlog.md #39: a separate `dbt source freshness` invocation (not part
    # of `dbt build`) checks each source's extracted_at_utc against the
    # per-source thresholds in dbt/models/staging/_sources.yml. Its own exit
    # code isn't gating here -- a stale source reports "error" status in
    # target/sources.json, which report.generate() below folds into
    # release_blocking_findings the same way any other failing check is.
    # This step only guards against the command not running at all (e.g. a
    # compile error), in which case sources.json is stale or absent and
    # report.generate() degrades to an empty freshness_checks list rather
    # than blocking the whole validate run over a best-effort extra gate.
    sources_path = DBT_PROJECT_DIR / "target" / "sources.json"
    freshness_started_at = time.time()
    subprocess.run(["uv", "run", "dbt", "source", "freshness"], cwd=DBT_PROJECT_DIR, check=False)
    if not sources_path.exists() or sources_path.stat().st_mtime < freshness_started_at:
        print(
            "`dbt source freshness` did not produce a fresh target/sources.json -- "
            "proceeding without freshness data",
            file=sys.stderr,
        )

    generated = report.generate()
    failing = generated["release_blocking_findings"]
    if failing:
        print(f"Validation gates failing: {failing}", file=sys.stderr)
        return 1
    print(f"Validation report written to {report.REPORT_PATH}")
    return 0


def _run_release(
    dataset_version: str,
    known_limitations: list[str],
    notes: list[str] | None = None,
    package: bool = False,
) -> int:
    try:
        manifest = release_build.build(
            dataset_version, known_limitations=known_limitations, notes=notes, package=package
        )
    except release_build.ReleaseBlockedError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Published dataset_version {dataset_version}: {len(manifest['tables'])} tables")
    if manifest.get("package"):
        print(
            f"Packaged {manifest['package']['file_name']} (sha256 {manifest['package']['sha256']})"
        )
    return 0


def _run_render_card(team_id: str | None, spec_path: Path | None, output_path: Path) -> int:
    if team_id is not None:
        team_card.render_for_team(team_id, output_path)
    else:
        team_card.render_for_spec(spec_path, output_path)
    print(f"Rendered card to {output_path}")
    return 0


def _run_render_share_cards(output_dir: Path | None) -> int:
    manifest = share_cards.render_share_cards(output_dir or share_cards.DEFAULT_OUTPUT_DIR)
    print(
        f"Rendered {len(manifest['teams'])} team cards and "
        f"{len(manifest['whats_changed'])} What changed cards"
    )
    return 0


def _run_build_dashboard(
    marts_dir: Path | None,
    normalized_dir: Path | None,
    output_dir: Path | None,
    fetch_icons: bool,
) -> int:
    kwargs = {"fetch_icons": fetch_icons}
    if marts_dir is not None:
        kwargs["marts_dir"] = marts_dir
    if normalized_dir is not None:
        kwargs["normalized_dir"] = normalized_dir
    if output_dir is not None:
        kwargs["output_dir"] = output_dir
    payload = dashboard_build.build(**kwargs)
    print(f"Dashboard built with {len(payload['marts'])} mart tables")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pokemon-champions-cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser(
        "extract", help="Run one source extractor, or 'all' to run every source in sequence"
    )
    extract_parser.add_argument("source", choices=[*sorted(_EXTRACTORS), "all"])
    extract_parser.add_argument(
        "--dataset-version",
        dest="dataset_version",
        default=None,
        help="Stamped onto every extracted row's dataset_version field; "
        "defaults to the latest published version (see pipelines/versioning.py)",
    )

    subparsers.add_parser("validate", help="Run dbt build and write the validation report")

    subparsers.add_parser(
        "live-events",
        help="Print the RK9 ids of events running now or just over, one per line "
        "(from the newest MunchStats snapshot); exit 1 when there are none",
    )

    release_parser = subparsers.add_parser(
        "release", help="Publish a versioned release package (gated on validate)"
    )
    release_parser.add_argument("--version", required=True, dest="dataset_version")
    release_parser.add_argument(
        "--known-limitation",
        action="append",
        dest="known_limitations",
        default=[],
        help="Repeatable; recorded in the manifest and changelog",
    )
    release_parser.add_argument(
        "--note",
        action="append",
        dest="notes",
        default=[],
        help="Repeatable; listed under the changelog's Notes",
    )
    release_parser.add_argument(
        "--package",
        action="store_true",
        help="Also zip the package into releases/packages/ with a sha256 checksum for a "
        "GitHub Release, and record it in the manifest (cut-release.yml does this)",
    )

    render_parser = subparsers.add_parser(
        "render-card", help="Render a team card PNG, from a team_id or an ad-hoc build spec"
    )
    render_source = render_parser.add_mutually_exclusive_group(required=True)
    render_source.add_argument("--team-id", dest="team_id")
    render_source.add_argument("--spec", dest="spec_path", type=Path)
    render_parser.add_argument("--output", required=True, dest="output_path", type=Path)

    dashboard_parser = subparsers.add_parser(
        "build-dashboard", help="Build the static analytics dashboard site from data/marts/*.csv"
    )
    dashboard_parser.add_argument("--marts-dir", dest="marts_dir", type=Path, default=None)
    dashboard_parser.add_argument(
        "--normalized-dir", dest="normalized_dir", type=Path, default=None
    )
    dashboard_parser.add_argument("--output-dir", dest="output_dir", type=Path, default=None)
    dashboard_parser.add_argument(
        "--no-fetch-icons",
        dest="fetch_icons",
        action="store_false",
        default=True,
        help="Skip fetching item icons over the network (species sprites and "
        "move-type icons are always local, offline copies)",
    )

    share_parser = subparsers.add_parser(
        "render-share-cards",
        help="Render the dashboard's share images (newest event's top 8, What changed cards, "
        "Open Graph image) with Playwright, before build-dashboard",
    )
    share_parser.add_argument("--output-dir", dest="output_dir", type=Path, default=None)

    args = parser.parse_args(argv)

    if args.command == "extract":
        dataset_version = args.dataset_version
        if dataset_version is None:
            dataset_version = versioning.latest_published_version()
        return _run_extract(args.source, dataset_version)
    if args.command == "live-events":
        live = live_event_ids()
        for event_id in live:
            print(event_id)
        return 0 if live else 1
    if args.command == "validate":
        return _run_validate()
    if args.command == "release":
        return _run_release(args.dataset_version, args.known_limitations, args.notes, args.package)
    if args.command == "render-card":
        return _run_render_card(args.team_id, args.spec_path, args.output_path)
    if args.command == "build-dashboard":
        return _run_build_dashboard(
            args.marts_dir, args.normalized_dir, args.output_dir, args.fetch_icons
        )
    if args.command == "render-share-cards":
        return _run_render_share_cards(args.output_dir)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
