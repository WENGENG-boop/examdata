"""考试时间表接口（/api/v1/timetable）：CIE Zone 5 与 Edexcel。

数据来自本包内的离线快照（由 `examdata.timetable.build` /
`examdata.timetable.build_edexcel` 生成）：

- CIE：`data/zone5/`，`index.json` 记录 25 个可得考季（2013-11 … 2026-11）与
  2 个不可得考季的证据，`YYYY-MM.json` 存单季结构化事件与单元考试日期窗口；
- Edexcel：`data/edexcel/`，`index.json` 记录 106 个可得考季（gcse / intgcse /
  ial / gce × 历年 1/6/10/11 月考季，含 R 卷）、6 个取消考季（COVID-19）与
  15 个有证据的不可得考季，`<family>/YYYY-MM[-r].json` 存单季事件与窗口。

运行时不联网、不查库，只读文件并按进程缓存。

考季键：CIE 为 `YYYY-MM`（`-06` 六月 / `-11` 十一月）；Edexcel 为
`<family>|YYYY-MM`（R 卷加 `|R`）。接口参数 `season`：CIE 接受
`Jun`/`June`/`Nov`/`November`；Edexcel 接受 `Jan`/`June`/`Oct`/`Nov`
（大小写不敏感）。有快照返回 200；取消考季与有证据的不可得考季返回 404
（detail 带 reason，不可得带 evidence）；形式合法但从未收录返回 422。

启动：
    examdata serve --host 127.0.0.1 --port 8000
    curl "http://127.0.0.1:8000/api/v1/timetable/seasons"
    curl "http://127.0.0.1:8000/api/v1/timetable/seasons?board=edexcel&family=ial"
    curl "http://127.0.0.1:8000/api/v1/timetable?year=2026&season=Jun&subject=9709"
    curl "http://127.0.0.1:8000/api/v1/timetable?board=edexcel&family=ial&year=2026&season=June"
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from .edexcel_parser import (
    FAMILIES as EDEXCEL_FAMILIES,
    normalize_month,
    season_key as edexcel_season_key,
)
from .parser import normalize_series, season_key

# 快照 schema 版本：字段增删（如新增过滤维度）由这个号标识。
SCHEMA_VERSION = "1"
ZONE = 5
BOARD = "cie"

_CIE_DATA_DIR = Path(__file__).resolve().parent / "data" / "zone5"
_EDEXCEL_DATA_DIR = Path(__file__).resolve().parent / "data" / "edexcel"
_DEFAULT_LIMIT = 200
_MAX_LIMIT = 2000
_SESSIONS = {"AM", "PM", "EV"}
_LEVELS = {"IG", "OL", "AS", "AL", "PR"}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_BOARD_ALIASES = {
    "cie": "cie",
    "cambridge": "cie",
    "ca": "cie",
    "edexcel": "edexcel",
    "edx": "edexcel",
    "pearson": "edexcel",
}

router = APIRouter(prefix="/api/v1", tags=["timetable"])

_lock = threading.Lock()
_cache: dict[str, Any] = {}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_board(board: str) -> str:
    token = str(board or "").strip().lower()
    canonical = _BOARD_ALIASES.get(token)
    if canonical is None:
        raise HTTPException(
            status_code=422, detail=f"无法识别的 board: {board!r}（支持 cie / edexcel）"
        )
    return canonical


def _normalize_family(family: str | None, *, required: bool) -> str:
    token = str(family or "").strip().lower()
    if not token and not required:
        return ""
    if token not in EDEXCEL_FAMILIES:
        raise HTTPException(
            status_code=422,
            detail=f"family 需为 {'/'.join(EDEXCEL_FAMILIES)}: {family!r}",
        )
    return token


def _data_dir(board: str) -> Path:
    return _CIE_DATA_DIR if board == "cie" else _EDEXCEL_DATA_DIR


def load_index(board: str = "cie") -> dict[str, Any]:
    """读取考季索引（进程内缓存）。快照缺失说明部署不完整，返回 503。"""
    with _lock:
        cache_key = f"{board}:index"
        index = _cache.get(cache_key)
        if index is None:
            path = _data_dir(board) / "index.json"
            if not path.is_file():
                raise HTTPException(status_code=503, detail=f"时间表快照缺失: {path}")
            index = _read_json(path)
            _cache[cache_key] = index
        return index


def _split_edexcel_key(key: str) -> tuple[str, str, str, bool]:
    parts = str(key).split("|")
    if len(parts) < 3:
        raise HTTPException(status_code=503, detail=f"非法考季键: {key}")
    return parts[0], parts[1], parts[2], len(parts) > 3 and parts[3].upper() == "R"


def load_season(board: str, key: str) -> dict[str, Any]:
    """读取单季快照（进程内缓存）。"""
    with _lock:
        cache_key = f"{board}:{key}"
        season = _cache.get(cache_key)
        if season is None:
            if board == "cie":
                path = _CIE_DATA_DIR / f"{key}.json"
            else:
                family, year_text, month_text, r_paper = _split_edexcel_key(key)
                suffix = "-r" if r_paper else ""
                path = _EDEXCEL_DATA_DIR / family / f"{year_text}-{month_text}{suffix}.json"
            if not path.is_file():
                raise HTTPException(status_code=503, detail=f"考季快照缺失: {path}")
            season = _read_json(path)
            _cache[cache_key] = season
        return season


def _resolve_cie_season(year: int, season: str) -> str:
    """CIE 考季参数归一为 `YYYY-MM`；不可得考季 404，未收录考季 422。"""
    try:
        canonical = normalize_series(season)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    key = season_key(year, canonical)
    index = load_index("cie")
    available = {item["key"] for item in index.get("seasons", [])}
    if key in available:
        return key
    for item in index.get("unobtainable", []):
        if item.get("key") == key:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": f"{key} 时间表不可得",
                    "reason": item.get("reason"),
                    "evidence": item.get("evidence"),
                },
            )
    raise HTTPException(status_code=422, detail=f"未收录的考季: {key}")


def _resolve_edexcel_season(family: str | None, year: int, season: str, r_paper: bool) -> str:
    """Edexcel 考季参数归一为 `<family>|YYYY-MM[|R]`：取消考季与不可得考季 404。"""
    fam = _normalize_family(family, required=True)
    try:
        month = normalize_month(season)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    key = edexcel_season_key(fam, year, month, r_paper=r_paper)
    index = load_index("edexcel")
    available = {item["key"] for item in index.get("seasons", [])}
    if key in available:
        return key
    base_key = edexcel_season_key(fam, year, month)
    for item in index.get("cancelled", []):
        if item.get("key") == base_key:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": f"{base_key} 考季已取消",
                    "reason": item.get("reason"),
                    "cancelled": True,
                },
            )
    for item in index.get("unobtainable", []):
        if item.get("key") == key:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": f"{key} 时间表不可得",
                    "reason": item.get("reason"),
                    "evidence": item.get("evidence"),
                },
            )
    raise HTTPException(status_code=422, detail=f"未收录的考季: {key}")


@router.get("/timetable/seasons")
def list_timetable_seasons(
    board: str = Query("cie", description="考试局：cie / edexcel（别名 cambridge/ca、edx/pearson）"),
    family: str | None = Query(
        None, description="Edexcel 系列：gcse / intgcse / ial / gce（仅 board=edexcel）"
    ),
) -> dict[str, Any]:
    """列出全部考季。

    CIE（默认）：25 个结构化快照考季 + 2 个有证据的不可得考季；Edexcel
    （board=edexcel）：106 个可得考季（含 R 卷）+ 6 个取消考季（COVID-19）+
    15 个有证据的不可得考季，可用 family 过滤。
    """
    board_key = _normalize_board(board)
    if board_key == "cie":
        if family:
            raise HTTPException(status_code=422, detail="family 仅适用于 board=edexcel")
        index = load_index("cie")
        return {
            "schema_version": SCHEMA_VERSION,
            "zone": ZONE,
            "board": BOARD,
            "generated_at": index.get("generated_at"),
            "totals": index.get("totals", {}),
            "counts": {
                "seasons": len(index.get("seasons", [])),
                "unobtainable": len(index.get("unobtainable", [])),
            },
            "seasons": index.get("seasons", []),
            "unobtainable": index.get("unobtainable", []),
            "unobtainable_search_note_zh": index.get("unobtainable_search_note_zh"),
        }
    fam = _normalize_family(family, required=False)
    index = load_index("edexcel")
    seasons = index.get("seasons", [])
    cancelled = index.get("cancelled", [])
    unobtainable = index.get("unobtainable", [])
    if fam:
        seasons = [item for item in seasons if item.get("family") == fam]
        cancelled = [item for item in cancelled if item.get("family") == fam]
        unobtainable = [item for item in unobtainable if item.get("family") == fam]
    return {
        "schema_version": SCHEMA_VERSION,
        "board": "edexcel",
        "family": fam or None,
        "generated_at": index.get("generated_at"),
        "totals": index.get("totals", {}),
        "counts": {
            "seasons": len(seasons),
            "cancelled": len(cancelled),
            "unobtainable": len(unobtainable),
        },
        "seasons": seasons,
        "cancelled": cancelled,
        "unobtainable": unobtainable,
    }


@router.get("/timetable")
def get_timetable(
    year: int = Query(..., description="考季年，如 2026"),
    season: str = Query(
        ..., description="考季：CIE Jun/June、Nov/November；Edexcel Jan/June/Oct/Nov（大小写不敏感）"
    ),
    board: str = Query("cie", description="考试局：cie / edexcel"),
    family: str | None = Query(
        None, description="Edexcel 系列：gcse / intgcse / ial / gce（board=edexcel 必填）"
    ),
    r_paper: bool = Query(False, description="Edexcel R 卷（仅 board=edexcel 生效）"),
    subject: str | None = Query(None, description="科目/单元代码，按前缀或全等匹配，如 9709 或 WAC"),
    date: str | None = Query(None, description="考试日期，ISO 格式 YYYY-MM-DD"),
    session: str | None = Query(None, description="时段：AM / PM / EV"),
    level: str | None = Query(None, description="等级：IG / OL / AS / AL / PR（仅 CIE）"),
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT, description="返回条数上限，默认 200"),
    offset: int = Query(0, ge=0, description="跳过条数，配合 limit 分页"),
) -> dict[str, Any]:
    """按考季返回结构化考试事件（单场考试一行）。

    CIE 每行含 `date`（ISO）、`weekday`、`session`、`level`、`subject_code`、
    `paper_code`、`subject_title`、`duration_raw`、`duration_minutes`、`raw`；
    Edexcel 每行含 `date`、`weekday`、`session`、`subject_code`、`paper_code`、
    `subject_title`、`duration_raw`、`duration_minutes`、`raw`，可选 `session_raw`
    与 `date_note`。响应顶层给出 `source`（PDF 文件名、sha256、页数与来源 URL）
    与 `count`（本次返回条数）、`total`（过滤后总条数）。

    错误语义：考季有归档证据表明不可得（或 Edexcel 已取消）→ 404（detail 带
    reason/evidence）；考季写法或年份从未收录 → 422；快照文件缺失 → 503。
    """
    board_key = _normalize_board(board)
    if board_key == "cie":
        if family:
            raise HTTPException(status_code=422, detail="family 仅适用于 board=edexcel")
        if r_paper:
            raise HTTPException(status_code=422, detail="r_paper 仅适用于 board=edexcel")
        key = _resolve_cie_season(year, season)
    else:
        key = _resolve_edexcel_season(family, year, season, r_paper)
    payload = load_season(board_key, key)
    events = payload.get("events", [])

    if subject:
        code = subject.strip()
        events = [
            event
            for event in events
            if event.get("subject_code") == code or str(event.get("subject_code", "")).startswith(code)
        ]
    if date:
        if not _DATE_RE.match(date.strip()):
            raise HTTPException(status_code=422, detail=f"date 需为 ISO 格式 YYYY-MM-DD: {date!r}")
        wanted = date.strip()
        events = [event for event in events if event.get("date") == wanted]
    if session:
        token = session.strip().upper()
        if token not in _SESSIONS:
            raise HTTPException(status_code=422, detail=f"session 只支持 AM/PM/EV: {session!r}")
        events = [event for event in events if event.get("session") == token]
    if level:
        if board_key != "cie":
            raise HTTPException(status_code=422, detail="level 仅适用于 CIE 时间表")
        token = level.strip().upper()
        if token not in _LEVELS:
            raise HTTPException(status_code=422, detail=f"level 只支持 {'/'.join(sorted(_LEVELS))}: {level!r}")
        events = [event for event in events if event.get("level") == token]

    total = len(events)
    page = events[offset : offset + limit]
    response: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "board": payload.get("board", board_key),
        "year": payload.get("year", year),
        "season": payload.get("season"),
        "key": key,
        "source": payload.get("source", {}),
        "count": len(page),
        "total": total,
        "offset": offset,
        "limit": limit,
        "events": page,
    }
    if board_key == "cie":
        response["zone"] = ZONE
    else:
        response["family"] = payload.get("family")
        response["variant"] = payload.get("variant")
    return response


@router.get("/timetable/windows")
def get_timetable_windows(
    year: int = Query(..., description="考季年，如 2026"),
    season: str = Query(
        ..., description="考季：CIE Jun/June、Nov/November；Edexcel Jan/June/Oct/Nov（大小写不敏感）"
    ),
    board: str = Query("cie", description="考试局：cie / edexcel"),
    family: str | None = Query(
        None, description="Edexcel 系列：gcse / intgcse / ial / gce（board=edexcel 必填）"
    ),
    r_paper: bool = Query(False, description="Edexcel R 卷（仅 board=edexcel 生效）"),
) -> dict[str, Any]:
    """按考季返回 "Test date windows"：各 syllabus/component 的考试日期窗口。

    CIE 每行含 `syllabus_name`、`syllabus_code`、`component_code`、`level`、
    `window_raw`（PDF 原文）与 `window_start` / `window_end`（ISO，解析不出时为
    null）；Edexcel 每行含 `subject_code`、`paper_code`、`subject_title`、
    `window_raw` 与 `window_start` / `window_end`。错误语义与 `/api/v1/timetable`
    一致：取消考季与不可得考季 404，未收录考季 422。
    """
    board_key = _normalize_board(board)
    if board_key == "cie":
        if family:
            raise HTTPException(status_code=422, detail="family 仅适用于 board=edexcel")
        if r_paper:
            raise HTTPException(status_code=422, detail="r_paper 仅适用于 board=edexcel")
        key = _resolve_cie_season(year, season)
    else:
        key = _resolve_edexcel_season(family, year, season, r_paper)
    payload = load_season(board_key, key)
    windows = payload.get("date_windows", [])
    response: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "board": payload.get("board", board_key),
        "year": payload.get("year", year),
        "season": payload.get("season"),
        "key": key,
        "source": payload.get("source", {}),
        "count": len(windows),
        "date_windows": windows,
    }
    if board_key == "cie":
        response["zone"] = ZONE
    else:
        response["family"] = payload.get("family")
        response["variant"] = payload.get("variant")
    return response
