"""治理层测试：人工修正、待检查队列、重新解析、溯源。

这些测试对应规格里三条容易被跳过但很硬的要求：
- "人工确认后的内容不应在下一次自动同步过程中被无条件覆盖"
- "重新解析不应该要求重新从官方网站下载全部历史文件"
- "能够追踪某一份试卷/题目/答案/图片最初来自哪个官方资源"

测试直接打真实数据库（与 test_api.py 一致），因为它们验证的是
"重解析后人工值还在不在"这类跨表、跨流程的性质，纯单元测试测不到。
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from examdata.core.db import session_scope
from examdata.core.models import (
    FieldOverride,
    Paper,
    Question,
    ReviewTask,
    ValidationFinding,
)
from examdata.governance import (
    OVERRIDABLE,
    OverrideError,
    coverage,
    diff,
    list_overrides,
    list_reviews,
    rebuild,
    reparse_documents,
    resolve_review,
    revert_override,
    set_override,
    snapshot,
    trace,
)
from examdata.governance.reparse import DocumentSnapshot


@pytest.fixture
def clean_overrides():
    """每个用例前后清空人工修正，避免互相污染。"""
    def _clear():
        with session_scope() as s:
            for o in s.scalars(select(FieldOverride)).all():
                s.delete(o)
    _clear()
    yield
    _clear()


def _some_question(session, document_id: int | None = None, path: str | None = None):
    stmt = select(Question.id).join(Paper, Paper.id == Question.paper_id)
    if document_id is not None:
        stmt = stmt.where(Paper.document_id == document_id)
    if path is not None:
        stmt = stmt.where(Question.number_path == path)
    stmt = stmt.order_by(Question.id).limit(1)
    qid = session.scalar(stmt)
    assert qid is not None, "测试依赖已解析的数据，请先跑 parse-docs"
    return qid


# --------------------------------------------------------------------------
# 字段白名单与参数校验
# --------------------------------------------------------------------------


def test_override_rejects_unknown_field(clean_overrides):
    with session_scope() as s:
        qid = _some_question(s)
        with pytest.raises(OverrideError):
            set_override(
                s, target_type="question", target_id=qid,
                field_path="not_a_real_field", value=1, author="t",
            )


def test_override_rejects_unknown_target_type(clean_overrides):
    with session_scope() as s:
        with pytest.raises(OverrideError):
            set_override(
                s, target_type="banana", target_id=1,
                field_path="marks", value=1, author="t",
            )


def test_override_requires_author(clean_overrides):
    with session_scope() as s:
        qid = _some_question(s)
        with pytest.raises(OverrideError):
            set_override(
                s, target_type="question", target_id=qid,
                field_path="marks", value=1, author="   ",
            )


def test_override_rejects_missing_target(clean_overrides):
    with session_scope() as s:
        with pytest.raises(OverrideError):
            set_override(
                s, target_type="question", target_id=10**9,
                field_path="marks", value=1, author="t",
            )


def test_overridable_map_is_deliberately_narrow():
    # 白名单存在的意义是阻止"任意字段可写"把数据改成自相矛盾的状态
    assert "question" in OVERRIDABLE
    assert "marks" in OVERRIDABLE["question"]
    assert "id" not in OVERRIDABLE["question"]
    assert "paper_id" not in OVERRIDABLE["question"]
    assert "parent_id" not in OVERRIDABLE["question"]


# --------------------------------------------------------------------------
# 修正生效 / 撤销 / 基线保留
# --------------------------------------------------------------------------


def test_override_writes_value_and_marks_flag(clean_overrides):
    with session_scope() as s:
        qid = _some_question(s)
        q = s.get(Question, qid)
        original = q.marks
        set_override(
            s, target_type="question", target_id=qid,
            field_path="marks", value=(original or 0) + 7, author="tester",
        )
        assert q.marks == (original or 0) + 7
        assert q.has_override is True

        ov = s.scalar(select(FieldOverride).where(FieldOverride.target_id == qid))
        assert ov.source_value == original, "必须记录被覆盖前的自动值作为冲突检测基线"
        assert ov.active is True


def test_override_keeps_original_baseline_on_second_edit(clean_overrides):
    """连续两次修正时，基线仍是最初的自动值。"""
    with session_scope() as s:
        qid = _some_question(s)
        original = s.get(Question, qid).marks
        set_override(s, target_type="question", target_id=qid,
                     field_path="marks", value=11, author="a")
        set_override(s, target_type="question", target_id=qid,
                     field_path="marks", value=12, author="b")
        ov = s.scalar(select(FieldOverride).where(FieldOverride.target_id == qid))
        assert ov.value == 12
        assert ov.source_value == original
        assert ov.author == "b"


def test_revert_restores_source_value(clean_overrides):
    with session_scope() as s:
        qid = _some_question(s)
        original = s.get(Question, qid).marks
        set_override(s, target_type="question", target_id=qid,
                     field_path="marks", value=(original or 0) + 4, author="a")

    with session_scope() as s:
        result = revert_override(s, target_type="question", target_id=qid,
                                 field_path="marks", author="b")
        assert result["active"] is False
        assert s.get(Question, qid).marks == original

    with session_scope() as s:
        # 不删除行：审计链要保留"改过又被撤销"
        ov = s.scalar(select(FieldOverride).where(FieldOverride.target_id == qid))
        assert ov is not None and ov.active is False
        assert ov.attrs.get("reverted_by") == "b"
        assert list_overrides(s, only_active=True) == []


def test_revert_restores_null_baseline(clean_overrides):
    """基线本身是 NULL 时，撤销必须把字段还原成 NULL。

    旧实现用 `if ov.source_value is not None` 判断是否还原，NULL 基线会被
    当成"没有基线"跳过，字段就一直留着已被撤销的人工值。
    """
    with session_scope() as s:
        qid = s.scalar(
            select(Question.id)
            .where(Question.marks.is_(None))
            .order_by(Question.id)
            .limit(1)
        )
        if qid is None:
            pytest.skip("没有 marks 为空的题目")
        set_override(s, target_type="question", target_id=qid,
                     field_path="marks", value=7, author="a")
        assert s.get(Question, qid).marks == 7
        ov = s.scalar(select(FieldOverride).where(FieldOverride.target_id == qid))
        assert ov.source_value is None, "基线必须是字段当时的 NULL"

    with session_scope() as s:
        result = revert_override(s, target_type="question", target_id=qid,
                                 field_path="marks", author="b")
        assert result["restored"] is None
        assert s.get(Question, qid).marks is None, "NULL 基线必须被还原"

    with session_scope() as s:
        active = list_overrides(s, target_type="question", target_id=qid, only_active=True)
        assert active == []


def test_revert_unknown_override_raises(clean_overrides):
    with session_scope() as s:
        with pytest.raises(OverrideError):
            revert_override(s, target_type="question", target_id=10**9,
                            field_path="marks", author="a")


# --------------------------------------------------------------------------
# 重新解析：人工值必须活下来
# --------------------------------------------------------------------------


def test_reparse_keeps_human_override(clean_overrides):
    """核心性质：重新解析后人工值仍然生效，且不误报冲突。"""
    with session_scope() as s:
        reparse_documents(s, document_ids=[10])

    with session_scope() as s:
        qid = _some_question(s, document_id=10, path="4")
        auto = s.get(Question, qid).marks
        set_override(s, target_type="question", target_id=qid,
                     field_path="marks", value=(auto or 0) + 3, author="tester")

    with session_scope() as s:
        result = reparse_documents(s, document_ids=[10])
        assert result["overrides"]["applied"] >= 1

    with session_scope() as s:
        ov = s.scalar(select(FieldOverride))
        assert ov is not None
        q = s.get(Question, ov.target_id)
        assert q is not None, "修正必须被接回重解析后新建的题目行"
        assert q.marks == (auto or 0) + 3
        assert q.has_override is True
        assert ov.conflict_detected is False


def test_reparse_reports_conflict_when_natural_key_disappears(clean_overrides):
    """自然键找不到时必须报冲突并进待检查，绝不静默丢弃人工值。"""
    with session_scope() as s:
        qid = _some_question(s, document_id=10, path="4")
        set_override(s, target_type="question", target_id=qid,
                     field_path="marks", value=99, author="tester")
        # 把题号路径改成一个重解析后不会出现的值，模拟"算法改动了题号"
        s.get(Question, qid).number_path = "999(zz)"

    with session_scope() as s:
        result = reparse_documents(s, document_ids=[10])
        assert result["overrides"]["conflicted"] >= 1

    with session_scope() as s:
        ov = s.scalar(select(FieldOverride))
        assert ov.conflict_detected is True
        assert ov.value == 99, "人工值必须保留，由人来判断谁对"
        assert ov.conflict_detail
        tasks = s.scalars(
            select(ReviewTask).where(
                ReviewTask.reason == "override_target_missing_after_reparse"
            )
        ).all()
        assert tasks, "冲突必须进入待检查队列"


def test_reparse_rebuilds_derived_intelligence(clean_overrides):
    """重新解析必须重建知识点/难度/相似题。

    这是真实踩过的坑：_purge_derived 会清掉派生数据，如果重解析不重建，
    重解析过的文档就会静默地比之前更不完整——解析统计看起来一切正常，
    但难度估计少了一批题。
    """
    from sqlalchemy import func

    from examdata.core.models import Difficulty, QuestionSimilarity, QuestionTaxonomy

    def counts(s):
        qids = list(
            s.scalars(
                select(Question.id)
                .join(Paper, Paper.id == Question.paper_id)
                .where(Paper.document_id == 10)
            ).all()
        )
        return {
            "questions": len(qids),
            "taxonomy": s.scalar(
                select(func.count(QuestionTaxonomy.id)).where(
                    QuestionTaxonomy.question_id.in_(qids)
                )
            )
            or 0,
            "difficulty": s.scalar(
                select(func.count(Difficulty.id)).where(Difficulty.question_id.in_(qids))
            )
            or 0,
        }

    with session_scope() as s:
        before = counts(s)
    if before["difficulty"] == 0:
        pytest.skip("智能层尚未构建，先跑 examdata enrich")

    with session_scope() as s:
        result = reparse_documents(s, document_ids=[10])
    assert "error" not in result["derived"], result["derived"]

    with session_scope() as s:
        after = counts(s)
    assert after["taxonomy"] >= before["taxonomy"]
    assert after["difficulty"] >= before["difficulty"]
    assert after["difficulty"] == after["questions"], "每道题都必须有难度估计"


def test_reparse_relinks_mark_scheme_entries(clean_overrides):
    """重新解析试卷后，评分条目的题目关联不能丢。

    清题目时必须断开 MarkSchemeEntry.question_id（外键会挡住删除），
    但 Mark Scheme 文档通常不在本次重解析范围内，不会自己再跑一遍，
    所以断开的关联必须由重解析主动恢复——否则关联数会永久下降。
    """
    from sqlalchemy import func

    from examdata.core.models import MarkSchemeEntry

    def linked(s):
        return (
            s.scalar(
                select(func.count(MarkSchemeEntry.id)).where(
                    MarkSchemeEntry.question_id.is_not(None)
                )
            )
            or 0
        )

    with session_scope() as s:
        before = linked(s)
    if before == 0:
        pytest.skip("尚无关联数据，先跑 parse-docs")

    with session_scope() as s:
        reparse_documents(s, document_ids=[10])

    with session_scope() as s:
        after = linked(s)
    assert after >= before, f"重解析后关联数下降: {before} -> {after}"


def test_reparse_does_not_redownload(clean_overrides):
    """重解析只读本地 artifact：artifact 行数与 sha 必须不变。"""
    from examdata.core.models import Artifact
    from sqlalchemy import func

    with session_scope() as s:
        before = s.scalar(select(func.count(Artifact.id)))
        before_keys = set(s.scalars(select(Artifact.storage_key)).all())

    with session_scope() as s:
        reparse_documents(s, document_ids=[10])

    with session_scope() as s:
        after = s.scalar(select(func.count(Artifact.id)))
        after_keys = set(s.scalars(select(Artifact.storage_key)).all())
    assert after == before
    assert after_keys == before_keys


def test_reparse_keeps_revision_history(clean_overrides):
    """document_revision（版本链）是历史资源本身，重解析不能删。"""
    from examdata.core.models import DocumentRevision

    with session_scope() as s:
        before = {r.id for r in s.scalars(select(DocumentRevision)).all()}

    with session_scope() as s:
        reparse_documents(s, document_ids=[10])

    with session_scope() as s:
        after = {r.id for r in s.scalars(select(DocumentRevision)).all()}
    assert before <= after


# --------------------------------------------------------------------------
# 新旧对比
# --------------------------------------------------------------------------


def test_snapshot_reports_structure():
    with session_scope() as s:
        snap = snapshot(s, 10)
    d = snap.to_dict()
    assert d["questions"] > 0
    assert d["roots"] > 0
    assert d["roots"] <= d["questions"]
    assert d["max_depth"] >= 0
    assert d["duplicate_paths"] == 0


def test_diff_detects_zeroing_as_regression():
    before = DocumentSnapshot(document_id=1, doc_type="question_paper",
                              questions=10, roots=3, marks_sum=20, entries_linked=5)
    after = DocumentSnapshot(document_id=1, doc_type="question_paper",
                             questions=0, roots=0, marks_sum=0, entries_linked=0)
    result = diff(before, after)
    assert result.is_regression
    assert any("题目数归零" in r for r in result.regressions)


def test_diff_flags_mark_drop_beyond_tolerance():
    before = DocumentSnapshot(document_id=1, doc_type="question_paper",
                              questions=10, marks_sum=100)
    after = DocumentSnapshot(document_id=1, doc_type="question_paper",
                             questions=10, marks_sum=50)
    result = diff(before, after)
    assert result.is_regression
    assert any("marks_sum" in r for r in result.regressions)


def test_diff_treats_improvement_as_normal_change():
    before = DocumentSnapshot(document_id=1, doc_type="question_paper",
                              questions=10, marks_sum=50, entries_linked=3)
    after = DocumentSnapshot(document_id=1, doc_type="question_paper",
                             questions=12, marks_sum=60, entries_linked=8)
    result = diff(before, after)
    assert not result.is_regression
    assert result.changes, "改善也要记录，只是不算回归"


def test_diff_detects_duplicate_paths():
    before = DocumentSnapshot(document_id=1, doc_type="question_paper", duplicate_paths=0)
    after = DocumentSnapshot(document_id=1, doc_type="question_paper", duplicate_paths=3)
    result = diff(before, after)
    assert result.is_regression


def test_diff_of_identical_snapshots_is_empty():
    snap = DocumentSnapshot(document_id=1, doc_type="question_paper", questions=5)
    result = diff(snap, snap)
    assert result.changes == []
    assert not result.is_regression


# --------------------------------------------------------------------------
# 待检查队列
# --------------------------------------------------------------------------


def test_resolve_review_requires_explicit_status(clean_overrides):
    with session_scope() as s:
        task = s.scalars(select(ReviewTask)).first()
        if task is None:
            pytest.skip("没有待检查项")
        with pytest.raises(OverrideError):
            resolve_review(s, review_id=task.id, resolution="x", author="a", status="closed")


def test_resolve_review_marks_finding_resolved():
    with session_scope() as s:
        task = s.scalars(
            select(ReviewTask).where(ReviewTask.status == "open")
        ).first()
        if task is None:
            pytest.skip("没有开放的待检查项")
        task_id, ttype, tid, reason = task.id, task.target_type, task.target_id, task.reason

    with session_scope() as s:
        result = resolve_review(s, review_id=task_id, resolution="已核对", author="tester")
        assert result["status"] == "done"

    with session_scope() as s:
        finding = s.scalar(
            select(ValidationFinding).where(
                ValidationFinding.subject_type == ttype,
                ValidationFinding.subject_id == tid,
                ValidationFinding.rule_code == reason,
            )
        )
        if finding is not None:
            assert finding.status in ("resolved", "ignored")

    # 复原，避免影响 monitor 视图的断言
    with session_scope() as s:
        t = s.get(ReviewTask, task_id)
        t.status = "open"
        t.resolution = None


def test_list_reviews_filters_by_status():
    with session_scope() as s:
        open_rows = list_reviews(s, status="open", limit=5)
    assert isinstance(open_rows, list)
    for r in open_rows:
        assert r["status"] == "open"


# --------------------------------------------------------------------------
# 溯源
# --------------------------------------------------------------------------


def test_provenance_rebuild_is_idempotent():
    with session_scope() as s:
        first = rebuild(s)
    with session_scope() as s:
        second = rebuild(s)
    assert first == second, "纯投影必须可重复重建且结果一致"


def test_provenance_covers_every_question():
    with session_scope() as s:
        rebuild(s)
        cov = coverage(s)
    assert cov["question"]["ratio"] == 1.0
    assert cov["mark_scheme_entry"]["ratio"] == 1.0
    assert cov["asset"]["ratio"] == 1.0
    assert cov["paper"]["ratio"] == 1.0
    # 去重主体数不能超过总数（否则说明按边数算了）
    for c in cov.values():
        assert c["linked"] <= c["total"]


def _board_edge_counts(session) -> dict[str, int]:
    """按主体归属统计各考试局名下的溯源边数。

    资产可能被多个考试局共用，归属口径与 rebuild 的删除逻辑一致：
    看边上的 attrs.question_id 落在哪个考试局。
    """
    from examdata.core.models import (
        Board,
        Document,
        MarkScheme,
        MarkSchemeEntry,
        OfficialAnswer,
        ProvenanceEdge,
    )

    key_by_id = dict(session.execute(select(Board.id, Board.key)).all())
    question_board = dict(
        session.execute(
            select(Question.id, Document.board_id)
            .join(Paper, Paper.id == Question.paper_id)
            .join(Document, Document.id == Paper.document_id)
        ).all()
    )
    entry_board = dict(
        session.execute(
            select(MarkSchemeEntry.id, Document.board_id)
            .join(MarkScheme, MarkScheme.id == MarkSchemeEntry.mark_scheme_id)
            .join(Document, Document.id == MarkScheme.document_id)
        ).all()
    )
    answer_board = dict(
        session.execute(
            select(OfficialAnswer.id, Document.board_id)
            .join(Question, Question.id == OfficialAnswer.question_id)
            .join(Paper, Paper.id == Question.paper_id)
            .join(Document, Document.id == Paper.document_id)
        ).all()
    )
    paper_board = dict(
        session.execute(
            select(Paper.id, Document.board_id).join(
                Document, Document.id == Paper.document_id
            )
        ).all()
    )
    owners = {
        "question": question_board,
        "mark_scheme_entry": entry_board,
        "official_answer": answer_board,
        "paper": paper_board,
    }
    counts: dict[str, int] = {}
    for subject_type, owner in owners.items():
        for (subject_id,) in session.execute(
            select(ProvenanceEdge.subject_id).where(
                ProvenanceEdge.subject_type == subject_type
            )
        ).all():
            key = key_by_id.get(owner.get(subject_id))
            if key is not None:
                counts[key] = counts.get(key, 0) + 1
    for (attrs,) in session.execute(
        select(ProvenanceEdge.attrs).where(ProvenanceEdge.subject_type == "asset")
    ).all():
        key = key_by_id.get(question_board.get((attrs or {}).get("question_id")))
        if key is not None:
            counts[key] = counts.get(key, 0) + 1
    return counts


def test_provenance_rebuild_board_scope_keeps_other_boards():
    """按 board 重建只重投影该考试局，其它考试局的边必须原样保留。

    旧实现忽略 board 参数，等价于全量重建：重建任何一个考试局都会把整张表
    删空重写。这里用"其它考试局的边数不变"和"返回的统计不超过该考试局自己
    的主体数"两条锁定过滤行为。
    """
    from sqlalchemy import func

    from examdata.core.models import Board, Document

    with session_scope() as s:
        rebuild(s)  # 先做一次全量重建，避免依赖用例执行顺序
        qid = _some_question(s)
        target = s.scalar(
            select(Board.key)
            .join(Document, Document.board_id == Board.id)
            .join(Paper, Paper.document_id == Document.id)
            .join(Question, Question.paper_id == Paper.id)
            .where(Question.id == qid)
        )
        board_keys = list(s.scalars(select(Board.key).order_by(Board.id)).all())
        others = [k for k in board_keys if k != target]
        if not others:
            pytest.skip("库里只有一个考试局，无法验证其它考试局不受影响")
        before = _board_edge_counts(s)
    assert before.get(target, 0) > 0, "目标考试局必须已有溯源边"

    with session_scope() as s:
        stats = rebuild(s, board=target)

    with session_scope() as s:
        after = _board_edge_counts(s)
        rows = trace(s, "question", qid)
        cov = coverage(s)

    target_edges = after.get(target, 0)
    assert target_edges == before[target], "目标考试局的边重建后必须还在"
    assert sum(stats.values()) == target_edges, "重建该考试局必须把它的边完整投影回来"
    for key in others:
        assert after.get(key, 0) == before.get(key, 0), f"{key} 的边被按 board 重建误删"
    assert rows and rows[0]["source_url"], "按 board 重建后该考试局的边仍必须可追溯"
    assert cov["question"]["ratio"] == 1.0

    # 反向：重建别的考试局不能删改目标考试局的边，返回的统计也不能超过
    # 该考试局自己的主体数（旧实现返回的是全库统计）
    other = others[0]
    with session_scope() as s:
        other_questions = (
            s.scalar(
                select(func.count(Question.id))
                .join(Paper, Paper.id == Question.paper_id)
                .join(Document, Document.id == Paper.document_id)
                .join(Board, Board.id == Document.board_id)
                .where(Board.key == other)
            )
            or 0
        )
    with session_scope() as s:
        other_stats = rebuild(s, board=other)
    with session_scope() as s:
        assert _board_edge_counts(s).get(target, 0) == target_edges, (
            f"重建 {other} 时动了 {target} 的边"
        )
    assert other_stats["questions"] <= other_questions, (
        f"重建 {other} 时重投影了别家的题目：{other_stats['questions']} > {other_questions}"
    )


def test_provenance_trace_has_official_url():
    with session_scope() as s:
        qid = _some_question(s)
        rows = trace(s, "question", qid)
    assert rows, "每道题都必须能追到来源"
    assert rows[0]["source_kind"] == "official_resource"
    assert rows[0]["source_url"], "必须能追到官方资源 URL"
    assert rows[0]["source_ref"].startswith("document:")
    assert rows[0]["attrs"]["artifact_sha256"], "必须能追到原始文件内容哈希"


def test_provenance_trace_asset_points_to_question():
    with session_scope() as s:
        from examdata.core.models import Asset

        aid = s.scalar(select(Asset.id).order_by(Asset.id).limit(1))
        if aid is None:
            pytest.skip("没有资产")
        rows = trace(s, "asset", aid)
    assert rows
    assert rows[0]["attrs"]["question_id"] is not None


def test_provenance_trace_unknown_subject_is_empty():
    with session_scope() as s:
        assert trace(s, "question", 10**9) == []
