"""CIE Zone 5 考试时间表 PDF 解析。

输入是 CIE 官网（或 Wayback 存档）下载的 zone 5 最终版时间表 PDF，每份 12–24 页（现代版式 12–17 页、旧版式 14–24 页）：
封面/目录/说明页之后是 "Test date windows"（各单元的考试日期窗口）、
"Weekly view"（按日期排的考试安排）与 "Syllabus view (A–Z)"（同一批数据按科目重排）。

本模块只从 **Weekly view** 取 events：这是唯一同时给出
日期、时段（AM/PM/EV）、单元代码与时长的视图；Syllabus view 是同一份数据的
重排，仅用于 `include_syllabus=True` 时的覆盖核对，不进入 JSON。

解析方式：这些 PDF 由 Office 导出，表格框线完整，因此用 pymupdf 的
`find_tables()` 取表格，再按列头（Syllabus/Component / Code / Duration / Session，
以及 Test date windows 的 Syllabus name / Code / Test date window）定位语义列。
日期不在列头里，而是每张表上方（或首行）的整行横幅，如 "Tuesday 25 April"；
横幅只有日月，年份由考季推断：6 月考季落在 1–7 月，11 月考季落在 8–12 月，
落在此范围之外的日期不静默改年，只在事件上打 `date_note`。

2013–2014 考季的旧版式没有表格框线，等级用符号表示（映射见 `_LEGACY_SYMBOL_LEVELS`），
每个考试日只在页边标注一次日期，左/右半栏对应 AM/PM；这类 PDF 自动路由到
`_parse_legacy_pdf` 做几何聚类解析，产出的事件结构与新版一致。

无法确信归属的行（无日期横幅、代码列不是 `9699/99` 形态等）写入
`unparsed_rows`（每季最多 50 条），不猜测、不丢弃。
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

# "Tuesday 25 April" / "Tuesday 25 April 2017"，容忍单元格里的杂散字符（页码残留等）。
_BANNER_RE = re.compile(
    r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+(\d{1,2})\s+"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"(?:\s+(\d{4}))?",
    re.IGNORECASE,
)
# 极少数横幅可能缺月份，此时沿用上一个已知月份。
_BANNER_DAY_RE = re.compile(
    r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+(\d{1,2})\b",
    re.IGNORECASE,
)

_CODE_RE = re.compile(r"^(\d{4})(?:\s*/\s*([0-9A-Za-z]{1,3}))?$")
_CODE_SEARCH_RE = re.compile(r"\b(\d{4})\s*/\s*([0-9A-Za-z]{1,3})\b")

_DURATION_RE = re.compile(r"(\d+)\s*h(?:\s*(\d+)\s*m)?", re.IGNORECASE)
_DURATION_MIN_RE = re.compile(r"(\d+)\s*m", re.IGNORECASE)

_WINDOW_RE = re.compile(
    r"(\d{1,2})/(\d{1,2})/(\d{4})\s*[–—-]\s*(\d{1,2})/(\d{1,2})/(\d{4})"
)

_SESSION_VALUES = {"AM", "PM", "EV"}

# Weekly view 行首的等级缩写；Test date windows 的分节标题用全称。
_LEVEL_ALIASES = {
    "ig": "IG",
    "igcse": "IG",
    "ol": "OL",
    "o level": "OL",
    "as": "AS",
    "as level": "AS",
    "al": "AL",
    "a level": "AL",
    "pr": "PR",
    "pre-u": "PR",
}

_WINDOW_SECTION_ALIASES = (
    ("cambridge igcse", "IG"),
    ("cambridge o level", "OL"),
    ("cambridge international as level", "AS"),
    ("cambridge international a level", "AL"),
    ("cambridge pre-u", "PR"),
)

_SERIES_MONTHS = {"Jun": (1, 7), "Nov": (8, 12)}

Banner = tuple[str, int, int, int | None]


def normalize_series(series: str) -> str:
    """把 `Jun` / `June` / `06` 统一成 `Jun`，`Nov` / `November` / `11` 统一成 `Nov`。"""
    token = str(series).strip().lower()
    if token in {"jun", "june", "06", "6"}:
        return "Jun"
    if token in {"nov", "november", "11"}:
        return "Nov"
    raise ValueError(f"未知考季: {series!r}（只支持 Jun/June 与 Nov/November）")


def season_key(year: int, series: str) -> str:
    """考季键：`YYYY-MM`，`-06` 为 6 月考季，`-11` 为 11 月考季。"""
    canonical = normalize_series(series)
    return f"{int(year):04d}-{'06' if canonical == 'Jun' else '11'}"


# --------------------------------------------------------------------------
# 文本小工具
# --------------------------------------------------------------------------


def _clean(text: Any) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def _cell(row: Sequence[Any], index: int | None) -> str:
    if index is None or index < 0 or index >= len(row):
        return ""
    return _clean(row[index])


def _normalize_level(text: str) -> str | None:
    token = _clean(text).lower().rstrip(".")
    if token in _LEVEL_ALIASES:
        return _LEVEL_ALIASES[token]
    for alias, level in _LEVEL_ALIASES.items():
        if token.startswith(alias + " ") or token.endswith(" " + alias):
            return level
    return None


def _split_code(text: str) -> tuple[str, str | None] | None:
    """`9693/13` → ("9693", "13")；只有科目代码时 paper 为 None。"""
    cleaned = _clean(text)
    if not cleaned:
        return None
    match = _CODE_RE.match(cleaned)
    if match:
        return match.group(1), match.group(2)
    match = _CODE_SEARCH_RE.search(cleaned)
    if match:
        return match.group(1), match.group(2)
    return None


def _code_trailing(text: str) -> str:
    """代码单元格里代码之后的残留字符。

    表格竖线偶尔把时长列切偏（"45m" 变成代码格 "0607/12 4" + 时长格 "5m"），
    残留字符需要并回时长再解析。
    """
    cleaned = _clean(text)
    match = _CODE_RE.match(cleaned) or _CODE_SEARCH_RE.search(cleaned)
    if match:
        return cleaned[match.end() :].strip()
    return ""


def _duration_minutes(text: str) -> int | None:
    if not text:
        return None
    match = _DURATION_RE.search(text)
    if match:
        minutes = int(match.group(1)) * 60
        if match.group(2):
            minutes += int(match.group(2))
        return minutes
    match = _DURATION_MIN_RE.search(text)
    if match:
        return int(match.group(1))
    return None


def _parse_day_month(text: str) -> Banner | None:
    """从横幅文本里取 (weekday, day, month, year?)；缺月份时 month 为 None。"""
    match = _BANNER_RE.search(text)
    if match:
        weekday = match.group(1).capitalize()
        day = int(match.group(2))
        month = _MONTHS[match.group(3).lower()]
        year = int(match.group(4)) if match.group(4) else None
        return weekday, day, month, year
    match = _BANNER_DAY_RE.match(text.strip())
    if match:
        return match.group(1).capitalize(), int(match.group(2)), None, None
    return None


def _is_banner_row(row: Sequence[Any]) -> str | None:
    """整行横幅行：只有一个非空单元格，且该单元格是日期横幅。"""
    values = [_clean(c) for c in row if _clean(c)]
    if len(values) != 1:
        return None
    if _parse_day_month(values[0]) is None:
        return None
    return values[0]


def _is_header_row(row: Sequence[Any]) -> bool:
    """列头行（含续表重复印刷的列头），不是数据行。"""
    cells = [_clean(c) for c in row if _clean(c)]
    if not cells:
        return False
    joined = " | ".join(cells)
    if "Syllabus/Component" in joined or "Syllabus name" in joined:
        return True
    return all(cell in {"Code", "Duration", "Session", "Date"} for cell in cells)


def _merge_banner(previous: Banner | None, current: Banner | None) -> Banner | None:
    if current is None:
        return previous
    weekday, day, month, year = current
    if month is None:
        if previous is None:
            return current
        month = previous[2]
    return weekday, day, month, year


# --------------------------------------------------------------------------
# 页面与表格读取
# --------------------------------------------------------------------------


def _page_lines(page: pymupdf.Page) -> list[tuple[float, str]]:
    """页内文本行及 y 坐标（从上到下），用于定位日期横幅与分节标题。"""
    lines: list[tuple[float, str]] = []
    payload = page.get_text("dict")
    for block in payload.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = _clean("".join(span.get("text", "") for span in line.get("spans", [])))
            if text:
                lines.append((float(line["bbox"][1]), text))
    lines.sort(key=lambda item: item[0])
    return lines


def _table_records(page: pymupdf.Page) -> list[dict[str, Any]]:
    """页内所有表格：{bbox, rows}，按从上到下、从左到右排序。"""
    records: list[dict[str, Any]] = []
    for table in page.find_tables().tables:
        try:
            rows = table.extract()
        except Exception:  # pragma: no cover - pymupdf 内部异常不阻断整季
            continue
        if not rows:
            continue
        # 导航条等非数据表：整表没有任何 `9699/99` 形态的代码。
        if not any(_split_code(_cell(row, index)) for row in rows for index in range(len(row))):
            continue
        records.append({"bbox": [float(v) for v in table.bbox], "rows": rows})
    records.sort(key=lambda record: (round(record["bbox"][1]), round(record["bbox"][0])))
    return records


def _header_kind(rows: Sequence[Sequence[Any]]) -> str | None:
    """按列头判断表格用途：windows / weekly / syllabus。"""
    for row in rows[:4]:
        cells = [_clean(c) for c in row]
        joined = " | ".join(cells)
        if "Syllabus name" in joined and "Test date window" in joined:
            return "windows"
        if "Syllabus/Component" in joined and "Duration" in joined:
            return "syllabus" if "Date" in cells else "weekly"
    return None


def _weekly_groups(rows: Sequence[Sequence[Any]]) -> list[dict[str, int | None]]:
    """从列头行得到每组语义列下标（左栏、必要时右栏）。"""
    for row in rows[:4]:
        cells = [_clean(c) for c in row]
        if "Syllabus/Component" not in cells:
            continue
        name_cols = [i for i, cell in enumerate(cells) if "Syllabus/Component" in cell]
        groups: list[dict[str, int | None]] = []
        for name_col in name_cols:
            duration_col = name_col + 2
            if duration_col >= len(cells) or "Duration" not in cells[duration_col]:
                continue
            session_col = duration_col + 1
            if session_col >= len(cells) or "Date" in cells[session_col]:
                continue  # Syllabus view 的列序不同，不作为 weekly 行使用
            groups.append(
                {
                    "level_col": name_col - 1 if name_col > 0 else None,
                    "name_col": name_col,
                    "code_col": name_col + 1,
                    "duration_col": duration_col,
                    "session_col": session_col,
                }
            )
        if groups:
            return groups
    return []


def _default_groups(columns: int) -> list[dict[str, int | None]]:
    """没有列头行的续表：按常见列数套用默认列序。"""
    templates = {
        # 4 列版式没有等级列；列序与 `_weekly_groups` 对 4 列表头的结果一致。
        4: [(None, 0, 1, 2, 3)],
        5: [(0, 1, 2, 3, 4)],
        10: [(0, 1, 2, 3, 4), (5, 6, 7, 8, 9)],
        11: [(0, 1, 2, 3, 4), (6, 7, 8, 9, 10)],
    }
    if columns not in templates:
        return []
    return [
        {
            "level_col": idx[0],
            "name_col": idx[1],
            "code_col": idx[2],
            "duration_col": idx[3],
            "session_col": idx[4],
        }
        for idx in templates[columns]
    ]


# --------------------------------------------------------------------------
# 事件抽取
# --------------------------------------------------------------------------


def _event_year(year: int, series: str, month: int, month_year: int | None) -> tuple[int, str | None]:
    """还原事件年份：6 月考季 1–7 月属当年，11 月考季 8–12 月属当年。"""
    if month_year is not None:
        return month_year, None
    low, high = _SERIES_MONTHS[series]
    if low <= month <= high:
        return year, None
    return year, f"日期月份 {month} 不在 {series} 考季常规范围（{low}–{high} 月），年份按考季年记录"


def _make_event(
    *,
    year: int,
    series: str,
    banner: Banner,
    level: str | None,
    subject_code: str,
    paper_code: str | None,
    subject_title: str,
    duration_raw: str,
    session: str,
    raw: str,
) -> dict[str, Any]:
    weekday, day, month, month_year = banner
    event_year, date_note = _event_year(year, series, month, month_year)
    event = {
        "date": date(event_year, month, day).isoformat(),
        "weekday": weekday,
        "session": session,
        "level": level,
        "subject_code": subject_code,
        "paper_code": paper_code,
        "subject_title": subject_title,
        "duration_raw": duration_raw or None,
        "duration_minutes": _duration_minutes(duration_raw),
        "raw": raw,
    }
    if date_note:
        event["date_note"] = date_note
    return event


def _row_text(row: Sequence[Any]) -> str:
    return " | ".join(_clean(c) for c in row if _clean(c))


def _count_code_cells(rows: Sequence[Sequence[Any]]) -> int:
    """数一个表里 `9699/99` 形态的代码格数量（Syllabus view 覆盖核对用）。"""
    total = 0
    for row in rows:
        if _is_header_row(row):
            continue
        total += sum(1 for cell in row if _split_code(_clean(cell)))
    return total


def _extract_weekly_rows(
    rows: Sequence[Sequence[Any]],
    *,
    groups: list[dict[str, int | None]],
    initial_banner: Banner | None,
    year: int,
    series: str,
    unparsed: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], Banner | None]:
    events: list[dict[str, Any]] = []
    banner = initial_banner
    pending: dict[int, dict[str, Any]] = {}
    for row in rows:
        banner_text = _is_banner_row(row)
        if banner_text:
            banner = _merge_banner(banner, _parse_day_month(banner_text))
            continue
        if _is_header_row(row):
            continue
        for group_index, group in enumerate(groups):
            code_text = _cell(row, group["code_col"])
            name_text = _cell(row, group["name_col"])
            level_text = _cell(row, group["level_col"])
            session_text = _cell(row, group["session_col"]).upper()
            if not code_text and not name_text:
                continue
            if not code_text:
                # 单元格内换行被拆出的续行：并入上一行科目名。
                previous = pending.get(group_index)
                if previous is not None and name_text:
                    if name_text not in previous["subject_title"]:
                        previous["subject_title"] = _clean(
                            f"{previous['subject_title']} {name_text}"
                        )
                        previous["raw"] = _clean(f"{previous['raw']} {name_text}")
                continue
            split = _split_code(code_text)
            if split is None:
                unparsed.append(
                    {"row": _row_text(row), "reason": f"代码列无法解析: {code_text!r}"}
                )
                continue
            if banner is None or banner[2] is None:
                unparsed.append({"row": _row_text(row), "reason": "缺少日期横幅，无法归属"})
                continue
            if session_text not in _SESSION_VALUES:
                unparsed.append(
                    {"row": _row_text(row), "reason": f"时段列无法解析: {session_text!r}"}
                )
                continue
            duration_raw = _cell(row, group["duration_col"])
            trailing = _code_trailing(code_text)
            if trailing:
                combined = f"{trailing}{duration_raw}".strip()
                if _duration_minutes(combined) is not None or not duration_raw:
                    duration_raw = combined
            raw_parts = [p for p in (level_text, name_text, code_text, duration_raw, session_text) if p]
            event = _make_event(
                year=year,
                series=series,
                banner=banner,
                level=_normalize_level(level_text),
                subject_code=split[0],
                paper_code=split[1],
                subject_title=name_text,
                duration_raw=duration_raw,
                session=session_text,
                raw=" | ".join(raw_parts),
            )
            events.append(event)
            pending[group_index] = event
    return events, banner


def _extract_windows_rows(
    rows: Sequence[Sequence[Any]],
    *,
    level: str | None,
    unparsed: list[dict[str, str]],
) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    header_seen = False
    for row in rows:
        cells = [_clean(c) for c in row]
        joined = " | ".join(cells)
        if "Syllabus name" in joined and "Test date window" in joined:
            header_seen = True
            continue
        if not header_seen:
            continue
        name = cells[0] if cells else ""
        code_text = cells[1] if len(cells) > 1 else ""
        window_raw = cells[2] if len(cells) > 2 else ""
        if not name and not code_text and not window_raw:
            continue
        split = _split_code(code_text)
        window_start = window_end = None
        match = _WINDOW_RE.search(window_raw)
        if match:
            window_start = date(
                int(match.group(3)), int(match.group(2)), int(match.group(1))
            ).isoformat()
            window_end = date(
                int(match.group(6)), int(match.group(5)), int(match.group(4))
            ).isoformat()
        if split is None or not window_raw:
            unparsed.append(
                {"row": joined, "reason": "Test date windows 行缺少可解析的代码或日期窗口"}
            )
            continue
        windows.append(
            {
                "syllabus_name": name,
                "syllabus_code": split[0],
                "component_code": split[1],
                "level": level,
                "window_raw": window_raw,
                "window_start": window_start,
                "window_end": window_end,
            }
        )
    return windows


def _section_levels(lines: Sequence[tuple[float, str]]) -> list[tuple[float, str]]:
    """Test date windows 页内的分节标题（Cambridge IGCSE 等）及其 y 坐标。"""
    found: list[tuple[float, str]] = []
    for y, text in lines:
        lowered = text.lower()
        for alias, level in _WINDOW_SECTION_ALIASES:
            if lowered.startswith(alias):
                found.append((y, level))
                break
    return found


def _level_above(sections: Sequence[tuple[float, str]], y: float) -> str | None:
    level = None
    for section_y, section_level in sections:
        if section_y <= y + 4:
            level = section_level
        else:
            break
    return level


def _banner_above(lines: Sequence[tuple[float, str]], y: float) -> Banner | None:
    """表格上方最近的日期横幅（横幅本身是表格首行时允许略低于表格顶边）。"""
    best: Banner | None = None
    best_y = float("-inf")
    for line_y, text in lines:
        if not (y - 60 <= line_y <= y + 15):
            continue
        parsed = _parse_day_month(text)
        if parsed and line_y >= best_y:
            best = parsed
            best_y = line_y
    return best


# --------------------------------------------------------------------------
# 共享：事件去重
# --------------------------------------------------------------------------


def _dedupe_events(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """按 (日期, 时段, 等级, 科目, 单元, 名称) 签名去重，返回 (保留事件, 删除数)。"""
    seen: set[tuple[Any, ...]] = set()
    deduped: list[dict[str, Any]] = []
    duplicates = 0
    for event in events:
        signature = (
            event["date"],
            event["session"],
            event["level"],
            event["subject_code"],
            event["paper_code"],
            event["subject_title"],
        )
        if signature in seen:
            duplicates += 1
            continue
        seen.add(signature)
        deduped.append(event)
    return deduped, duplicates


# --------------------------------------------------------------------------
# Legacy 版式（2013–2014 考季）
# --------------------------------------------------------------------------

# 旧版用符号表示等级（Wingdings 私有区字符与真 Unicode 各一套）。
_LEGACY_SYMBOL_LEVELS = {
    "\uf074": "IG",
    "\uf06c": "OL",
    "\uf06e": "AS",
    "\uf070": "AL",
    "\uf0cc": "PR",
    "\u2666": "IG",
    "\u25cf": "OL",
    "\u25a0": "AS",
    "\u25b2": "AL",
    "+": "PR",
}

_LEGACY_SYMBOL_RE = re.compile(r"^[\u2666\u25a0\u25cf\u25b2\u25cb\u25a1+\uf000-\uf8ff]+$")

_LEGACY_FULL_WEEKDAYS = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday",
}

_LEGACY_MONTHS_ABBR = {name[:3]: num for name, num in _MONTHS.items()}

_LEGACY_WEEKDAY_RE = re.compile(
    r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|"
    r"Tues|Thur|Thurs|Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b",
    re.IGNORECASE,
)
_LEGACY_LABEL_DATE_RE = re.compile(r"^(\d{1,2})\s+([A-Za-z]{3,})(?:\s+\d{4})?$")

# 科目名尾部粘连的单元号，如 "Travel and Tourism 13"。
_LEGACY_TRAILING_NUMS_RE = re.compile(
    r"^(?P<title>.+?)(?P<nums>(?:\s+\d{1,3})+)(?P<tail>\s+\(.*\))?$"
)

# 页眉/页脚/图例等非数据文本。
_LEGACY_PAGE_RANGE_RE = re.compile(r"^\d{1,2}\s*[–-]\s*\d{1,2}\s+[A-Za-z]+\s+\d{4}")
_LEGACY_EXCLUDE_TEXTS = {
    "Morning session",
    "Afternoon session",
    "Morning Session",
    "Afternoon Session",
    "FINAL",
    "Code",
    "Duration",
    "Code Duration",
}
_LEGACY_LEGEND_TEXTS = {
    "IGCSE",
    "IGCSE (9-1)",
    "O Level",
    "AS Level",
    "A Level",
    "Principal Level",
    "GPR",
    "GPR Level 3 Cert",
    "Key:",
    "Key",
    "Cambridge IGCSE",
    "Cambridge O Level",
}


def _legacy_clean(text: Any) -> str:
    """旧版 PDF 用私有区字符 \\uf020 当空格，先还原再压缩空白。"""
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text).replace("\uf020", " ")).strip()


def _median(values: list[float]) -> float:
    values = sorted(values)
    return values[len(values) // 2]


def _legacy_cluster_ys(ys: list[float], tol: float = 4.0) -> list[float]:
    """把近似同一水平线的 y 合并成一个值（与上一值的差 ≤ tol 视为同一线）。"""
    out: list[float] = []
    for y in sorted(ys):
        if out and y - out[-1] <= tol:
            continue
        out.append(y)
    return out


def _legacy_group_rows(
    spans: list[tuple[float, float, str]], tol: float = 6.0
) -> list[tuple[float, list[tuple[float, str]]]]:
    """把 (y, x0, 文本) 片段按相邻 y 间距 ≤ tol 聚成可视行，返回 (行顶 y, 行内片段)。"""
    ys = sorted({y for (y, _, _) in spans})
    clusters: list[list[float]] = []
    current: list[float] = []
    for y in ys:
        if current and y - current[-1] > tol:
            clusters.append(current)
            current = []
        current.append(y)
    if current:
        clusters.append(current)
    rows: list[tuple[float, list[tuple[float, str]]]] = []
    for cluster in clusters:
        lo, hi = cluster[0], cluster[-1]
        group = sorted(
            [(x0, text) for (y, x0, text) in spans if lo <= y <= hi],
            key=lambda item: item[0],
        )
        rows.append((lo, group))
    return rows


def _legacy_strip_comp_tail(title: str, paper: str) -> str | None:
    """剥离科目名尾部的单元号。

    仅当其数字多重集是 paper 编号数字的子集时剥离（"Travel and Tourism 13" +
    "13" → "Travel and Tourism"）；否则返回 None，调用方保留原名。
    """
    match = _LEGACY_TRAILING_NUMS_RE.match(re.sub(r"\)(?=\d)", ") ", title))
    if not match:
        return None
    tail = [ch for ch in match.group("nums") if ch.isdigit()]
    paper_digits = [ch for ch in paper if ch.isdigit()]
    if not paper_digits or any(
        tail.count(ch) > paper_digits.count(ch) for ch in set(tail)
    ):
        return None
    return _legacy_clean(match.group("title") + (match.group("tail") or ""))


def _legacy_is_noise(text: str) -> bool:
    cleaned = _legacy_clean(text)
    if cleaned in _LEGACY_EXCLUDE_TEXTS or "FINAL" in cleaned:
        return True
    if _LEGACY_PAGE_RANGE_RE.match(cleaned):
        return True
    if cleaned in _LEGACY_LEGEND_TEXTS:
        return True
    if cleaned.startswith("Key:") or "GPR Level 3 Cert" in cleaned:
        return True
    return False


def _legacy_page_spans(page: pymupdf.Page) -> list[tuple[float, float, float, str]]:
    """页内所有非空文本 span：(y, x0, x1, 原文)。"""
    out: list[tuple[float, float, float, str]] = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"]
                if _legacy_clean(text):
                    out.append(
                        (
                            round(span["bbox"][1], 1),
                            round(span["bbox"][0], 1),
                            round(span["bbox"][2], 1),
                            text,
                        )
                    )
    return out


def _legacy_parse_label(text: str) -> tuple[str | None, int | None, int | None] | None:
    """页边日期标签 → (星期, 日, 月)；解析不出任何成分时返回 None。"""
    cleaned = _legacy_clean(text)
    weekday = None
    rest = cleaned
    match = _LEGACY_WEEKDAY_RE.match(cleaned)
    if match:
        token = match.group(1).lower()
        weekday = _LEGACY_FULL_WEEKDAYS.get(token[:3])
        rest = cleaned[match.end():].strip()
    day = month = None
    match = _LEGACY_LABEL_DATE_RE.match(rest)
    if match:
        month = _MONTHS.get(match.group(2).lower()) or _LEGACY_MONTHS_ABBR.get(
            match.group(2).lower()[:3]
        )
        if month is not None:
            day = int(match.group(1))
    if weekday is None and day is None:
        return None
    return weekday, day, month


def _legacy_detect_columns(
    spans: list[tuple[float, float, float, str]], band_ys: list[float]
) -> dict[str, Any] | None:
    """由各日期块表头行推算左右半栏的名称/代码/时长列 x 坐标。"""
    name_left: list[float] = []
    name_right: list[float] = []
    code_left: list[float] = []
    code_right: list[float] = []
    duration_left: list[float] = []
    duration_right: list[float] = []
    for band_y in band_ys:
        header = sorted(
            [(x0, x1, text) for (y, x0, x1, text) in spans if abs(y - band_y) <= 4],
            key=lambda item: item[0],
        )
        syllabus = [item for item in header if "Syllabus" in item[2]]
        if len(syllabus) < 2:
            continue
        name_left.append(syllabus[0][0])
        name_right.append(syllabus[1][0])
        split = syllabus[1][0]
        for (x0, _x1, text) in header:
            cleaned = _legacy_clean(text)
            if "Syllabus" in cleaned:
                continue
            if "Code" in cleaned:
                (code_left if x0 < split else code_right).append(x0)
            if "Duration" in cleaned and "Code" not in cleaned:
                (duration_left if x0 < split else duration_right).append(x0)
    if not name_left or not name_right:
        return None
    columns = {
        "name_L": _median(name_left),
        "name_R": _median(name_right),
        "code_L": _median(code_left) if code_left else None,
        "code_R": _median(code_right) if code_right else None,
        "dur_L": _median(duration_left) if duration_left else None,
        "dur_R": _median(duration_right) if duration_right else None,
    }
    if columns["code_L"] is None and columns["code_R"] is not None:
        columns["code_L"] = columns["name_L"] + (columns["code_R"] - columns["name_R"])
    if columns["code_R"] is None and columns["code_L"] is not None:
        columns["code_R"] = columns["name_R"] + (columns["code_L"] - columns["name_L"])
    if (
        columns["dur_L"] is None
        and columns["dur_R"] is not None
        and columns["code_L"] is not None
        and columns["code_R"] is not None
    ):
        columns["dur_L"] = columns["code_L"] + (columns["dur_R"] - columns["code_R"])
    if (
        columns["dur_R"] is None
        and columns["dur_L"] is not None
        and columns["code_L"] is not None
        and columns["code_R"] is not None
    ):
        columns["dur_R"] = columns["code_R"] + (columns["dur_L"] - columns["code_L"])
    missing = [
        name
        for name in ("name_L", "name_R", "code_L", "code_R", "dur_L", "dur_R")
        if columns[name] is None
    ]
    if missing:
        return {"error": f"missing columns {missing}"}
    return {
        "cols_L": (columns["name_L"], columns["code_L"], columns["dur_L"]),
        "cols_R": (columns["name_R"], columns["code_R"], columns["dur_R"]),
    }


def _legacy_extract_page(page: pymupdf.Page) -> dict[str, Any] | None:
    """解析一个 legacy 周页，返回 {"events", "unparsed"}；页面不含表格时返回 None。"""
    spans = _legacy_page_spans(page)
    band_spans = [
        (y, x0, x1, text)
        for (y, x0, x1, text) in spans
        if "Syllabus" in text and "Component" in text
    ]
    if not band_spans:
        return None
    band_ys = _legacy_cluster_ys([y for y, _, _, _ in band_spans])
    columns = _legacy_detect_columns(spans, band_ys)
    if columns is None or "error" in columns:
        return {"error": (columns or {}).get("error", "no columns")}
    cols_left, cols_right = columns["cols_L"], columns["cols_R"]

    def half_of(x0: float) -> str:
        distance_left = min(abs(x0 - column) for column in cols_left)
        distance_right = min(abs(x0 - column) for column in cols_right)
        return "L" if distance_left <= distance_right else "R"

    margin: list[tuple[float, tuple[str | None, int | None, int | None], str]] = []
    rows: list[tuple[float, str, float, str]] = []
    for y, x0, _x1, text in spans:
        cleaned = _legacy_clean(text)
        if "Syllabus" in cleaned and "Component" in cleaned:
            continue
        if _legacy_is_noise(cleaned):
            continue
        if x0 < cols_left[0] - 5:
            label = _legacy_parse_label(cleaned)
            if label is not None:
                margin.append((y, label, cleaned))
                continue
        if y < band_ys[0] - 5:
            continue
        rows.append((y, half_of(x0), x0, cleaned))

    per_half_rows: dict[str, list[tuple[float, list[tuple[float, str]]]]] = {
        "L": [],
        "R": [],
    }
    for half in ("L", "R"):
        half_spans = [(y, x0, text) for (y, h, x0, text) in rows if h == half]
        for lo, group in _legacy_group_rows(half_spans, tol=6.0):
            per_half_rows[half].append((lo, group))

    label_by_block: dict[int, tuple[str | None, int | None, int | None]] = {}
    for y, label, _text in sorted(margin):
        index = None
        for i, band_y in enumerate(band_ys):
            if y >= band_y - 12:
                index = i
        if index is None:
            continue
        previous = label_by_block.get(index)
        weekday, day, month = label
        weekday = weekday or (previous[0] if previous else None)
        day = day if day is not None else (previous[1] if previous else None)
        month = month if month is not None else (previous[2] if previous else None)
        label_by_block[index] = (weekday, day, month)

    def block_of(y: float) -> int | None:
        index = None
        for i, band_y in enumerate(band_ys):
            if y >= band_y - 6:
                index = i
        return index

    events: list[dict[str, Any]] = []
    unparsed: list[dict[str, str]] = []
    for half in ("L", "R"):
        pending: dict[str, Any] | None = None
        carry: dict[str, Any] | None = None
        for row_y, group in per_half_rows[half]:
            symbols: list[str] = []
            rest: list[str] = []
            for (_x0, text) in group:
                if not rest and _LEGACY_SYMBOL_RE.match(text):
                    symbols.append(text)
                else:
                    rest.append(text)
            text = _legacy_clean(" ".join(rest))
            if not text and not symbols:
                continue
            match = _CODE_SEARCH_RE.search(text) if text else None
            if match is None:
                if (
                    text
                    and not symbols
                    and pending is not None
                    and row_y - pending["last_y"] <= 24
                ):
                    pending["name_parts"].append(text)
                    pending["last_y"] = row_y
                    continue
                if carry is not None and carry["text"]:
                    unparsed.append(carry["entry"])
                carry = {
                    "y": row_y,
                    "text": text,
                    "symbols": symbols,
                    "entry": {"row": text, "reason": "行内未找到试卷代码"},
                }
                continue
            name_raw = _legacy_clean(text[: match.start()])
            duration_raw = _legacy_clean(text[match.end():])
            if carry is not None and not symbols and row_y - carry["y"] <= 24:
                name_parts = ([carry["text"]] if carry["text"] else []) + [name_raw]
                symbols = carry["symbols"]
                carry = None
            else:
                if carry is not None and carry["text"]:
                    unparsed.append(carry["entry"])
                carry = None
                name_parts = [name_raw]
            pending = {
                "name_parts": name_parts,
                "code": match.group(0),
                "dur": duration_raw,
                "symbol": symbols[0] if symbols else None,
                "label": label_by_block.get(block_of(row_y)),
                "half": half,
                "last_y": row_y,
                "text": text,
            }
            events.append(pending)
        if carry is not None and carry["text"]:
            unparsed.append(carry["entry"])
    return {"events": events, "unparsed": unparsed}


def _is_legacy_weekly_page(text: str) -> bool:
    """legacy 周页标志：同页既有 Morning session 说明，表头又是 Syllabus/Component。"""
    return ("Morning session" in text or "Morning Session" in text) and (
        "Syllabus/Component" in text or "Syllabus / Component" in text
    )


def _is_legacy_document(document: pymupdf.Document) -> bool:
    return any(_is_legacy_weekly_page(page.get_text()) for page in document)


def _parse_legacy_pdf(
    document: pymupdf.Document,
    pdf_path: Path,
    year: int,
    series: str,
) -> dict[str, Any]:
    """解析 2013–2014 旧版式时间表，返回与 `parse_pdf` 相同的结构。"""
    events: list[dict[str, Any]] = []
    unparsed: list[dict[str, str]] = []
    weekly_pages = 0
    for page in document:
        if not _is_legacy_weekly_page(page.get_text()):
            continue
        weekly_pages += 1
        result = _legacy_extract_page(page)
        if result is None or "error" in result:
            reason = (result or {}).get("error", "未找到表头")
            unparsed.append(
                {"row": "", "reason": f"第 {page.number + 1} 页 legacy 版式无法解析: {reason}"}
            )
            continue
        unparsed.extend(result["unparsed"])
        for row in result["events"]:
            label = row["label"]
            if label is None or label[1] is None or label[2] is None:
                unparsed.append({"row": row["text"], "reason": "缺少日期标签，无法归属"})
                continue
            match = _CODE_SEARCH_RE.match(row["code"])
            if match is None:
                unparsed.append(
                    {"row": row["text"], "reason": f"代码无法解析: {row['code']!r}"}
                )
                continue
            subject_code = match.group(1)
            paper_raw = match.group(2)
            paper_code = paper_raw.zfill(2) if paper_raw.isdigit() else paper_raw
            weekday, day, month = label
            if weekday is None:
                event_year, _note = _event_year(year, series, month, None)
                weekday = date(event_year, month, day).strftime("%A")
            name_raw = _legacy_clean(" ".join(row["name_parts"]))
            stripped = _legacy_strip_comp_tail(name_raw, paper_raw)
            subject_title = stripped if stripped is not None else name_raw
            level = _LEGACY_SYMBOL_LEVELS.get(row["symbol"]) if row["symbol"] else None
            session = "AM" if row["half"] == "L" else "PM"
            raw = " | ".join(
                part
                for part in (level or "", name_raw, row["code"], row["dur"], session)
                if part
            )
            events.append(
                _make_event(
                    year=year,
                    series=series,
                    banner=(weekday, day, month, None),
                    level=level,
                    subject_code=subject_code,
                    paper_code=paper_code,
                    subject_title=subject_title,
                    duration_raw=row["dur"],
                    session=session,
                    raw=raw,
                )
            )
    deduped, duplicates = _dedupe_events(events)
    return {
        "key": season_key(year, series),
        "year": int(year),
        "series": series,
        "file": pdf_path.name,
        "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        "pages": document.page_count,
        "events": deduped,
        "date_windows": [],
        "unparsed_rows": unparsed[:MAX_UNPARSED_PER_SEASON],
        "stats": {
            "weekly_pages": weekly_pages,
            "windows_pages": 0,
            "syllabus_pages": 0,
            "legacy_layout": True,
            "duplicates_removed": duplicates,
            "unparsed_total": len(unparsed),
        },
    }


# --------------------------------------------------------------------------
# 主入口
# --------------------------------------------------------------------------


def parse_pdf(
    path: Path | str,
    year: int,
    series: str,
    *,
    include_syllabus: bool = False,
) -> dict[str, Any]:
    """解析单个 zone 5 时间表 PDF。

    参数：
        path: PDF 路径。
        year: 考季年（如 2026）。
        series: `Jun` / `Nov`（也接受 `June` / `November`）。
        include_syllabus: 额外解析 Syllabus view（仅供覆盖核对，不写 JSON）。

    2013–2014 旧版式 PDF 自动路由到 `_parse_legacy_pdf`：返回结构相同，
    `date_windows` 为空，`stats` 含 `legacy_layout: true`。

    返回：
        {
          "key", "year", "series", "file", "sha256", "pages",
          "events": [...], "date_windows": [...], "unparsed_rows": [...],
          "stats": {...},  # include_syllabus=True 时含 syllabus_rows
        }
    """
    pdf_path = Path(path)
    canonical = normalize_series(series)
    document = pymupdf.open(pdf_path)
    page_total = document.page_count
    events: list[dict[str, Any]] = []
    windows: list[dict[str, Any]] = []
    unparsed: list[dict[str, str]] = []
    stats: dict[str, Any] = {"weekly_pages": 0, "windows_pages": 0, "syllabus_pages": 0}
    syllabus_rows = 0
    carried_banner: Banner | None = None

    try:
        if _is_legacy_document(document):
            return _parse_legacy_pdf(document, pdf_path, int(year), canonical)
        for page in document:
            text = page.get_text()
            has_components = "Syllabus/Component" in text
            has_windows = "Test date window" in text or (
                "Syllabus name" in text and "Code" in text
            )
            if not has_components and not has_windows:
                continue

            lines = _page_lines(page)
            records = _table_records(page)
            kinds = [kind for record in records if (kind := _header_kind(record["rows"]))]
            page_kind = max(set(kinds), key=kinds.count) if kinds else None
            if page_kind:
                stats[f"{page_kind}_pages"] += 1

            for record in records:
                rows = record["rows"]
                kind = _header_kind(rows) or page_kind
                if kind == "windows":
                    level = _level_above(_section_levels(lines), record["bbox"][1])
                    windows.extend(_extract_windows_rows(rows, level=level, unparsed=unparsed))
                    continue
                if kind == "syllabus":
                    if include_syllabus:
                        syllabus_rows += _count_code_cells(rows)
                    continue
                if kind != "weekly":
                    continue
                groups = _weekly_groups(rows) or _default_groups(len(rows[0]) if rows else 0)
                if not groups:
                    continue
                initial = _banner_above(lines, record["bbox"][1]) or carried_banner
                table_events, carried_banner = _extract_weekly_rows(
                    rows,
                    groups=groups,
                    initial_banner=initial,
                    year=year,
                    series=canonical,
                    unparsed=unparsed,
                )
                events.extend(table_events)
    finally:
        document.close()

    # 完全重复的行（续表重复印刷等）只保留一份。
    deduped, duplicates = _dedupe_events(events)

    stats["duplicates_removed"] = duplicates
    stats["unparsed_total"] = len(unparsed)
    if include_syllabus:
        stats["syllabus_rows"] = syllabus_rows

    return {
        "key": season_key(year, canonical),
        "year": int(year),
        "series": canonical,
        "file": pdf_path.name,
        "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        "pages": page_total,
        "events": deduped,
        "date_windows": windows,
        "unparsed_rows": unparsed[:MAX_UNPARSED_PER_SEASON],
        "stats": stats,
    }


def iter_seasons(pdf_dir: Path | str) -> Iterator[tuple[Path, int, str]]:
    """枚举形如 `2026-06.pdf` 的时间表文件，产出 (路径, 年, 考季)。"""
    for path in sorted(Path(pdf_dir).glob("*.pdf")):
        match = re.match(r"^(\d{4})-(06|11)$", path.stem)
        if not match:
            continue
        yield path, int(match.group(1)), "Jun" if match.group(2) == "06" else "Nov"
