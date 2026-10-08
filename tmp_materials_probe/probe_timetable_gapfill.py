"""探测D-5：Zone 5 时间表缺口补齐。

A) 对 wayback 失败/缺失的年份：按 URL 查全部快照，逐个尝试纯 replay 与 id_ replay
B) 从归档的 exam-timetables 页面 HTML 中提取 Nov2020/Nov2021/Nov2022 的 zone-5 链接
C) 重新核验已下载文件的实际考季（整卷前3页全文搜索）
"""

import hashlib
import json
import re
import sys
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

PAGE_URL = ("https://www.cambridgeinternational.org/exam-administration/cambridge-exams-officers-guide/"
            "phase-1-preparation/timetabling-exams/exam-timetables/")

# ---------- C) 先重扫已下载文件 ----------
def series_of(pdf_bytes):
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    txt = "".join(p.get_text() for p in doc[:3])
    txt1 = re.sub(r"\s+", " ", txt)
    m = re.search(r"(?:Final Exam Timetable|Exam Timetable)\s+((?:June|November|March|May|October)\s+20\d\d)", txt1)
    if not m:
        m = re.search(r"\b((?:June|November|March|May|October)\s+20\d\d)\b", txt1)
    return (m.group(1) if m else None), len(doc), txt1[:300]

print("== C) 已下载文件考季复核 ==")
rescan = {}
for fp in sorted(DL.glob("zone5_*.pdf")):
    season = fp.stem.replace("zone5_", "")
    b = fp.read_bytes()
    s, npages, head = series_of(b)
    rescan[season] = {"series": s, "pages": npages, "sha256": hashlib.sha256(b).hexdigest(), "head": head}
    print(f"  {season}: series={s} pages={npages} sha256={rescan[season]['sha256'][:16]}")

# ---------- A) wayback 逐个快照尝试 ----------
FALLBACK_URLS = {
    "2013-11": "https://www.cambridgeinternational.org/images/85678-november-2013-timetable-zone-5.pdf",
    "2014-06": "https://www.cambridgeinternational.org/Images/152491--june-2014-timetable-zone-5.pdf",
    "2015-06": "https://www.cambridgeinternational.org/images/180301-june-2015-timetable-zone-5.pdf",
    "2015-11": "https://www.cambridgeinternational.org/Images/207027-november-2015-timetable-zone-5.pdf",
    "2016-06": "https://www.cambridgeinternational.org/Images/267322-june-2016-timetable-zone-5.pdf",
    "2016-11": "https://www.cambridgeinternational.org/images/296275-november-2016-timetable-zone-5.pdf",
    "2019-06": "https://www.cambridgeinternational.org/Images/513557-june-2019-timetable-zone-5.pdf",
}

def cdx_snapshots(url):
    u = ("http://web.archive.org/cdx/search/cdx?url=" + quote(url, safe="")
         + "&output=json&fl=timestamp,statuscode&limit=50")
    r = fetcher.get_text(u)
    if not r.text:
        return []
    try:
        rows = json.loads(r.text)
    except Exception:
        return []
    return [(row[0], row[1]) for row in rows[1:]]

results = {}
print("\n== A) wayback 多快照尝试 ==")
for season, url in FALLBACK_URLS.items():
    snaps = cdx_snapshots(url)
    print(f"  {season}: snapshots={snaps}")
    got = None
    for ts, code in snaps:
        if code != "200":
            continue
        for form in (f"https://web.archive.org/web/{ts}id_/{url}", f"https://web.archive.org/web/{ts}/{url}"):
            r = fetcher.get(form, expect_binary=True, follow_redirects=True)
            ok = bool(r.content and r.content[:4] == b"%PDF")
            print(f"     try {form.split('/web/')[1][:40]} -> HTTP {r.status} pdf={ok} bytes={len(r.content or b'')}")
            if ok:
                got = (form, r.content)
                break
        if got:
            break
    if got:
        form, b = got
        sha = hashlib.sha256(b).hexdigest()
        s, npages, head = series_of(b)
        DL.joinpath(f"zone5_{season}.pdf").write_bytes(b)
        doc = pymupdf.open(stream=b, filetype="pdf")
        EV.joinpath(f"zone5_{season}.txt").write_text("".join(p.get_text() for p in doc), encoding="utf-8")
        results[season] = {"source": form, "sha256": sha, "series": s, "pages": npages}
        print(f"  ✔ {season} series={s} pages={npages} sha256={sha[:16]}")
    else:
        results[season] = {"source": None, "note": "all wayback replays failed"}
        print(f"  ✘ {season} 无可用快照")

# ---------- B) 归档页面链接提取（Nov2020/2021/2022 等） ----------
print("\n== B) 归档 exam-timetables 页面提取 zone-5 链接 ==")
PAGE_SNAPSHOTS = {
    "2020-11": ["20201104174752", "20201129075946", "20201202130901"],
    "2021-11": ["20211018012638", "20210920044628", "20210920044627"],
    "2022-11": ["20221022012120", "20220927204507", "20220813113426"],
    "2020-06": ["20200409232632", "20200815022504", "20200922130252"],
    "2019-06": ["20190922075537", "20191119182057", "20190716041309"],
    "2021-06": ["20210225165403", "20210507003453", "20210729214912"],
    "2022-06": ["20220120005135", "20220129210649", "20220313062257"],
}
page_findings = {}
for season, tss in PAGE_SNAPSHOTS.items():
    found = []
    for ts in tss:
        u = f"https://web.archive.org/web/{ts}/{PAGE_URL}"
        r = fetcher.get_text(u, follow_redirects=True)
        if not r.text:
            print(f"  {season} {ts}: HTTP {r.status} 无内容 err={r.error}")
            continue
        links = set()
        for m in re.finditer(r"(?:https?://web\.archive\.org/web/\d+\w*/)?(?:https?://www\.cambridgeinternational\.org)?(/[Ii]mages/[^\"'\\\s>]*?\.pdf)", r.text):
            link = m.group(1)
            if re.search(r"zone[-_ ]?5", link, re.I) or ("timetable" in link.lower() and "zone" in link.lower()):
                links.add(link)
        print(f"  {season} {ts}: HTTP {r.status} bytes={len(r.text)} zone5/timetable links={sorted(links)[:8]}")
        if links:
            found.append({"ts": ts, "links": sorted(links)})
    page_findings[season] = found

EV.joinpath("zone5_gapfill.json").write_text(json.dumps({
    "rescan": rescan, "wayback_retry": results, "page_findings": page_findings,
}, indent=2, ensure_ascii=False), encoding="utf-8")
print("\nsaved zone5_gapfill.json")
