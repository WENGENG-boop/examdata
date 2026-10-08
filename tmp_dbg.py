import sqlite3
from pathlib import Path
ROOT = Path(__file__).resolve().parent
uri = f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro"
print('URI =', uri)
con = sqlite3.connect(uri, uri=True)
c = con.cursor()
print('ok:', c.execute("select count(*) from question").fetchone())
