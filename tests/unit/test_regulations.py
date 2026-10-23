from datetime import date

from pipelines import regulations


def test_registry_covers_every_champions_regulation_so_far():
    codes = [r.regulation_code for r in regulations.load_regulations()]
    assert codes[:3] == ["m-a", "m-b", "m-c"]


def test_registry_dates_are_contiguous():
    regs = regulations.load_regulations()
    for earlier, later in zip(regs, regs[1:], strict=False):
        assert earlier.end_date == later.start_date
        assert earlier.start_date < earlier.end_date


def test_current_regulation_picks_the_set_in_force():
    assert regulations.current_regulation(date(2026, 10, 18)).regulation_code == "m-c"
    assert regulations.current_regulation(date(2026, 6, 17)).regulation_code == "m-b"
    assert regulations.current_regulation(date(2026, 4, 8)).regulation_code == "m-a"


def test_current_regulation_falls_back_to_latest_when_registry_lags(tmp_path):
    registry = tmp_path / "regs.csv"
    registry.write_text(
        "regulation_code,regulation_name,munchstats_format,limitless_format,start_date,end_date\n"
        "m-a,A,fa,la,2026-04-08,2026-06-17\n"
        "m-b,B,fb,lb,2026-06-17,2026-09-09\n",
        encoding="utf-8",
    )
    assert regulations.current_regulation(date(2027, 1, 1), path=registry).regulation_code == "m-b"


def test_format_sets_match_the_seed():
    assert "gen9championsvgc2026regmc" in regulations.munchstats_formats()
    assert "m-c" in regulations.limitless_formats()


def test_online_format_labels_come_from_the_seed():
    # docs/upgrade-plan-2027q2.md, S1: Limitless' online platform labels
    # sets "M-C"; nothing in the extractor hardcodes them.
    assert "M-C" in regulations.limitless_play_formats()
    assert all(r.limitless_play_format for r in regulations.load_regulations())


def test_a_registry_without_the_online_column_still_loads(tmp_path):
    registry = tmp_path / "regs.csv"
    registry.write_text(
        "regulation_code,regulation_name,munchstats_format,limitless_format,start_date,end_date\n"
        "m-a,A,fa,la,2026-04-08,2026-06-17\n",
        encoding="utf-8",
    )
    assert regulations.load_regulations(registry)[0].limitless_play_format == ""
    assert regulations.limitless_play_formats(registry) == frozenset()
