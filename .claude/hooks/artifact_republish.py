#!/usr/bin/env python3
"""Republish the dashboard's claude.ai artifact before pushing dashboard code.

Two hook modes (.claude/settings.json):

  record  PostToolUse on the Artifact tool. After a publish to the
          dashboard's artifact, notes a fingerprint of pipelines/dashboard/
          as it stands in .claude/state/artifact-published.json.
  check   PreToolUse on Bash. A `git push` whose commits change
          pipelines/dashboard/ is refused unless that fingerprint matches
          the code being pushed, that is, unless the artifact was
          republished after the last change.

The rule and the rebuild steps: CLAUDE.md, "Dashboard artifact". Stdlib
only, so it runs with any python3.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ARTIFACT_ID = "Lfb9NxbaAwRkshcGCQ11wR"
ARTIFACT_URL = f"https://claude.ai/artifact/{ARTIFACT_ID}"
WATCHED = "pipelines/dashboard"
MARKER = Path(".claude/state/artifact-published.json")
_PUSH = re.compile(r"(^|[\s;&|(])git(\s+-\S+(\s+\S+)?)*\s+push\b")


def mentions_push(command: str) -> bool:
    return bool(_PUSH.search(command or ""))


def fingerprint(root: Path) -> str:
    """A hash of every file under pipelines/dashboard/ (bytecode aside)."""
    digest = hashlib.sha256()
    base = root / WATCHED
    for path in sorted(base.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _git(root: Path, *args: str) -> str | None:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def pushes_dashboard_changes(root: Path) -> bool:
    """Whether HEAD carries pipelines/dashboard/ changes its upstream (else
    origin/main) lacks. Unknown counts as yes."""
    base = _git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}") or "origin/main"
    changed = _git(root, "diff", "--name-only", f"{base}...HEAD", "--", WATCHED)
    return changed is None or bool(changed)


def read_marker(root: Path) -> dict:
    try:
        return json.loads((root / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def is_dashboard_publish(event: dict) -> bool:
    tool_input = event.get("tool_input") or {}
    if (tool_input.get("action") or "publish") != "publish" or tool_input.get("asset"):
        return False
    seen = json.dumps(tool_input) + json.dumps(event.get("tool_response"), default=str)
    return ARTIFACT_ID in seen


def record(root: Path, event: dict) -> None:
    if not is_dashboard_publish(event):
        return
    (root / MARKER).parent.mkdir(parents=True, exist_ok=True)
    (root / MARKER).write_text(
        json.dumps(
            {
                "fingerprint": fingerprint(root),
                "head": _git(root, "rev-parse", "HEAD"),
                "published_at": datetime.now(UTC).isoformat(),
            }
        ),
        encoding="utf-8",
    )


def check(root: Path, event: dict) -> dict | None:
    """The PreToolUse decision for a Bash call, or None to let it run."""
    if not mentions_push((event.get("tool_input") or {}).get("command", "")):
        return None
    if not pushes_dashboard_changes(root):
        return None
    if read_marker(root).get("fingerprint") == fingerprint(root):
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "This push carries pipelines/dashboard/ changes, and the dashboard's artifact "
                f"({ARTIFACT_URL}) hasn't been republished since they were made. Rebuild it with "
                "`python -m pipelines.cli build-artifact-site --output-dir <fresh dir>`, publish "
                "the plan's page and batches to that URL with the Artifact tool (see CLAUDE.md, "
                '"Dashboard artifact"), then push again.'
            ),
        }
    }


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".")
    if mode == "record":
        record(root, event)
    elif mode == "check":
        decision = check(root, event)
        if decision:
            print(json.dumps(decision))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
