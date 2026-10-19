"""backlog.md #46: pipelines/dashboard/static/*.js and the committed
docs/dashboard/*.js are supposed to be byte-identical copies (build.py's
`build()` copies the former into the latter), but nothing enforced that --
editing the wrong one silently produces a published site that disagrees
with its source. This guards against that drift directly, independent of
`build()`, so it also catches someone hand-editing the committed copy.
"""

from pipelines.dashboard import build

SCRIPT_NAMES = ("app.js", "matchup.js", "teams.js", "expansions.js")


def test_committed_dashboard_scripts_match_static_source():
    published_dir = build.REPO_ROOT / "docs" / "dashboard"
    for script_name in SCRIPT_NAMES:
        source_path = build.STATIC_DIR / script_name
        published_path = published_dir / script_name
        assert published_path.exists(), f"{published_path} is missing"
        assert source_path.read_bytes() == published_path.read_bytes(), (
            f"{published_path} has drifted from {source_path} -- rerun "
            "`make dashboard` and commit the result"
        )
