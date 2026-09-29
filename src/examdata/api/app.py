"""只读检索 API（需求：题目检索能力 / 试卷检索能力 / 随机抽题 / 后台监控）。

设计取舍：
- **只读**。写入类操作（人工修正、重新解析）走 CLI 与后台任务，不开放匿名写接口，
  避免"生成内容与官方内容物理隔离"这条约束被绕过。
- **无状态**。每次请求开一个 SQLAlchemy session，连接池交给引擎。
- 响应字段与 `examdata.query` 的返回结构一一对应，不做二次包装，
  这样 CLI 与 HTTP 两条出口返回的数据形态完全一致。

启动：
    examdata serve --host 127.0.0.1 --port 8000
    uvicorn examdata.api.app:app --reload
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.db import init_db, session_scope
from ..query import (
    PaperFilter,
    QuestionFilter,
    board_health,
    count_papers,
    count_questions,
    get_paper_tree,
    get_question_bundle,
    review_queue,
    sample_questions,
    search_papers,
    search_questions,
    similar_questions,
    sync_status,
    taxonomy_tree,
)

from ..paperqa import query as paperqa_query, resolve as paperqa_resolve
from ..paperqa.api import json_payload, response_payload
from ..paperqa.errors import PaperQAError
from fastapi.responses import Response


app = FastAPI(
    title="国际考试真题统一数据服务",
    description="试卷检索 / 题目检索 / 单题完整内容 / 整卷题目树 / 随机抽题 / 后台监控",
    version="0.1.0",
)


@app.get(
    "/paper-qa/resolve",
    summary="解析真题清单（不下载文件）",
    description=(
        "只解析官方清单，返回可 JSON 序列化的 manifest："
        "`schema_version` / `request` / `counts` / `documents` / `files`。\n\n"
        "本接口从不下载文件，因此 `files` 恒为空数组——它只回答"
        "\"这个组合对应哪些官方文件\"，不回答\"文件内容是什么\"。\n\n"
        "错误体固定为 FastAPI 的 `{\"detail\": ...}`：422 参数非法、"
        "404 上游没有对应文件、403 非公开资源、409 命中多份候选、502 上游故障。"
    ),
)
def paper_qa_resolve(
    board: str, subject: str, year: int, season: str,
    paper: Optional[str] = None, question: Optional[str] = None, mode: Optional[str] = None,
):
    try:
        return paperqa_resolve(board, subject, year, season, paper, question, mode).metadata()
    except PaperQAError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get(
    "/paper-qa/query",
    summary="取回真题文件（默认二进制；format=json 走 base64）",
    description=(
        "解析并下载：单文件直接返回原始字节，多文件（`mode=both` / `mode=qa`）"
        "在内存里打 `application/zip`。二进制响应带 `Content-Disposition`"
        "（含文件名）与 `Content-Length`，客户端可直接落盘。\n\n"
        "`format=json` 供处理不了二进制的客户端使用：返回与 `/paper-qa/resolve`"
        "和 CLI `--json` 同一套 schema 的 JSON，每个文件额外带 `data_base64`"
        "（载荷的 base64）、`sha256` 与裁剪来源 `page` / `bbox`。\n\n"
        "服务端全程只在内存中处理，不落盘；需要文件请由客户端自行保存。"
    ),
)
def paper_qa_query(
    board: str, subject: str, year: int, season: str,
    paper: Optional[str] = None, question: Optional[str] = None, mode: Optional[str] = None,
    format: Optional[str] = Query(
        None, description="binary（默认，返回原始字节/ZIP）或 json（base64 + 元数据）"
    ),
):
    if format not in (None, "binary", "json"):
        raise HTTPException(status_code=422, detail="format must be binary or json")
    try:
        result = paperqa_query(board, subject, year, season, paper, question, mode)
        if format == "json":
            return json_payload(result)
        file = response_payload(result)
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


def get_session():
    """每请求一个 session。"""
    init_db()
    with session_scope() as session:
        yield session


@app.get("/health")
def health() -> dict[str, Any]:
    """存活探针，同时确认数据库可达。"""
    try:
        with session_scope() as session:
            total = count_papers(session, PaperFilter())
        return {"status": "ok", "papers": total}
    except Exception as exc:  # pragma: no cover - 只在数据库不可用时触发
        raise HTTPException(status_code=503, detail=f"数据库不可用: {exc}") from exc


@app.get("/papers")
def list_papers(
    board: Optional[str] = None,
    qualification: Optional[str] = None,
    subject: Optional[str] = Query(None, description="科目代码，如 0580"),
    year: Optional[int] = None,
    session_name: Optional[str] = Query(None, alias="session"),
    paper: Optional[str] = Query(None, description="Paper 代码，如 11"),
    component: Optional[str] = None,
    variant: Optional[str] = None,
    level: Optional[str] = None,
    doc_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """按考试信息检索试卷。"""
    f = PaperFilter(
        board=board,
        qualification=qualification,
        subject_code=subject,
        year=year,
        session=session_name,
        paper_code=paper,
        component=component,
        variant=variant,
        level=level,
        doc_type=doc_type,
        limit=limit,
        offset=offset,
    )
    return {"total": count_papers(db, f), "limit": limit, "offset": offset, "items": search_papers(db, f)}


@app.get("/questions")
def list_questions(
    board: Optional[str] = None,
    subject: Optional[str] = None,
    year: Optional[int] = None,
    session_name: Optional[str] = Query(None, alias="session"),
    paper: Optional[str] = None,
    level: Optional[str] = None,
    number_path: Optional[str] = Query(None, description="题号路径，如 1(a)"),
    keyword: Optional[str] = Query(None, description="题干关键词"),
    marks_min: Optional[int] = None,
    marks_max: Optional[int] = None,
    leaves_only: bool = Query(False, description="只取可独立作答的叶子题"),
    roots_only: bool = Query(False, description="只取大题"),
    has_asset: Optional[bool] = Query(None, description="是否要求带图形/图表"),
    has_answer: Optional[bool] = Query(None, description="是否要求有官方答案"),
    taxonomy: Optional[str] = Query(None, description="知识点代码"),
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """题目级检索。"""
    f = QuestionFilter(
        board=board,
        subject_code=subject,
        year=year,
        session=session_name,
        paper_code=paper,
        level=level,
        number_path=number_path,
        keyword=keyword,
        marks_min=marks_min,
        marks_max=marks_max,
        leaves_only=leaves_only,
        roots_only=roots_only,
        has_asset=has_asset,
        has_official_answer=has_answer,
        taxonomy_code=taxonomy,
        limit=limit,
        offset=offset,
    )
    return {
        "total": count_questions(db, f),
        "limit": limit,
        "offset": offset,
        "items": search_questions(db, f),
    }


@app.get("/questions/{question_id}")
def question_detail(question_id: int, db: Session = Depends(get_session)) -> dict[str, Any]:
    """单题完整内容：题干、层级、图形资产、官方答案、评分条目、知识点、难度。"""
    bundle = get_question_bundle(db, question_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail=f"题目 {question_id} 不存在")
    return bundle


@app.get("/questions/{question_id}/similar")
def question_similar(
    question_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """相似题（需求：相似题识别）。同型题、同知识点换数字的重复题。"""
    from ..core.models import Question

    if db.get(Question, question_id) is None:
        raise HTTPException(status_code=404, detail=f"题目 {question_id} 不存在")
    items = similar_questions(db, question_id, limit=limit)
    return {"question_id": question_id, "count": len(items), "items": items}


@app.get("/taxonomy")
def taxonomy(
    board: Optional[str] = None,
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """知识点体系（topic -> subtopic），带每题计数。"""
    roots = taxonomy_tree(db, board=board)
    return {"roots": roots, "topic_count": len(roots)}


@app.get("/papers/{paper_id}/tree")
def paper_tree(paper_id: int, db: Session = Depends(get_session)) -> dict[str, Any]:
    """整卷题目树。"""
    tree = get_paper_tree(db, paper_id)
    if tree is None:
        raise HTTPException(status_code=404, detail=f"试卷 {paper_id} 不存在")
    return tree


@app.post("/sample")
def sample(
    subject: Optional[str] = None,
    year: Optional[int] = None,
    paper: Optional[str] = None,
    marks_min: Optional[int] = None,
    count: Optional[int] = Query(None, ge=1, le=200, description="抽题数量"),
    marks_target: Optional[int] = Query(None, ge=1, le=300, description="目标总分"),
    seed: Optional[int] = Query(None, description="随机种子，便于复现"),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """随机抽题 / 自动组题基础能力（数据层，不含学生端逻辑）。"""
    if count is None and marks_target is None:
        raise HTTPException(status_code=422, detail="count 与 marks_target 至少给一个")
    f = QuestionFilter(
        subject_code=subject,
        year=year,
        paper_code=paper,
        marks_min=marks_min,
        leaves_only=True,
        limit=5000,
    )
    comp = sample_questions(db, f, count=count, marks_target=marks_target, seed=seed)
    return {
        "marks_total": comp.marks_total,
        "requested_marks": comp.requested_marks,
        "question_count": len(comp.questions),
        "questions": comp.questions,
    }


@app.get("/monitor")
def monitor(db: Session = Depends(get_session)) -> dict[str, Any]:
    """后台监控：同步/解析状态、采集健康度、待人工检查队列。"""
    return {
        "sync": sync_status(db),
        "health": board_health(db),
        "review_queue": review_queue(db, limit=200),
    }


@app.get("/questions/{question_id}/provenance")
def question_provenance(
    question_id: int, db: Session = Depends(get_session)
) -> dict[str, Any]:
    """追踪一道题最初来自哪个官方资源、哪份文件、何时被发现。

    需求："需要能够追踪某一份试卷、某一道题、某一个答案、某一份评分标准
    或某一个图片资源最初来自哪个考试局、哪个官方资源以及何时被系统发现和更新。"
    """
    from ..core.models import Question
    from ..governance import trace

    if db.get(Question, question_id) is None:
        raise HTTPException(status_code=404, detail=f"题目 {question_id} 不存在")
    return {"question_id": question_id, "sources": trace(db, "question", question_id)}


@app.get("/assets/{asset_id}/provenance")
def asset_provenance(asset_id: int, db: Session = Depends(get_session)) -> dict[str, Any]:
    """追踪一个图片/图形资产来自哪份官方文件。"""
    from ..core.models import Asset
    from ..governance import trace

    if db.get(Asset, asset_id) is None:
        raise HTTPException(status_code=404, detail=f"资产 {asset_id} 不存在")
    return {"asset_id": asset_id, "sources": trace(db, "asset", asset_id)}


@app.get("/provenance/coverage")
def provenance_coverage(db: Session = Depends(get_session)) -> dict[str, Any]:
    """溯源覆盖率。低于 100% 说明有派生数据追不到来源。"""
    from ..governance import coverage

    cov = coverage(db)
    return {
        "coverage": cov,
        "complete": all(c["ratio"] >= 1.0 for c in cov.values()),
    }


@app.get("/review")
def review(
    status: str = Query("open", description="open / in_progress / done / dismissed"),
    target_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """待人工检查队列（需求：低置信度或冲突数据进入待检查状态）。"""
    from ..governance import list_reviews

    items = list_reviews(db, status=status, target_type=target_type, limit=limit)
    return {"status": status, "count": len(items), "items": items}


@app.get("/overrides")
def overrides(
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    conflicts: bool = Query(False, description="只看冲突未生效的"),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """已登记的人工修正（需求：人工确认后的内容不被自动同步覆盖）。"""
    from ..governance import list_overrides

    items = list_overrides(
        db, target_type=target_type, target_id=target_id, only_conflicts=conflicts
    )
    return {"count": len(items), "items": items}


@app.get("/classifications")
def classifications(
    document_id: Optional[int] = None,
    method: Optional[str] = Query(None, description="label+content / conflict / content / label"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """文件类型判定及其证据（需求：类型判断要结合页面信息与文档内容）。"""
    from sqlalchemy import select as _select

    from ..core.models import DocClassification

    stmt = (
        _select(DocClassification)
        .order_by(DocClassification.id.desc())
        .limit(limit)
    )
    if document_id is not None:
        stmt = stmt.where(DocClassification.document_id == document_id)
    if method:
        stmt = stmt.where(DocClassification.method == method)
    rows = db.scalars(stmt).all()
    items = [
        {
            "id": r.id,
            "document_id": r.document_id,
            "doc_type": r.doc_type,
            "confidence": r.confidence,
            "method": r.method,
            "evidence": r.evidence,
        }
        for r in rows
    ]
    conflicts = sum(1 for i in items if i["method"] == "conflict")
    return {"count": len(items), "conflicts": conflicts, "items": items}


@app.get("/questions/{question_id}/explanation")
def question_explanation(
    question_id: int, db: Session = Depends(get_session)
) -> dict[str, Any]:
    """系统生成的解题解析。

    响应里显式带上 is_official=false 与 review_status：调用方必须能一眼看出
    这是生成内容而不是官方答案，且未审核的内容不应直接展示给学生。
    """
    from sqlalchemy import select as _select

    from ..core.models import GeneratedExplanation, Question, OfficialAnswer

    if db.get(Question, question_id) is None:
        raise HTTPException(status_code=404, detail=f"题目 {question_id} 不存在")

    official = db.scalars(
        _select(OfficialAnswer).where(OfficialAnswer.question_id == question_id)
    ).all()
    generated = db.scalars(
        _select(GeneratedExplanation).where(GeneratedExplanation.question_id == question_id)
    ).all()
    return {
        "question_id": question_id,
        "official": [
            {
                "id": a.id,
                "source": a.source,
                "content": a.content,
                "is_official": a.is_official,
            }
            for a in official
        ],
        "generated": [
            {
                "id": g.id,
                "provider": g.provider,
                "model": g.model,
                "prompt_version": g.prompt_version,
                "approach": g.approach,
                "steps": g.steps,
                "final_answer": g.final_answer,
                "marking_points": g.marking_points,
                "common_errors": g.common_errors,
                "review_status": g.review_status,
                "is_official": g.is_official,
            }
            for g in generated
        ],
    }


@app.get("/explanations/review-queue")
def explanation_review_queue(
    status: str = Query("pending", description="pending / approved / rejected"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_session),
) -> dict[str, Any]:
    """待审核的生成解析队列（需求：生成内容必须与官方内容区分且可人工把关）。"""
    from sqlalchemy import func as _func
    from sqlalchemy import select as _select

    from ..core.models import GeneratedExplanation

    items = db.scalars(
        _select(GeneratedExplanation)
        .where(GeneratedExplanation.review_status == status)
        .order_by(GeneratedExplanation.id)
        .limit(limit)
    ).all()
    total = (
        db.scalar(
            _select(_func.count(GeneratedExplanation.id)).where(
                GeneratedExplanation.review_status == status
            )
        )
        or 0
    )
    return {
        "status": status,
        "total": total,
        "count": len(items),
        "items": [
            {
                "id": g.id,
                "question_id": g.question_id,
                "provider": g.provider,
                "review_status": g.review_status,
            }
            for g in items
        ],
    }


@app.get("/assets/{asset_id}")
def asset_file(asset_id: int, db: Session = Depends(get_session)) -> FileResponse:
    """按内容寻址返回图形资产原件。

    需求"题目被独立提取以后，不能因为拆分而丢失完成该题所需要的图片"，
    因此这里必须能真正取回文件，而不是只返回 storage_key。
    """
    from ..core.models import Asset

    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"资产 {asset_id} 不存在")
    path = get_settings().artifacts_dir / asset.storage_key
    if not path.exists():
        raise HTTPException(status_code=410, detail="资产文件已丢失")
    return FileResponse(path, media_type=asset.mime or "application/octet-stream")
