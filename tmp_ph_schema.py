from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)
for t in ['taxonomy_node','question_taxonomy']:
    print(f'== {t}')
    for r in s.execute(text(f"PRAGMA table_info({t})")):
        print('  ', r[1], r[2])
print('== WPH11 nodes')
for r in s.execute(text("SELECT * FROM taxonomy_node WHERE code LIKE 'WPH11-%' ORDER BY code LIMIT 3")):
    print(r)
