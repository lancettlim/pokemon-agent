import json

import pytest

from pipelines.dashboard import artifact


def _write(path, data=b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_board_keys_takes_every_board_in_either_grouping():
    payload = {
        "kpis_by_scope": {
            "m-c": {
                "top_12_boards": {
                    "all": {
                        "forms": [{"pokemon_key": "kingambit"}],
                        "species": [{"pokemon_key": "floette"}],
                    },
                    "day2": {"forms": [{"pokemon_key": "incineroar"}, {"pokemon_key": ""}]},
                }
            },
            "m-b": {"top_12_boards": {}},
            "all": {},
        }
    }
    assert artifact.board_keys(payload) == {"kingambit", "floette", "incineroar"}
    assert artifact.board_keys({}) == set()


def test_batches_put_data_before_images_and_respect_the_limits(tmp_path, monkeypatch):
    _write(tmp_path / "index.html")
    _write(tmp_path / "app.js")
    _write(tmp_path / "data" / "core.json")
    for name in ("a", "b", "c"):
        _write(tmp_path / "images" / f"{name}.png", b"12345")
    monkeypatch.setattr(artifact, "MAX_BATCH_FILES", 3)

    batches = artifact.publish_batches(tmp_path)

    # The page is published on its own; data and scripts lead.
    assert batches == [
        ["app.js", "data/core.json", "images/a.png"],
        ["images/b.png", "images/c.png"],
    ]

    monkeypatch.setattr(artifact, "MAX_BATCH_BYTES", 10)
    assert [len(b) for b in artifact.publish_batches(tmp_path)] == [3, 2]


def test_the_artifact_site_skips_item_icons_and_limits_hero_art(tmp_path, monkeypatch):
    seen = {}

    def fake_build(**kwargs):
        seen.update(kwargs)
        _write(kwargs["output_dir"] / "index.html")
        return {"kpis_by_scope": {}}

    monkeypatch.setattr(artifact.build, "build", fake_build)

    artifact.build_artifact_site(tmp_path / "site", marts_dir=tmp_path / "marts")

    assert seen["item_icons"] is False
    assert seen["hero_art_keys"] is artifact.board_keys
    assert seen["fetch_icons"] is False
    assert seen["marts_dir"] == tmp_path / "marts"


def test_a_site_over_the_artifact_limit_is_refused(tmp_path, monkeypatch):
    def fake_build(**kwargs):
        for i in range(4):
            _write(kwargs["output_dir"] / f"{i}.js")
        return {}

    monkeypatch.setattr(artifact.build, "build", fake_build)
    monkeypatch.setattr(artifact, "MAX_FILES", 3)

    with pytest.raises(ValueError, match="4 files, over the 3"):
        artifact.build_artifact_site(tmp_path / "site")


def test_the_plan_maps_each_batch_and_names_the_page(tmp_path):
    site = tmp_path / "site"
    _write(site / "index.html")
    _write(site / "app.js")
    _write(site / "images" / "pikachu.png")

    plan = artifact.write_plan(site, tmp_path / "plan.json")

    assert json.loads((tmp_path / "plan.json").read_text(encoding="utf-8")) == plan
    assert plan["artifact_url"] == artifact.ARTIFACT_URL
    assert plan["page"] == str(site / "index.html")
    assert plan["file_count"] == 3
    assert plan["batches"] == [{"app.js": "app.js", "images/pikachu.png": "images/pikachu.png"}]
