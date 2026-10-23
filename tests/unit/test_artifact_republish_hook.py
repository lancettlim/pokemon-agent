"""The hook that keeps the dashboard's claude.ai artifact republished before
dashboard code is pushed (.claude/hooks/artifact_republish.py)."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "artifact_republish.py"
spec = importlib.util.spec_from_file_location("artifact_republish", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    """A clone of a bare origin whose main holds one dashboard file."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", "-b", "main", str(origin))
    work = tmp_path / "work"
    _git(tmp_path, "clone", str(origin), str(work))
    for key, value in (("user.email", "t@example.com"), ("user.name", "T")):
        _git(work, "config", key, value)
    (work / "pipelines" / "dashboard").mkdir(parents=True)
    (work / "pipelines" / "dashboard" / "app.js").write_text("one", encoding="utf-8")
    (work / "README.md").write_text("readme", encoding="utf-8")
    _git(work, "add", ".")
    _git(work, "commit", "-m", "base")
    _git(work, "push", "-u", "origin", "main")
    return work


def _commit(repo, path, text):
    (repo / path).write_text(text, encoding="utf-8")
    _git(repo, "commit", "-am", f"change {path}")


PUSH = {"tool_input": {"command": "git push -u origin main"}}
PUBLISH = {
    "tool_input": {"file_path": "/tmp/site/index.html"},
    "tool_response": f"Published /tmp/site/index.html at {hook.ARTIFACT_URL} (Version 11)",
}


@pytest.mark.parametrize(
    "command,expected",
    [
        ("git push -u origin main", True),
        ("cd /repo && git push", True),
        ("git -C /repo push origin HEAD", True),
        ("git --no-pager push", True),
        ("git log --grep push", False),
        ("echo git pushed", False),
        ("uv run pytest", False),
    ],
)
def test_only_a_git_push_is_checked(command, expected):
    assert hook.mentions_push(command) is expected


def test_a_push_without_dashboard_changes_goes_through(repo):
    _commit(repo, "README.md", "edited")
    assert hook.check(repo, PUSH) is None


def test_dashboard_changes_wait_for_a_republish(repo):
    _commit(repo, "pipelines/dashboard/app.js", "two")

    decision = hook.check(repo, PUSH)

    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert hook.ARTIFACT_URL in decision["hookSpecificOutput"]["permissionDecisionReason"]
    # Commands other than a push are never held up.
    assert hook.check(repo, {"tool_input": {"command": "git status"}}) is None

    hook.record(repo, PUBLISH)
    assert hook.check(repo, PUSH) is None

    # A later change needs another republish.
    _commit(repo, "pipelines/dashboard/app.js", "three")
    assert hook.check(repo, PUSH) is not None


def test_only_a_publish_to_the_dashboard_artifact_counts(repo):
    _commit(repo, "pipelines/dashboard/app.js", "two")
    hook.record(repo, {"tool_input": {"action": "read", "url": hook.ARTIFACT_URL}})
    hook.record(
        repo,
        {
            "tool_input": {"file_path": "x.html"},
            "tool_response": "Published at https://claude.ai/artifact/other",
        },
    )
    assert hook.check(repo, PUSH) is not None


def test_bytecode_doesnt_change_the_fingerprint(repo):
    before = hook.fingerprint(repo)
    cache = repo / "pipelines" / "dashboard" / "__pycache__"
    cache.mkdir()
    (cache / "app.cpython-311.pyc").write_bytes(b"\x00")
    assert hook.fingerprint(repo) == before


def test_the_hook_runs_as_a_script(repo, monkeypatch):
    _commit(repo, "pipelines/dashboard/app.js", "two")
    env = {"CLAUDE_PROJECT_DIR": str(repo), "PATH": "/usr/bin:/bin"}
    out = subprocess.run(
        ["python3", str(HOOK), "check"],
        input=json.dumps(PUSH),
        env=env,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0
    assert json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    subprocess.run(
        ["python3", str(HOOK), "record"], input=json.dumps(PUBLISH), env=env, check=True, text=True
    )
    out = subprocess.run(
        ["python3", str(HOOK), "check"],
        input=json.dumps(PUSH),
        env=env,
        capture_output=True,
        text=True,
    )
    assert out.stdout == ""
