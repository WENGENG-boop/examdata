"""Edexcel（Pearson）考试时间表 PDF 解析。

输入是从 Pearson 官网（或 Wayback 存档）下载的各考季时间表 PDF，分四个系列：
`gcse` / `intgcse` / `ial` / `gce`，每季一个文件（R 卷单独文件，文件名后缀 `-r`）。

版式按“表头签名”识别，每个文件可能混用多种版式：

- modern：`Date | Examination code | Subject | Title | Time | Duration`。
  日期与时段是纵向合并单元格（合并区首行文本重复 N 次、其余行 None），
  解析时向前填充并跨表跨页 carry；R 卷文件名与普通卷同构。
- modern_notime：同上但无 Time 列（2021 年两季的特殊文件），session 为 None。
- old grid：`Date | Morning | Length | Afternoon | Length`。单元格内 `\\n` 分隔
  多条条目（可跨行续行），代码后有 `\\x07` 残留字符；时长按位置对齐；
  日期单元格带 "(Window)" 的行只产出 date_windows。
- window：`Date | Unit | Length`（含 `Date |  | Length` 与 `Date | Unit` 两列变体）。
  日期单元格含多个 `(Window)` 短语，与单元条目配对：数量相等按位置、
  1↔N 全共享、其余用单元格内词坐标按 y 对齐，几何失败退回首个窗口并记 unparsed。
- master：非旋转的 `Date | Exam series | Board | Qual | Examination code | Subject |
  Title | Time | Duration` 总表（intgcse/2022-01 起）。
- rotated master：整本页面旋转 90° 的文件，先 `set_rotation(0)` 再取表，
  得到 9 行转置表（行=字段、列=记录）；字段名在 col0 的表跳过首列，
  续表的字段行序固定（duration/time/title/subject/code/qual/board/series/date）。

其余含代码的表是“摘要/缩略”重复页（旋转文件的 p2–p3 等）：其代码被已解析的
事件或窗口覆盖时静默跳过（condensed），否则记入 unclassified_samples。

事件（events）与日期窗口（date_windows）分离：窗口表与 old grid 的 "(Window)"
行只产出 date_windows。重复事件按（日期、时段、科目代码、卷号、名称、时长）去重。
无法确信归属的行写入 `unparsed_rows`（每季最多 50 条），不猜测、不丢弃。
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path
from typing import Any, Iterator, Sequence

import pymupdf

# 每季 unparsed_rows 上限，避免异常文件把 JSON 撑爆。
MAX_UNPARSED_PER_SEASON = 50

FAMILIES = ("gcse", "intgcse", "ial", "gce")

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# 各考季（文件名月份）的常规考试日期范围，用于无显式年份时的推断与 date_note。
_SEASON_MONTHS = {1: (1, 2), 6: (4, 7), 10: (10, 11), 11: (10, 12)}

_MONTH_NAME = "(January|February|March|April|May|June|July|August|September|October|November|December)"
_WEEKDAY_NAME = "(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"

_BANNER_RE = re.compile(
    rf"{_WEEKDAY_NAME}\s+(\d{{1,2}})\s+{_MONTH_NAME}(?:\s+(\d{{4}}))?",
    re.IGNORECASE,
)
_BANNER_PLAIN_RE = re.compile(
    rf"(?<!\d)(\d{{1,2}})\s+{_MONTH_NAME}(?:\s+(\d{{4}}))?",
    re.IGNORECASE,
)
_RANGE_FULL_RE = re.compile(
    rf"(\d{{1,2}})\s+{_MONTH_NAME}(?:\s+(\d{{4}}))?\s*[–—-]\s*"
    rf"(?:{_WEEKDAY_NAME}\s+)?(\d{{1,2}})\s+{_MONTH_NAME}(?:\s+(\d{{4}}))?",
    re.IGNORECASE,
)
_RANGE_SHORT_RE = re.compile(
    rf"(\d{{1,2}})\s*[–—-]\s*(\d{{1,2}})\s+{_MONTH_NAME}(?:\s+(\d{{4}}))?",
    re.IGNORECASE,
)
_SINGLE_DATE_RE = re.compile(
    rf"(\d{{1,2}})\s+{_MONTH_NAME}(?:\s+(\d{{4}}))?",
    re.IGNORECASE,
)
_WINDOW_MARK_RE = re.compile(r"\(Window[^)]*\)", re.IGNORECASE)

_DURATION_RE = re.compile(r"(\d+)\s*h(?:\s*(\d+)\s*m)?", re.IGNORECASE)

# 整格代码："4MA1 1F" / "9HI0 1A-1H" / "1HIA B1-B4" / "WIT03 01" / "5RS01"。
_CODE_CELL_RE = re.compile(r"^([0-9A-Z]{4,6})(?:\s+([0-9A-Z][0-9A-Z]{0,2}(?:-[0-9A-Za-z]{1,3})?))?$")
# 条目行首代码："6957 \x07Information..." / "4IT0 02 ..."。
_ENTRY_CODE_RE = re.compile(r"^([0-9A-Z]{4,6})(?=[\s\x07]|$)")
# 条目代码之后的卷号："01 Applied ICT ..." / "1A-1H History ..."。
_PAPER_RE = re.compile(r"^([0-9][0-9A-Z]{0,2}(?:-[0-9A-Za-z]{1,3})?)\s+(.*)$")

_ROT_DATE_RE = re.compile(r"^(\d{2})-(\d{2})-(\d{2})$")
_MASTER_DATE_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")

# 摘要页出现的单个科目代码（4-6 位、至少含一个数字；19xx/20xx 年份样另行排除）。
_SUMMARY_CODE_RE = re.compile(r"\b(?=[0-9A-Z]*[0-9])([0-9][0-9A-Z]{3,5}|[A-Z][0-9A-Z]{3,5})\b")
_YEAR_LIKE_RE = re.compile(r"(19|20)\d{2}")

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

_SESSION_WORDS = {"morning": "AM", "afternoon": "PM", "evening": "EV", "window": "WINDOW"}

_MODERN_HDR = ["date", "examination code", "subject", "title", "time", "duration"]
_MODERN_NOTIME_HDR = ["date", "examination code", "subject", "title", "duration"]
_OLD_GRID_HDRS = (
    ["date", "morning", "length", "afternoon", "length"],
    ["date", "morning session", "length", "afternoon session", "length"],
)
_WINDOW_HDRS = (
    ["date", "unit", "length"],
    ["date", "", "length"],
    ["date", "unit"],
)
_MASTER_HDR = [
    "date",
    "exam series",
    "board",
    "qual",
    "examination code",
    "subject",
    "title",
    "time",
    "duration",
]

_ROT_FIELDS = (
    "Exam duration",
    "Exam time",
    "Title",
    "Subject",
    "Examination code",
    "Qual",
    "Board",
    "Exam series",
    "Exam date",
)
_ROT_FIELD_LOOKUP = {name.lower(): name for name in _ROT_FIELDS}
_ROT_REQUIRED = ("Exam duration", "Exam time", "Title", "Subject", "Examination code", "Exam date")

Banner = tuple[str | None, int, int, int | None]


# --------------------------------------------------------------------------
# 文本小工具
# --------------------------------------------------------------------------


def _clean(text: Any) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", _CONTROL_RE.sub(" ", str(text))).strip()


def _first_line(text: Any) -> str:
    if text is None:
        return ""
    return _clean(str(text).split("\n", 1)[0])


def _raw_cell(row: Sequence[Any], index: int) -> Any:
    return row[index] if 0 <= index < len(row) else None


def _cell(row: Sequence[Any], index: int | None) -> str:
    if index is None:
        return ""
    return _clean(_raw_cell(row, index))


def _row_text(row: Sequence[Any]) -> str:
    return " | ".join(_clean(c) for c in row if _clean(c))[:400]


def _header(row: Sequence[Any]) -> list[str]:
    values = [_clean(c).lower() for c in row]
    while values and not values[-1]:
        values.pop()
    return values


def _duration_minutes(text: Any) -> int | None:
    match = _DURATION_RE.search(_clean(text))
    if not match:
        return None
    minutes = int(match.group(1)) * 60
    if match.group(2):
        minutes += int(match.group(2))
    return minutes


def _combo_title(subject: str, title: str) -> str:
    """科目与标题合成展示名；标题已含科目时不再重复前缀。"""
    subject, title = _clean(subject), _clean(title)
    if not title:
        return subject
    if subject and title.lower().startswith(subject.lower()):
        return title
    return f"{subject} {title}".strip()


def _normalize_session(text: str) -> str | None:
    cleaned = _clean(text).lower().rstrip(".")
    if not cleaned:
        return None
    if cleaned in _SESSION_WORDS:
        return _SESSION_WORDS[cleaned]
    first = cleaned.split()[0]
    if first in _SESSION_WORDS:
        return _SESSION_WORDS[first]
    return None


def _split_code(text: str) -> tuple[str, str | None] | None:
    """整格代码："4MA1 1F" → ("4MA1", "1F")；只有科目代码时 paper 为 None。"""
    normalized = _clean(_clean(text).replace("_", " "))
    match = _CODE_CELL_RE.match(normalized)
    if not match:
        return None
    return match.group(1), match.group(2)


def _entry_code(text: str) -> str | None:
    match = _ENTRY_CODE_RE.match(text)
    if match and any(ch.isdigit() for ch in match.group(1)):
        return match.group(1)
    return None


def _split_entry(entry: str) -> tuple[str, str | None, str] | None:
    match = _ENTRY_CODE_RE.match(entry)
    if not match or not any(ch.isdigit() for ch in match.group(1)):
        return None
    code = match.group(1)
    rest = entry[match.end():].strip()
    paper_match = _PAPER_RE.match(rest)
    if paper_match:
        return code, paper_match.group(1), paper_match.group(2).strip()
    return code, None, rest


def _split_entries(cell: Any) -> list[str]:
    """单元格内按行切条目；行首有代码的行开启新条目，无代码行并入上一条（跨行续行）；单元格开头的无代码行单独成条，便于上层记录。"""
    entries: list[str] = []
    for line in str(cell or "").split("\n"):
        cleaned = _clean(line)
        if not cleaned:
            continue
        if _entry_code(cleaned) or not entries:
            entries.append(cleaned)
        else:
            entries[-1] = f"{entries[-1]} {cleaned}"
    return entries


def _split_lengths(cell: Any) -> list[str | None]:
    """时长单元格按行切分：保留中间空项，仅去掉尾部空项。"""
    values: list[str | None] = [_clean(line) or None for line in str(cell or "").split("\n")]
    while values and values[-1] is None:
        values.pop()
    return values


def _align_lengths(
    entries: Sequence[str],
    lengths: Sequence[str | None],
    unparsed: list[dict[str, Any]],
    row_text: str,
    page_no: int,
) -> list[str | None]:
    if not lengths:
        return [None] * len(entries)
    if len(lengths) == len(entries):
        return list(lengths)
    unparsed.append(
        {
            "page": page_no,
            "row": row_text,
            "reason": f"时长 {len(lengths)} 项与考试条目 {len(entries)} 项数量不一致，时长整体置空",
        }
    )
    return [None] * len(entries)


# --------------------------------------------------------------------------
# 日期与窗口
# --------------------------------------------------------------------------


def _parse_banner(text: str) -> Banner | None:
    match = _BANNER_RE.search(text)
    if match:
        weekday = match.group(1).capitalize()
        day = int(match.group(2))
        month_number = _MONTHS[match.group(3).lower()]
        explicit = int(match.group(4)) if match.group(4) else None
        return weekday, day, month_number, explicit
    match = _BANNER_PLAIN_RE.search(text)
    if match:
        day = int(match.group(1))
        month_number = _MONTHS[match.group(2).lower()]
        explicit = int(match.group(3)) if match.group(3) else None
        return None, day, month_number, explicit
    return None


def _event_year(
    year: int, season_month: int, month: int, explicit: int | None
) -> tuple[int, str | None]:
    if explicit:
        return int(explicit), None
    if month >= 9 and season_month <= 6:
        return year - 1, None
    low, high = _SEASON_MONTHS.get(season_month, (month, month))
    if low <= month <= high:
        return year, None
    return year, (
        f"日期月份 {month} 不在 {season_month:02d} 考季常规范围（{low}–{high} 月），年份按考季年 {year} 记录"
    )


def _window_year(year: int, season_month: int, month: int) -> int:
    if season_month <= 2 and month >= 9:
        return year - 1
    return year


def _window_phrases(text: str) -> list[str]:
    """从含 `(Window)` 标记的文本里切出窗口短语列表。

    每个短语从上一标记之后开始、到本标记结束；短语内若含多个日期区间，
    取最后一个区间作为短语起点，修剪掉前面的标题/星期前缀。
    """
    cleaned = _clean(text)
    phrases: list[str] = []
    previous_end = 0
    for mark in _WINDOW_MARK_RE.finditer(cleaned):
        segment = cleaned[previous_end:mark.end()].strip(" |")
        previous_end = mark.end()
        if not segment or not re.search(r"\d", segment):
            continue
        best_start = None
        for regex in (_RANGE_FULL_RE, _RANGE_SHORT_RE):
            for match in regex.finditer(segment):
                if best_start is None or match.start() > best_start:
                    best_start = match.start()
        if best_start is not None:
            segment = segment[best_start:]
        phrases.append(segment)
    return phrases


def _window_range(phrase: str, season_year: int, season_month: int) -> tuple[str | None, str | None]:
    """把窗口短语解析成 (window_start, window_end) ISO 日期；无法解析时为 (None, None)。"""
    text = _clean(phrase)
    full = _RANGE_FULL_RE.search(text)
    if full:
        start_day = int(full.group(1))
        start_month = _MONTHS[full.group(2).lower()]
        start_year = int(full.group(3)) if full.group(3) else None
        end_day = int(full.group(5))
        end_month = _MONTHS[full.group(6).lower()]
        end_year = int(full.group(7)) if full.group(7) else None
    else:
        short = _RANGE_SHORT_RE.search(text)
        if short:
            start_day = int(short.group(1))
            end_day = int(short.group(2))
            start_month = _MONTHS[short.group(3).lower()]
            end_month = start_month
            start_year = int(short.group(4)) if short.group(4) else None
            end_year = None
        else:
            single = _SINGLE_DATE_RE.search(text)
            if not single:
                return None, None
            start_day = end_day = int(single.group(1))
            start_month = end_month = _MONTHS[single.group(2).lower()]
            start_year = int(single.group(3)) if single.group(3) else None
            end_year = None
    resolved_start = start_year if start_year else _window_year(season_year, season_month, start_month)
    resolved_end = end_year if end_year else (resolved_start + 1 if end_month < start_month else resolved_start)
    try:
        return (
            date(resolved_start, start_month, start_day).isoformat(),
            date(resolved_end, end_month, end_day).isoformat(),
        )
    except ValueError:
        return None, None


# --------------------------------------------------------------------------
# 事件构造
# --------------------------------------------------------------------------


def _make_event(
    *,
    year: int,
    season_month: int,
    banner: Banner,
    subject_code: str,
    paper_code: str | None,
    subject_title: str,
    duration_raw: str | None,
    session: str | None,
    session_raw: str | None,
    raw: str,
) -> dict[str, Any] | None:
    weekday, day, month, explicit = banner
    event_year, date_note = _event_year(year, season_month, month, explicit)
    try:
        event_date = date(event_year, month, day)
    except ValueError:
        return None
    event: dict[str, Any] = {
        "date": event_date.isoformat(),
        "weekday": weekday or _WEEKDAYS[event_date.weekday()],
        "session": session,
        "subject_code": subject_code,
        "paper_code": paper_code,
        "subject_title": subject_title,
        "duration_raw": duration_raw or None,
        "duration_minutes": _duration_minutes(duration_raw),
        "raw": raw,
    }
    if session_raw and session_raw != session:
        event["session_raw"] = session_raw
    if date_note:
        event["date_note"] = date_note
    return event


def _dedupe_events(events: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: set[tuple[Any, ...]] = set()
    kept: list[dict[str, Any]] = []
    duplicates = 0
    for event in events:
        signature = (
            event["date"],
            event["session"],
            event["subject_code"],
            event["paper_code"],
            event["subject_title"],
            event["duration_raw"],
        )
        if signature in seen:
            duplicates += 1
            continue
        seen.add(signature)
        kept.append(event)
    return kept, duplicates


def _dedupe_windows(windows: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: set[tuple[Any, ...]] = set()
    kept: list[dict[str, Any]] = []
    duplicates = 0
    for window in windows:
        signature = (window["window_raw"], window["subject_code"], window["paper_code"])
        if signature in seen:
            duplicates += 1
            continue
        seen.add(signature)
        kept.append(window)
    return kept, duplicates


# --------------------------------------------------------------------------
# 版式识别
# --------------------------------------------------------------------------


def _is_rotated(rows: Sequence[Sequence[Any]]) -> bool:
    if len(rows) != 9:
        return False
    col0 = [_clean(row[0]) if row else "" for row in rows]
    hits = sum(1 for value in col0 if value in _ROT_FIELD_LOOKUP.values())
    if hits >= 6:
        return True
    values = [_clean(c) for c in rows[8]]
    values = [value for value in values if value]
    return len(values) >= 2 and all(_ROT_DATE_RE.match(value) for value in values)


def _classify(rows: Sequence[Sequence[Any]]) -> str:
    if not rows or not rows[0]:
        return "unknown"
    hdr = _header(rows[0])
    if not hdr:
        return "unknown"
    if hdr[0] in ("subject", "a subject"):
        return "index"
    if hdr == _MODERN_HDR:
        return "modern"
    if hdr == _MODERN_NOTIME_HDR:
        return "modern_notime"
    if hdr in _OLD_GRID_HDRS:
        return "old_grid"
    if hdr in _WINDOW_HDRS:
        return "window"
    if hdr == _MASTER_HDR:
        return "master"
    if len(rows) == 9 and _is_rotated(rows):
        return "rotated"
    return "unknown"


def _table_codes(rows: Sequence[Sequence[Any]]) -> set[str]:
    """摘要页里出现的科目代码集合，用于判断是否只是重复印刷。"""
    codes: set[str] = set()
    for row in rows:
        for cell in row:
            text = _clean(cell)
            if not text:
                continue
            for token in _SUMMARY_CODE_RE.findall(text):
                if _YEAR_LIKE_RE.fullmatch(token):
                    continue
                codes.add(token)
    return codes


# --------------------------------------------------------------------------
# 窗口几何对齐
# --------------------------------------------------------------------------


def _cell_lines(page: pymupdf.Page, bbox: Sequence[float] | None) -> list[tuple[int, str]]:
    """单元格 bbox 内按视觉行分组的 (y, 文本)，用于窗口/单元对齐。"""
    if not bbox:
        return []
    rect = pymupdf.Rect(bbox)
    words = page.get_text("words", clip=rect)
    buckets: dict[int, list[tuple[float, str]]] = {}
    for word in words:
        y = round(word[1])
        buckets.setdefault(y, []).append((word[0], word[4]))
    return [(y, " ".join(text for _, text in sorted(buckets[y]))) for y in sorted(buckets)]


def _map_windows(
    page: pymupdf.Page,
    date_bbox: Sequence[float] | None,
    unit_bbox: Sequence[float] | None,
    window_count: int,
    unit_count: int,
) -> list[int] | None:
    """每个单元对应的窗口下标；数量相等按位置、单窗口全共享，其余按 y 几何对齐。"""
    if window_count == unit_count:
        return list(range(window_count))
    if window_count == 1:
        return [0] * unit_count
    try:
        window_ys = [
            y
            for y, text in _cell_lines(page, date_bbox)
            if "(window" not in text.lower() and re.search(r"\d", text)
        ]
        unit_ys = [y for y, text in _cell_lines(page, unit_bbox) if _entry_code(text)]
    except Exception:
        return None
    if len(window_ys) != window_count or len(unit_ys) != unit_count:
        return None
    mapping: list[int] = []
    for unit_y in unit_ys:
        index = 0
        for window_index, window_y in enumerate(window_ys):
            if window_y <= unit_y + 3:
                index = window_index
        mapping.append(index)
    return mapping


# --------------------------------------------------------------------------
# 各版式解析
# --------------------------------------------------------------------------


def _parse_modern(
    rows: Sequence[Sequence[Any]],
    *,
    year: int,
    month: int,
    page_no: int,
    unparsed: list[dict[str, Any]],
    events: list[dict[str, Any]],
    state: dict[str, Any],
    with_time: bool,
) -> None:
    """modern / modern_notime 表；日期与时段沿用整文件级 state（向前填充）。"""
    for row in rows[1:]:
        date_text = _first_line(_raw_cell(row, 0))
        time_text = _first_line(_raw_cell(row, 4)) if with_time else ""
        code_text = _clean(_raw_cell(row, 1))
        subject = _clean(_raw_cell(row, 2))
        title = _clean(_raw_cell(row, 3))
        duration_raw = _clean(_raw_cell(row, 5 if with_time else 4))
        if date_text:
            parsed = _parse_banner(date_text)
            if parsed is not None:
                state["date"] = parsed
            else:
                unparsed.append(
                    {"page": page_no, "row": _row_text(row), "reason": f"日期单元格无法解析: {date_text!r}"}
                )
        if with_time and time_text:
            session = _normalize_session(time_text)
            if session is not None:
                state["session"] = session
                state["session_raw"] = time_text
            else:
                unparsed.append(
                    {"page": page_no, "row": _row_text(row), "reason": f"时段单元格无法解析: {time_text!r}"}
                )
        if not code_text:
            if subject or title or duration_raw or time_text:
                unparsed.append({"page": page_no, "row": _row_text(row), "reason": "代码列为空"})
            continue
        split = _split_code(code_text)
        if split is None:
            unparsed.append(
                {"page": page_no, "row": _row_text(row), "reason": f"代码单元格无法解析: {code_text!r}"}
            )
            continue
        if state["date"] is None:
            unparsed.append({"page": page_no, "row": _row_text(row), "reason": "缺少可用的日期，无法归属"})
            continue
        subject_title = _combo_title(subject, title)
        if not subject_title:
            unparsed.append({"page": page_no, "row": _row_text(row), "reason": "科目与标题均为空"})
            continue
        event = _make_event(
            year=year,
            season_month=month,
            banner=state["date"],
            subject_code=split[0],
            paper_code=split[1],
            subject_title=subject_title,
            duration_raw=duration_raw,
            session=state["session"] if with_time else None,
            session_raw=state["session_raw"] if with_time else None,
            raw=" | ".join(p for p in (date_text, code_text, subject, title, time_text, duration_raw) if p),
        )
        if event is None:
            unparsed.append(
                {"page": page_no, "row": _row_text(row), "reason": f"日期 {state['date']!r} 无法构成合法日期"}
            )
            continue
        events.append(event)


def _parse_old_grid(
    rows: Sequence[Sequence[Any]],
    *,
    year: int,
    month: int,
    page_no: int,
    unparsed: list[dict[str, Any]],
    events: list[dict[str, Any]],
    windows: list[dict[str, Any]],
) -> None:
    """`Date | Morning | Length | Afternoon | Length` 版式；含 (Window) 的行进窗口。"""
    for row in rows[1:]:
        date_text = _clean(_raw_cell(row, 0))
        if not date_text or date_text.lower() == "date":
            continue
        if (
            "window" in date_text.lower()
            or _RANGE_FULL_RE.search(date_text)
            or _RANGE_SHORT_RE.search(date_text)
        ):
            _parse_old_grid_window_row(
                row, date_text, year=year, month=month, page_no=page_no, unparsed=unparsed, windows=windows
            )
            continue
        banner = _parse_banner(date_text)
        if banner is None:
            unparsed.append(
                {"page": page_no, "row": _row_text(row), "reason": f"日期单元格无法解析: {date_text!r}"}
            )
            continue
        for cell_index, length_index, session, raw_word in (
            (1, 2, "AM", "Morning"),
            (3, 4, "PM", "Afternoon"),
        ):
            entries = _split_entries(_raw_cell(row, cell_index))
            if not entries:
                continue
            lengths = _split_lengths(_raw_cell(row, length_index))
            durations = _align_lengths(entries, lengths, unparsed, _row_text(row), page_no)
            for entry, duration in zip(entries, durations):
                split = _split_entry(entry)
                if split is None:
                    unparsed.append(
                        {"page": page_no, "row": _row_text(row), "reason": f"条目无法解析: {entry!r}"}
                    )
                    continue
                subject_code, paper_code, rest = split
                event = _make_event(
                    year=year,
                    season_month=month,
                    banner=banner,
                    subject_code=subject_code,
                    paper_code=paper_code,
                    subject_title=rest,
                    duration_raw=duration,
                    session=session,
                    session_raw=raw_word,
                    raw=" | ".join(p for p in (date_text, entry, duration) if p),
                )
                if event is None:
                    unparsed.append(
                        {"page": page_no, "row": _row_text(row), "reason": f"日期 {banner!r} 无法构成合法日期"}
                    )
                    continue
                events.append(event)


def _parse_old_grid_window_row(
    row: Sequence[Any],
    date_text: str,
    *,
    year: int,
    month: int,
    page_no: int,
    unparsed: list[dict[str, Any]],
    windows: list[dict[str, Any]],
) -> None:
    date_phrases = _window_phrases(date_text) or [date_text]
    for cell_index, length_index in ((1, 2), (3, 4)):
        entries = _split_entries(_raw_cell(row, cell_index))
        if not entries:
            continue
        lengths = _split_lengths(_raw_cell(row, length_index))
        durations = _align_lengths(entries, lengths, unparsed, _row_text(row), page_no)
        for entry, duration in zip(entries, durations):
            split = _split_entry(entry)
            if split is None:
                unparsed.append(
                    {"page": page_no, "row": _row_text(row), "reason": f"窗口条目无法解析: {entry!r}"}
                )
                continue
            subject_code, paper_code, rest = split
            phrases = _window_phrases(rest)
            if phrases:
                phrase = phrases[0]
                title = _clean(rest.replace(phrase, "")) or rest
            else:
                phrase = date_phrases[0]
                title = rest
            start, end = _window_range(phrase, year, month)
            windows.append(
                {
                    "subject_code": subject_code,
                    "paper_code": paper_code,
                    "subject_title": title,
                    "duration_raw": duration,
                    "duration_minutes": _duration_minutes(duration),
                    "window_raw": phrase,
                    "window_start": start,
                    "window_end": end,
                    "raw": " | ".join(p for p in (date_text, entry, duration) if p),
                }
            )


def _parse_window_table(
    page: pymupdf.Page,
    table: Any,
    rows: Sequence[Sequence[Any]],
    *,
    year: int,
    month: int,
    page_no: int,
    unparsed: list[dict[str, Any]],
    windows: list[dict[str, Any]],
) -> None:
    """`Date | Unit | Length` 窗口表；窗口短语与单元条目按单元格内 y 坐标对齐。"""
    ncols = len(rows[0]) if rows and rows[0] else 0
    length_col: int | None = ncols - 1 if ncols >= 3 and _clean(rows[0][-1]).lower() == "length" else None
    for index in range(1, len(rows)):
        row = rows[index]
        date_text = _clean(_raw_cell(row, 0))
        if not date_text:
            continue
        phrases = _window_phrases(date_text) or [date_text]
        entries = _split_entries(_raw_cell(row, 1))
        if not entries:
            continue
        lengths = _split_lengths(_raw_cell(row, length_col)) if length_col is not None else []
        durations = _align_lengths(entries, lengths, unparsed, _row_text(row), page_no)
        bboxes = None
        try:
            bboxes = table.rows[index].cells
        except Exception:
            bboxes = None
        mapping = None
        if bboxes and len(bboxes) > 1 and bboxes[0] and bboxes[1]:
            mapping = _map_windows(page, bboxes[0], bboxes[1], len(phrases), len(entries))
        if mapping is None:
            if len(phrases) >= len(entries):
                mapping = list(range(len(entries)))
            else:
                mapping = [0] * len(entries)
                unparsed.append(
                    {
                        "page": page_no,
                        "row": _row_text(row),
                        "reason": f"窗口短语 {len(phrases)} 个与单元条目 {len(entries)} 条无法对齐，按首个窗口归属",
                    }
                )
        for position, entry in enumerate(entries):
            split = _split_entry(entry)
            if split is None:
                unparsed.append(
                    {"page": page_no, "row": _row_text(row), "reason": f"窗口条目无法解析: {entry!r}"}
                )
                continue
            subject_code, paper_code, rest = split
            phrase = phrases[mapping[position]]
            start, end = _window_range(phrase, year, month)
            duration = durations[position]
            windows.append(
                {
                    "subject_code": subject_code,
                    "paper_code": paper_code,
                    "subject_title": rest,
                    "duration_raw": duration,
                    "duration_minutes": _duration_minutes(duration),
                    "window_raw": phrase,
                    "window_start": start,
                    "window_end": end,
                    "raw": " | ".join(p for p in (date_text, entry, duration) if p),
                }
            )


def _parse_master(
    rows: Sequence[Sequence[Any]],
    *,
    year: int,
    month: int,
    page_no: int,
    unparsed: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> None:
    """非旋转的总表：日期为 dd/mm/yyyy，含显式年份。"""
    for row in rows[1:]:
        date_text = _clean(_raw_cell(row, 0))
        code_text = _clean(_raw_cell(row, 4))
        if not code_text:
            if date_text or _clean(_raw_cell(row, 5)) or _clean(_raw_cell(row, 6)):
                unparsed.append({"page": page_no, "row": _row_text(row), "reason": "代码列为空"})
            continue
        date_match = _MASTER_DATE_RE.match(date_text)
        if date_match is None:
            unparsed.append(
                {"page": page_no, "row": _row_text(row), "reason": f"日期无法解析: {date_text!r}"}
            )
            continue
        try:
            event_date = date(
                int(date_match.group(3)), int(date_match.group(2)), int(date_match.group(1))
            )
        except ValueError:
            unparsed.append(
                {"page": page_no, "row": _row_text(row), "reason": f"日期非法: {date_text!r}"}
            )
            continue
        split = _split_code(code_text)
        if split is None:
            unparsed.append(
                {"page": page_no, "row": _row_text(row), "reason": f"代码单元格无法解析: {code_text!r}"}
            )
            continue
        subject = _clean(_raw_cell(row, 5))
        title = _clean(_raw_cell(row, 6))
        subject_title = _combo_title(subject, title)
        if not subject_title:
            unparsed.append({"page": page_no, "row": _row_text(row), "reason": "科目与标题均为空"})
            continue
        time_text = _clean(_raw_cell(row, 7))
        session = _normalize_session(time_text)
        if session is None and time_text:
            unparsed.append(
                {"page": page_no, "row": _row_text(row), "reason": f"时段无法解析: {time_text!r}"}
            )
        duration_raw = _clean(_raw_cell(row, 8))
        banner: Banner = (_WEEKDAYS[event_date.weekday()], event_date.day, event_date.month, event_date.year)
        event = _make_event(
            year=year,
            season_month=month,
            banner=banner,
            subject_code=split[0],
            paper_code=split[1],
            subject_title=subject_title,
            duration_raw=duration_raw,
            session=session,
            session_raw=time_text or None,
            raw=" | ".join(p for p in (date_text, code_text, subject, title, time_text, duration_raw) if p),
        )
        if event is None:
            unparsed.append({"page": page_no, "row": _row_text(row), "reason": f"日期非法: {date_text!r}"})
            continue
        events.append(event)


def _parse_rotated(
    rows: Sequence[Sequence[Any]],
    *,
    year: int,
    month: int,
    page_no: int,
    unparsed: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> None:
    """旋转 90° 的转置总表：行=字段、列=记录；col0 为字段名时跳过首列。"""
    col0 = [_clean(row[0]) if row else "" for row in rows]
    field_rows: dict[str, int] = {}
    for index, value in enumerate(col0):
        name = _ROT_FIELD_LOOKUP.get(value.lower())
        if name and name not in field_rows:
            field_rows[name] = index
    if all(name in field_rows for name in _ROT_REQUIRED):
        data_start = 1
    else:
        field_rows = {name: index for index, name in enumerate(_ROT_FIELDS)}
        data_start = 0
    ncols = len(rows[0]) if rows and rows[0] else 0
    for column in range(data_start, ncols):
        code_text = _clean(_raw_cell(rows[field_rows["Examination code"]], column))
        date_text = _clean(_raw_cell(rows[field_rows["Exam date"]], column))
        if not code_text and not date_text:
            continue
        date_match = _ROT_DATE_RE.match(date_text)
        if date_match is None:
            unparsed.append(
                {
                    "page": page_no,
                    "row": f"col {column + 1}: {date_text!r} | {code_text!r}",
                    "reason": f"日期无法解析: {date_text!r}",
                }
            )
            continue
        split = _split_code(code_text)
        if split is None:
            unparsed.append(
                {
                    "page": page_no,
                    "row": f"col {column + 1}: {date_text!r} | {code_text!r}",
                    "reason": f"代码无法解析: {code_text!r}",
                }
            )
            continue
        try:
            event_date = date(2000 + int(date_match.group(3)), int(date_match.group(2)), int(date_match.group(1)))
        except ValueError:
            unparsed.append(
                {
                    "page": page_no,
                    "row": f"col {column + 1}: {date_text!r} | {code_text!r}",
                    "reason": f"日期非法: {date_text!r}",
                }
            )
            continue
        time_text = _clean(_raw_cell(rows[field_rows["Exam time"]], column))
        session = _normalize_session(time_text)
        subject = _clean(_raw_cell(rows[field_rows["Subject"]], column))
        title = _clean(_raw_cell(rows[field_rows["Title"]], column))
        subject_title = _combo_title(subject, title)
        if not subject_title:
            unparsed.append(
                {
                    "page": page_no,
                    "row": f"col {column + 1}: {date_text!r} | {code_text!r}",
                    "reason": "科目与标题均为空",
                }
            )
            continue
        duration_raw = _clean(_raw_cell(rows[field_rows["Exam duration"]], column))
        banner: Banner = (_WEEKDAYS[event_date.weekday()], event_date.day, event_date.month, event_date.year)
        event = _make_event(
            year=year,
            season_month=month,
            banner=banner,
            subject_code=split[0],
            paper_code=split[1],
            subject_title=subject_title,
            duration_raw=duration_raw,
            session=session,
            session_raw=time_text or None,
            raw=" | ".join(
                p for p in (date_text, code_text, subject, title, time_text, duration_raw) if p
            ),
        )
        if event is None:
            continue
        events.append(event)


# --------------------------------------------------------------------------
# 主入口
# --------------------------------------------------------------------------


def season_key(family: str, year: int, month: int, *, r_paper: bool = False) -> str:
    """考季键：`<family>|YYYY-MM`（R 卷加 `|R` 后缀）。"""
    return f"{family}|{int(year):04d}|{int(month):02d}" + ("|R" if r_paper else "")


# 考季写法归一与展示名（Edexcel 考季为 1/6/10/11 月），API 层与构建脚本共用。
MONTH_ALIASES: dict[str, int] = {
    "jan": 1,
    "january": 1,
    "winter": 1,
    "jun": 6,
    "june": 6,
    "summer": 6,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
}
MONTH_NAMES: dict[int, str] = {1: "Jan", 6: "Jun", 10: "Oct", 11: "Nov"}


def normalize_month(season: str) -> int:
    """把考季写法（Jan / January / June / winter 等）归一为月份数字（1 / 6 / 10 / 11）。"""
    token = str(season).strip()
    if token.isdigit() and int(token) in MONTH_NAMES:
        return int(token)
    month = MONTH_ALIASES.get(token.lower())
    if month is None:
        raise ValueError(f"无法识别的考季: {season!r}（支持 Jan/June/Oct/Nov）")
    return month


def month_name(month: int) -> str:
    """月份数字 → 展示用短名（1→Jan）；未知月份回落为两位数字。"""
    return MONTH_NAMES.get(int(month), f"{int(month):02d}")


def iter_seasons(pdf_dir: Path | str) -> Iterator[tuple[Path, str, int, int, bool]]:
    """枚举 `pdf_dir/<family>/YYYY-MM[-r].pdf`，产出 (路径, 系列, 年, 月, 是否 R 卷)。"""
    root = Path(pdf_dir)
    for family in FAMILIES:
        family_dir = root / family
        if not family_dir.is_dir():
            continue
        for path in sorted(family_dir.glob("*.pdf")):
            match = re.match(r"^(\d{4})-(\d{2})(-r)?$", path.stem)
            if match is None:
                continue
            yield path, family, int(match.group(1)), int(match.group(2)), bool(match.group(3))


def parse_pdf(
    path: Path | str,
    family: str,
    year: int,
    month: int,
    *,
    r_paper: bool = False,
) -> dict[str, Any]:
    """解析单个 Edexcel 时间表 PDF。

    参数：
        path: PDF 路径。
        family: `gcse` / `intgcse` / `ial` / `gce`。
        year: 考季年（如 2022）。
        month: 考季月份（1 / 6 / 10 / 11）。
        r_paper: 是否为 R 卷文件。

    返回：
        {
          "key", "family", "year", "month", "variant", "file", "sha256", "pages",
          "events": [...], "date_windows": [...], "unparsed_rows": [...],
          "stats": {...},
        }
    """
    pdf_path = Path(path)
    family_key = str(family).strip().lower()
    if family_key not in FAMILIES:
        raise ValueError(f"未知系列: {family!r}（支持 {', '.join(FAMILIES)}）")
    year_value = int(year)
    month_value = int(month)
    document = pymupdf.open(pdf_path)
    page_total = document.page_count
    events: list[dict[str, Any]] = []
    windows: list[dict[str, Any]] = []
    unparsed: list[dict[str, Any]] = []
    stats: dict[str, Any] = {
        "modern_tables": 0,
        "modern_notime_tables": 0,
        "old_grid_tables": 0,
        "window_tables": 0,
        "master_tables": 0,
        "rotated_tables": 0,
        "index_tables": 0,
        "noise_tables": 0,
        "condensed_tables": 0,
        "unclassified_tables": 0,
        "unclassified_samples": [],
        "duplicates_removed": 0,
        "window_duplicates_removed": 0,
        "date_notes": 0,
        "unparsed_total": 0,
    }
    pending_condensed: list[dict[str, Any]] = []
    modern_state: dict[str, Any] = {"date": None, "session": None, "session_raw": None}

    try:
        for page_index in range(page_total):
            page = document[page_index]
            try:
                if page.rotation:
                    page.set_rotation(0)
                tables = list(page.find_tables().tables)
            except Exception:
                continue
            for table in tables:
                try:
                    rows = table.extract()
                except Exception:
                    unparsed.append({"page": page_index + 1, "row": "", "reason": "表格提取失败"})
                    continue
                if not rows or not any(any(_clean(c) for c in row) for row in rows):
                    continue
                kind = _classify(rows)
                page_no = page_index + 1
                if kind == "index":
                    stats["index_tables"] += 1
                    continue
                if kind == "modern":
                    stats["modern_tables"] += 1
                    _parse_modern(
                        rows,
                        year=year_value,
                        month=month_value,
                        page_no=page_no,
                        unparsed=unparsed,
                        events=events,
                        state=modern_state,
                        with_time=True,
                    )
                    continue
                if kind == "modern_notime":
                    stats["modern_notime_tables"] += 1
                    _parse_modern(
                        rows,
                        year=year_value,
                        month=month_value,
                        page_no=page_no,
                        unparsed=unparsed,
                        events=events,
                        state=modern_state,
                        with_time=False,
                    )
                    continue
                if kind == "old_grid":
                    stats["old_grid_tables"] += 1
                    _parse_old_grid(
                        rows,
                        year=year_value,
                        month=month_value,
                        page_no=page_no,
                        unparsed=unparsed,
                        events=events,
                        windows=windows,
                    )
                    continue
                if kind == "window":
                    stats["window_tables"] += 1
                    _parse_window_table(
                        page,
                        table,
                        rows,
                        year=year_value,
                        month=month_value,
                        page_no=page_no,
                        unparsed=unparsed,
                        windows=windows,
                    )
                    continue
                if kind == "master":
                    stats["master_tables"] += 1
                    _parse_master(
                        rows,
                        year=year_value,
                        month=month_value,
                        page_no=page_no,
                        unparsed=unparsed,
                        events=events,
                    )
                    continue
                if kind == "rotated":
                    stats["rotated_tables"] += 1
                    _parse_rotated(
                        rows,
                        year=year_value,
                        month=month_value,
                        page_no=page_no,
                        unparsed=unparsed,
                        events=events,
                    )
                    continue
                codes = _table_codes(rows)
                if codes:
                    pending_condensed.append(
                        {
                            "page": page_no,
                            "shape": f"{len(rows)}x{len(rows[0]) if rows[0] else 0}",
                            "first": _clean(rows[0][0])[:80] if rows[0] else "",
                            "codes": codes,
                        }
                    )
                else:
                    stats["noise_tables"] += 1
    finally:
        document.close()

    deduped, duplicates = _dedupe_events(events)
    deduped_windows, window_duplicates = _dedupe_windows(windows)
    covered_subjects = {e["subject_code"] for e in deduped}
    covered_subjects |= {w["subject_code"] for w in deduped_windows}
    samples: list[dict[str, Any]] = []
    for item in pending_condensed:
        uncovered = sorted(item["codes"] - covered_subjects)
        if uncovered:
            stats["unclassified_tables"] += 1
            if len(samples) < 5:
                samples.append(
                    {
                        "page": item["page"],
                        "shape": item["shape"],
                        "first": item["first"],
                        "uncovered_codes": uncovered[:10],
                    }
                )
        else:
            stats["condensed_tables"] += 1
    stats["unclassified_samples"] = samples
    stats["duplicates_removed"] = duplicates
    stats["window_duplicates_removed"] = window_duplicates
    stats["date_notes"] = sum(1 for event in deduped if "date_note" in event)
    stats["unparsed_total"] = len(unparsed)

    session_rank = {"AM": 0, "PM": 1, "EV": 2, "WINDOW": 3}
    deduped.sort(
        key=lambda e: (e["date"], session_rank.get(e["session"], 9), e["subject_code"], e["paper_code"] or "")
    )
    deduped_windows.sort(key=lambda w: (w["window_start"] or "", w["subject_code"], w["paper_code"] or ""))

    return {
        "key": season_key(family_key, year_value, month_value, r_paper=r_paper),
        "family": family_key,
        "year": year_value,
        "month": month_value,
        "variant": "R" if r_paper else "standard",
        "file": pdf_path.name,
        "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        "pages": page_total,
        "events": deduped,
        "date_windows": deduped_windows,
        "unparsed_rows": unparsed[:MAX_UNPARSED_PER_SEASON],
        "stats": stats,
    }
