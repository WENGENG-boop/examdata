"""Cambridge 只读对照评估：同一个 BM25 打分器，换一套候选节点。

对照口径
--------
- 候选 = 该科目 cambridge 种子节点里的 **subtopic**（叶子层，与 keyword-v1 的主挂载点同级）。
  种子节点没有 ``attrs.text``，因此文档只用 ``name``（祖先 topic 名照旧加权合并），
  这是"同一打分器"的公平下限：信息量比 Edexcel 官方大纲原文少得多。
- keyword-v1 的 top-1 = 该题所有挂载行里 confidence 最高的那一行
  （它同时挂 subtopic 与其父 topic，父节点行按 0.9 倍记，因此 top-1 通常是 subtopic）。
- 一致率给三个口径：
  * strict：两边 top-1 的 code 完全相同；
  * lenient：BM25 的 top-1 落在 keyword-v1 挂过的任一节点上（部分正确也算命中）；
  * top3：keyword-v1 的 top-1 出现在 BM25 的前三名里（排序没跑偏，只是第一名不同）。

本模块**只读**：不 add、不 delete、不 flush，也不写任何文件。
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.models import Board, QuestionTaxonomy, TaxonomyNode
from .assign import CALIBRATION, TOP_K, rank_question
from .corpus import CorpusSet, PointCandidate, iter_questions

BOARD_KEY = "cambridge"
STEM_PREVIEW_CHARS = 220


def load_seed_points(session: Session, *, board_key: str = BOARD_KEY) -> list[PointCandidate]:
    """cambridge 种子节点 → 候选内容点（只用 name 与祖先名，没有 attrs.text）。"""
    board = session.scalar(select(Board).where(Board.key == board_key))
    if board is None:
        return []
    nodes = list(session.scalars(select(TaxonomyNode).where(TaxonomyNode.board_id == board.id)))
    by_id = {node.id: node for node in nodes}
    out: list[PointCandidate] = []
    for node in nodes:
        if node.node_type != "subtopic":
            continue
        attrs = node.attrs if isinstance(node.attrs, dict) else {}
        subject = attrs.get("subject_code")
        if not isinstance(subject, str) or not subject.strip():
            continue
        ancestors: list[str] = []
        parent_id = node.parent_id
        depth = 0
        while parent_id is not None and depth < 4:
            parent = by_id.get(parent_id)
            if parent is None:
                break
            ancestors.append(parent.name)
            parent_id = parent.parent_id
            depth += 1
        out.append(
            PointCandidate(
                node_id=node.id,
                code=node.code,
                name=node.name,
                text="",
                subject=subject.strip().lower(),
                unit_code=None,
                ancestors=tuple(ancestors),
            )
        )
    out.sort(key=lambda point: point.code)
    return out


def _keyword_rows(session: Session, *, board_key: str = BOARD_KEY) -> dict[int, dict[str, Any]]:
    """每题一行：{top1: {...}, codes: set, methods: set}。"""
    stmt = (
        select(
            QuestionTaxonomy.question_id,
            QuestionTaxonomy.confidence,
            QuestionTaxonomy.assigned_by,
            TaxonomyNode.code,
            TaxonomyNode.name,
        )
        .join(TaxonomyNode, TaxonomyNode.id == QuestionTaxonomy.node_id)
        .join(Board, Board.id == TaxonomyNode.board_id)
        .where(Board.key == board_key)
        .order_by(QuestionTaxonomy.question_id, TaxonomyNode.code)
    )
    grouped: dict[int, dict[str, Any]] = {}
    for question_id, confidence, assigned_by, code, name in session.execute(stmt):
        entry = grouped.setdefault(
            question_id, {"top1": None, "codes": set(), "methods": set(), "rows": 0}
        )
        entry["rows"] += 1
        entry["codes"].add(code)
        entry["methods"].add(assigned_by or "")
        current = entry["top1"]
        candidate = (float(confidence or 0.0), code, name)
        if current is None or (-candidate[0], candidate[1]) < (-current[0], current[1]):
            entry["top1"] = candidate
    return grouped


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def evaluate_cambridge(
    session: Session,
    *,
    examples: int = 10,
    subject: Optional[str] = None,
    board_key: str = BOARD_KEY,
) -> dict[str, Any]:
    """跑一遍只读评估，返回覆盖率 / 一致率 / 分歧样例。"""
    points = load_seed_points(session, board_key=board_key)
    report: dict[str, Any] = {
        "board": board_key,
        "candidates": len(points),
        "subjects": sorted({point.subject or "" for point in points}),
        "questions": 0,
        "bm25_assigned": 0,
        "bm25_coverage": 0.0,
        "keyword_assigned": 0,
        "keyword_coverage": 0.0,
        "both": 0,
        "agree_top1": 0,
        "agreement_strict": 0.0,
        "agree_any": 0,
        "agreement_lenient": 0.0,
        "agree_top3": 0,
        "agreement_top3": 0.0,
        "bm25_only": 0,
        "keyword_only": 0,
        "neither": 0,
        "keyword_methods": [],
        "per_subject": {},
        "disagreements": [],
    }
    if not points:
        return report

    corpora = CorpusSet(points)
    keyword = _keyword_rows(session, board_key=board_key)
    questions = iter_questions(session, board_key=board_key, subject=subject)
    methods: set[str] = set()
    per_subject: dict[str, dict[str, int]] = {}
    disagreements: list[dict[str, Any]] = []

    for question in questions:
        report["questions"] += 1
        bucket = per_subject.setdefault(
            (question.subject_code or "unknown").lower(),
            {"questions": 0, "bm25_assigned": 0, "keyword_assigned": 0, "agree_top1": 0, "agree_any": 0},
        )
        bucket["questions"] += 1

        _, candidates = rank_question(corpora, question, calibration=CALIBRATION, top_k=TOP_K)
        bm25_top = candidates[0] if candidates else None
        kw = keyword.get(question.question_id)
        if kw:
            methods.update(kw["methods"])
        kw_top = kw["top1"] if kw else None

        if bm25_top is not None:
            report["bm25_assigned"] += 1
            bucket["bm25_assigned"] += 1
        if kw_top is not None:
            report["keyword_assigned"] += 1
            bucket["keyword_assigned"] += 1

        if bm25_top is None and kw_top is None:
            report["neither"] += 1
            continue
        if bm25_top is None:
            report["keyword_only"] += 1
            continue
        if kw_top is None:
            report["bm25_only"] += 1
            continue

        report["both"] += 1
        same = bm25_top.code == kw_top[1]
        if same:
            report["agree_top1"] += 1
            bucket["agree_top1"] += 1
        elif bm25_top.code in kw["codes"]:
            report["agree_any"] += 1
            bucket["agree_any"] += 1
        elif len(disagreements) < examples:
            disagreements.append(
                {
                    "question_id": question.question_id,
                    "number_label": question.number_label,
                    "subject": question.subject_code,
                    "stem": " ".join(question.stem_text.split())[:STEM_PREVIEW_CHARS],
                    "keyword_top1": {"code": kw_top[1], "name": kw_top[2], "confidence": round(kw_top[0], 4)},
                    "bm25_top1": {
                        "code": bm25_top.code,
                        "name": bm25_top.name,
                        "score": bm25_top.score,
                        "confidence": bm25_top.confidence,
                    },
                }
            )
        if kw_top[1] in {candidate.code for candidate in candidates}:
            report["agree_top3"] += 1

    both = report["both"]
    report["bm25_coverage"] = _ratio(report["bm25_assigned"], report["questions"])
    report["keyword_coverage"] = _ratio(report["keyword_assigned"], report["questions"])
    report["agreement_strict"] = _ratio(report["agree_top1"], both)
    report["agreement_lenient"] = _ratio(report["agree_top1"] + report["agree_any"], both)
    report["agreement_top3"] = _ratio(report["agree_top3"], both)
    report["keyword_methods"] = sorted(method for method in methods if method)
    for name, bucket in sorted(per_subject.items()):
        bucket["agreement_strict"] = _ratio(bucket["agree_top1"], bucket["keyword_assigned"])
    report["per_subject"] = per_subject
    report["disagreements"] = disagreements
    return report


__all__ = ["BOARD_KEY", "evaluate_cambridge", "load_seed_points"]
