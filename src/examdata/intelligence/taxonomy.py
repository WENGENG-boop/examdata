"""知识点标注。

策略（分层，可解释、可回溯）：
1. **关键词打分**：把 syllabus 种子里每个 subtopic 的关键词表编译成正则，
   在题干文本上计命中数。命中词越长权重越高（"quadratic formula" 比 "solve" 有信息量）。
2. **只挂 subtopic 与它的父 topic**：不给题目臆造更细的层级。
3. **置信度 = 归一化得分**，低于阈值的题不标注（宁缺毋滥），
   并写 ValidationFinding 让它们进入待补标注队列，而不是随便猜一个。
4. **来源区分**：source="auto"；人工确认后由治理层改成 "manual"。

这一层完全确定性，不依赖外部模型，因此可以随解析重跑而稳定复现。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.models import (
    Board,
    Qualification,
    Question,
    QuestionTaxonomy,
    Subject,
    TaxonomyNode,
)
from .taxonomy_seed import SEEDS


# 关键词权重：词越长越具体，权重越高。
def _keyword_weight(word: str) -> float:
    n = len(word)
    if n >= 14:
        return 3.0
    if n >= 9:
        return 2.2
    if n >= 6:
        return 1.5
    return 1.0


@dataclass
class _Compiled:
    code: str
    name: str
    node_type: str
    parent_code: Optional[str]
    patterns: list[tuple[re.Pattern[str], float]]


def _compile(nodes: Iterable[dict[str, Any]], parent_code: Optional[str] = None) -> list[_Compiled]:
    out: list[_Compiled] = []
    for node in nodes:
        code = node["code"]
        children = node.get("children") or []
        if children:
            out.extend(_compile(children, parent_code=code))
            continue
        pats: list[tuple[re.Pattern[str], float]] = []
        for kw in node.get("keywords", []):
            # 词边界： 对 "sin2"、"3d" 这类词失效，因此改用前后非字母数字。
            pat = re.compile(r"(?<![A-Za-z0-9])" + re.escape(kw) + r"(?![A-Za-z0-9])", re.I)
            pats.append((pat, _keyword_weight(kw)))
        out.append(
            _Compiled(
                code=code,
                name=node["name"],
                node_type="subtopic",
                parent_code=parent_code,
                patterns=pats,
            )
        )
    return out


_COMPILED: dict[str, list[_Compiled]] = {code: _compile(nodes) for code, nodes in SEEDS.items()}


def sync_taxonomy(session: Session, *, subject_codes: Optional[Iterable[str]] = None) -> dict[str, int]:
    """把种子知识点写库。幂等：按 (board_id, code) 更新而不是重复插入。"""
    board = session.scalar(select(Board).where(Board.key == "cambridge"))
    if board is None:
        return {"nodes": 0, "subjects": 0}

    stats = {"nodes": 0, "subjects": 0}
    allowed_codes = None if subject_codes is None else set(subject_codes)
    for subject_code, nodes in SEEDS.items():
        if allowed_codes is not None and subject_code not in allowed_codes:
            continue
        # Subject 通过 qualification 归属考试局，没有直接的 board_id
        subject = session.scalar(
            select(Subject)
            .join(Qualification, Qualification.id == Subject.qualification_id)
            .where(Qualification.board_id == board.id, Subject.code == subject_code)
        )
        if subject is None:
            continue
        stats["subjects"] += 1
        # 先建父节点，再建子节点
        for node in nodes:
            parent = _upsert(session, board.id, node["code"], node["name"], "topic", None, subject_code)
            stats["nodes"] += parent
            for child in node.get("children", []):
                stats["nodes"] += _upsert(
                    session,
                    board.id,
                    child["code"],
                    child["name"],
                    "subtopic",
                    node["code"],
                    subject_code,
                )
    session.flush()
    return stats


def _upsert(
    session: Session,
    board_id: int,
    code: str,
    name: str,
    node_type: str,
    parent_code: Optional[str],
    subject_code: str,
) -> int:
    existing = session.scalar(
        select(TaxonomyNode).where(TaxonomyNode.board_id == board_id, TaxonomyNode.code == code)
    )
    parent_id = None
    if parent_code:
        parent = session.scalar(
            select(TaxonomyNode).where(
                TaxonomyNode.board_id == board_id, TaxonomyNode.code == parent_code
            )
        )
        parent_id = parent.id if parent else None
    if existing is None:
        session.add(
            TaxonomyNode(
                board_id=board_id,
                parent_id=parent_id,
                code=code,
                name=name,
                node_type=node_type,
                source="seed",
                attrs={"subject_code": subject_code},
            )
        )
        return 1
    if existing.source not in {"seed", "auto"}:
        return 0
    existing.name = name
    existing.node_type = node_type
    existing.parent_id = parent_id
    return 0


@dataclass
class TaxonomyAssignment:
    question_id: int
    node_code: str
    node_name: str
    score: float
    confidence: float
    hits: list[str]


MIN_CONFIDENCE = 0.18


def classify_question(stem_text: str, subject_code: str) -> list[TaxonomyAssignment]:
    """给单道题打分，返回按得分降序的候选（最多 2 个）。"""
    compiled = _COMPILED.get(subject_code)
    if not compiled or not stem_text:
        return []
    text = stem_text
    scored: list[tuple[float, _Compiled, list[str]]] = []
    for node in compiled:
        total = 0.0
        hits: list[str] = []
        for pat, weight in node.patterns:
            m = pat.search(text)
            if m:
                total += weight
                hits.append(m.group(0).lower())
        if total > 0:
            scored.append((total, node, hits))
    if not scored:
        return []
    scored.sort(key=lambda t: -t[0])
    best = scored[0][0]
    out: list[TaxonomyAssignment] = []
    for total, node, hits in scored[:2]:
        # 归一化：绝对分越高越可信，同时相对第一名的占比也参与，
        # 避免一道题命中很多弱词却给出虚高置信度。
        absolute = min(1.0, total / 6.0)
        relative = total / best
        confidence = round(0.65 * absolute + 0.35 * relative, 4)
        if confidence < MIN_CONFIDENCE:
            continue
        out.append(
            TaxonomyAssignment(
                question_id=0,
                node_code=node.code,
                node_name=node.name,
                score=round(total, 3),
                confidence=confidence,
                hits=sorted(set(hits)),
            )
        )
    return out


def assign_taxonomy(
    session: Session,
    *,
    subject_code: Optional[str] = None,
    limit: Optional[int] = None,
    replace: bool = False,
) -> dict[str, int]:
    """批量标注。replace=True 时先清掉 source="auto" 的旧标注（不动 manual）。"""
    stats = {"scanned": 0, "assigned": 0, "unassigned": 0, "skipped_manual": 0}

    node_by_code = {
        n.code: n
        for n in session.scalars(
            select(TaxonomyNode).where(TaxonomyNode.node_type.in_(["topic", "subtopic"]))
        ).all()
    }

    # 题目 -> 试卷 -> 文档 -> 科目，这条链是唯一的科目归属来源
    rows = session.execute(_question_subject_stmt(subject_code, limit)).all()
    for question, subj_code in rows:
        stats["scanned"] += 1
        manual_node_ids: set[int] = set()
        if replace:
            for old in session.scalars(
                select(QuestionTaxonomy).where(
                    QuestionTaxonomy.question_id == question.id,
                    QuestionTaxonomy.source == "auto",
                )
            ).all():
                session.delete(old)
            # 必须先 flush：删除只在会话里排队，紧接着的 INSERT 会在同一个
            # 事务里与尚未落地的旧行撞上 (question_id, node_id) 唯一约束。
            session.flush()
            # 唯一约束不含 source：manual 行不能删，自动结果必须避开这些节点。
            manual_node_ids = set(
                session.scalars(
                    select(QuestionTaxonomy.node_id).where(
                        QuestionTaxonomy.question_id == question.id,
                        QuestionTaxonomy.source == "manual",
                    )
                ).all()
            )
        else:
            manual = session.scalar(
                select(QuestionTaxonomy.id).where(
                    QuestionTaxonomy.question_id == question.id,
                    QuestionTaxonomy.source == "manual",
                )
            )
            if manual is not None:
                stats["skipped_manual"] += 1
                continue
            auto = session.scalar(
                select(QuestionTaxonomy.id).where(
                    QuestionTaxonomy.question_id == question.id,
                    QuestionTaxonomy.source == "auto",
                )
            )
            if auto is not None:
                continue

        assigns = classify_question(question.stem_text or "", subj_code or "")
        if not assigns:
            stats["unassigned"] += 1
            continue
        seen: set[int] = set()
        for a in assigns:
            node = node_by_code.get(a.node_code)
            if node is None:
                continue
            targets = [node]
            if node.parent_id is not None:
                parent = session.get(TaxonomyNode, node.parent_id)
                if parent is not None:
                    targets.append(parent)
            for t in targets:
                if t.id in seen or t.id in manual_node_ids:
                    continue
                seen.add(t.id)
                session.add(
                    QuestionTaxonomy(
                        question_id=question.id,
                        node_id=t.id,
                        source="auto",
                        confidence=a.confidence if t is node else round(a.confidence * 0.9, 4),
                        assigned_by="keyword-v1",
                        reviewed=False,
                    )
                )
                stats["assigned"] += 1
    session.flush()
    return stats


def _question_subject_stmt(subject_code: Optional[str], limit: Optional[int]):
    from ..core.models import Document, Paper

    stmt = (
        select(Question, Subject.code)
        .join(Paper, Paper.id == Question.paper_id)
        .join(Document, Document.id == Paper.document_id)
        .join(Subject, Subject.id == Document.subject_id, isouter=True)
        .order_by(Question.id)
    )
    if subject_code:
        stmt = stmt.where(Subject.code == subject_code)
    if limit:
        stmt = stmt.limit(limit)
    return stmt
