"""只读诊断：复现 'unable to open database file' 的 temp 文件机制。

用法: python temp_exp.py <case>
  case: no-pragma | memory   （连接后设置 PRAGMA temp_store）
环境: 由调用方设置 TMP/TEMP 控制 temp 目录有效性。
对 examdata/.data/examdata.db 以 mode=ro 打开，运行与服务日志中完全相同的 count SQL。
"""
import os
import re
import sqlite3
import sys

LOG = r"C:\Users\weo\Desktop\api\cie-location-batch\work\serve-8000.err.log"
DB = r"C:\Users\weo\Desktop\api\examdata\.data\examdata.db"

case = sys.argv[1] if len(sys.argv) > 1 else "no-pragma"

text = open(LOG, encoding="utf-8", errors="replace").read()
m = re.search(r"\[SQL: (SELECT count\(\*\).*?)\]\n\[parameters: \('edexcel',\)\]", text, re.S)
if not m:
    raise SystemExit("could not extract SQL from log")
sql = m.group(1).strip()

print("sqlite_version =", sqlite3.sqlite_version)
print("TMP =", os.environ.get("TMP"), "| TEMP =", os.environ.get("TEMP"), "| TMPDIR =", os.environ.get("TMPDIR"))
print("DB =", DB, "| case =", case)

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
try:
    if case == "memory":
        con.execute("PRAGMA temp_store=MEMORY")
    for board in ("edexcel", "cie"):
        try:
            row = con.execute(sql, (board,)).fetchone()
            print(f"[OK]   board={board} count={row[0] if row else None}")
        except Exception as e:
            print(f"[FAIL] board={board} {type(e).__name__}: {e}")
finally:
    con.close()
