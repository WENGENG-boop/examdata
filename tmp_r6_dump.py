"""Dump r6 WMA13 batch rows (current labels) + raw MS text with newlines."""
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent
BATCH = ROOT / 'tmp_jev_full_batches_r6' / 'ial18-mathematics' / 'batches'

mode = sys.argv[1] if len(sys.argv) > 1 else 'batch'

if mode == 'batch':
    rows = []
    for f in sorted(BATCH.glob('batch-*.jsonl')):
        for line in open(f, encoding='utf-8'):
            rec = json.loads(line)
            if rec.get('unit_code') == 'WMA13':
                rows.append(rec)
    print('n_rows', len(rows))
    if rows:
        print('keys', sorted(rows[0].keys()))
        print('sample rec:')
        print(json.dumps({k: v for k, v in rows[0].items() if k != 'stem'}, ensure_ascii=False, indent=1)[:2000])
    for r in rows:
        cur = r.get('current')
        print(r['question_id'], 'cur=', cur, '| label=', r.get('label'), '| pack=', r.get('pack'))
else:
    eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
    s = Session(eng)
    for qid in [int(x) for x in sys.argv[2:]]:
        print(f'########## Q {qid}')
        for ms in s.execute(text(
                "SELECT number_path, marks, answer_text FROM mark_scheme_entry "
                "WHERE question_id=:q ORDER BY id"), {'q': qid}):
            print(f'--- MS [{ms[0]}] {ms[1]}mk')
            print(ms[2][:4000])
