"""只读诊断 v2：TMP 有效性与 temp_store 对 count SQL 的矩阵实验。

用法: python temp_exp2.py <tmp-value> <case>
  tmp-value: 传给 TMP/TEMP 的值（'none' 表示删除该变量）
  case: no-pragma | memory
脚本在进程内先设置 TMP/TEMP，再打开数据库并运行多个查询变体。
"""
import ctypes
import os
import re
import sqlite3
import sys

tmp_value = sys.argv[1] if len(sys.argv) > 1 else "none"
case = sys.argv[2] if len(sys.argv) > 2 else "no-pragma"

if tmp_value == "none":
    os.environ.pop("TMP", None)
    os.environ.pop("TEMP", None)
else:
    os.environ["TMP"] = tmp_value
    os.environ["TEMP"] = tmp_value
os.environ.pop("SQLITE_TMPDIR", None)

buf = ctypes.create_unicode_buffer(260)
n = ctypes.windll.kernel32.GetTempPathW(260, buf)
print(f"case={case} TMP={tmp_value!r} GetTempPathW={buf.value[:n]!r}")

LOG = r"C:\Users\weo\Desktop\api\cie-location-batch\work\serve-8000.err.log"
DB = r"C:\Users\weo\Desktop\api\examdata\.data\examdata.db"

text = open(LOG, encoding="utf-8", errors="replace").read()
m = re.search(r"\[SQL: (SELECT count\(\*\).*?)\]\n\[parameters: \('edexcel',\)\]", text, re.S)
full_sql = m.group(1).strip()

# 变体：完整 SQL / 去掉 ORDER BY 的同一子查询
no_order = re.sub(r" ORDER BY [^)]*\) AS anon_1", ") AS anon_1", full_sql)

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
try:
    if case == "memory":
        con.execute("PRAGMA temp_store=MEMORY")
    print("  PRAGMA temp_store =", con.execute("PRAGMA temp_store").fetchone()[0])

    def run(label, sql, params):
        try:
            row = con.execute(sql, params).fetchone()
            print(f"  [OK]   {label} -> {row[0] if row else None}")
        except Exception as e:
            print(f"  [FAIL] {label} -> {type(e).__name__}: {e}")

    run("Q1 full(ORDER BY) edexcel", full_sql, ("edexcel",))
    run("Q2 no-ORDER-BY  edexcel", no_order, ("edexcel",))
    run("Q3 simple count question", "SELECT count(*) FROM question", ())
    try:
        con.execute("CREATE TEMP TABLE _t(x)")
        con.execute("INSERT INTO _t VALUES(1)")
        print("  [OK]   Q4 create+insert temp table ->", con.execute("SELECT count(*) FROM _t").fetchone()[0])
    except Exception as e:
        print(f"  [FAIL] Q4 create temp table -> {type(e).__name__}: {e}")
    run("Q5 big sort of question ids", "SELECT count(*) FROM (SELECT id FROM question ORDER BY id DESC)", ())
    # 直接写文件探针：验证 TMP 目录可写性
    import tempfile
    try:
        fd, p = tempfile.mkstemp(prefix="probe_", dir=os.environ.get("TMP") or None)
        os.close(fd)
        os.unlink(p)
        print("  [OK]   write probe in TMP dir")
    except Exception as e:
        print(f"  [FAIL] write probe in TMP dir -> {type(e).__name__}: {e}")
finally:
    con.close()
