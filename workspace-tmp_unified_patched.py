"""统一网关（/api/v1）：把两个上游考试局收进同一套调用形态。

存在的理由：paperqa 层与数据库层的 board 命名不一致——paperqa 认 `cie` /
`edexcel`，数据库 `board.key` 是 `cambridge` / `edexcel`；考季的写法同样两套
（数据库里是 `june` / `june 2025` / `november 2025` 这种自由文本，paperqa 只认
`Mar` / `Jun` / `Nov` 与 `January` / `June` / `October` / `November`）。
调用方不该知道这些差异。本模块是**唯一**的归一位置。

三件归一：

1. board 别名（`cie` / `cambridge` / `ca` / `pearson` ...）→ 规范名 + 数据库 key；
2. 未显式给 board 时按科目代码形态自动判定（四位数字 → cie，其余 → edexcel）；
3. 考季写法 → 该考试局认的考季名，单题视图给出的 `paper_endpoint` 因此是
   真的可以直接调用的，而不是"看起来像"的字符串。

本模块只做归一与转发，不改变既有 `/paper-qa/*` 与数据库检索端点的行为——
那两条出口保持原样，便于回归对比。所有响应都在顶层带 `board` 与
`board_source`（`explicit` 表示调用方显式给了 board，`inferred` 表示系统判的）。
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any, Optional
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..core.db import init_db, session_scope
from ..core.models import Board, Document, ExamSeries, Subject
from ..paperqa import query as paperqa_query
from ..paperqa import resolve as paperqa_resolve
from ..paperqa.api import json_payload, response_payload
from ..paperqa.errors import PaperQAError
from ..paperqa.models import CIE_SEASONS, EDEXCEL_SEASONS
from ..paperqa.sources.cie_fraft import ORIGIN as CIE_ORIGIN
from ..paperqa.sources.pearson import ORIGIN as PEARSON_ORIGIN
from ..query import (
    QuestionFilter,
    count_questions,
    get_question_bundle,
    search_questions,
)

# 网关自身的 schema 版本，与 paperqa 的 SCHEMA_VERSION 无关：
# 网关的字段增删（如新增 board 元信息）由这个号标识。
SCHEMA_VERSION = "1"

router = APIRouter(prefix="/api/v1", tags=["unified"])


# --------------------------------------------------------------------------
# board 归一
# --------------------------------------------------------------------------

# 规范名 -> 该考试局全部可接受的别名（含规范名自身）。
BOARD_ALIASES: dict[str, tuple[str, ...]] = {
    "cie": ("cie", "cambridge", "ca"),
    "edexcel": ("edexcel", "edx", "pearson", "ial"),
}

# 规范名 -> 数据库 board.key。两张命名表就在这里对接，别处不再重复。
BOARD_DB_KEY: dict[str, str] = {"cie": "cambridge", "edexcel": "edexcel"}
DB_KEY_TO_CANONICAL: dict[str, str] = {db: canon for canon, db in BOARD_DB_KEY.items()}

_ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: canonical
    for canonical, aliases in BOARD_ALIASES.items()
    for alias in aliases
}

# 考季别名表直接复用 paperqa 的，避免两处各写一份后漂移。
_SEASON_TABLES: dict[str, dict[str, str]] = {
    "cie": CIE_SEASONS,
    "edexcel": EDEXCEL_SEASONS,
}

# exam_series.month 是数字时的兜底映射（该列目前多为空，属于防御性处理）。
_MONTH_SEASONS: dict[str, dict[int, str]] = {
    "cie": {3: "mar", 6: "jun", 11: "nov"},
    "edexcel": {1: "jan", 6: "jun", 10: "oct", 11: "nov"},
}

# 科目代码形态：四位数字判为 CIE，其余判为 Edexcel。
RE_CIE_SUBJECT = re.compile(r"\d{4}")

BOARD_META: dict[str, dict[str, Any]] = {
    "cie": {
        "name": "Cambridge International",
        "upstream": urlsplit(CIE_ORIGIN).hostname,
        "subject_hint": "四位数字科目代码，如 0580 / 9709",
        "subject_pattern": r"^\d{4}$",
        "seasons": ["Mar", "Jun", "Nov"],
        "modes": ["qp", "ms", "both"],
        "question_crop": False,
        "default_mode": "qp",
    },
    "edexcel": {
        "name": "Pearson Edexcel",
        "upstream": urlsplit(PEARSON_ORIGIN).hostname,
        "subject_hint": "Pearson 规格代码或科目名（非四位数字），如 ial18-accounting / accounting",
        "subject_pattern": r"^(?!\d{4}$).+$",
        "seasons": ["January", "June", "October", "November"],
        "modes": ["paper", "question", "qa"],
        "question_crop": True,
        "default_mode": "paper",
    },
}

AUTO_DETECT: dict[str, Any] = {
    "rule": "未显式传 board 时：科目代码去空白后匹配四位数字则判为 cie，否则判为 edexcel",
    "cie_subject_pattern": r"^\d{4}$",
    "fallback_board": "edexcel",
    "explicit_board_wins": True,
}


def infer_board(subject: str) -> str:
    """按科目代码形态自动判定考试局：四位数字 → `cie`，其余 → `edexcel`。"""
    return "cie" if RE_CIE_SUBJECT.fullmatch(str(subject).strip()) else "edexcel"


def normalize_board(value: Optional[str]) -> Optional[str]:
    """board 别名归一（大小写不敏感）。无法识别 → 422。"""
    if value is None:
        return None
    canonical = _ALIAS_TO_CANONICAL.get(str(value).strip().lower())
    if canonical is None:
        raise HTTPException(
            status_code=422,
            detail=f"无法识别的 board: {value}（可用别名：cie/cambridge/ca 或 edexcel/edx/pearson/ial）",
        )
    return canonical


def resolve_board(value: Optional[str], subject: str) -> tuple[str, str]:
    """确定本次请求的 board，返回 `(规范名, 来源)`。

    显式传入时以显式为准（来源 `explicit`），否则按科目代码形态判定
    （来源 `inferred`）。
    """
    canonical = normalize_board(value)
    if canonical is not None:
        return canonical, "explicit"
    return infer_board(subject), "inferred"


def normalize_season(
    session: Optional[str], board: Optional[str], month: Optional[int] = None
) -> Optional[str]:
    """把数据库里的考季写法归一成该考试局认的考季名，识别不了时返回 None。

    `exam_series.session` 的实际取值不规范（`june` / `june 2025` /
    `november 2025`），先按非字母切词逐个查别名表，再退回 `month` 数字。
    CIE 只认 Mar / Jun / Nov，Edexcel 认 January / June / October / November。
    """
    table = _SEASON_TABLES.get(board or "")
    if table is None:
        return None
    for token in re.split(r"[^a-z]+", str(session or "").lower()):
        if token in table:
            return table[token]
    key = _MONTH_SEASONS[board].get(month) if month is not None else None
    return table.get(key) if key else None


def _paper_endpoint(
    board: Optional[str],
    subject_code: Optional[str],
    year: Optional[int],
    season: Optional[str],
    paper_code: Optional[str],
) -> Optional[str]:
    """拼出可直接调用的取卷 URL；缺关键定位信息时返回 None。

    只给相对路径，网关挂在哪个主机、哪个前缀下都能用。mode 用该考试局的
    默认值（CIE `qp`、Edexcel `paper`），因为题目来自哪份卷子由 paper 指定。
    """
    if not (board and subject_code and year and season):
        return None
    params = {
        "subject": subject_code,
        "year": str(year),
        "season": season,
        "mode": BOARD_META[board]["default_mode"],
    }
    if paper_code:
        params["paper"] = paper_code
    return f"/api/v1/paper?{urlencode(params)}"


def get_session():
    """每请求一个 session。

    与 `api.app.get_session` 同语义。这里自带一份是因为 `api.app` 需要
    import 本模块来挂路由，反向 import 会成环。
    """
    init_db()
    with session_scope() as session:
        yield session


# --------------------------------------------------------------------------
# 能力发现
# --------------------------------------------------------------------------


@router.get(
    "/boards",
    summary="考试局能力清单（含别名、考季、模式与自动判定规则）",
    description=(
        "无参数。调用方据此决定 subject / season / mode 该传什么，"
        "不必读文档或猜。\n\n"
        "`aliases` 是 board 参数可接受的写法；`db_key` 是该考试局在数据库"
        "`board.key` 里的名字（检索接口返回的 `board` 字段用它）；`upstream` 是"
        "上游主机名；`subject_hint` / `subject_pattern` 描述科目代码形态；"
        "`question_crop` 表示上游是否支持按题裁剪（CIE 只给整卷）。\n\n"
        "`auto_detect` 描述未显式传 board 时的判定规则：科目代码去空白后是四位"
        "数字判为 cie，否则判为 edexcel。"
    ),
)
def list_boards() -> dict[str, Any]:
    """跨考试局能力发现。"""
    boards = []
    for canonical in ("cie", "edexcel"):
        meta = BOARD_META[canonical]
        boards.append(
            {
                "board": canonical,
                "aliases": list(BOARD_ALIASES[canonical]),
                "db_key": BOARD_DB_KEY[canonical],
                "name": meta["name"],
                "upstream": meta["upstream"],
                "subject_hint": meta["subject_hint"],
                "subject_pattern": meta["subject_pattern"],
                "seasons": list(meta["seasons"]),
                "season_aliases": list(_SEASON_TABLES[canonical]),
                "modes": list(meta["modes"]),
                "question_crop": meta["question_crop"],
                "default_mode": meta["default_mode"],
            }
        )
    return {"schema_version": SCHEMA_VERSION, "auto_detect": AUTO_DETECT, "boards": boards}


# --------------------------------------------------------------------------
# 统一取卷
# --------------------------------------------------------------------------


@router.get(
    "/paper",
    summary="统一取卷（解析清单与下载合一，board 可自动判定）",
    description=(
        "把 `/paper-qa/resolve` 与 `/paper-qa/query` 合成一个入口，并按科目代码"
        "形态自动判定 board（`board` 显式传入时以显式为准）。\n\n"
        "三种出口：\n"
        "- `download=false`：只解析清单，schema 与 `GET /paper-qa/resolve` 完全一致；\n"
        "- `download=true`（默认）且 `format` 不是 `json`：返回原始字节——单文件是"
        "PDF，多文件（`mode=both` / `mode=qa`）在内存里打 ZIP，响应头带"
        "`Content-Disposition` 与 `Content-Length`；\n"
        "- `download=true&format=json`：base64 内联载荷，schema 与"
        "`GET /paper-qa/query?format=json` 完全一致。\n\n"
        "前两种 JSON 出口另加 `board`（规范名 `cie` / `edexcel`）与 `board_source`"
        "（`explicit` / `inferred`）。`format` 只接受 `binary` 与 `json`，"
        "其它值一律 422。\n\n"
        "上游与参数错误按 `PaperQAError.status_code` 转成 FastAPI 的"
        "`{\"detail\": ...}`：422 参数非法、404 上游没有对应文件、403 非公开资源、"
        "409 命中多份候选、502 上游故障。"
    ),
)
def unified_paper(
    subject: str = Query(..., description="科目代码，如 0580；也用于自动判定 board"),
    year: int = Query(..., description="考试年份，2000..2099"),
    season: str = Query(..., description="考季，取值见 /api/v1/boards 的 seasons"),
    board: Optional[str] = Query(None, description="考试局别名，如 cie / cambridge / pearson；不传则自动判定"),
    paper: Optional[str] = Query(None, description="Paper 代码，如 11 / wec11-01"),
    question: Optional[str] = Query(None, description="题号，如 2(a)；仅 Edexcel 的 question/qa 模式支持"),
    mode: Optional[str] = Query(None, description="qp/ms/both（CIE）或 paper/question/qa（Edexcel）"),
    download: bool = Query(True, description="true 取回文件字节；false 只解析清单"),
    format: Optional[str] = Query(
        None, description="binary（默认，原始字节/ZIP）或 json（base64 + 元数据）"
    ),
):
    """统一取卷：解析 + 下载合一。"""
    if format not in (None, "binary", "json"):
        raise HTTPException(status_code=422, detail="format must be binary or json")
    canonical, board_source = resolve_board(board, subject)
    try:
        if not download:
            manifest = paperqa_resolve(
                canonical, subject, year, season, paper, question, mode
            ).metadata()
            return {**manifest, "board": canonical, "board_source": board_source}
        if format == "json":
            payload = json_payload(
                paperqa_query(canonical, subject, year, season, paper, question, mode)
            )
            return {**payload, "board": canonical, "board_source": board_source}
        file = response_payload(
            paperqa_query(canonical, subject, year, season, paper, question, mode)
        )
    except PaperQAError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return Response(
        file.data,
        media_type=file.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file.name}"',
            "Content-Length": str(len(file.data)),
        },
    )


# --------------------------------------------------------------------------
# 跨考试局检索
# --------------------------------------------------------------------------


@router.get(
    "/search",
    summary="跨考试局统一检索（读数据库）",
    description=(
        "一条查询同时覆盖两个考试局：`items` 与 `GET /questions` 的 `items` "
        "形状完全一致（已含 `board` 字段，值是数据库 key `cambridge` / "
        "`edexcel`），`by_board` 给出同一组条件下各考试局的命中数——"
        "跨局检索时\"某一局没有结果\"和\"这一局根本没有数据\"是两件事，必须能区分。\n\n"
        "`board` 走别名归一（`cie` / `cambridge` / `ca` / `edexcel` / `edx` / "
        "`pearson` / `ial`），不传则不限考试局。顶层 `board` 是归一后的规范名"
        "（未传时为 null），`by_board` 的键是数据库 key。\n\n"
        "`session` 是数据库里的原始考季写法（如 `june` / `june 2025`），"
        "与 `/questions` 的 `session` 语义一致，不做归一。"
    ),
)
def unified_search(
    keyword: Optional[str] = Query(None, description="题干关键词"),
    subject: Optional[str] = Query(None, description="科目代码，如 0580"),
    board: Optional[str] = Query(None, description="考试局别名，不传则跨局检索"),
    year: Optional[int] = None,
    session_name: Optional[str] = Query(None, alias="session", description="数据库原始考季写法"),
    paper: Optional[str] = None,
    marks_min: Optional[int] = None,
    marks_max: Optional[int] = None,
    leaves_only: bool = Query(False, description="只取可独立作答的叶子题"),
    has_answer: Optional[bool] = Query(None, description="是否要求有官方答案"),
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """跨考试局检索题目。"""
    canonical = normalize_board(board)
    f = QuestionFilter(
        board=BOARD_DB_KEY[canonical] if canonical else None,
        subject_code=subject,
        year=year,
        session=session_name,
        paper_code=paper,
        keyword=keyword,
        marks_min=marks_min,
        marks_max=marks_max,
        leaves_only=leaves_only,
        has_official_answer=has_answer,
        limit=limit,
        offset=offset,
    )
    # 分局计数复用同一份条件，只换 board；这样 by_board 与 total 一定自洽。
    by_board = {
        db_key: count_questions(db, dataclasses.replace(f, board=db_key))
        for db_key in ("cambridge", "edexcel")
    }
    return {
        "total": count_questions(db, f),
        "limit": limit,
        "offset": offset,
        "by_board": by_board,
        "items": search_questions(db, f),
        "board": canonical,
        "board_source": "explicit" if canonical else None,
    }


# --------------------------------------------------------------------------
# 单题聚合视图
# --------------------------------------------------------------------------


@router.get(
    "/question/{question_id}",
    summary="单题聚合视图（题目内容 + 所属试卷定位 + 可直接调用的取卷入口）",
    description=(
        "一次请求拿到两件事：`bundle` 是 `GET /questions/{id}` 的原样结果"
        "（题干、层级、图形资产、官方答案、评分条目、知识点、难度、相似题），"
        "`source` 是这道题所属试卷的定位信息。\n\n"
        "`source.board` 是数据库 key（`cambridge` / `edexcel`），"
        "`source.board_canonical` 是统一层规范名（`cie` / `edexcel`）；"
        "`source.session` 已把数据库里不规范的考季写法归一成 paperqa 认的考季名，"
        "并保留原始值在 `session_raw`。`source.paper_endpoint` 是可直接调用的"
        "相对 URL（形如 `/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&mode=qp`），"
        "原样请求它就能取到该卷 PDF；只有当这道题缺少年份/考季/科目等定位信息时"
        "（例如无考季的样卷）才为 null，绝不拼一个取不回来的 URL。\n\n"
        "题目不存在 → 404。"
    ),
)
def unified_question(
    question_id: int, db: Session = Depends(get_session)
) -> dict[str, Any]:
    """单题聚合视图：内容 + 来源定位 + 取卷入口。"""
    bundle = get_question_bundle(db, question_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail=f"题目 {question_id} 不存在")

    document_id = bundle["paper"]["document_id"]
    doc = db.get(Document, document_id) if document_id else None
    if doc is None:
        raise HTTPException(
            status_code=404, detail=f"题目 {question_id} 所属试卷不存在"
        )
    board = db.get(Board, doc.board_id)
    subject = db.get(Subject, doc.subject_id) if doc.subject_id else None
    series = db.get(ExamSeries, doc.series_id) if doc.series_id else None

    db_key = board.key if board else None
    canonical = DB_KEY_TO_CANONICAL.get(db_key or "")
    session = normalize_season(
        series.session if series else None,
        canonical,
        series.month if series else None,
    )
    subject_code = subject.code if subject else None
    return {
        "question_id": question_id,
        "board": db_key,
        "board_source": "inferred",
        "source": {
            "board": db_key,
            "board_canonical": canonical,
            "subject_code": subject_code,
            "year": doc.year,
            "session": session,
            "session_raw": series.session if series else None,
            "paper_code": doc.paper_code,
            "document_id": doc.id,
            "doc_type": doc.doc_type,
            "paper_endpoint": _paper_endpoint(
                canonical, subject_code, doc.year, session, doc.paper_code
            ),
        },
        "bundle": bundle,
    }
