"""The dashboard as a claude.ai artifact.

The dashboard is mirrored to a private claude.ai artifact (ARTIFACT_URL),
which is republished whenever dashboard code changes, before the change is
pushed: .claude/hooks/artifact_republish.py blocks a `git push` that carries
pipelines/dashboard/ changes until it has been (see CLAUDE.md, "Dashboard
artifact").

An artifact version holds at most MAX_FILES files and the full site has
about a thousand, most of them images, so build_artifact_site builds a
lighter copy:

  - every sprite, type icon, script and data shard, as the site has them;
  - hero art only for the Pokémon on a Top 12 board (the rest of the page
    falls back to their sprite);
  - no item icons (items show as their names) and no share cards (the
    download and share buttons don't appear).

One publish takes at most MAX_BATCH_FILES files and MAX_BATCH_BYTES, so
publish_batches splits the files besides index.html (the page itself) into
batches to send one after another to the same artifact.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipelines.dashboard import build

ARTIFACT_URL = "https://claude.ai/artifact/Lfb9NxbaAwRkshcGCQ11wR"
MAX_FILES = 511
MAX_BATCH_FILES = 255
MAX_BATCH_BYTES = 64 * 1024 * 1024
PAGE = "index.html"


def board_keys(payload: dict[str, Any]) -> set[str]:
    """Every Pokémon on any regulation's Top 12 boards, either grouping."""
    keys: set[str] = set()
    for kpis in (payload.get("kpis_by_scope") or {}).values():
        for board in (kpis.get("top_12_boards") or {}).values():
            for group in ("forms", "species"):
                keys.update(
                    t["pokemon_key"] for t in board.get(group) or [] if t.get("pokemon_key")
                )
    return keys


def site_files(site_dir: Path) -> list[Path]:
    """Every file of a built site, relative to it."""
    return sorted(p.relative_to(site_dir) for p in site_dir.rglob("*") if p.is_file())


def publish_batches(site_dir: Path) -> list[list[str]]:
    """The files besides the page, in publish-sized batches: data and
    scripts first, then images, so each partial version is a working page."""
    files = [p for p in site_files(site_dir) if p.as_posix() != PAGE]
    files.sort(key=lambda p: (p.parts[0] == "images", p.as_posix()))
    batches: list[list[str]] = []
    current: list[str] = []
    size = 0
    for path in files:
        bytes_ = (site_dir / path).stat().st_size
        if current and (len(current) >= MAX_BATCH_FILES or size + bytes_ > MAX_BATCH_BYTES):
            batches.append(current)
            current, size = [], 0
        current.append(path.as_posix())
        size += bytes_
    if current:
        batches.append(current)
    return batches


def build_artifact_site(output_dir: Path, **build_kwargs: Any) -> dict[str, Any]:
    """Build the lighter site into output_dir (a fresh directory, so no
    share cards are picked up) and check it fits one artifact version."""
    build_kwargs.setdefault("fetch_icons", False)
    payload = build.build(
        output_dir=output_dir, item_icons=False, hero_art_keys=board_keys, **build_kwargs
    )
    count = len(site_files(output_dir))
    if count > MAX_FILES:
        raise ValueError(
            f"the artifact site has {count} files, over the {MAX_FILES} an artifact holds"
        )
    return payload


def write_plan(site_dir: Path, plan_path: Path) -> dict[str, Any]:
    """Write the publish plan: the page, the artifact and the batches, each
    a {published path: source path} map relative to site_dir."""
    plan = {
        "artifact_url": ARTIFACT_URL,
        "root": str(site_dir),
        "page": str(site_dir / PAGE),
        "file_count": len(site_files(site_dir)),
        "batches": [{p: p for p in batch} for batch in publish_batches(site_dir)],
    }
    plan_path.write_text(json.dumps(plan, indent=1), encoding="utf-8")
    return plan
