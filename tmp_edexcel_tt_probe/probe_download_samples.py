"""下载样例：live CDN 时间表 + Wayback 历史时间表，检查可解析性。"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

OUT = Path(r"C:/Users/weo/Desktop/api/tmp_edexcel_tt_probe")
EV = OUT / "evidence"
DL = OUT / "downloads"
fetcher = Fetcher(Settings())

ORIGIN = "https://qualifications.pearson.com"

live = [
    "/content/dam/pdf/Support/Examination-timetables-for-International-Advanced-Levels/ial-summer-2027-final.pdf",
    "/content/dam/pdf/Support/Examination-timetables-for-International-Advanced-Levels/ial-january-2027-final.pdf",
    "/content/dam/pdf/Support/Examination-timetables-for-Edexcel-International-GCSE/int-gcse-summer-2027-final.pdf",
    "/content/dam/pdf/Support/Examination-timetables-for-Edexcel-International-GCSE/int-gcse-r-paper-summer-2027-final.pdf",
]

wayback = [
    ("ial-summer-2026-final.pdf", "20250815143926",
     "/content/dam/pdf/Support/Examination-timetables-for-International-Advanced-Levels/ial-summer-2026-final.pdf"),
    ("int-gcse-summer-2026-final.pdf", "20250706222814",
     "/content/dam/pdf/Support/Examination-timetables-for-Edexcel-International-GCSE/int-gcse-summer-2026-final.pdf"),
    ("ial-summer-2025-final.pdf", "20241217105606",
     "/content/dam/pdf/Support/Examination-timetables-for-International-Advanced-Levels/ial-summer-2025-final.pdf"),
    ("int-gcse-summer-2025-final.pdf", "20250117054604",
     "/content/dam/pdf/Support/Examination-timetables-for-Edexcel-International-GCSE/int-gcse-summer-2025-final.pdf"),
]

import pymupdf

report = []


def handle(name, url, tag):
    r = fetcher.get(url, expect_binary=True, follow_redirects=True)
    body = r.content or b""
    rec = {"tag": tag, "file": name, "status": r.status, "ctype": getattr(r, "content_type", None),
           "bytes": len(body), "magic": body[:4].decode("latin1"), "error": r.error}
    if body[:4] == b"%PDF":
        dest = DL / name
        dest.write_bytes(body)
        rec["sha256"] = hashlib.sha256(body).hexdigest()
        try:
            doc = pymupdf.open(str(dest))
            rec["pages"] = doc.page_count
            head = ""
            for p in range(min(2, doc.page_count)):
                head += doc[p].get_text()
            rec["head"] = " ".join(head.split())[:600]
            doc.close()
        except Exception as e:
            rec["pdf_error"] = repr(e)
    else:
        rec["note"] = "not a PDF"
    print(json.dumps(rec, ensure_ascii=False)[:900])
    print("-" * 50)
    report.append(rec)


print("== LIVE ==")
for p in live:
    handle(p.split("/")[-1], ORIGIN + p, "live")

print("== WAYBACK ==")
for name, ts, path in wayback:
    wb = f"https://web.archive.org/web/{ts}id_/{ORIGIN}{path}"
    handle(name, wb, f"wayback:{ts}")

(EV / "sample_downloads.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
print("saved")
