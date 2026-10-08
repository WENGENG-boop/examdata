"""只读：核验 17 组同名不同编号 spec 点的上下文 + question_taxonomy 完整性。

用法: python tmp_dup_context.py
输出: tmp_dup_context.txt
"""
from __future__ import annotations

import json
import sqlite3

con = sqlite3.connect("file:.data/examdata.db?mode=ro", uri=True)
cur = con.cursor()

lines: list[str] = []

# 1) dump the 17 dup groups with full names + parent chains
GROUPS = [
    ["WPS01I5-1.2.8", "WPS02I5-4.2.6"],
    ["WPS04I5-8.3.2", "WPS04I5-9.1.15"],
    ["WPS03I5-5.3.4", "WPS03I5-6.3.3", "WPS03I5-7.3.3", "WPS04I5-8.3.4"],
    ["WPS01I5-2.2.11", "WPS02I5-3.2.7", "WPS02I5-4.2.5"],
    ["WBS13-3.3.3.4(c)", "WBS13-3.3.5.2(a)"],
    ["WBS13-3.3.3.2(d)", "WBS13-3.3.3.3(b)"],
    ["WBS14-4.3.2.2(a)", "WBS14-4.3.2.3(a)", "WBS14-4.3.4.3(a)"],
    ["WCP01-3.1.1", "WCP01-3.1.2"],
    ["WFM02-4.3", "WFM02-5.2"],
    ["WME01-4.4", "WME01-5.3"],
    ["WPH14-86", "WPH14-115"],
    ["WPH14-94", "WPH14-95", "WPH14-97", "WPH14-101"],
    ["WPH15-132", "WPH15-157"],
    ["WPH15-156", "WPH15-158"],
    ["WPS02-3.2.7", "WPS02-4.2.5"],
    ["WPS03-5.3.4", "WPS03-6.3.3", "WPS03-7.3.3"],
    ["WPS04-8.3.2", "WPS04-9.1.15"],
]

rows = cur.execute(
    "select id, parent_id, code, name, node_type, attrs from taxonomy_node where board_id=2"
).fetchall()
by_id = {r[0]: r for r in rows}
by_code = {r[2]: r for r in rows}


def chain(code: str) -> str:
    r = by_code.get(code)
    if not r:
        return "MISSING"
    parts = []
    cur_id = r[0]
    seen = 0
    while cur_id and seen < 8:
        n = by_id.get(cur_id)
        if not n:
            break
        parts.append(f"{n[2]}={n[3]!r}")
        cur_id = n[1]
        seen += 1
    return " < ".join(parts)


lines.append("== 17 dup-name groups: full context ==")
for g in GROUPS:
    lines.append("-" * 100)
    for code in g:
        r = by_code.get(code)
        nm = r[3] if r else "MISSING"
        lines.append(f"[{code}] name={nm!r}")
        lines.append(f"    chain: {chain(code)}")

# 2) question_taxonomy integrity
n_q = cur.execute("select count(*) from question_taxonomy").fetchone()[0]
dup_pairs = cur.execute(
    "select question_id, node_id, count(*) c from question_taxonomy "
    "group by question_id, node_id having c > 1"
).fetchall()
dangling = cur.execute(
    "select count(*) from question_taxonomy qt left join taxonomy_node tn on tn.id=qt.node_id "
    "where tn.id is null"
).fetchone()[0]
multi = cur.execute(
    "select c, count(*) from (select question_id, count(*) c from question_taxonomy group by question_id) group by c order by c"
).fetchall()
lines.append("")
lines.append("== question_taxonomy integrity ==")
lines.append(f"rows={n_q} dup(question,node) pairs={len(dup_pairs)} dangling node refs={dangling}")
lines.append(f"labels-per-question distribution (count -> #questions): {multi}")
if dup_pairs:
    for p in dup_pairs[:20]:
        lines.append(f"  DUP: q={p[0]} node={p[1]} x{p[2]}")

# 3) sanity: same question same code via different node ids?
same_code_diff_node = cur.execute(
    "select qt.question_id, tn.code, count(distinct qt.node_id) c "
    "from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id "
    "group by qt.question_id, tn.code having c > 1 limit 20"
).fetchall()
lines.append(f"same question+code via multiple node ids: {len(same_code_diff_node)}")
for r in same_code_diff_node:
    lines.append(f"  {r}")

out = "\n".join(lines)
open("tmp_dup_context.txt", "w", encoding="utf-8").write(out)
print(out)
