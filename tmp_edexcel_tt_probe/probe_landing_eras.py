"""从 Wayback 抓取不同年代的 Pearson 考试时间表落地页快照，
提取当时页面列出的 PDF 链接（initDocList/hiddenAssetDetails），
用于发现「缺口考季」在当时使用的确切文件名。

输出：evidence/landing_era_<ts>.html 与 evidence/landing_era_links.json
"""

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

ERAS = [
    ("20160915", "uk-gcse-nov2016 / ial-oct2016"),
    ("20170201", "ial-june2017 / intgcse-june2017"),
    ("20180115", "ial-june2018 / intgcse-june2018"),
    ("20190201", "intgcse-june2019 / ial-june2019"),
    ("20200801", "intgcse-nov2020 / intgcse-jan2021"),
    ("20220801", "intgcse-nov2022 / uk-gcse-nov2022"),
]

results = {}
for ts, label in ERAS:
    url = f"https://web.archive.org/web/{ts}/{LANDING}"
    rec = {"ts": ts, "label": label, "url": url}
    try:
        r = fetcher.get_text(url)
        rec["status"] = r.status
        text = r.text or ""
        rec["len"] = len(text)
        (EV / f"landing_era_{ts}.html").write_text(text, encoding="utf-8")
        links = sorted(set(re.findall(r"[/\w%().,\-]*?/content/dam/pdf/Support/[\w%().,\-]+\.(?:pdf|xlsx)", text)))
        rec["n_links"] = len(links)
        rec["links"] = links
        print(f"{ts} {label}: status={r.status} len={len(text)} links={len(links)}")
    except Exception as e:
        rec["error"] = repr(e)
        print(f"{ts} {label}: ERROR {e!r}")
    results[ts] = rec

(EV / "landing_era_links.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
print("saved landing_era_links.json")
