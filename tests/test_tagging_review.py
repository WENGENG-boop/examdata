"""复核导出/回写测试：自建临时库，不依赖真实语料。

覆盖：低置信导出包（points 清单 + 分批 JSONL）、keep/change/drop 回写、
校验失败清单、reviewed 行对 ``assign --replace`` 的冻结保护。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core.models import (
    Base,
    Board,
    Document,
    Paper,
    Question,
    QuestionTaxonomy,
    Qualification,
    Subject,
    TaxonomyNode,
)
from examdata.tagging.assign import (
    ASSIGNED_BY,
    REVIEW_ASSIGNED_BY,
    REVIEW_SOURCE,
    assign,
)
from examdata.tagging.review import apply_review, export_review


def _seed(session: Session) -> dict[str, int]:
    ids: dict[str, int] = {}
    board = Board(key="edexcel", name="Pearson Edexcel")
    session.add(board)
    session.flush()
    qual = Qualification(board_id=board.id, key="ial", name="International A Level")
    session.add(qual)
    session.flush()
    subject = Subject(qualification_id=qual.id, code="wbi11", title="Biology", slug="wbi11")
    session.add(subject)
    session.flush()

    def node(code, name, node_type, parent=None, attrs=None):
        row = TaxonomyNode(
            board_id=board.id,
            parent_id=parent.id if parent is not None else None,
            code=code,
            name=name,
            node_type=node_type,
            source="official",
            attrs=dict(attrs or {}),
        )
        session.add(row)
        session.flush()
        return row

    point_attrs = {"subject": "wbi11", "text": ""}
    unit11 = node("WBI11", "Unit 1", "unit")
    topic11 = node("WBI11-1", "Biological molecules", "topic", unit11)
    sub11 = node("WBI11-1.1", "Molecules", "subtopic", topic11)
    p1 = node("WBI11-1.1.1", "The structure of starch as a polysaccharide", "point", sub11, point_attrs)
    p2 = node("WBI11-1.1.2", "The structure of glycogen as a polysaccharide", "point", sub11, point_attrs)
    p3 = node("WBI11-1.1.3", "The structure of triglycerides", "point", sub11, point_attrs)
    unit12 = node("WBI12", "Unit 2", "unit")
    topic12 = node("WBI12-1", "Genes and health", "topic", unit12)
    sub12 = node("WBI12-1.1", "DNA", "subtopic", topic12)
    p4 = node("WBI12-1.1.1", "The structure of DNA nucleotides", "point", sub12, point_attrs)
    ids.update(p1=p1.id, p2=p2.id, p3=p3.id, p4=p4.id)

    def document(identity_key, paper_code):
        row = Document(
            board_id=board.id,
            subject_id=subject.id,
            identity_key=identity_key,
            doc_type="question_paper",
            paper_code=paper_code,
            year=2024,
        )
        session.add(row)
        session.flush()
        return row

    def question(paper, label, stem):
        row = Question(
            paper_id=paper.id,
            number_label=label,
            number_path=label,
            display_order=int(label),
            stem_text=stem,
            marks=1,
        )
        session.add(row)
        session.flush()
        return row

    doc_a = document("wbi11-01-qp", "mock-01")
    paper_a = Paper(document_id=doc_a.id, attrs={"unit_code": "WBI11"})
    session.add(paper_a)
    session.flush()
    q1 = question(paper_a, "1", "Describe the structure of starch and glycogen as polysaccharides.")
    q2 = question(paper_a, "2", "Describe the structure of triglycerides.")

    doc_b = document("wbi12-01-qp", "wbi12-01")
    paper_b = Paper(document_id=doc_b.id, attrs={})
    session.add(paper_b)
    session.flush()
    q4 = question(paper_b, "4", "Describe the structure of DNA nucleotides.")
    ids.update(q1=q1.id, q2=q2.id, q4=q4.id)
    return ids


@pytest.fixture()
def seeded(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "review.db").as_posix())
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        ids = _seed(session)
        session.commit()
        yield session, ids
    engine.dispose()


def _rows(session: Session, question_id: int) -> list[QuestionTaxonomy]:
    return list(
        session.scalars(
            select(QuestionTaxonomy).where(QuestionTaxonomy.question_id == question_id)
        )
    )


def _write_decisions(path: Path, rows: list[dict]) -> Path:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def test_export_review_bundles_low_confidence_items(seeded, tmp_path):
    session, ids = seeded
    assign(session, dry_run=False, review_dir=tmp_path / "r1")
    session.commit()

    out_dir = tmp_path / "review-out"
    stats = export_review(session, subject="wbi11", out_dir=out_dir)
    assert stats["subject"] == "wbi11"
    assert stats["items"] >= 1
    assert stats["units"] == 2

    points_file = Path(stats["points_file"])
    payload = json.loads(points_file.read_text(encoding="utf-8"))
    assert set(payload["units"]) == {"WBI11", "WBI12"}
    assert any(row["code"] == "WBI11-1.1.3" for row in payload["units"]["WBI11"])

    items = {}
    for batch in sorted((out_dir / "batches").glob("*.jsonl")):
        for line in batch.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            items[item["question_id"]] = item
    assert ids["q1"] in items  # 淀粉+糖原同分并列 → 低置信
    item = items[ids["q1"]]
    assert "starch" in item["stem"]
    assert {row["code"] for row in item["current"]} == {"WBI11-1.1.1", "WBI11-1.1.2"}
    assert all(row["confidence"] < 0.35 for row in item["current"])

    with pytest.raises(LookupError):
        export_review(session, subject="nosuch", out_dir=tmp_path / "nope")


def test_apply_review_keep_change_drop(seeded, tmp_path):
    session, ids = seeded
    assign(session, dry_run=False, review_dir=tmp_path / "r1")
    session.commit()
    before = {qid: len(_rows(session, qid)) for qid in (ids["q1"], ids["q2"], ids["q4"])}
    assert all(count >= 1 for count in before.values())

    decisions = _write_decisions(
        tmp_path / "decisions.jsonl",
        [
            {"question_id": ids["q1"], "decision": "keep", "reason": "correct"},
            {"question_id": ids["q2"], "decision": "change", "code": "WBI11-1.1.1", "reason": "wrong point"},
            {"question_id": ids["q4"], "decision": "drop", "reason": "noise"},
        ],
    )

    dry = apply_review(session, subject="wbi11", decisions_path=decisions, dry_run=True)
    assert (dry["kept"], dry["changed"], dry["dropped"], dry["errors"]) == (1, 1, 1, [])
    assert {qid: len(_rows(session, qid)) for qid in before} == before  # dry-run 不落库
    assert all(not row.reviewed for row in _rows(session, ids["q1"]))

    stats = apply_review(session, subject="wbi11", decisions_path=decisions, dry_run=False)
    session.commit()
    assert (stats["kept"], stats["changed"], stats["dropped"], stats["errors"]) == (1, 1, 1, [])

    q1_rows = _rows(session, ids["q1"])
    assert len(q1_rows) == before[ids["q1"]]
    assert all(row.reviewed for row in q1_rows)
    assert all(row.assigned_by == ASSIGNED_BY for row in q1_rows)

    q2_rows = _rows(session, ids["q2"])
    assert len(q2_rows) == 1
    assert q2_rows[0].source == REVIEW_SOURCE
    assert q2_rows[0].assigned_by == REVIEW_ASSIGNED_BY
    assert q2_rows[0].reviewed is True
    assert q2_rows[0].confidence == 1.0
    assert q2_rows[0].node_id == ids["p1"]

    assert _rows(session, ids["q4"]) == []


def test_apply_review_reports_invalid_decisions(seeded, tmp_path):
    session, ids = seeded
    assign(session, dry_run=False, review_dir=tmp_path / "r1")
    session.commit()
    decisions = _write_decisions(
        tmp_path / "bad.jsonl",
        [
            {"question_id": ids["q1"], "decision": "change", "code": "WBI12-1.1.1"},  # 跨单元
            {"question_id": ids["q1"], "decision": "keep"},  # 重复
            {"question_id": 999999, "decision": "keep"},  # 不存在
            {"question_id": ids["q2"], "decision": "nope"},  # 未知决策
            {"question_id": ids["q2"], "decision": "change", "code": "WBI99-9.9.9"},  # 非本科研点
        ],
    )
    stats = apply_review(session, subject="wbi11", decisions_path=decisions, dry_run=True)
    assert (stats["kept"], stats["changed"], stats["dropped"]) == (0, 0, 0)
    assert len(stats["errors"]) == 5
    assert any("duplicate" in message for message in stats["errors"])
    assert any("belongs to unit" in message for message in stats["errors"])
    assert all(not row.reviewed for row in _rows(session, ids["q1"]))


def test_assign_replace_freezes_reviewed_questions(seeded, tmp_path):
    session, ids = seeded
    assign(session, dry_run=False, review_dir=tmp_path / "r1")
    session.commit()
    q4_before = len(_rows(session, ids["q4"]))

    decisions = _write_decisions(
        tmp_path / "decisions.jsonl",
        [
            {"question_id": ids["q1"], "decision": "keep", "reason": "correct"},
            {"question_id": ids["q2"], "decision": "change", "code": "WBI11-1.1.1", "reason": "wrong point"},
            {"question_id": ids["q4"], "decision": "drop", "reason": "noise"},
        ],
    )
    apply_review(session, subject="wbi11", decisions_path=decisions, dry_run=False)
    session.commit()

    stats = assign(session, dry_run=False, replace=True, review_dir=tmp_path / "r2")
    session.commit()
    assert stats["skipped_reviewed"] == 2  # q1 keep、q2 change 都冻结
    assert stats["replaced"] == 0

    q1_rows = _rows(session, ids["q1"])
    assert all(row.reviewed for row in q1_rows)
    q2_rows = _rows(session, ids["q2"])
    assert len(q2_rows) == 1 and q2_rows[0].source == REVIEW_SOURCE
    # drop 不写标记行：重跑会重新标注（已知取舍，复核日志里留有原因）
    assert len(_rows(session, ids["q4"])) == q4_before


def test_cli_review_subcommand_defaults():
    from examdata.tagging.cli import build_parser

    apply_args = build_parser().parse_args(
        ["review-apply", "--subject", "wbi11", "--decisions", "d.jsonl"]
    )
    assert apply_args.write is False
    export_args = build_parser().parse_args(
        ["review-export", "--subject", "wbi11", "--out", "out"]
    )
    assert export_args.batch_size >= 1 and export_args.max_confidence > 0
