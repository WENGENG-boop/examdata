import sqlite3

con = sqlite3.connect('.data/examdata.db')
cur = con.cursor()

print('=== schema question ===')
for r in cur.execute("select sql from sqlite_master where name in ('question','question_taxonomy')"):
    print(r[0])
print()

print('=== TOPIC AREA rows in German questions ===')
rows = cur.execute(
    "select id, substr(replace(stem_text, char(10), ' '),1,220) from question "
    "where stem_text like '%TOPIC AREA%' order by id").fetchall()
print('count:', len(rows))
for r in rows:
    print(r[0], '|', r[1][:200])
print()

print('=== specific stems ===')
for qid in (54841, 54564, 53693, 54295, 53964, 54233, 54639, 53701, 53215, 53191):
    row = cur.execute(
        "select substr(replace(replace(stem_text, char(10), ' '), char(9), ' '),1,500) "
        "from question where id=?", (qid,)).fetchone()
    print('###', qid, '::', row[0] if row else None)
    print()

con.close()
