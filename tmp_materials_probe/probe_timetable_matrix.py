"""探测D-4：Zone 5 时间表历年候选 —— 完整采集与内容核验。

1) CDX 补漏（2019-2022 November / 2013 June 等）
2) 官方在线测试 + 内容年份核验（防止 Images ID 复用导致张冠李戴）
3) 拿不到的走 Wayback replay，落 sha256 + 文本
输出：evidence/zone5_matrix.json + downloads/zone5_<season>.pdf + evidence/zone5_<season>.txt
"""

import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

import pymupdf

OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe")
EV = OUT / "evidence"
DL = OUT / "downloads"
fetcher = Fetcher(Settings())

# ---------- 1) CDX 补漏 ----------
extra_patterns = [
    r".*november-2019.*timetable.*",
    r".*november-2020.*timetable.*",
    r".*november-2021.*timetable.*",
    r".*november-2022.*timetable.*",
    r".*june-2013.*timetable.*",
    r".*zone-5.*",
]
cdx_extra = {}
for flt in extra_patterns:
    u = ("http://web.archive.org/cdx/search/cdx?url=" + quote("cambridgeinternational.org/Images/", safe="")
         + "&matchType=prefix&output=json&fl=timestamp,original&filter=original:" + flt + "&collapse=urlkey&limit=500")
    u2 = ("http://web.archive.org/cdx/search/cdx?url=" + quote("cambridgeinternational.org/images/", safe="")
          + "&matchType=prefix&output=json&fl=timestamp,original&filter=original:" + flt + "&collapse=urlkey&limit=500")
    for uu in (u, u2):
        r = fetcher.get_text(uu)
        rows = []
        if r.text:
            try:
                rows = json.loads(r.text)[1:]
            except Exception:
                rows = []
        for ts, orig in rows:
            if "timetable" in orig.lower() and re.search(r"zone[-_ ]?5", orig, re.I):
                cdx_extra.setdefault(orig, []).append(ts)
    print(f"CDX {flt}: 累计 zone5 候选 {len(cdx_extra)}")
for k, v in cdx_extra.items():
    print("   ", k, sorted(v)[:4])
EV.joinpath("cdx_extra_zone5.json").write_text(json.dumps(cdx_extra, indent=2, ensure_ascii=False), encoding="utf-8")

# ---------- 2) 候选清单（人工整理，来源=上面 CDX 结果） ----------
# season -> (label, official_url, wayback_snapshot_ts or None)
CANDIDATES = [
    ("2013-11", "November 2013", "https://www.cambridgeinternational.org/images/85678-november-2013-timetable-zone-5.pdf", "20240713153957"),
    ("2014-06", "June 2014", "https://www.cambridgeinternational.org/Images/152491--june-2014-timetable-zone-5.pdf", "20240714001129"),
    ("2015-06", "June 2015", "https://www.cambridgeinternational.org/images/180301-june-2015-timetable-zone-5.pdf", "20240619231140"),
    ("2015-11", "November 2015", "https://www.cambridgeinternational.org/Images/207027-november-2015-timetable-zone-5.pdf", "20240620203607"),
    ("2016-06", "June 2016", "https://www.cambridgeinternational.org/Images/267322-june-2016-timetable-zone-5.pdf", "20240807102002"),
    ("2016-11", "November 2016", "https://www.cambridgeinternational.org/images/296275-november-2016-timetable-zone-5.pdf", "20171031145014"),
    ("2017-06", "June 2017", "https://www.cambridgeinternational.org/Images/340764-june-2017-timetable-zone-5.pdf", "20171013034848"),
    ("2017-11", "November 2017", "https://www.cambridgeinternational.org/Images/373326-november-2017-timetable-zone-5.pdf", "20171013021925"),
    ("2018-06", "June 2018", "https://www.cambridgeinternational.org/Images/422448-zone-5-june-2018-timetable.pdf", "20171117202233"),
    ("2018-11", "November 2018", "https://www.cambridgeinternational.org/Images/469286-zone-5-november-2018-timetable.pdf", "20180613164739"),
    ("2019-06", "June 2019", "https://www.cambridgeinternational.org/Images/513557-june-2019-timetable-zone-5.pdf", "20240616114744"),
    ("2019-11", "November 2019", "https://www.cambridgeinternational.org/Images/469286-zone-5-november-timetable.pdf", "20190825002103"),
    ("2020-06", "June 2020", "https://www.cambridgeinternational.org/Images/513557-june-2020-timetable-zone-5.pdf", "20201001225904"),
    ("2020-11", "November 2020", None, None),
    ("2021-06", "June 2021", "https://www.cambridgeinternational.org/Images/513557-june-2021-timetable-zone-5.pdf", "20210624151318"),
    ("2021-11", "November 2021", None, None),
    ("2022-06", "June 2022", "https://www.cambridgeinternational.org/Images/638139-june-2022-zone-5-time-table.pdf", "20220120031648"),
    ("2022-11", "November 2022", None, None),
    ("2023-06", "June 2023", "https://www.cambridgeinternational.org/Images/638139-june-2023-zone-5-time-table.pdf", "20230102142651"),
    ("2023-11", "November 2023", "https://www.cambridgeinternational.org/Images/373326-november-2023-timetable-zone-5.pdf", "20230331025446"),
    ("2024-06", "June 2024", "https://www.cambridgeinternational.org/Images/638139-june-2024-zone-5-time-table.pdf", "20240226202036"),
    ("2024-11", "November 2024", "https://www.cambridgeinternational.org/Images/710670-november-2024-zone-5-timetable.pdf", "20240812034438"),
    ("2025-06", "June 2025", "https://www.cambridgeinternational.org/Images/722879-june-2025-zone-5-timetable.pdf", "20241212061354"),
    ("2025-11", "November 2025", "https://www.cambridgeinternational.org/Images/732807-november-2025-zone-5-timetable.pdf", "20250401154935"),
    ("2026-06", "June 2026", "https://www.cambridgeinternational.org/Images/745760-june-2026-zone-5-timetable.pdf", "20251118112911"),
    ("2026-11", "November 2026", "https://www.cambridgeinternational.org/Images/757650-november-2026-zone-5-timetable.pdf", "20260509200959"),
]

def content_year(pdf_bytes):
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        txt = "".join(p.get_text() for p in doc[:3])
        return txt[:600], len(doc)
    except Exception as e:
        return f"<pymupdf error: {e}>", 0

matrix = {}
for season, label, url, ts in CANDIDATES:
    entry = {"season": season, "label": label, "official_url": url, "wayback_ts": ts}
    pdf = None
    if url:
        r = fetcher.get(url, expect_binary=True, follow_redirects=True)
        entry["live_status"] = r.status
        entry["live_bytes"] = len(r.content or b"")
        if r.content and r.content[:4] == b"%PDF":
            pdf = r.content
            entry["served_by"] = "official"
    if pdf is None and ts and url:
        wb = f"https://web.archive.org/web/{ts}id_/{url}"
        r2 = fetcher.get(wb, expect_binary=True, follow_redirects=True)
        entry["wayback_url"] = wb
        entry["wayback_status"] = r2.status
        entry["wayback_bytes"] = len(r2.content or b"")
        if r2.content and r2.content[:4] == b"%PDF":
            pdf = r2.content
            entry["served_by"] = "wayback"
    if pdf:
        entry["sha256"] = hashlib.sha256(pdf).hexdigest()
        head, npages = content_year(pdf)
        entry["pages"] = npages
        first = re.sub(r"\s+", " ", head)[:350]
        entry["head"] = first
        m = re.search(r"(June|November|March|May|October)\s+20\d\d", head)
        entry["detected_series"] = m.group(0) if m else None
        entry["year_match"] = bool(m and (("June" in label and "June" in m.group(0)) or ("November" in label and "November" in m.group(0))))
        fp = DL / f"zone5_{season}.pdf"
        fp.write_bytes(pdf)
        try:
            doc = pymupdf.open(stream=pdf, filetype="pdf")
            EV.joinpath(f"zone5_{season}.txt").write_text("".join(p.get_text() for p in doc), encoding="utf-8")
        except Exception:
            pass
    else:
        entry["served_by"] = None
    matrix[season] = entry
    print(f"{season} {label:15s} live={entry.get('live_status')} served={entry.get('served_by')} "
          f"bytes={entry.get('live_bytes') or entry.get('wayback_bytes')} "
          f"series={entry.get('detected_series')} match={entry.get('year_match')}")

EV.joinpath("zone5_matrix.json").write_text(json.dumps(matrix, indent=2, ensure_ascii=False), encoding="utf-8")
print("saved zone5_matrix.json +", sum(1 for e in matrix.values() if e.get("served_by")), "pdfs downloadable")
