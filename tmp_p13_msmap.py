import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
eng = create_engine("sqlite:///.data/examdata.db")
s = Session(eng)
pid = int(sys.argv[1])
print(f"===== paper {pid} questions =====")
qs = s.execute(text("SELECT id, parent_id, number_label, marks FROM question WHERE paper_id=:p ORDER BY display_order, id"), {'p': pid}).fetchall()
for q in qs:
    ms = s.execute(text("SELECT number_path, answer_text FROM mark_scheme_entry WHERE question_id=:q ORDER BY id"), {'q': q[0]}).fetchall()
    if not ms:
        continue
    print(f"\n### q{q[0]} par={q[1]} {q[2]!r} {q[3]}mk")
    for m in ms:
        txt = ' '.join((m[1] or '').split())
        print(f"   MS[{m[0]}] {txt[:180]}")
