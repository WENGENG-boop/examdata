"""r3 review helper: dump full subtree (labels, stems, MS) for given qids. Read-only."""
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

eng = create_engine("sqlite:///.data/examdata.db")
s = Session(eng)


def lab(qid):
    r = s.execute(text(
        "SELECT tn.code FROM question_taxonomy qt JOIN taxonomy_node tn ON tn.id=qt.node_id"
        " WHERE qt.question_id=:q"), {"q": qid}).fetchone()
    return r[0] if r else "-"


def dump(qid, depth=0, maxstem=1400):
    r = s.execute(text(
        "SELECT id, number_label, marks, parent_id,"
        " substr(replace(stem_text,char(10),' '),1,:m) FROM question WHERE id=:q"),
        {"q": qid, "m": maxstem}).fetchone()
    if not r:
        print("  " * depth + f"Q{qid} NOT FOUND")
        return
    print("  " * depth + f"Q{r[0]} #{r[1]} {r[2]}mk [{lab(qid)}] {r[4]}")
    for ms in s.execute(text(
        "SELECT number_path, substr(replace(answer_text,char(10),' | '),1,400)"
        " FROM mark_scheme_entry WHERE question_id=:q ORDER BY id"), {"q": qid}):
        print("  " * depth + f"  MS[{ms[0]}] {ms[1]}")
    for ch in s.execute(text("SELECT id FROM question WHERE parent_id=:q ORDER BY display_order"), {"q": qid}):
        dump(ch[0], depth + 1, maxstem)


for qid in [int(x) for x in sys.argv[1:]]:
    dump(qid)
    print("=" * 100)
