from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)
print('-- node types --')
for r in s.execute(text("SELECT node_type, count(*) FROM taxonomy_node GROUP BY node_type")):
    print(r[0], r[1])
print('-- physics board nodes mentioning unit/prefix/SI --')
for r in s.execute(text("""SELECT code, node_type, substr(name,1,90) FROM taxonomy_node
    WHERE code LIKE 'WPH%' AND (name LIKE '%prefix%' OR name LIKE '%SI unit%' OR name LIKE '%unit%')
    LIMIT 25""")):
    print(r[0], r[1], '|', r[2])
