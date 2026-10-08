"""Dump full stems, paper info, and WMA13 point list."""
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent))
from examdata.tagging.corpus import load_points

ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)

mode = sys.argv[1]
if mode == 'stems':
    for qid in [int(x) for x in sys.argv[2:]]:
        row = s.execute(text(
            "SELECT id, number_label, marks, stem_text FROM question WHERE id=:q"),
            {'q': qid}).fetchone()
        print('=' * 20, row[0], repr(row[1]), row[2], 'marks')
        print(row[3])
        print()
elif mode == 'points':
    points = load_points(s)
    for p in points:
        if (p.subject or '').strip().lower() == 'ial18-mathematics' and p.unit_code == 'WMA13':
            d = {k: v for k, v in vars(p).items() if not k.startswith('_')}
            print(d.get('code'), '|', d.get('name'), '|', str(d.get('description'))[:200])
elif mode == 'paper':
    for pid in [int(x) for x in sys.argv[2:]]:
        row = s.execute(text("SELECT * FROM paper WHERE id=:p"), {'p': pid}).fetchone()
        print(pid, row)
