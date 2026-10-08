"""低置信标注的复核导出与回写。

``assign`` 的 BM25 初判对低置信题目只是"矮子里拔将军"：top-1 分数低不代表
贴题。本模块把低置信题导出为复核包（题干 + 当前标签 + 单元内容点清单），
复核者（AI 或人工）逐题给出 keep / change / drop 决策后回写：

- ``keep``：现有算法行标记 ``reviewed=True``；
- ``change``：删除算法行，写入 ``source="ai-review"`` 复核行
  （``reviewed=True``、``confidence=1.0``，表示经复核确认而非算法打分）；
- ``drop``：删除算法行、不写标签，原因记入应用日志。

``reviewed=True`` 的行不会再出现在复核包里，也不会被 ``assign`` 重跑覆盖
（``_existing_rows`` 把 reviewed 行视为占用）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..core.models import (
    Board,
    Document,
    Paper,
    Question,
    QuestionTaxonomy,
    Subject,
    TaxonomyNode,
)
from .assign import ASSIGNED_BY, REVIEW_ASSIGNED_BY, REVIEW_SOURCE
from .corpus import BOARD_KEY, load_points, unit_code_from_paper

DEFAULT_MAX_CONFIDENCE = 0.35
DEFAULT_BATCH_SIZE = 50
DECISIONS = {"keep", "change", "drop"}


def _resolve_subject(session: Session, subject: str) -> Subject:
    key = subject.strip().lower()
    row = session.scalar(
        select(Subject).where(or_(Subject.code == key, Subject.slug == key))
    )
    if row is None:
        raise LookupError(f"subject {subject} is not in the database")
    return row


def _subject_points(session: Session, subject_row: Subject, *, board_key: str) -> list:
    keys = {
        (subject_row.code or "").strip().lower(),
        (subject_row.slug or "").strip().lower(),
    }
    keys.discard("")
    return [
        point
        for point in load_points(session, board_key=board_key)
        if (point.subject or "").strip().lower() in keys
    ]


def _safe_name(value: str) -> str:
    return "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in value) or "unknown"


def export_review(
    session: Session,
    *,
    subject: str,
    out_dir: Path,
    max_confidence: float = DEFAULT_MAX_CONFIDENCE,
    batch_size: int = DEFAULT_BATCH_SIZE,
    board_key: str = BOARD_KEY,
) -> dict[str, Any]:
    """导出某科目的低置信复核包：points 清单 + 分批 JSONL。"""
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    subject_row = _resolve_subject(session, subject)
    points = _subject_points(session, subject_row, board_key=board_key)
    if not points:
        raise LookupError(f"subject {subject} has no spec points loaded")

    by_node = {point.node_id: point for point in points}
    unit_points: dict[str, list[dict[str, str]]] = {}
    for point in points:
        unit_points.setdefault(point.unit_code or "", []).append(
            {"code": point.code, "name": point.name}
        )
    for rows in unit_points.values():
        rows.sort(key=lambda row: row["code"])

    stmt = (
        select(
            QuestionTaxonomy.question_id,
            Question.number_label,
            Question.stem_text,
            Document.paper_code,
            Paper.attrs,
            QuestionTaxonomy.node_id,
            QuestionTaxonomy.confidence,
        )
        .join(Question, Question.id == QuestionTaxonomy.question_id)
        .join(Paper, Paper.id == Question.paper_id)
        .join(Document, Document.id == Paper.document_id)
        .where(
            Document.subject_id == subject_row.id,
            QuestionTaxonomy.assigned_by == ASSIGNED_BY,
            QuestionTaxonomy.reviewed.is_(False),
            QuestionTaxonomy.confidence < max_confidence,
        )
        .order_by(QuestionTaxonomy.question_id)
    )

    items: dict[int, dict[str, Any]] = {}
    for qid, number_label, stem, paper_code, paper_attrs, node_id, confidence in session.execute(stmt):
        point = by_node.get(node_id)
        if point is None:
            continue
        item = items.setdefault(
            qid,
            {
                "question_id": qid,
                "number_label": number_label or "",
                "paper_code": paper_code,
                "unit_code": unit_code_from_paper(paper_attrs, paper_code),
                "stem": stem or "",
                "current": [],
            },
        )
        item["current"].append(
            {"code": point.code, "name": point.name, "confidence": round(confidence, 4)}
        )

    out_dir = Path(out_dir)
    points_file = out_dir / f"points-{_safe_name(subject)}.json"
    points_file.parent.mkdir(parents=True, exist_ok=True)
    points_file.write_text(
        json.dumps(
            {"subject": subject, "units": unit_points},
            ensure_ascii=False,
            indent=1,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    batches_dir = out_dir / "batches"
    batches_dir.mkdir(parents=True, exist_ok=True)
    ordered = [items[qid] for qid in sorted(items)]
    batch_files: list[str] = []
    for index in range(0, len(ordered), batch_size):
        path = batches_dir / f"batch-{index // batch_size + 1:03d}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for item in ordered[index : index + batch_size]:
                handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
        batch_files.append(str(path))

    return {
        "subject": subject,
        "items": len(ordered),
        "batches": len(batch_files),
        "batch_files": batch_files,
        "points_file": str(points_file),
        "out_dir": str(out_dir),
        "units": len(unit_points),
    }


def _read_decisions(path: Path) -> list[dict[str, Any]]:
    files: list[Path]
    if path.is_dir():
        # 排除本模块自己写的应用日志，避免重跑时把日志当决策读回来。
        files = sorted(
            p
            for p in path.glob("*.jsonl")
            if p.name != "applied.jsonl" and not p.name.endswith(".applied.jsonl")
        )
    else:
        files = [path]
    out: list[dict[str, Any]] = []
    for file in files:
        for lineno, line in enumerate(file.read_text(encoding="utf-8").splitlines(), start=1):
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{file}:{lineno}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{file}:{lineno}: decision must be a JSON object")
            out.append(row)
    return out


def apply_review(
    session: Session,
    *,
    subject: str,
    decisions_path: Path,
    dry_run: bool = True,
    board_key: str = BOARD_KEY,
) -> dict[str, Any]:
    """把复核决策回写数据库。``dry_run=True`` 只校验、不落库。"""
    subject_row = _resolve_subject(session, subject)
    points = _subject_points(session, subject_row, board_key=board_key)
    if not points:
        raise LookupError(f"subject {subject} has no spec points loaded")
    point_by_code = {point.code: point for point in points}

    board = session.scalar(select(Board).where(Board.key == board_key))
    if board is None:
        raise LookupError(f"board {board_key} is not in the database")

    decisions = _read_decisions(Path(decisions_path))
    stats: dict[str, Any] = {
        "subject": subject,
        "dry_run": dry_run,
        "decisions": len(decisions),
        "kept": 0,
        "changed": 0,
        "dropped": 0,
        "skipped": 0,
        "errors": [],
    }
    applied: list[dict[str, Any]] = []
    seen: set[int] = set()

    def fail(row: dict[str, Any], message: str) -> None:
        stats["errors"].append(f"question {row.get('question_id')}: {message}")
        applied.append(
            {
                "question_id": row.get("question_id"),
                "decision": row.get("decision"),
                "code": row.get("code"),
                "reason": row.get("reason"),
                "status": "error",
                "message": message,
            }
        )

    for row in decisions:
        qid = row.get("question_id")
        decision = str(row.get("decision") or "").strip().lower()
        if not isinstance(qid, int):
            fail(row, "question_id must be an integer")
            continue
        if qid in seen:
            fail(row, "duplicate decision for this question")
            continue
        seen.add(qid)
        if decision not in DECISIONS:
            fail(row, f"unknown decision {decision!r}")
            continue

        question = session.get(Question, qid)
        if question is None:
            fail(row, "question not found")
            continue
        paper = session.get(Paper, question.paper_id)
        document = session.get(Document, paper.document_id) if paper else None
        if paper is None or document is None or document.subject_id != subject_row.id:
            fail(row, "question does not belong to this subject")
            continue

        algo_rows = list(
            session.scalars(
                select(QuestionTaxonomy).where(
                    QuestionTaxonomy.question_id == qid,
                    QuestionTaxonomy.assigned_by == ASSIGNED_BY,
                    QuestionTaxonomy.reviewed.is_(False),
                )
            )
        )
        if not algo_rows:
            fail(row, "no unreviewed algorithm tags to act on")
            continue

        if decision == "keep":
            stats["kept"] += 1
            if not dry_run:
                for link in algo_rows:
                    link.reviewed = True
        elif decision == "change":
            code = str(row.get("code") or "").strip()
            point = point_by_code.get(code)
            if point is None:
                fail(row, f"code {code!r} is not a point of this subject")
                continue
            unit = unit_code_from_paper(paper.attrs, document.paper_code)
            if unit and point.unit_code and point.unit_code.upper() != unit.upper():
                fail(row, f"code {code} belongs to unit {point.unit_code}, question is in {unit}")
                continue
            stats["changed"] += 1
            if not dry_run:
                for link in algo_rows:
                    session.delete(link)
                session.flush()
                existing = session.scalar(
                    select(QuestionTaxonomy.id).where(
                        QuestionTaxonomy.question_id == qid,
                        QuestionTaxonomy.node_id == point.node_id,
                    )
                )
                if existing is None:
                    session.add(
                        QuestionTaxonomy(
                            question_id=qid,
                            node_id=point.node_id,
                            source=REVIEW_SOURCE,
                            confidence=1.0,
                            assigned_by=REVIEW_ASSIGNED_BY,
                            reviewed=True,
                        )
                    )
        else:  # drop
            stats["dropped"] += 1
            if not dry_run:
                for link in algo_rows:
                    session.delete(link)

        applied.append(
            {
                "question_id": qid,
                "decision": decision,
                "code": row.get("code"),
                "reason": row.get("reason"),
                "status": "applied" if not dry_run else "dry-run",
            }
        )

    if not dry_run:
        session.flush()
        path = Path(decisions_path)
        log_path = (path / "applied.jsonl") if path.is_dir() else Path(str(path) + ".applied.jsonl")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as handle:
            for entry in applied:
                handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        stats["applied_log"] = str(log_path)

    return stats


__all__ = [
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_MAX_CONFIDENCE",
    "apply_review",
    "export_review",
]
