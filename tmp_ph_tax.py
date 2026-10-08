import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)
for unit in ['WPH11','WPH12','WPH13','WPH14','WPH15','WPH16']:
    rows = s.execute(text("""
      SELECT code, substr(replace(label,char(10),' '),1,110), id
      FROM taxonomy_node WHERE code LIKE :u ORDER BY code
    """), {'u': unit+'%'}).fetchall()
    print(f'=== {unit}: {len(rows)} nodes')
    for c,l,i in rows:
        print(f'  {c} | {l}')
