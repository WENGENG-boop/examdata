import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
eng = create_engine("sqlite:///.data/examdata.db")
s = Session(eng)
for qid in [int(x) for x in sys.argv[1:]]:
    print(f"########## {qid}")
    for ms in s.execute(text("""SELECT number_path, answer_text FROM mark_scheme_entry WHERE question_id=:q ORDER BY id"""), {'q':qid}):
        print(f"--- MS[{ms[0]}]\n{ms[1][:2500]}")
