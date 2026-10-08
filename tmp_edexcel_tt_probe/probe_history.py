"""探测 Edexcel 历史时间表可得性：候选页面 + 可预测 PDF URL 模式。"""

import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

OUT = Path(r"C:/Users/weo/Desktop/api/tmp_edexcel_tt_probe")
EV = OUT / "evidence"
fetcher = Fetcher(Settings())

ORIGIN = "https://qualifications.pearson.com"

pages = [
    "/en/support/support-topics/exams/exam-timetables/past-timetables.html",
    "/en/support/support-topics/exams/exam-timetables/past-exam-timetables.html",
    "/en/support/support-topics/exams/exam-timetables/provisional-timetables.html",
    "/en/support/support-topics/exams/exam-timetables/useful-information.html",
    "/en/support/support-topics/exams/exam-timetables/international-start-times.html",
]

print("== candidate pages ==")
for p in pages:
    r = fetcher.get_text(ORIGIN + p)
    n = len(r.text or "")
    print(f"{r.status} len={n} {p}")
    if r.status == 200 and r.text:
        name = p.strip("/").split("/")[-1].replace(".html", "") + ".html"
        (EV / name).write_text(r.text, encoding="utf-8")

# predictable historical PDF patterns
cands = []
for y in (2024, 2025, 2026):
    for fam, folder, series in [
        ("ial", "Examination-timetables-for-International-Advanced-Levels", "summer"),
        ("ial", "Examination-timetables-for-International-Advanced-Levels", "january"),
        ("ial", "Examination-timetables-for-International-Advanced-Levels", "october"),
        ("intgcse", "Examination-timetables-for-Edexcel-International-GCSE", "summer"),
        ("intgcse", "Examination-timetables-for-Edexcel-International-GCSE", "november"),
        ("intgcse", "Examination-timetables-for-Edexcel-International-GCSE", "nov"),
        ("intgcse", "Examination-timetables-for-Edexcel-International-GCSE", "january"),
    ]:
        for suffix in ("-final.pdf", ".pdf"):
            if fam == "ial":
                fname = f"ial-{series}{y}{suffix}" if series in ("october",) else f"ial-{series}-{y}{suffix}"
            else:
                fname = f"int-gcse-{series}-{y}{suffix}" if series == "summer" else f"intgcse-{series}-{y}{suffix}"
            cands.append(f"/content/dam/pdf/Support/{folder}/{fname}")

print("\n== pdf pattern probe ==")
results = []
for path in dict.fromkeys(cands):
    url = ORIGIN + path
    r = fetcher.get(url, expect_binary=True, follow_redirects=True)
    rec = {"url": path, "status": r.status, "ctype": getattr(r, "content_type", None),
           "bytes": len(r.content) if r.content else 0, "error": r.error}
    results.append(rec)
    flag = "OK " if r.status == 200 else "   "
    print(f"{flag}{r.status} {len(r.content or b'')} {path}")

(EV / "historical_probe.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
print("saved")
