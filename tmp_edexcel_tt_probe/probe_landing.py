"""探测 Edexcel（Pearson）考试时间表落地页：抓取 HTML 并提取 timetable 相关链接。"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

OUT = Path(r"C:/Users/weo/Desktop/api/tmp_edexcel_tt_probe")
EV = OUT / "evidence"
fetcher = Fetcher(Settings())

LANDING = "https://qualifications.pearson.com/en/support/support-topics/exams/exam-timetables.html"

r = fetcher.get_text(LANDING)
print("status:", r.status, "error:", r.error, "len:", len(r.text or ""))
if r.text:
    (EV / "landing.html").write_text(r.text, encoding="utf-8")

    html = r.text
    # all hrefs
    hrefs = re.findall(r'href="([^"]+)"', html)
    print("total hrefs:", len(hrefs))

    # filter timetable-ish
    hits = [h for h in hrefs if re.search(r"timetable|Timetable", h)]
    print("timetable hrefs:", len(hits))
    for h in dict.fromkeys(hits):
        print("  ", h)

    # pdf links
    pdfs = [h for h in hrefs if ".pdf" in h.lower()]
    print("pdf hrefs:", len(pdfs))
    for h in dict.fromkeys(pdfs)[:0]:
        pass

    # keywords context: find sections mentioning International
    for m in re.finditer(r"[^<>]{0,120}International[^<>]{0,160}", html):
        s = " ".join(m.group(0).split())
        if "timetable" in s.lower() or "pdf" in s.lower():
            print("CTX:", s[:280])
