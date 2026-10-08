"""`examdata.timetable.parser` / `build` 纯函数单测。

只覆盖不依赖 PDF、网络与数据库的内部工具函数（考季规范化、文本清洗、列序
推断、事件组装、去重、legacy 版式辅助、不可得理由切分等）。PDF 级解析已由
`data/zone5` 离线快照与 `test_api_timetable.py` 的端到端契约覆盖，此处不重复。
"""

from __future__ import annotations

import pytest

from examdata.timetable import parser as P
from examdata.timetable.build import _split_reason

# ---------------------------------------------------------------------------
# 考季与文本小工具
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Jun", "Jun"),
        ("june", "Jun"),
        ("06", "Jun"),
        ("6", "Jun"),
        ("  Jun  ", "Jun"),
        ("Nov", "Nov"),
        ("november", "Nov"),
        ("11", "Nov"),
        ("NOV", "Nov"),
    ],
)
def test_normalize_series(raw, expected):
    assert P.normalize_series(raw) == expected


def test_normalize_series_rejects_unknown():
    with pytest.raises(ValueError):
        P.normalize_series("Dec")


def test_season_key():
    assert P.season_key(2013, "Nov") == "2013-11"
    assert P.season_key(2026, "June") == "2026-06"
    assert P.season_key(2026, "06") == "2026-06"


def test_clean_collapses_whitespace():
    assert P._clean(None) == ""
    assert P._clean("  a\t b\nc ") == "a b c"


def test_cell_bounds_and_clean():
    row = [" 0607/12 ", None, "AM"]
    assert P._cell(row, 0) == "0607/12"
    assert P._cell(row, 1) == ""
    assert P._cell(row, None) == ""
    assert P._cell(row, -1) == ""
    assert P._cell(row, 9) == ""


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("IG.", "IG"),
        ("igcse core", "IG"),
        ("Cambridge IGCSE", "IG"),
        ("O Level", "OL"),
        ("ol", "OL"),
        ("AS", "AS"),
        ("AS Level", "AS"),
        ("A Level", "AL"),
        ("al", "AL"),
        ("Pre-U", "PR"),
        ("pr", "PR"),
        ("", None),
        ("xyz", None),
    ],
)
def test_normalize_level(raw, expected):
    assert P._normalize_level(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("0500", ("0500", None)),
        ("9693/13", ("9693", "13")),
        (" 0607 / 12 ", ("0607", "12")),
        ("AB 0607/12 CD", ("0607", "12")),
        ("9709/13 extra", ("9709", "13")),
        ("", None),
        ("hello", None),
        ("123", None),
    ],
)
def test_split_code(raw, expected):
    assert P._split_code(raw) == expected


def test_code_trailing():
    assert P._code_trailing("0607/12 4") == "4"
    assert P._code_trailing("0607/12") == ""
    assert P._code_trailing("no code") == ""


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1h45m", 105),
        ("2h", 120),
        ("45m", 45),
        ("1 h 30 m", 90),
        ("", None),
        ("abc", None),
    ],
)
def test_duration_minutes(raw, expected):
    assert P._duration_minutes(raw) == expected


def test_parse_day_month():
    assert P._parse_day_month("Tuesday 25 April") == ("Tuesday", 25, 4, None)
    assert P._parse_day_month("Tuesday 25 April 2017") == ("Tuesday", 25, 4, 2017)
    assert P._parse_day_month("Monday 7 Oct") == ("Monday", 7, None, None)
    assert P._parse_day_month("7 – 12 October 2013") is None
    assert P._parse_day_month("noise") is None


def test_is_banner_row():
    assert P._is_banner_row(["Tuesday 25 April 2026"]) == "Tuesday 25 April 2026"
    assert P._is_banner_row([" Tuesday 25 April 2026 ", ""]) == "Tuesday 25 April 2026"
    assert P._is_banner_row(["Tuesday 25 April 2026", "extra"]) is None
    assert P._is_banner_row(["not a date"]) is None


def test_is_header_row():
    assert P._is_header_row(["Level", "Syllabus/Component", "Code"]) is True
    assert P._is_header_row(["Code", "Duration"]) is True
    assert P._is_header_row(["IG", "English", "0500/12"]) is False
    assert P._is_header_row([]) is False
    assert P._is_header_row([None, ""]) is False


def test_merge_banner():
    previous = ("Tuesday", 25, 4, 2026)
    assert P._merge_banner(previous, None) == previous
    assert P._merge_banner(None, ("Monday", 7, None, None)) == ("Monday", 7, None, None)
    assert P._merge_banner(previous, ("Monday", 7, None, None)) == ("Monday", 7, 4, None)
    assert P._merge_banner(previous, ("Monday", 7, 5, None)) == ("Monday", 7, 5, None)


# ---------------------------------------------------------------------------
# 年份归属与事件组装
# ---------------------------------------------------------------------------


def test_event_year():
    assert P._event_year(2026, "Jun", 5, None) == (2026, None)
    assert P._event_year(2026, "Nov", 11, None) == (2026, None)
    year, note = P._event_year(2026, "Jun", 10, None)
    assert year == 2026
    assert note and "10" in note
    assert P._event_year(2026, "Jun", 1, 2027) == (2027, None)


def test_make_event_basic():
    event = P._make_event(
        year=2026,
        series="Jun",
        banner=("Tuesday", 5, 5, None),
        level="IG",
        subject_code="0500",
        paper_code="12",
        subject_title="English",
        duration_raw="1h30m",
        session="AM",
        raw="IG | English | 0500/12 | 1h30m | AM",
    )
    assert event["date"] == "2026-05-05"
    assert event["weekday"] == "Tuesday"
    assert event["session"] == "AM"
    assert event["level"] == "IG"
    assert event["subject_code"] == "0500"
    assert event["paper_code"] == "12"
    assert event["duration_raw"] == "1h30m"
    assert event["duration_minutes"] == 90
    assert "date_note" not in event


def test_make_event_out_of_range_month_gets_note():
    event = P._make_event(
        year=2026,
        series="Jun",
        banner=("Monday", 5, 10, None),
        level=None,
        subject_code="9709",
        paper_code="13",
        subject_title="Mathematics",
        duration_raw="",
        session="PM",
        raw="",
    )
    assert event["date"] == "2026-10-05"
    assert event["duration_raw"] is None
    assert event["duration_minutes"] is None
    assert "date_note" in event


def test_make_event_month_year_wins():
    event = P._make_event(
        year=2026,
        series="Jun",
        banner=("Monday", 5, 1, 2027),
        level="AL",
        subject_code="9709",
        paper_code="13",
        subject_title="Mathematics",
        duration_raw="2h",
        session="AM",
        raw="",
    )
    assert event["date"] == "2027-01-05"
    assert "date_note" not in event


# ---------------------------------------------------------------------------
# 列序推断
# ---------------------------------------------------------------------------


def test_default_groups_known_column_counts():
    assert P._default_groups(5) == [
        {"level_col": 0, "name_col": 1, "code_col": 2, "duration_col": 3, "session_col": 4}
    ]
    assert P._default_groups(10) == [
        {"level_col": 0, "name_col": 1, "code_col": 2, "duration_col": 3, "session_col": 4},
        {"level_col": 5, "name_col": 6, "code_col": 7, "duration_col": 8, "session_col": 9},
    ]
    assert P._default_groups(11) == [
        {"level_col": 0, "name_col": 1, "code_col": 2, "duration_col": 3, "session_col": 4},
        {"level_col": 6, "name_col": 7, "code_col": 8, "duration_col": 9, "session_col": 10},
    ]
    assert P._default_groups(7) == []


def test_default_groups_four_columns_without_level():
    # 4 列表格没有等级列，列序须与 `_weekly_groups` 对 4 列表头的结果一致。
    assert P._default_groups(4) == [
        {"level_col": None, "name_col": 0, "code_col": 1, "duration_col": 2, "session_col": 3}
    ]


def test_header_kind():
    assert P._header_kind([["Syllabus name", "Code", "Test date window"]]) == "windows"
    assert P._header_kind([["Syllabus/Component", "Code", "Duration", "Date"]]) == "syllabus"
    assert (
        P._header_kind([["Level", "Syllabus/Component", "Code", "Duration", "Session"]])
        == "weekly"
    )
    assert P._header_kind([["foo", "bar"]]) is None


def test_weekly_groups_single_half():
    rows = [["Level", "Syllabus/Component", "Code", "Duration", "Session"]]
    assert P._weekly_groups(rows) == [
        {"level_col": 0, "name_col": 1, "code_col": 2, "duration_col": 3, "session_col": 4}
    ]


def test_weekly_groups_two_halves():
    rows = [
        [
            "Level",
            "Syllabus/Component",
            "Code",
            "Duration",
            "Session",
            "",
            "Level",
            "Syllabus/Component",
            "Code",
            "Duration",
            "Session",
        ]
    ]
    assert P._weekly_groups(rows) == [
        {"level_col": 0, "name_col": 1, "code_col": 2, "duration_col": 3, "session_col": 4},
        {"level_col": 6, "name_col": 7, "code_col": 8, "duration_col": 9, "session_col": 10},
    ]


def test_weekly_groups_skips_syllabus_view():
    rows = [["Syllabus/Component", "Code", "Duration", "Date"]]
    assert P._weekly_groups(rows) == []


def test_weekly_groups_no_header():
    assert P._weekly_groups([["IG", "English", "0500/12", "1h30m", "AM"]]) == []


# ---------------------------------------------------------------------------
# 事件抽取与去重
# ---------------------------------------------------------------------------


def _event_stub(**overrides):
    event = {
        "date": "2026-05-05",
        "session": "AM",
        "level": "IG",
        "subject_code": "0500",
        "paper_code": "12",
        "subject_title": "English",
    }
    event.update(overrides)
    return event


def test_dedupe_events_removes_identical_signatures():
    events = [_event_stub(), _event_stub(raw="dup"), _event_stub(subject_title="Maths")]
    deduped, removed = P._dedupe_events(events)
    assert removed == 1
    assert [event["subject_title"] for event in deduped] == ["English", "Maths"]


def test_dedupe_events_keeps_distinct_sessions():
    deduped, removed = P._dedupe_events([_event_stub(), _event_stub(session="PM")])
    assert removed == 0
    assert len(deduped) == 2


def test_extract_windows_rows_parses_date_window():
    rows = [
        ["Syllabus name", "Code", "Test date window"],
        ["English", "0500/12", "12/3/2026 – 20/3/2026"],
        ["", "", ""],
    ]
    unparsed: list = []
    windows = P._extract_windows_rows(rows, level="IG", unparsed=unparsed)
    assert unparsed == []
    assert len(windows) == 1
    window = windows[0]
    assert window["syllabus_name"] == "English"
    assert window["syllabus_code"] == "0500"
    assert window["component_code"] == "12"
    assert window["level"] == "IG"
    assert window["window_start"] == "2026-03-12"
    assert window["window_end"] == "2026-03-20"


def test_extract_windows_rows_flags_bad_rows():
    rows = [
        ["Syllabus name", "Code", "Test date window"],
        ["No code", "???", "12/3/2026 – 20/3/2026"],
        ["No window", "9701/12", ""],
    ]
    unparsed: list = []
    windows = P._extract_windows_rows(rows, level=None, unparsed=unparsed)
    assert windows == []
    assert len(unparsed) == 2


def test_extract_weekly_rows_parses_and_merges_continuation():
    rows = [
        ["Tuesday 25 April 2026"],
        ["Level", "Syllabus/Component", "Code", "Duration", "Session"],
        ["IG", "English", "0500/12", "1h30m", "AM"],
        ["IG", "Language and Literature", "", "", ""],
    ]
    groups = P._weekly_groups(rows)
    assert groups
    unparsed: list = []
    events, banner = P._extract_weekly_rows(
        rows, groups=groups, initial_banner=None, year=2026, series="Jun", unparsed=unparsed
    )
    assert unparsed == []
    assert banner == ("Tuesday", 25, 4, 2026)
    assert len(events) == 1
    event = events[0]
    assert event["date"] == "2026-04-25"
    assert event["session"] == "AM"
    assert event["level"] == "IG"
    assert event["subject_code"] == "0500"
    assert event["paper_code"] == "12"
    assert event["subject_title"] == "English Language and Literature"
    assert event["duration_minutes"] == 90


def test_extract_weekly_rows_missing_banner_flags_row():
    rows = [["IG", "English", "0500/12", "1h30m", "AM"]]
    groups = P._default_groups(5)
    unparsed: list = []
    events, banner = P._extract_weekly_rows(
        rows, groups=groups, initial_banner=None, year=2026, series="Jun", unparsed=unparsed
    )
    assert events == []
    assert banner is None
    assert len(unparsed) == 1
    assert "缺少日期横幅" in unparsed[0]["reason"]


def test_extract_weekly_rows_invalid_session_flags_row():
    rows = [
        ["Tuesday 25 April 2026"],
        ["IG", "English", "0500/12", "1h30m", "XX"],
    ]
    groups = P._default_groups(5)
    unparsed: list = []
    events, _ = P._extract_weekly_rows(
        rows, groups=groups, initial_banner=None, year=2026, series="Jun", unparsed=unparsed
    )
    assert events == []
    assert len(unparsed) == 1
    assert "时段列" in unparsed[0]["reason"]


def test_extract_weekly_rows_invalid_code_flags_row():
    rows = [
        ["Tuesday 25 April 2026"],
        ["IG", "English", "ABC", "1h30m", "AM"],
    ]
    groups = P._default_groups(5)
    unparsed: list = []
    events, _ = P._extract_weekly_rows(
        rows, groups=groups, initial_banner=None, year=2026, series="Jun", unparsed=unparsed
    )
    assert events == []
    assert len(unparsed) == 1
    assert "代码列" in unparsed[0]["reason"]


def test_extract_weekly_rows_rejoins_split_duration():
    rows = [
        ["Tuesday 25 April 2026"],
        ["IG", "English", "0607/12 4", "5m", "AM"],
    ]
    groups = P._default_groups(5)
    unparsed: list = []
    events, _ = P._extract_weekly_rows(
        rows, groups=groups, initial_banner=None, year=2026, series="Jun", unparsed=unparsed
    )
    assert unparsed == []
    assert events[0]["paper_code"] == "12"
    assert events[0]["duration_raw"] == "45m"
    assert events[0]["duration_minutes"] == 45


def test_extract_weekly_rows_four_columns_via_default_groups():
    rows = [
        ["Tuesday 25 April 2026"],
        ["English", "0500/12", "1h30m", "AM"],
    ]
    groups = P._default_groups(4)
    unparsed: list = []
    events, _ = P._extract_weekly_rows(
        rows, groups=groups, initial_banner=None, year=2026, series="Jun", unparsed=unparsed
    )
    assert unparsed == []
    assert len(events) == 1
    assert events[0]["level"] is None
    assert events[0]["subject_code"] == "0500"
    assert events[0]["subject_title"] == "English"


def test_row_text_and_count_code_cells():
    assert P._row_text(["A", None, " B "]) == "A | B"
    rows = [
        ["Syllabus/Component", "Code"],
        ["Maths", "9709/13"],
        ["", "0607/12"],
    ]
    assert P._count_code_cells(rows) == 2


# ---------------------------------------------------------------------------
# Legacy 版式辅助
# ---------------------------------------------------------------------------


def test_legacy_clean():
    assert P._legacy_clean(None) == ""
    assert P._legacy_clean("\uf020Hello\uf020\uf020World") == "Hello World"
    assert P._legacy_clean("a\n  b") == "a b"


def test_median():
    assert P._median([3, 1, 2]) == 2
    assert P._median([5.0]) == 5.0


def test_legacy_cluster_ys():
    assert P._legacy_cluster_ys([10.0, 11.5, 20.0, 20.4]) == [10.0, 20.0]


def test_legacy_group_rows():
    spans = [(10.0, 5.0, "A"), (11.0, 1.0, "B"), (30.0, 0.0, "C")]
    assert P._legacy_group_rows(spans) == [
        (10.0, [(1.0, "B"), (5.0, "A")]),
        (30.0, [(0.0, "C")]),
    ]


def test_legacy_strip_comp_tail():
    assert P._legacy_strip_comp_tail("Travel and Tourism 13", "13") == "Travel and Tourism"
    assert P._legacy_strip_comp_tail("Travel and Tourism 13", "12") is None
    assert P._legacy_strip_comp_tail("Mathematics", "12") is None


def test_legacy_is_noise():
    assert P._legacy_is_noise("FINAL") is True
    assert P._legacy_is_noise("Morning session") is True
    assert P._legacy_is_noise("7 – 12 October 2013") is True
    assert P._legacy_is_noise("IGCSE") is True
    assert P._legacy_is_noise("9709/13") is False
    assert P._legacy_is_noise("Mathematics") is False


def test_legacy_parse_label():
    assert P._legacy_parse_label("Tuesday 25 April") == ("Tuesday", 25, 4)
    assert P._legacy_parse_label("Tues 2 June 2026") == ("Tuesday", 2, 6)
    assert P._legacy_parse_label("Mon") == ("Monday", None, None)
    assert P._legacy_parse_label("9 June") == (None, 9, 6)
    assert P._legacy_parse_label("Hello") is None


def test_legacy_detect_columns_full_header():
    spans = [
        (100.0, 50.0, 120.0, "Syllabus/Component"),
        (100.0, 150.0, 200.0, "Code"),
        (100.0, 250.0, 300.0, "Duration"),
        (100.0, 350.0, 420.0, "Syllabus/Component"),
        (100.0, 450.0, 500.0, "Code"),
        (100.0, 550.0, 600.0, "Duration"),
    ]
    assert P._legacy_detect_columns(spans, [100.0]) == {
        "cols_L": (50.0, 150.0, 250.0),
        "cols_R": (350.0, 450.0, 550.0),
    }


def test_legacy_detect_columns_derives_missing_right_columns():
    spans = [
        (100.0, 50.0, 120.0, "Syllabus/Component"),
        (100.0, 150.0, 200.0, "Code"),
        (100.0, 250.0, 300.0, "Duration"),
        (100.0, 350.0, 420.0, "Syllabus/Component"),
    ]
    assert P._legacy_detect_columns(spans, [100.0]) == {
        "cols_L": (50.0, 150.0, 250.0),
        "cols_R": (350.0, 450.0, 550.0),
    }


def test_legacy_detect_columns_reports_missing():
    spans = [
        (100.0, 50.0, 120.0, "Syllabus/Component"),
        (100.0, 350.0, 420.0, "Syllabus/Component"),
    ]
    result = P._legacy_detect_columns(spans, [100.0])
    assert result is not None and "error" in result


def test_legacy_detect_columns_needs_two_syllabus_columns():
    spans = [(100.0, 50.0, 120.0, "Syllabus/Component")]
    assert P._legacy_detect_columns(spans, [100.0]) is None


def test_section_levels_and_level_above():
    lines = [
        (10.0, "Cambridge IGCSE"),
        (100.0, "Cambridge International AS Level"),
        (200.0, "Cambridge O Level"),
    ]
    sections = P._section_levels(lines)
    assert sections == [(10.0, "IG"), (100.0, "AS"), (200.0, "OL")]
    assert P._level_above(sections, 150.0) == "AS"
    assert P._level_above(sections, 50.0) == "IG"
    assert P._level_above(sections, 5.0) is None


def test_banner_above():
    lines = [(100.0, "Tuesday 25 April 2026"), (200.0, "Monday 1 June 2026")]
    assert P._banner_above(lines, 130.0) == ("Tuesday", 25, 4, 2026)
    assert P._banner_above(lines, 90.0) == ("Tuesday", 25, 4, 2026)
    assert P._banner_above(lines, 300.0) is None


def test_is_legacy_weekly_page():
    assert P._is_legacy_weekly_page("Morning session\nSyllabus/Component") is True
    assert P._is_legacy_weekly_page("Syllabus/Component") is False
    assert P._is_legacy_weekly_page("Morning session") is False


# ---------------------------------------------------------------------------
# build 辅助与文件枚举
# ---------------------------------------------------------------------------


def test_split_reason_short_head_falls_back_to_full_text():
    raw = "该季文件（2019-06）无法取回"
    assert _split_reason(raw) == (raw, raw)


def test_split_reason_splits_on_comma_when_head_is_long_enough():
    raw = "穷尽检索未发现该季任何可用快照，见 §4"
    reason, evidence = _split_reason(raw)
    assert reason == "穷尽检索未发现该季任何可用快照"
    assert evidence == raw


def test_split_reason_handles_ascii_parenthesis():
    raw = "No snapshot found (checked all mirrors)"
    reason, evidence = _split_reason(raw)
    assert reason == "No snapshot found"
    assert evidence == raw


def test_iter_seasons_filters_and_sorts(tmp_path):
    (tmp_path / "2026-06.pdf").write_bytes(b"x")
    (tmp_path / "2026-11.pdf").write_bytes(b"x")
    (tmp_path / "2025-06.pdf").write_bytes(b"x")
    (tmp_path / "random.pdf").write_bytes(b"x")
    (tmp_path / "2026-06.txt").write_bytes(b"x")
    got = [(path.name, year, series) for path, year, series in P.iter_seasons(tmp_path)]
    assert got == [
        ("2025-06.pdf", 2025, "Jun"),
        ("2026-06.pdf", 2026, "Jun"),
        ("2026-11.pdf", 2026, "Nov"),
    ]
