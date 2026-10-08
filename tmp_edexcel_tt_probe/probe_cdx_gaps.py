"""补齐缺口考季的 CDX 查询。

缺口：IntGCSE 2019-06 / 2022-11 / 2021-01-R；IAL 2017-06 / 2018-06；
      UK GCSE 2016-11 等。
对相关文件夹做时间窗口查询，另对具体 URL 做 prefix 查询。
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

QUERIES = [
    # (label, url)
    ("intgcse 2019-2020 window",
     "https://web.archive.org/cdx/search/cdx"
     "?url=qualifications.pearson.com/content/dam/pdf/Support/Examination-timetables-for-Edexcel-International-GCSE/*"
     "&output=json&fl=original,timestamp,statuscode,length&from=20190101&to=20200601&limit=20000"),
    ("intgcse 2022-2023 window",
     "https://web.archive.org/cdx/search/cdx"
     "?url=qualifications.pearson.com/content/dam/pdf/Support/Examination-timetables-for-Edexcel-International-GCSE/*"
     "&output=json&fl=original,timestamp,statuscode,length&from=20220101&to=20230601&limit=20000"),
    ("root folder 2022 window (nov 2022 intgcse?)",
     "https://web.archive.org/cdx/search/cdx"
     "?url=qualifications.pearson.com/content/dam/pdf/Support/Examination-timetables/*"
     "&output=json&fl=original,timestamp,statuscode,length&from=20220101&to=20230601&limit=20000"),
    ("1906IntGCSE prefix",
     "https://web.archive.org/cdx/search/cdx"
     "?url=qualifications.pearson.com/content/dam/pdf/Support/Examination-timetables-for-Edexcel-International-GCSE/1906IntGCSE.pdf"
     "&output=json&fl=original,timestamp,statuscode,length&limit=20000"),
    ("Jan-2021-R prefix",
     "https://web.archive.org/cdx/search/cdx"
     "?url=qualifications.pearson.com/content/dam/pdf/Support/Examination-timetables-for-Edexcel-International-GCSE/Jan-2021-Final-Int-GCSE-R*"
     "&output=json&fl=original,timestamp,statuscode,length&limit=20000"),
    ("IAL folder 2017-2018 window",
     "https://web.archive.org/cdx/search/cdx"
     "?url=qualifications.pearson.com/content/dam/pdf/Support/Examination-timetables-for-International-Advanced-Levels/*"
     "&output=json&fl=original,timestamp,statuscode,length&from=20170101&to=20190101&limit=20000"),
    ("root folder 2017 window (ial june 2017/2018?)",
     "https://web.archive.org/cdx/search/cdx"
     "?url=qualifications.pearson.com/content/dam/pdf/Support/Examination-timetables/*"
     "&output=json&fl=original,timestamp,statuscode,length&from=20170101&to=20180601&limit=20000"),
    ("UK GCSE folder 2016-2017 window",
     "https://web.archive.org/cdx/search/cdx"
     "?url=qualifications.pearson.com/content/dam/pdf/Support/Examination-timetables-for-UK-Edexcel-GCSE/*"
     "&output=json&fl=original,timestamp,statuscode,length&from=20160101&to=20180101&limit=20000"),
]

results = {}
for label, url in QUERIES:
    for attempt in range(3):
        try:
            r = fetcher.get_text(url)
            if r.status == 200 and r.text is not None:
                break
        except Exception as e:
            print(label, "attempt", attempt, "error:", e)
    else:
        print(label, "-> FAILED")
        continue
    try:
        rows = json.loads(r.text)
    except Exception as e:
        print(label, "-> parse error", e, (r.text or "")[:200])
        continue
    results[label] = rows
    n = max(len(rows) - 1, 0)
    print(f"{label} -> {n} rows")

(EV / "cdx_gaps.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
print("saved cdx_gaps.json")
