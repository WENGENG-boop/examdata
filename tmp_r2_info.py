"""Read-only r2 info dump: old label (from applied.jsonl) + current + conf + stem + MS.

usage: python tmp_r2_info.py qid1 qid2 ...
"""
import json
import re
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent
APPLIED = ROOT / 'tmp_jev_full_decisions' / 'ial18-physics' / 'applied.jsonl'

old_map = {}
for line in open(APPLIED, encoding='utf-8'):
    e = json.loads(line)
    if e.get('status') != 'applied':
        continue
    old = re.search(r'与原标签（(.+?)）不符', e.get('reason') or '')
    conf = re.search(r'置信度 ([\d.]+)', e.get('reason') or '')
    old_map[e['question_id']] = (old.group(1) if old else None,
                                 float(conf.group(1)) if conf else None,
                                 e.get('decision'), e.get('code'))

eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)

for arg in sys.argv[1:]:
    if not arg.isdigit():
        continue
    qid = int(arg)
    row = s.execute(text("""
      SELECT q.number_label, q.marks, q.parent_id,
             substr(replace(q.stem_text,char(10),' '),1,220)
      FROM question q WHERE q.id=:q"""), {'q': qid}).fetchone()
    o = old_map.get(qid, (None, None, None, None))
    print(f'== {qid} #{row[0]} {row[1]}mk parent={row[2]} | old={o[0]} conf={o[1]} dec={o[2]} new={o[3]}')
    print(f'   {row[3]}')
    for ms in s.execute(text("""
      SELECT number_path, marks, substr(replace(answer_text,char(10),' | '),1,300)
      FROM mark_scheme_entry WHERE question_id=:q ORDER BY id"""), {'q': qid}):
        print(f'   MS[{ms[0]}] {ms[1]}mk: {ms[2]}')
