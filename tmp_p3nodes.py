import sqlite3, json

db = sqlite3.connect('.data/examdata.db')
cur = db.cursor()
cur.execute("SELECT code, attrs FROM taxonomy_node WHERE code LIKE 'WPH11-%' ORDER BY code")
for code, attrs in cur.fetchall():
    a = {}
    try:
        a = json.loads(attrs) if attrs else {}
    except Exception:
        pass
    best = ''
    if isinstance(a, dict):
        best = a.get('text') or ''
        if not best:
            for k, v in a.items():
                if isinstance(v, str) and len(v) > len(best):
                    best = v
    print('###', code)
    print((best or str(attrs))[:1200].replace('\n', ' '))
    print()
