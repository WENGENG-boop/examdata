"""人工修正与待检查队列治理。

规格两条硬要求：
1. "人工确认后的内容不应在下一次自动同步过程中被无条件覆盖。"
2. "低置信度或存在冲突的数据应进入待检查状态。"

第 1 条由 `field_override` 表 + 解析流水线的 `_apply_overrides` 共同保证：
覆盖值与自动解析值分开存放，重解析时重新应用；若自动值变了（说明
上游数据或算法变了），**不静默覆盖**，而是标记冲突并进待检查。

本模块提供人工侧的操作入口：登记修正、撤销修正、处置待检查项。
所有操作都要求 author（谁改的），因为"人工确认"必须可追责。
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.models import FieldOverride, ReviewTask, ValidationFinding

# 允许人工修正的字段路径白名单。
# 不做成任意字段可写：解析产物之间有结构约束（如 depth 与 parent_id 必须自洽），
# 放开任意字段会让数据进入自相矛盾的状态，而校验规则抓不到这类破坏。
OVERRIDABLE: dict[str, set[str]] = {
    "question": {
        "number_label",
        "number_path",
        "marks",
        "stem_text",
        "kind",
        "depth",
        "page_from",
        "page_to",
        "parse_confidence",
    },
    "mark_scheme_entry": {
        "number_label",
        "number_path",
        "marks",
        "answer_text",
        "method_marks",
        "accuracy_marks",
        "independent_marks",
        "ecf",
        "guidance",
        "parse_confidence",
    },
    "document": {"doc_type", "year", "paper_code", "component", "variant", "level", "title", "status"},
    "paper": {"paper_no", "marks_total", "question_count", "duration_minutes", "page_count"},
}

_TARGET_MODELS: dict[str, str] = {
    "question": "Question",
    "mark_scheme_entry": "MarkSchemeEntry",
    "document": "Document",
    "paper": "Paper",
}


class OverrideError(ValueError):
    """修正请求本身不合法（不是"冲突"，是调用方给错了）。"""


def _model(target_type: str):
    from ..core import models

    name = _TARGET_MODELS.get(target_type)
    if name is None:
        raise OverrideError(
            f"不支持的目标类型 {target_type!r}，可选：{sorted(_TARGET_MODELS)}"
        )
    return getattr(models, name)


def set_override(
    session: Session,
    *,
    target_type: str,
    target_id: int,
    field_path: str,
    value: Any,
    author: str,
    applies_to_parser_versions: Any = "*",
    note: Optional[str] = None,
) -> dict[str, Any]:
    """登记一条人工修正。

    覆盖前记录 source_value（当前自动解析值），用于后续冲突检测。
    同一字段重复修正时更新 value，但**保留最初的 source_value**——
    否则连续两次修正会让冲突检测失去基线。
    """
    allowed = OVERRIDABLE.get(target_type)
    if allowed is None:
        raise OverrideError(f"不支持的目标类型 {target_type!r}，可选：{sorted(OVERRIDABLE)}")
    if field_path not in allowed:
        raise OverrideError(
            f"{target_type} 不允许修正字段 {field_path!r}，可选：{sorted(allowed)}"
        )
    if not author or not author.strip():
        raise OverrideError("人工修正必须记录 author")

    model = _model(target_type)
    obj = session.get(model, target_id)
    if obj is None:
        raise OverrideError(f"{target_type} {target_id} 不存在")

    current = getattr(obj, field_path, None)
    existing = session.scalar(
        select(FieldOverride).where(
            FieldOverride.target_type == target_type,
            FieldOverride.target_id == target_id,
            FieldOverride.field_path == field_path,
        )
    )
    if existing is None:
        existing = FieldOverride(
            target_type=target_type,
            target_id=target_id,
            field_path=field_path,
            value=value,
            source_value=current,
            author=author,
            active=True,
            applies_to_parser_versions=applies_to_parser_versions,
            conflict_detected=False,
            attrs={"note": note} if note else {},
        )
        session.add(existing)
    else:
        existing.value = value
        existing.author = author
        existing.active = True
        existing.applies_to_parser_versions = applies_to_parser_versions
        existing.conflict_detected = False
        existing.conflict_detail = None
        if note:
            existing.attrs = {**(existing.attrs or {}), "note": note}

    setattr(obj, field_path, value)
    if hasattr(obj, "has_override"):
        obj.has_override = True
    session.flush()
    return {
        "id": existing.id,
        "target_type": target_type,
        "target_id": target_id,
        "field_path": field_path,
        "value": value,
        "source_value": existing.source_value,
    }


def revert_override(
    session: Session,
    *,
    target_type: str,
    target_id: int,
    field_path: str,
    author: str,
) -> dict[str, Any]:
    """撤销一条人工修正，并把字段恢复成当时的自动解析值。

    不删除行：改成 active=False 保留"曾经改过又被撤销"的历史，
    否则审计链会断。
    """
    ov = session.scalar(
        select(FieldOverride).where(
            FieldOverride.target_type == target_type,
            FieldOverride.target_id == target_id,
            FieldOverride.field_path == field_path,
        )
    )
    if ov is None:
        raise OverrideError(f"没有找到 {target_type}:{target_id} 的 {field_path} 修正记录")
    ov.active = False
    ov.attrs = {**(ov.attrs or {}), "reverted_by": author}
    # source_value 一定是 set_override 当时记录的自动值，可能合法地为 NULL
    # （字段本来就没有值）：不能用 `is not None` 判断，否则 NULL 基线不还原，
    # 字段会一直留着已被撤销的人工值。
    model = _model(target_type)
    obj = session.get(model, target_id)
    if obj is not None:
        setattr(obj, field_path, ov.source_value)
    session.flush()
    return {"id": ov.id, "active": False, "restored": ov.source_value}


def list_overrides(
    session: Session,
    *,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    only_conflicts: bool = False,
    only_active: bool = True,
) -> list[dict[str, Any]]:
    stmt = select(FieldOverride).order_by(FieldOverride.id)
    if target_type:
        stmt = stmt.where(FieldOverride.target_type == target_type)
    if target_id is not None:
        stmt = stmt.where(FieldOverride.target_id == target_id)
    if only_active:
        stmt = stmt.where(FieldOverride.active.is_(True))
    if only_conflicts:
        stmt = stmt.where(FieldOverride.conflict_detected.is_(True))
    return [
        {
            "id": o.id,
            "target_type": o.target_type,
            "target_id": o.target_id,
            "field_path": o.field_path,
            "value": o.value,
            "source_value": o.source_value,
            "author": o.author,
            "active": o.active,
            "applies_to_parser_versions": o.applies_to_parser_versions,
            "conflict_detected": o.conflict_detected,
            "conflict_detail": o.conflict_detail,
        }
        for o in session.scalars(stmt).all()
    ]


# --------------------------------------------------------------------------
# 待检查队列
# --------------------------------------------------------------------------


def list_reviews(
    session: Session,
    *,
    status: str = "open",
    target_type: Optional[str] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    stmt = select(ReviewTask).order_by(ReviewTask.priority, ReviewTask.id).limit(limit)
    if status:
        stmt = stmt.where(ReviewTask.status == status)
    if target_type:
        stmt = stmt.where(ReviewTask.target_type == target_type)
    return [
        {
            "id": r.id,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "reason": r.reason,
            "priority": r.priority,
            "status": r.status,
            "assignee": r.assignee,
            "resolution": r.resolution,
        }
        for r in session.scalars(stmt).all()
    ]


def resolve_review(
    session: Session,
    *,
    review_id: int,
    resolution: str,
    author: str,
    status: str = "done",
) -> dict[str, Any]:
    """处置一条待检查项。

    status 只允许 done / dismissed / in_progress：
    "关闭"必须由人显式选择是"已处理"还是"确认无需处理"，
    不提供模糊的关闭动作，否则队列会积累无法解释的历史。
    """
    if status not in ("done", "dismissed", "in_progress"):
        raise OverrideError("status 只能是 done / dismissed / in_progress")
    task = session.get(ReviewTask, review_id)
    if task is None:
        raise OverrideError(f"待检查项 {review_id} 不存在")
    task.status = status
    task.assignee = author
    task.resolution = resolution
    # 对应的校验发现一并结案，避免监控视图里长期显示"未解决错误"
    session.execute(
        ValidationFinding.__table__.update()
        .where(
            ValidationFinding.subject_type == task.target_type,
            ValidationFinding.subject_id == task.target_id,
            ValidationFinding.rule_code == task.reason,
            ValidationFinding.status == "open",
        )
        .values(status="resolved" if status == "done" else "ignored")
    )
    session.flush()
    return {"id": task.id, "status": task.status, "resolution": resolution, "assignee": author}


def claim_review(session: Session, *, review_id: int, author: str) -> dict[str, Any]:
    task = session.get(ReviewTask, review_id)
    if task is None:
        raise OverrideError(f"待检查项 {review_id} 不存在")
    task.status = "in_progress"
    task.assignee = author
    session.flush()
    return {"id": task.id, "status": task.status, "assignee": author}
