"""r8/r13 专项核验：对 r8 重切的 84 卷与 r13 重切的 16 卷逐卷计算答案覆盖率。

复用 examdata.query.service.resolve_answer（与查询层一致）。
- r8 文档列表来自 tmp_r8_apply_write.out（applied.jsonl 为空文件）。
- r13 文档列表为 16 个硬编码 id。
输出：每卷覆盖率；0 覆盖卷数；最低/中位覆盖率；<50% 的卷明细。
"""
from __future__ import annotations

import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "src")
from examdata.query.service import AnswerEntry, resolve_answer  # noqa: E402

ROOT = Path(__file__).resolve().parent
R13_DOCS = [3487, 3553, 3554, 3555, 3556, 3564, 3566, 3578, 3590, 3591, 3598, 3609, 3625, 3627, 3628, 3666]

txt = (ROOT / "tmp_r8_apply_write.out").read_text(encoding="utf-8")
r8_docs = sorted({int(m) for m in re.findall(r"doc (\d+): matched=", txt)})
print(f"r8 docs from write.out: {len(r8_docs)}")

DB = sys.argv[1] if len(sys.argv) > 1 else "file:.data/examdata.db?mode=ro"
print(f"db: {DB}")
conn = sqlite3.connect(DB, uri=True)

questions = list(conn.execute(
    """
    select q.id, q.number_path, p.document_id
      from question q join paper p on p.id = q.paper_id
    """
))
q_by_doc: dict[int, list[tuple[int, str]]] = defaultdict(list)
for qid, path, doc_id in questions:
    q_by_doc[doc_id].append((qid, path or ""))

scheme_by_doc: dict[int, list[int]] = defaultdict(list)
for ms_id, doc_id in conn.execute(
    "select id, matched_paper_document_id from mark_scheme where matched_paper_document_id is not null"
):
    scheme_by_doc[doc_id].append(ms_id)

entries_by_scheme: dict[int, list] = defaultdict(list)
for eid, ms_id, path, text, qid in conn.execute(
    "select id, mark_scheme_id, number_path, answer_text, question_id from mark_scheme_entry"
):
    entries_by_scheme[ms_id].append((eid, path or "", text, qid))

entries_by_doc: dict[int, dict[str, list[AnswerEntry]]] = {}
for doc_id, scheme_ids in scheme_by_doc.items():
    by_path: dict[str, list[AnswerEntry]] = defaultdict(list)
    for ms_id in scheme_ids:
        for eid, path, text, _qid in entries_by_scheme.get(ms_id, ()):
            if path:
                by_path[path].append(AnswerEntry(eid, path, text))
    entries_by_doc[doc_id] = dict(by_path)

exact_by_question: dict[int, list[AnswerEntry]] = defaultdict(list)
for eid, qid, path, text in conn.execute(
    "select id, question_id, number_path, answer_text from mark_scheme_entry where question_id is not null"
):
    exact_by_question[qid].append(AnswerEntry(eid, path or "", text))

official_by_question: dict[int, list[AnswerEntry]] = defaultdict(list)
for oid, qid, content in conn.execute(
    "select id, question_id, content from official_answer"
):
    official_by_question[qid].append(AnswerEntry(oid, "", content))


def doc_coverage(doc_id: int) -> tuple[int, int]:
    qs = q_by_doc.get(doc_id, [])
    covered = 0
    for qid, path in qs:
        ans = resolve_answer(
            path,
            exact_entries=exact_by_question.get(qid, ()),
            entries_by_path=entries_by_doc.get(doc_id, {}),
            official_entries=official_by_question.get(qid, ()),
        )
        if ans:
            covered += 1
    return covered, len(qs)


def report(name: str, docs: list[int]) -> None:
    rows = []
    for d in docs:
        cov, tot = doc_coverage(d)
        rows.append((d, cov, tot, (cov / tot * 100) if tot else 0.0))
    zero = [r for r in rows if r[1] == 0 and r[2] > 0]
    empty = [r for r in rows if r[2] == 0]
    pcts = sorted(r[3] for r in rows if r[2] > 0)
    med = pcts[len(pcts) // 2] if pcts else 0.0
    print(f"=== {name}: {len(docs)} docs ===")
    print(f"  zero-coverage: {len(zero)}  no-questions: {len(empty)}")
    if pcts:
        print(f"  coverage min={pcts[0]:.1f}% median={med:.1f}% max={pcts[-1]:.1f}%")
    for r in zero:
        print(f"  ZERO doc {r[0]} q={r[2]}")
    low = [r for r in rows if r[2] > 0 and r[3] < 50]
    for d, cov, tot, pct in low:
        print(f"  LOW  doc {d} cov={cov}/{tot} ({pct:.1f}%)")


report("r8 resplit docs", r8_docs)
report("r13 resplit docs", R13_DOCS)
