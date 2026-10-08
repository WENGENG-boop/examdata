"""全量 CDX 收获：四个文件夹的所有捕获 + 302 重定向追踪。

作为下载计划的权威数据源；每个文件夹查询完立即保存，避免超时丢结果。
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

EV = Path(r"C:/Users/weo/Desktop/api/tmp_edexcel_tt_probe/evidence")
fetcher = Fetcher(Settings())
CDX = "https://web.archive.org/cdx/search/cdx"

FOLDERS = {
    "root": "Examination-timetables",
    "intgcse": "Examination-timetables-for-Edexcel-International-GCSE",
    "ukgcse": "Examination-timetables-for-UK-Edexcel-GCSE",
    "ial": "Examination-timetables-for-International-Advanced-Levels",
}

for key, folder in FOLDERS.items():
    url = (f"{CDX}?url=qualifications.pearson.com/content/dam/pdf/Support/{folder}/*"
           f"&output=json&fl=original,timestamp,statuscode,length,digest&limit=20000")
    print(f"[{key}] querying...", flush=True)
    t0 = time.time()
    try:
        r = fetcher.get_text(url)
    except Exception as e:  # noqa: BLE001
        print(f"[{key}] EXC {type(e).__name__}: {e}", flush=True)
        continue
    dt = time.time() - t0
    if r.status != 200 or not r.text:
        print(f"[{key}] status={r.status} dt={dt:.1f}s", flush=True)
        continue
    try:
        rows = json.loads(r.text)
    except Exception as e:  # noqa: BLE001
        print(f"[{key}] parse err {e} head={r.text[:120]!r}", flush=True)
        continue
    out = EV / f"cdx_full_{key}.json"
    out.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    n = max(0, len(rows) - 1)
    print(f"[{key}] rows={n} dt={dt:.1f}s saved {out.name}", flush=True)

print("== redirect checks ==", flush=True)
REDIRECTS = [
    ("Nov2016 ukgcse 20210507", "20210507040042",
     "https://qualifications.pearson.com/content/dam/pdf/Support/Examination-timetables-for-UK-Edexcel-GCSE/GCSE_November_2016_final_timetable.pdf"),
    ("Nov2016 ukgcse 20250816", "20250816120605",
     "https://qualifications.pearson.com/content/dam/pdf/Support/Examination-timetables-for-UK-Edexcel-GCSE/GCSE_November_2016_final_timetable.pdf"),
    ("1906IntGCSE 20240623", "20240623143324",
     "https://qualifications.pearson.com/content/dam/pdf/Support/Examination-timetables-for-Edexcel-International-GCSE/1906IntGCSE.pdf"),
]
redir = []
for label, ts, orig in REDIRECTS:
    try:
        r = fetcher.get(f"https://web.archive.org/web/{ts}id_/{orig}",
                        expect_binary=True, follow_redirects=False)
        rec = {"label": label, "ts": ts, "status": r.status,
               "location": r.headers.get("location"), "bytes": len(r.content or b"")}
    except Exception as e:  # noqa: BLE001
        rec = {"label": label, "ts": ts, "error": f"{type(e).__name__}: {e}"}
    print(json.dumps(rec, ensure_ascii=False), flush=True)
    redir.append(rec)
(EV / "redirect_checks.json").write_text(
    json.dumps(redir, ensure_ascii=False, indent=1), encoding="utf-8")
print("done", flush=True)
