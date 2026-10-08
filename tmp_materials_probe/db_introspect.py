import sqlite3

con = sqlite3.connect("file:examdata/.data/examdata.db?mode=ro", uri=True)
cur = con.cursor()
tabs = [r[0] for r in cur.execute("select name from sqlite_master where type='table' order by name").fetchall()]
print("tables:", tabs)
for t in tabs:
    try:
        n = cur.execute(f"select count(*) from {t}").fetchone()[0]
        print(f"count {t} = {n}")
    except Exception as e:
        print(f"count {t} ERR {e}")

for t in ("documents", "questions", "papers"):
    if t in tabs:
        cols = [r[1] for r in cur.execute(f"pragma table_info({t})").fetchall()]
        print(f"cols {t}: {cols}")

if "documents" in tabs:
    cols = [r[1] for r in cur.execute("pragma table_info(documents)").fetchall()]
    bcol = "board_id" if "board_id" in cols else ("board" if "board" in cols else None)
    if bcol:
        print("documents by board:")
        for r in cur.execute(f"select {bcol}, count(*) from documents group by {bcol}").fetchall():
            print("  ", r)
if "questions" in tabs:
    print("questions by board:")
    try:
        for r in cur.execute(
            "select d.board_id, count(*) from questions q join documents d on q.document_id=d.id group by d.board_id"
        ).fetchall():
            print("  ", r)
    except Exception as e:
        print("  join failed:", e)

if "boards" in tabs:
    print("boards:")
    for r in cur.execute("select * from boards").fetchall():
        print("  ", r)
