"""只读：统计 0% 答案覆盖试卷（QP 有题但全部无答案），并分类 A/B/C。

- A：该 QP 无任何匹配 MS（matched_paper_document_id 指向它）
- B：有匹配 MS 但 MS 条目全空（0 条目）
- C：其他（有非空条目但全部路径不匹配）
同时统计全库匹配到的 MS 文档中 0 条目的数量。
"""

from __future__ import annotations

import sqlite3
import sys
from collections import Counter, defaultdict

sys.path.insert(0, "src")

from examdata.query.service import AnswerEntry, resolve_answer  # noqa: E402

DB = "file:.data/examdata.db?mode=ro"


def main() -> None:
    conn = sqlite3.connect(DB, uri=True)

    questions: list[tuple[int, str, int, str]] = [
        (qid, path, doc_id, subject_code or "?")
        for qid, path, doc_id, subject_code in conn.execute(
            """
            select q.id, q.number_path, p.document_id, s.code
              from question q
              join paper p on p.id = q.paper_id
              left join document d on d.id = p.document_id
              left join subject s on s.id = d.subject_id
            """
        )
    ]

    scheme_by_doc: dict[int, list[int]] = defaultdict(list)
    for ms_id, doc_id in conn.execute(
        "select id, matched_paper_document_id from mark_scheme"
        " where matched_paper_document_id is not null"
    ):
        scheme_by_doc[doc_id].append(ms_id)

    entries_by_scheme: dict[int, list[tuple[int, str, str | None, int | None]]] = defaultdict(list)
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
        "select id, question_id, number_path, answer_text from mark_scheme_entry"
        " where question_id is not null"
    ):
        exact_by_question[qid].append(AnswerEntry(eid, path or "", text))
    official_by_question: dict[int, list[AnswerEntry]] = defaultdict(list)
    for oid, qid, content in conn.execute(
        "select id, question_id, content from official_answer"
    ):
        official_by_question[qid].append(AnswerEntry(oid, "", content))

    per_doc_total: Counter[int] = Counter()
    per_doc_covered: Counter[int] = Counter()
    for qid, path, doc_id, subject in questions:
        per_doc_total[doc_id] += 1
        answer = resolve_answer(
            path,
            exact_entries=exact_by_question.get(qid, ()),
            entries_by_path=entries_by_doc.get(doc_id, {}),
            official_entries=official_by_question.get(qid, ()),
        )
        if answer:
            per_doc_covered[doc_id] += 1

    # doc info
    doc_info = {
        doc_id: (title, subject)
        for doc_id, title, subject in conn.execute(
            """
            select d.id, d.title, s.code from document d
            left join subject s on s.id = d.subject_id
            """
        )
    }

    zero_docs = [
        (doc_id, per_doc_total[doc_id], doc_info.get(doc_id, ("?", "?"))[1])
        for doc_id in per_doc_total
        if per_doc_covered[doc_id] == 0
    ]
    print(f"QP 有题但 0% 答案覆盖: {len(zero_docs)} 张")
    cat = Counter()
    rows_out = []
    for doc_id, nq, subject in sorted(zero_docs, key=lambda r: (r[2], r[0])):
        schemes = scheme_by_doc.get(doc_id, [])
        if not schemes:
            c = "A(无匹配MS)"
        elif all(len(entries_by_scheme.get(ms, ())) == 0 for ms in schemes):
            c = "B(MS全空)"
        else:
            c = "C(其他)"
        cat[c] += 1
        title = doc_info.get(doc_id, ("?", ""))[0]
        rows_out.append((doc_id, subject, nq, c, title))
    print("分类:", dict(cat))
    print()
    for r in rows_out:
        print(f"  doc {r[0]:<5} {r[1]:<24} q={r[2]:<3} {r[3]:<10} {r[4]}")
    print()

    # 全库匹配 MS 文档中 0 条目
    empty_ms = []
    for doc_id, scheme_ids in scheme_by_doc.items():
        for ms in scheme_ids:
            if len(entries_by_scheme.get(ms, ())) == 0:
                empty_ms.append((ms, doc_id))
    print(f"匹配到但 0 条目的 MS 文档数（含重复计数按 ms 记录）: {len(empty_ms)}")
    # 去重按 ms 文档
    ms_doc_ids = {ms for ms, _ in empty_ms}
    print(f"其中 distinct MS id: {len(ms_doc_ids)}")
    # 这些 MS 对应哪些 QP 文档
    qp_of_empty = Counter()
    for ms, doc_id in empty_ms:
        qp_of_empty[doc_id] += 1
    print(f"涉及 QP 文档数: {len(qp_of_empty)}")


if __name__ == "__main__":
    main()
