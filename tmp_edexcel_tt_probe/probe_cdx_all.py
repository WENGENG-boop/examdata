"""枚举 4 个 Edexcel 时间表文件夹的全部 Wayback 快照，输出覆盖矩阵原料。

对每个文件夹查询 CDX（不折叠），得到 (url, timestamp, status, length) 全量，
再按 URL 分组选最优快照。结果写入 evidence/cdx_all_captures.json。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

OUT = Path(r"C:/Users/weo/Desktop/api/tmp_edexcel_tt_probe")
EV = OUT / "evidence"
fetcher = Fetcher(Settings())

FOLDERS = [
    "Examination-timetables-for-International-Advanced-Levels",
    "Examination-timetables-for-Edexcel-International-GCSE",
    "Examination-timetables-for-UK-Edexcel-GCSE",
    "Examination-timetables",
]

all_rows = []
for folder in FOLDERS:
    url = (
        "https://web.archive.org/cdx/search/cdx"
        f"?url=qualifications.pearson.com/content/dam/pdf/Support/{folder}/*"
        "&output=json&fl=original,timestamp,statuscode,length,digest&limit=20000"
    )
    r = fetcher.get_text(url)
    print(folder, "->", r.status, len(r.text or ""))
    if not r.text:
        continue
    try:
        rows = json.loads(r.text)
    except Exception as e:
        print("  parse error", e)
        continue
    if not rows:
        continue
    header = rows[0]
    for row in rows[1:]:
        rec = dict(zip(header, row))
        rec["folder"] = folder
        all_rows.append(rec)

print("total capture rows:", len(all_rows))
(EV / "cdx_all_captures.json").write_text(json.dumps(all_rows, ensure_ascii=False, indent=1), encoding="utf-8")

# summarize per folder
from collections import Counter
c = Counter(r["folder"] for r in all_rows)
for k, v in c.items():
    print(" ", k, v)
