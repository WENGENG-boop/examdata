from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import json
ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)
out=open('tmp_ph_points.txt','w',encoding='utf-8')
for unit in ['WPH11','WPH12','WPH13','WPH14','WPH15','WPH16']:
    rows = s.execute(text("""
      SELECT code, name, attrs FROM taxonomy_node
      WHERE code LIKE :u AND node_type='point' ORDER BY code
    """), {'u': unit+'%'}).fetchall()
    out.write(f'=== {unit} ({len(rows)} points)\n')
    for c,n,a in rows:
        try:
            at = json.loads(a) if isinstance(a,str) else (a or {})
        except Exception:
            at = {}
        txt = (at.get('text') or '').replace('\n',' ')
        out.write(f'{c} | {n} | {txt}\n')
    out.write('\n')
out.close()
print(open('tmp_ph_points.txt',encoding='utf-8').read()[:200])
