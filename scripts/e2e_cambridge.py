"""端到端验证：试卷解析 + Mark Scheme 解析 + 题目级关联。"""
from pathlib import Path

from examdata.parsing.pdfdoc import load_pdf
from examdata.parsing.metadata import extract_paper_metadata
from examdata.parsing.segment import build_question_tree
from examdata.markscheme.cambridge import CambridgeMarkSchemeParser, link_entries_to_questions

QP = Path(".data/samples/0580_qp_11.pdf")
MS = Path(".data/samples/0580_ms_11.pdf")

qp_doc = load_pdf(QP)
qp_md = extract_paper_metadata(qp_doc)
tree = build_question_tree(qp_doc, expected_total_marks=qp_md.total_marks)

ms_doc = load_pdf(MS)
ms_draft = CambridgeMarkSchemeParser().parse(ms_doc)

print("== 试卷 ==")
print(f"  {qp_md.subject_code}/{qp_md.paper_code}  {qp_md.session} {qp_md.year}  总分 {qp_md.total_marks}")
print(f"  题目数 {len(tree.roots)}  计算总分 {tree.total_marks}")

print()
print("== Mark Scheme ==")
print(f"  条目数 {ms_draft.metadata.get('entry_count')}  不同题号 {ms_draft.metadata.get('distinct_numbers')}")
print(f"  MS 分值合计 {ms_draft.metadata.get('total_marks')}")
print("  前 12 条:")
for e in ms_draft.entries[:12]:
    ans = (e.answer_text or "").replace("\n", " ")[:42]
    print(f"    {e.number_path:<9} marks={e.marks}  conf={e.parse_confidence}  {ans!r}")

# 关联：用轻量对象代替 ORM
class Q:
    def __init__(self, node, qid):
        self.id = qid
        self.number_path = node.number_path

questions = [Q(n, i + 1) for i, n in enumerate(tree.walk())]
linked, unmatched, without = link_entries_to_questions(ms_draft.entries, questions)

print()
print("== 题目级关联 ==")
print(f"  已关联条目 {len(linked)} / {len(ms_draft.entries)}")
print(f"  未匹配条目 {len(unmatched)}: {unmatched[:12]}")
print(f"  无评分标准的题目 {len(without)}: {without[:12]}")
cov = len(linked) / max(len(ms_draft.entries), 1)
print(f"  覆盖率 {cov:.1%}")
