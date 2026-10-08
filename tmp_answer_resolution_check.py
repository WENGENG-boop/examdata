"""只读全库答案解析体检：统计每道题最终落到 exact / ancestor / descendants / none。

- 只读打开 `.data/examdata.db`（mode=ro），不写任何表。
- 复用 `examdata.query.service.resolve_answer` 的同一套纯函数逻辑；
  与查询层一致：按题目所在 QP 文档聚合匹配到的 MS 条目，再逐题在内存解析。
- 输出总计与逐科目的来源分布，并报告耗时。
"""

from __future__ import annotations

import sqlite3
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, "src")

from examdata.query.service import AnswerEntry, resolve_answer  # noqa: E402

DB = "file:.data/examdata.db?mode=ro"


def main() -> None:
    started = time.perf_counter()
    conn = sqlite3.connect(DB, uri=True)

    # 题目 -> QP 文档 / 科目
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
    # 题目 -> 考试局（用于按 board 汇总）
    question_board: dict[int, str] = {
        qid: board
        for qid, board in conn.execute(
            """
            select q.id, b.key
              from question q
              join paper p on p.id = q.paper_id
              join document d on d.id = p.document_id
              join board b on b.id = d.board_id
            """
        )
    }

    # QP 文档 -> 匹配到的 MS 集合（一个 QP 文档可能匹配多份 MS）
    scheme_by_doc: dict[int, list[int]] = defaultdict(list)
    for ms_id, doc_id in conn.execute(
        "select id, matched_paper_document_id from mark_scheme"
        " where matched_paper_document_id is not null"
    ):
        scheme_by_doc[doc_id].append(ms_id)

    # MS -> 条目
    entries_by_scheme: dict[int, list[tuple[int, str, str | None, int | None]]] = defaultdict(list)
    for eid, ms_id, path, text, qid in conn.execute(
        "select id, mark_scheme_id, number_path, answer_text, question_id from mark_scheme_entry"
    ):
        entries_by_scheme[ms_id].append((eid, path or "", text, qid))

    # 文档 -> {路径: 条目}
    entries_by_doc: dict[int, dict[str, list[AnswerEntry]]] = {}
    for doc_id, scheme_ids in scheme_by_doc.items():
        by_path: dict[str, list[AnswerEntry]] = defaultdict(list)
        for ms_id in scheme_ids:
            for eid, path, text, _qid in entries_by_scheme.get(ms_id, ()):
                if path:
                    by_path[path].append(AnswerEntry(eid, path, text))
        entries_by_doc[doc_id] = dict(by_path)

    # question_id 直连条目 与 official_answer
    exact_by_question: dict[int, list[AnswerEntry]] = defaultdict(list)
    linked_total = 0
    for eid, qid, path, text in conn.execute(
        "select id, question_id, number_path, answer_text from mark_scheme_entry"
        " where question_id is not null"
    ):
        linked_total += 1
        exact_by_question[qid].append(AnswerEntry(eid, path or "", text))
    official_by_question: dict[int, list[AnswerEntry]] = defaultdict(list)
    official_total = 0
    for oid, qid, content in conn.execute(
        "select id, question_id, content from official_answer"
    ):
        official_total += 1
        official_by_question[qid].append(AnswerEntry(oid, "", content))

    # 不变式：question_id 直连的条目必然来自该题 QP 文档匹配到的 MS
    doc_of_question = {qid: doc_id for qid, _path, doc_id, _subject in questions}
    question_of_entry: dict[int, int] = {}
    for ms_id, rows in entries_by_scheme.items():
        for eid, _path, _text, qid in rows:
            if qid is not None:
                question_of_entry[eid] = qid
    scheme_of_entry = {
        eid: ms_id for ms_id, rows in entries_by_scheme.items() for eid, *_ in rows
    }
    mismatched = 0
    for eid, qid in question_of_entry.items():
        doc_id = doc_of_question.get(qid)
        if doc_id is None or scheme_of_entry.get(eid) not in scheme_by_doc.get(doc_id, ()):
            mismatched += 1

    # 逐题解析
    overall: Counter[str] = Counter()
    per_subject: dict[str, Counter[str]] = defaultdict(Counter)
    per_board: dict[str, Counter[str]] = defaultdict(Counter)
    samples: dict[str, tuple[int, str]] = {}
    for qid, path, doc_id, subject in questions:
        answer = resolve_answer(
            path,
            exact_entries=exact_by_question.get(qid, ()),
            entries_by_path=entries_by_doc.get(doc_id, {}),
            official_entries=official_by_question.get(qid, ()),
        )
        source = answer["source"] if answer else "none"
        overall[source] += 1
        per_subject[subject][source] += 1
        per_board[question_board.get(qid, "?")][source] += 1
        if source not in samples:
            samples[source] = (qid, (answer or {}).get("text", "")[:70].replace("\n", " "))

    elapsed = time.perf_counter() - started
    total = len(questions)

    def report(title: str, counts: Counter[str], scope_total: int) -> None:
        print(f"=== {title}（{scope_total} 题） ===")
        for source in ("exact", "ancestor", "descendants", "none"):
            count = counts[source]
            print(f"  {source:<12} {count:>6}  {count / scope_total * 100:5.1f}%")
        covered = scope_total - counts["none"]
        print(f"  {'有答案合计':<10} {covered:>6}  {covered / scope_total * 100:5.1f}%")
        print()

    print(f"题目总数: {total}")
    print(f"exact 直连条目: {linked_total}  official_answer: {official_total}")
    print(f"不变式违规（直连条目不在该题 QP 匹配 MS 中）: {mismatched}")
    print()
    report("来源分布（全库）", overall, total)
    for board in sorted(per_board):
        report(f"来源分布（board={board}）", per_board[board], sum(per_board[board].values()))
    print("=== 来源分布（逐科目） ===")
    print(f"{'科目':<26}{'题目':>7}{'exact':>8}{'ancestor':>9}{'desc':>8}{'none':>8}{'覆盖率':>9}")
    for subject in sorted(per_subject, key=lambda s: (-sum(per_subject[s].values()), s)):
        counts = per_subject[subject]
        subject_total = sum(counts.values())
        covered = subject_total - counts["none"]
        print(
            f"{subject:<26}{subject_total:>7}{counts['exact']:>8}{counts['ancestor']:>9}"
            f"{counts['descendants']:>8}{counts['none']:>8}{covered / subject_total * 100:>8.1f}%"
        )
    print()
    print("=== 各来源样例 ===")
    for source, (qid, text) in samples.items():
        print(f"  {source:<12} q{qid}: {text}")
    print()
    print(f"脚本耗时: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
