"""人工修正的解析器版本适用范围：锁定 `_apply_overrides` 的 "*" 语义。

`FieldOverride.applies_to_parser_versions` 的默认值是字符串 "*"，表示
"适用于所有解析器版本"。旧实现写成：

    if ov.applies_to_parser_versions and parse_run.parser_version not in ov.applies_to_parser_versions:

applies 是字符串时 `not in` 退化成**子串匹配**：`"0.1.0" not in "*"` 为 True，
于是"适用于所有版本"的修正反而被判为不适用——不应用，还被标记冲突。
现在改为显式比较 `applies != "*"`，非列表值先包装成单元素列表再比较。

测试跑进程内 SQLite（真实 ORM 行、真实 JSON 列往返），既不依赖
.data/examdata.db 是否已有数据，也不会给共享库留下残留行。
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from examdata.core.config import get_settings
from examdata.core.models import (
    Base,
    Board,
    Document,
    FieldOverride,
    Paper,
    ParseRun,
    Question,
)
from examdata.parsing.pipeline import ParsePipeline

# 当前解析器版本。不写死 "0.1.0"（默认值）：用例要验证的是"适用范围是否命中
# 当前版本"，版本号升级不该把用例变成另一件事。
CURRENT_VERSION = get_settings().parser_version
# 确定与当前版本不同的旧版本号，用于"适用范围不含当前版本"的用例。
STALE_VERSION = "0.0.9"


@pytest.fixture
def session():
    """进程内 SQLite：真实表结构，测试之间互不可见。"""
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    try:
        with Session(bind=engine, future=True) as s:
            yield s
    finally:
        engine.dispose()


def _question(session: Session, marks: int = 2) -> Question:
    """落一条最小可用的题目行：_apply_overrides 按 (target_type, target_id) 查修正。"""
    board = Board(key="test-board", name="Test Board")
    session.add(board)
    session.flush()
    document = Document(
        identity_key="test-document", board_id=board.id, doc_type="question_paper"
    )
    session.add(document)
    session.flush()
    paper = Paper(document_id=document.id, paper_no="1")
    session.add(paper)
    session.flush()
    question = Question(
        paper_id=paper.id,
        number_label="1",
        number_path="1",
        display_order=1,
        marks=marks,
    )
    session.add(question)
    session.flush()
    return question


def _override(session: Session, question: Question, applies) -> FieldOverride:
    """落一条人工修正行。

    只写修正表、不动题目：_apply_overrides 拿题目当前值与 source_value 比对，
    重解析产出的题目对象应当是自动解析值（source_value），而不是人工值。
    """
    override = FieldOverride(
        target_type="question",
        target_id=question.id,
        field_path="marks",
        value=7,
        source_value=2,
        author="tester",
        active=True,
        applies_to_parser_versions=applies,
        conflict_detected=False,
        attrs={},
    )
    session.add(override)
    session.commit()
    return override


def _apply(session: Session, question: Question, version: str = CURRENT_VERSION) -> None:
    """跑一次 _apply_overrides 并提交，让断言落在落库状态而非内存改动上。"""
    parse_run = ParseRun(parser_version=version)
    session.add(parse_run)
    session.flush()
    ParsePipeline(session)._apply_overrides("question", question, parse_run)
    session.commit()


# --------------------------------------------------------------------------
# 适用范围：所有版本
# --------------------------------------------------------------------------


@pytest.mark.parametrize("applies", ["*", "", None])
def test_wildcard_applies_to_every_version(session, applies):
    """'*'（以及空值）表示适用于所有版本：应用人工值，且不得标记冲突。

    这是本次修复的核心：旧实现下 "*" 被当成待匹配的字符串，任何版本号都
    不可能是它的子串，于是修正被判为"不适用"。
    """
    question = _question(session)
    override = _override(session, question, applies)

    _apply(session, question)

    assert question.marks == 7
    assert question.has_override is True
    assert override.conflict_detected is False
    assert override.conflict_detail is None


# --------------------------------------------------------------------------
# 适用范围：指定版本
# --------------------------------------------------------------------------


def test_other_version_does_not_apply_and_flags_conflict(session):
    """适用范围不含当前版本：不写入人工值，标记冲突待人工确认。"""
    assert STALE_VERSION != CURRENT_VERSION, "用例前提：该版本号不是当前版本"
    question = _question(session)
    override = _override(session, question, STALE_VERSION)

    _apply(session, question)

    assert question.marks == 2, "版本不匹配时不得写入人工值"
    assert question.has_override is False
    assert override.conflict_detected is True
    assert CURRENT_VERSION in override.conflict_detail


def test_current_version_in_list_applies(session):
    """适用范围列表命中当前版本：正常应用，不标记冲突。"""
    question = _question(session)
    override = _override(session, question, [CURRENT_VERSION])

    _apply(session, question)

    assert question.marks == 7
    assert question.has_override is True
    assert override.conflict_detected is False


def test_bare_version_string_is_matched_as_whole_value(session):
    """applies 存成裸字符串（非列表）时按单元素列表比较，不做子串匹配。"""
    question = _question(session)
    override = _override(session, question, CURRENT_VERSION)

    _apply(session, question)

    assert question.marks == 7
    assert question.has_override is True
    assert override.conflict_detected is False
