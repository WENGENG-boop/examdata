"""为 103 张解析失败 QP 构建定向重切计划（含匹配 MS）。

- QP: 当前 revision.parse_status='failed' 且无题目的 QP 文档。
- MS: 用与 split_subject 相同的 _lookup_qp 逻辑找匹配这些 QP 的 MS 文档
  （同科目+series 内精确/归一化/单元家族匹配）。
输出: tmp_fixplan_failed_qp.json
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

from examdata.core.config import get_settings  # noqa: E402
from examdata.core.db import get_session_factory, init_db  # noqa: E402
from examdata.core.models import DocumentRevision  # noqa: E402
from examdata.edexcel_papers.pipeline import (  # noqa: E402
    DOC_MARK_SCHEME,
    DOC_QUESTION_PAPER,
    _documents,
    _lookup_qp,
    _paper_code_of,
    _subject,
)

def main() -> None:
    # read-only list of failed QP docs from sqlite
    con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
    cur = con.cursor()
    rows = list(cur.execute("""
    SELECT s.code, d.id
    FROM document d
    JOIN document_revision dr ON dr.document_id=d.id
    JOIN subject s ON s.id=d.subject_id
    JOIN qualification q ON q.id=s.qualification_id
    WHERE d.board_id=2 AND d.doc_type='question_paper' AND q.board_id=2
      AND NOT EXISTS (SELECT 1 FROM paper p WHERE p.document_id=d.id AND p.question_count>0)
      AND dr.parse_status='failed'
    """))
    con.close()
    failed: dict[str, list[int]] = {}
    for slug, did in rows:
        failed.setdefault(slug, []).append(did)
    print("failed QP docs by subject:", {k: len(v) for k, v in sorted(failed.items())})

    init_db()
    session = get_session_factory()()
    settings = get_settings()
    plan: dict = {}
    try:
        for slug, qp_ids in sorted(failed.items()):
            subject = _subject(session, slug)
            if subject is None:
                print(f"!! {slug}: not in db"); continue
            qp_docs = _documents(session, subject.id, DOC_QUESTION_PAPER, None, None)
            qp_index = {}
            for doc in qp_docs:
                revision = session.get(DocumentRevision, doc.current_revision_id)
                code = _paper_code_of(doc, revision)
                if code:
                    qp_index[(doc.subject_id, doc.series_id, code)] = doc
            failed_set = set(qp_ids)
            ms_docs = _documents(session, subject.id, DOC_MARK_SCHEME, None, None)
            ms_ids = []
            for doc in ms_docs:
                revision = session.get(DocumentRevision, doc.current_revision_id)
                code = _paper_code_of(doc, revision)
                qp_doc, conf, method = _lookup_qp(qp_index, doc, code)
                if qp_doc is not None and qp_doc.id in failed_set:
                    ms_ids.append(doc.id)
            plan[slug] = {"qp": sorted(qp_ids), "ms": sorted(ms_ids)}
            print(f"  {slug}: qp={len(qp_ids)} ms_matched={len(ms_ids)}")
    finally:
        session.close()

    out = ROOT / 'tmp_fixplan_failed_qp.json'
    out.write_text(json.dumps({"plan": plan}, ensure_ascii=False, indent=1), encoding='utf-8')
    nq = sum(len(v['qp']) for v in plan.values())
    nm = sum(len(v['ms']) for v in plan.values())
    print(f"plan written: {len(plan)} subjects, qp={nq}, ms={nm} -> {out.name}")


if __name__ == '__main__':
    main()
