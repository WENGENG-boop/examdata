"""缺口4 复核：以单元格引用（cell ref）重解析 Nov 2026 早考卷/预发行清单 xlsx。

上一次解析（probe_gap_fixes1.py）按行内出现顺序取单元格，若存在空单元格会产生错位。
本脚本按 r="A2" 形式的引用还原真实列位，并换算日期序列值，输出：
  evidence/gap4_pre_release_xlsx_cells.json
不保存原件（仅内存解析）。
"""

import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings  # noqa: E402
from examdata.core.fetch import Fetcher  # noqa: E402

OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/evidence")
URL = "https://www.cambridgeinternational.org/Images/761208-early-question-papers-and-pre-release-material-november-2026.xlsx"

fetcher = Fetcher(Settings())
r = fetcher.get(URL, expect_binary=True)
rec = {"url": URL, "http": getattr(r, "status", None), "error": r.error}
if not (r.ok and r.content):
    (OUT / "gap4_pre_release_xlsx_cells.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print("fetch failed:", rec)
    raise SystemExit(1)

rec["bytes"] = len(r.content)
rec["sha256"] = hashlib.sha256(r.content).hexdigest()

zf = zipfile.ZipFile(BytesIO(r.content))
names = zf.namelist()

ss = zf.read("xl/sharedStrings.xml").decode("utf-8", "replace")
shared = []
for si in re.findall(r"<si>(.*?)</si>", ss, flags=re.S):
    texts = re.findall(r"<t[^>]*>(.*?)</t>", si, flags=re.S)
    shared.append(re.sub(r"<[^>]+>", "", "".join(texts)))

sx = zf.read(sorted(n for n in names if re.match(r"xl/worksheets/sheet\d+\.xml$", n))[0]).decode("utf-8", "replace")
cells = {}  # (row, col) -> raw cell dict
for rm in re.finditer(r"<row[^>]*r=\"(\d+)\"[^>]*>(.*?)</row>", sx, flags=re.S):
    row_no = int(rm.group(1))
    for cm in re.finditer(r"<c([^>]*)>(.*?)</c>|<c([^>]*)/>", rm.group(2), flags=re.S):
        attrs = cm.group(1) or cm.group(3) or ""
        inner = cm.group(2) or ""
        ref_m = re.search(r'r="([A-Z]+)(\d+)"', attrs)
        if not ref_m:
            continue
        col, rn = ref_m.group(1), int(ref_m.group(2))
        t_m = re.search(r't="(\w+)"', attrs)
        ctype = t_m.group(1) if t_m else None
        v_m = re.search(r"<v>(.*?)</v>", inner, flags=re.S)
        is_m = re.search(r"<is>.*?<t[^>]*>(.*?)</t>.*?</is>", inner, flags=re.S)
        if v_m is not None:
            raw = v_m.group(1)
            if ctype == "s" and raw.isdigit():
                val = shared[int(raw)]
            else:
                val = raw
        elif is_m is not None:
            val = re.sub(r"<[^>]+>", "", is_m.group(1))
        else:
            val = None
        if val is not None:
            cells[(rn, col)] = val

max_row = max(rn for rn, _ in cells) if cells else 0
max_col = max(col for _, col in cells) if cells else "A"


def col_idx(c):
    n = 0
    for ch in c:
        n = n * 26 + (ord(ch) - 64)
    return n


def col_name(i):
    s = ""
    while i:
        i, rem = divmod(i - 1, 26)
        s = chr(65 + rem) + s
    return s


ncols = col_idx(max_col)
headers = {col_name(i): cells.get((1, col_name(i))) for i in range(1, ncols + 1)}

EPOCH = datetime(1899, 12, 30)


def as_date(v):
    if v and re.fullmatch(r"\d{4,5}", v):
        return (EPOCH + timedelta(days=int(v))).strftime("%Y-%m-%d")
    return v


rows_out = []
for rn in range(2, max_row + 1):
    row = {}
    for i in range(1, ncols + 1):
        c = col_name(i)
        if (rn, c) in cells:
            v = cells[(rn, c)]
            hdr = headers.get(c) or ""
            if "Date" in hdr or "date" in hdr:
                v = as_date(v)
            row[c] = v
    if row:
        rows_out.append({"row": rn, **row})

rec["headers"] = headers
rec["rows"] = rows_out
rec["pre_release_components"] = sorted({
    rw["A"] for rw in rows_out if any(
        isinstance(v, str) and "Pre-release" in v for k, v in rw.items() if k != "row")
})
rec["source_file_rows"] = sorted({
    rw["A"] for rw in rows_out if any(
        isinstance(v, str) and "Source file" in v for k, v in rw.items() if k != "row")
})
(OUT / "gap4_pre_release_xlsx_cells.json").write_text(
    json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")

print("http", rec["http"], "bytes", rec["bytes"], "sha256", rec["sha256"])
print("headers:", json.dumps(headers, ensure_ascii=False, indent=1))
for rw in rows_out:
    print(json.dumps(rw, ensure_ascii=False))
print("pre_release_components:", rec["pre_release_components"])
print("source_file_rows:", rec["source_file_rows"])
