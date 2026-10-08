"""内容核验：下载存疑候选文件，读取首页文本确认其考季与家族。

候选项：
- IAL_provisional_Examination_Dates.pdf（两个快照，疑似 IAL June 2017）
- IAL- timetable-2018-international.pdf（疑似 IAL June 2018）
- 57065-gcse-timetable-january-2018-final.pdf（UK GCSE 还是 Certificate？）
- Apr_May_2021_FINAL_IAL.pdf / Apr_May_2021_FINAL_Int_GCSE.pdf（考季归属）
- International_GCSE_Timetable.pdf（未知考季）
- 1906IntGCSE.pdf（302 捕获，尝试取得内容或跳转目标）
"""

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

import pymupdf

OUT = Path(r"C:/Users/weo/Desktop/api/tmp_edexcel_tt_probe")
EV = OUT / "evidence"
DL = OUT / "downloads" / "content_check"
DL.mkdir(parents=True, exist_ok=True)
fetcher = Fetcher(Settings())
ORIGIN = "https://qualifications.pearson.com"

ITEMS = [
    ("IAL_provisional_Examination_Dates_20170110.pdf", "20170110104749",
     "/content/dam/pdf/Support/Examination-timetables-for-International-Advanced-Levels/IAL_provisional_Examination_Dates.pdf"),
    ("IAL_provisional_Examination_Dates_20170622.pdf", "20170622194939",
     "/content/dam/pdf/Support/Examination-timetables-for-International-Advanced-Levels/IAL_provisional_Examination_Dates.pdf"),
    ("IAL_timetable_2018_international.pdf", "20171118014303",
     "/content/dam/pdf/Support/Examination-timetables/IAL-%20timetable-2018-international.pdf"),
    ("57065-gcse-timetable-january-2018-final.pdf", "20170712210929",
     "/content/dam/pdf/Support/Examination-timetables-for-UK-Edexcel-GCSE/57065-gcse-timetable-january-2018-final.pdf"),
    ("Apr_May_2021_FINAL_IAL.pdf", "20210801104722",
     "/content/dam/pdf/Support/Examination-timetables-for-International-Advanced-Levels/Apr_May_2021_FINAL_IAL.pdf"),
    ("Apr_May_2021_FINAL_Int_GCSE.pdf", "20210414115610",
     "/content/dam/pdf/Support/Examination-timetables-for-Edexcel-International-GCSE/Apr_May_2021_FINAL_Int_GCSE.pdf"),
    ("International_GCSE_Timetable.pdf", "20161213091756",
     "/content/dam/pdf/Support/Examination-timetables-for-Edexcel-International-GCSE/International_GCSE_Timetable.pdf"),
]

report = []


def inspect(name, body):
    rec = {"file": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()[:16]}
    dest = DL / name
    dest.write_bytes(body)
    doc = pymupdf.open(str(dest))
    rec["pages"] = doc.page_count
    text = ""
    for p in range(min(2, doc.page_count)):
        text += doc[p].get_text()
    doc.close()
    flat = " ".join(text.split())
    rec["head"] = flat[:700]
    seasons = set(re.findall(r"(January|June|October|November|Summer|Autumn)\s*(?:20\d\d)", flat, re.I))
    rec["season_words"] = sorted({" ".join(s).title() for s in seasons})
    years = sorted(set(re.findall(r"\b20[12]\d\b", flat)))
    rec["years"] = years
    codes = sorted(set(re.findall(r"\b[4WK][A-Z0-9]{3}\s?\d{2}[A-Z]?\b", flat)))[:12]
    rec["codes_sample"] = codes
    return rec


for name, ts, path in ITEMS:
    url = f"https://web.archive.org/web/{ts}id_/{ORIGIN}{path}"
    try:
        r = fetcher.get(url, expect_binary=True, follow_redirects=True)
        body = r.content or b""
        if body[:4] == b"%PDF":
            rec = inspect(name, body)
            rec.update({"ts": ts, "url": url})
            print(json.dumps({k: rec[k] for k in ("file", "bytes", "pages", "season_words", "years", "codes_sample")}, ensure_ascii=False))
        else:
            rec = {"file": name, "ts": ts, "status": r.status, "bytes": len(body),
                   "magic": body[:4].decode("latin1"), "note": "not a pdf"}
            print(json.dumps(rec, ensure_ascii=False))
    except Exception as e:
        rec = {"file": name, "ts": ts, "error": repr(e)}
        print(json.dumps(rec, ensure_ascii=False))
    print("-" * 40)
    report.append(rec)

# 1906IntGCSE 302 特殊处理
try:
    url = (f"https://web.archive.org/web/20240623143324id_/{ORIGIN}"
           "/content/dam/pdf/Support/Examination-timetables-for-Edexcel-International-GCSE/1906IntGCSE.pdf")
    r = fetcher.get(url, expect_binary=True, follow_redirects=False)
    rec = {"file": "1906IntGCSE.pdf", "ts": "20240623143324", "status": r.status,
           "bytes": len(r.content or b""), "magic": (r.content or b"")[:4].decode("latin1")}
    print(json.dumps(rec, ensure_ascii=False))
    report.append(rec)
except Exception as e:
    print("1906IntGCSE:", repr(e))

(EV / "content_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
print("saved content_check.json")
