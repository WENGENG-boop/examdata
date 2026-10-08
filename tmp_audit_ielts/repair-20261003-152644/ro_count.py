import sqlite3
DB = r"C:\Users\weo\Desktop\api\examdata\.data\examdata.db"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
con.execute("PRAGMA temp_store=MEMORY")
SQL = """SELECT count(*) FROM question
JOIN paper ON question.paper_id = paper.id
JOIN document ON paper.document_id = document.id
JOIN board ON document.board_id = board.id
WHERE board.key = ?"""
for board in ("cambridge", "cie", "edexcel"):
    n = con.execute(SQL, (board,)).fetchone()[0]
    print(f"board.key={board} count={n}")
con.close()
