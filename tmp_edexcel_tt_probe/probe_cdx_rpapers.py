"""查询新发现的候选文件（R 卷、缺口考季）在 Wayback 的快照情况。

对每个具体 URL 做 prefix CDX 查询；对已知 302 的捕获读 Location 头。
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

CDX = "https://web.archive.org/cdx/search/cdx"

FOLDERS = {
    "intgcse": "Examination-timetables-for-Edexcel-International-GCSE",
    "ukgcse": "Examination-timetables-for-UK-Edexcel-GCSE",
    "ial": "Examination-timetables-for-International-Advanced-Levels",
    "root": "Examination-timetables",
}

# (label, folder, filename)
TARGETS = [
    ("7741 IGCSE R June 2016", "root", "7741_IGCSE_R_Paper_June_2016_Final_Timetable.pdf"),
    ("iGCSE-R Jan 2017", "root", "iGCSE-R-paper-Final-Timetable-January-2017.pdf"),
    ("IntGCSE June 2017 R", "intgcse", "International_GCSE_June_2017_final_timetable_R_code.pdf"),
    ("1901 IntGCSE R", "intgcse", "1901_intGCSER_final.pdf"),
    ("1906 IntGCSE R", "intgcse", "1906IntGCSER.pdf"),
    ("1906 IntGCSE", "intgcse", "1906IntGCSE.pdf"),
    ("Jan-2021 R pdf", "intgcse", "Jan-2021-Final-Int-GCSE-R.pdf"),
    ("GCSE june2018 intl", "root", "GCSE-timetable-June-2018-international.pdf"),
    ("IAL Oct18 prov", "ial", "IAL-October18-Provisional.pdf"),
    ("GCSE Jan2018 intgcse?", "intgcse", "GCSE-Timetable-January-2018.pdf"),
    ("GCSE Jan2018 root", "root", "GCSE-January-timetable2018.pdf"),
    ("GCSE Nov2018 prov", "ukgcse", "GCSE-November-2018-provisional-timetable.pdf"),
    ("Nov2016 ukgcse", "ukgcse", "GCSE_November_2016_final_timetable.pdf"),
    ("GCSE June2018 intl alt", "root", "GCSE-Timetable-June-2018.pdf"),
    ("IGCSE June2018 intl", "root", "IGCSE-Timetable-June-2018-international.pdf"),
]

report = {}
for label, folder, fname in TARGETS:
    url = (f"{CDX}?url=qualifications.pearson.com/content/dam/pdf/Support/"
           f"{FOLDERS[folder]}/{fname}&output=json&fl=original,timestamp,statuscode,length&limit=500")
    rows = None
    for attempt in range(3):
        r = fetcher.get_text(url)
        if r.status == 200 and r.text is not None:
            try:
                rows = json.loads(r.text)
                break
            except Exception as e:
                print(label, "parse err", e)
        print(label, "retry", attempt, "status", r.status)
    if rows is None:
        report[label] = {"error": "cdx failed"}
        print(f"== {label}: CDX FAILED")
        continue
    header = rows[0] if rows else []
    caps = [dict(zip(header, row)) for row in rows[1:]] if rows else []
    report[label] = {"folder": folder, "file": fname, "captures": caps}
    print(f"== {label}: {len(caps)} captures")
    for c in caps[:12]:
        print(f"   {c['statuscode']} {c['length']:>8} {c['timestamp']}")

# 302 Location 追踪
print("\n== redirect targets ==")
REDIRECTS = [
    ("Nov2016 ukgcse 20210507", "20210507040042",
     "https://qualifications.pearson.com/content/dam/pdf/Support/Examination-timetables-for-UK-Edexcel-GCSE/GCSE_November_2016_final_timetable.pdf"),
    ("Nov2016 ukgcse 20250816", "20250816120605",
     "https://qualifications.pearson.com/content/dam/pdf/Support/Examination-timetables-for-UK-Edexcel-GCSE/GCSE_November_2016_final_timetable.pdf"),
    ("1906IntGCSE 20240623", "20240623143324",
     "https://qualifications.pearson.com/content/dam/pdf/Support/Examination-timetables-for-Edexcel-International-GCSE/1906IntGCSE.pdf"),
]
redir_report = []
for label, ts, orig in REDIRECTS:
    url = f"https://web.archive.org/web/{ts}id_/{orig}"
    r = fetcher.get(url, expect_binary=True, follow_redirects=False)
    rec = {"label": label, "ts": ts, "status": r.status,
           "location": r.headers.get("location"), "bytes": len(r.content or b"")}
    print(json.dumps(rec, ensure_ascii=False))
    redir_report.append(rec)

report["_redirects"] = redir_report
(EV / "cdx_rpapers.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
print("saved cdx_rpapers.json")
