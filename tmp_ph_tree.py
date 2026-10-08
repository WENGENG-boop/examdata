import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)
unit = sys.argv[1]
rows = s.execute(text("""
  SELECT p.code, p.name, c.code, substr(c.name,1,70) FROM taxonomy_node c
  JOIN taxonomy_node p ON p.id=c.parent_id
  WHERE c.code LIKE :u ORDER BY p.code, c.code
"""), {'u': unit+'%'}).fetchall()
cur=None
for pc,pn,cc,cn in rows:
    if pc!=cur:
        cur=pc; print(f'\n[{pc}] {pn}')
    print(f'   {cc} | {cn}')
