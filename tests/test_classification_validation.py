"""文件类型交叉校验测试。

需求："文件类型判断不能只依赖文件名，还需要能够结合官方页面信息、
文件本身信息以及文档内容进行判断。"

解析流水线必须把"页面判定"和"内容判定"这两个独立信号真正对上一次，
不一致时写校验发现让文件进待检查——否则所谓"多信号判断"就只是两个
各自为政的字段。
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from examdata.core.db import session_scope
from examdata.core.models import ValidationFinding


def _findings(rule: str) -> list[ValidationFinding]:
    with session_scope() as s:
        return list(
            s.scalars(select(ValidationFinding).where(ValidationFinding.rule_code == rule)).all()
        )


def test_conflict_rule_exists_in_pipeline():
    """规则必须真的被注册，而不是只写在文档里。"""
    import inspect

    from examdata.parsing import pipeline

    src = inspect.getsource(pipeline.ParsePipeline._record_classification_finding)
    assert "doc_type_content_conflict" in src
    assert "classify_content" in src
    assert "reconcile" in src


def test_conflict_finding_is_error_severity():
    """冲突必须是 error 级，否则不会触发 needs_review。"""
    import inspect

    from examdata.parsing import pipeline

    src = inspect.getsource(pipeline.ParsePipeline._record_classification_finding)
    assert '"severity": "error"' in src or "'severity': 'error'" in src


def test_no_false_conflicts_on_real_corpus():
    """真实语料上页面判定与内容判定必须完全一致——有冲突说明分类器有 bug。"""
    rows = _findings("doc_type_content_conflict")
    assert rows == [], (
        "真实数据上出现了类型判定冲突，应检查 content_classify 的规则："
        + str([(r.subject_id, r.evidence) for r in rows[:3]])
    )


def test_classification_finding_carries_evidence_when_present():
    """一旦有冲突，证据必须完整到能人工判断。"""
    rows = _findings("doc_type_content_conflict")
    for r in rows:
        assert r.evidence.get("label_type")
        assert r.evidence.get("content_type")
        assert "content_scores" in r.evidence
        assert r.evidence.get("resolved_type")


def test_content_classifier_covers_every_pdf_document():
    """每份 PDF 文档都应能被内容分类器给出判定。

    非 PDF（如 .docx 的 Scheme of Work）不在覆盖范围内：内容分类器
    基于 PDF 文本层，对它本来就无能为力。硬要求它判定会逼出一个
    无意义的"兜底标签"，反而掩盖真正需要关注的 PDF 判定失败。
    """
    from examdata.core.config import get_settings
    from examdata.core.models import Artifact, Document, DocumentRevision
    from examdata.parsing.content_classify import classify_content

    with session_scope() as s:
        rows = s.execute(
            select(Document.id, Artifact.storage_key, Artifact.mime)
            .join(DocumentRevision, DocumentRevision.document_id == Document.id)
            .join(Artifact, Artifact.id == DocumentRevision.artifact_id)
        ).all()
    assert rows, "测试依赖已解析数据"
    settings = get_settings()
    failures = []
    checked = 0
    for did, key, mime in rows:
        if not (str(mime or "").startswith("application/pdf") or key.lower().endswith(".pdf")):
            continue  # 非 PDF 不在此能力的覆盖范围内
        checked += 1
        ev = classify_content(settings.artifacts_dir / key)
        if ev.doc_type is None:
            failures.append((did, ev.error))
    assert checked > 0, "至少应有一份 PDF 可供检查"
    assert not failures, f"内容分类器未能判定这些 PDF: {failures}"


def test_non_pdf_is_reported_not_misclassified():
    """非 PDF 输入必须如实报错，不能编一个类型。"""
    from examdata.parsing.content_classify import classify_content

    ev = classify_content(__file__)  # 拿一个 .py 文件当输入
    assert ev.doc_type is None, "非 PDF 不应给出类型判定"
    assert ev.error, "必须说明为什么判定不了"
