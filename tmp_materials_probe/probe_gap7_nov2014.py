"""Gap-7 复核：2014-11（及边界考季 2013-06 / 2012-11）Zone 5 时间表三类检索。

①CDX 多模式候选扫描（november-2014 / june-2013 / november-2012 / zone5×2014）
②按 Image ID 前缀扫描（165xxx 时代邻域 + 2013-11 的 85678 邻域）
③归档 exam-timetables 目录页提取（2014-06..2015-06 快照）
输出：evidence/gap7_nov2014_scan.json
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

EV = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/evidence")
fetcher = Fetcher(Settings())
out = {"generated_at": datetime.now(timezone.utc).isoformat(), "scans": {}}


def cdx_prefix(prefix, flt=None, limit=1000, collapse="urlkey", fl="timestamp,original,statuscode"):
    u = ("http://web.archive.org/cdx/search/cdx?url=" + quote(prefix, safe="")
         + f"&matchType=prefix&output=json&fl={fl}&limit={limit}&collapse={collapse}")
    if flt:
        u += "&filter=" + quote("original:" + flt, safe="")
    r = fetcher.get_text(u)
    rows = []
    if r.text:
        try:
            data = json.loads(r.text)
            rows = data[1:] if data else []
        except Exception:
            rows = []
    return rows, r.status, r.error


def looks_timetable(u):
    return "timetable" in u.lower() or re.search(r"zone[-_ ]?5", u, re.I) is not None


# ---------- ① CDX 多模式 ----------
print("== ① CDX 多模式扫描 ==")
for label, flt in [
    ("nov-2014-any", r"(?i)november-2014"),
    ("jun-2013-any", r"(?i)june-2013"),
    ("nov-2012-any", r"(?i)november-2012"),
    ("zone5-2014", r"(?i)2014.*zone[-_ ]?5"),
    ("zone5-2014b", r"(?i)zone[-_ ]?5.*2014"),
]:
    for prefix in ["cambridgeinternational.org/Images/", "cambridgeinternational.org/images/"]:
        rows, st, err = cdx_prefix(prefix, flt, limit=1000)
        key = f"{label}|{prefix}"
        hits = [r for r in rows if looks_timetable(r[1])]
        out["scans"][key] = {"status": st, "error": err, "rows": len(rows),
                             "timetable_hits": hits, "sample": [r[1] for r in rows[:60]]}
        print(f"  {key}: rows={len(rows)} tt_hits={len(hits)}")
        for h in hits[:10]:
            print("      HIT", h[1])

# ---------- ② Image ID 前缀扫描 ----------
print("== ② Image ID 前缀扫描 ==")
for idp in ["1658", "16582", "165821", "8567"]:
    rows, st, err = cdx_prefix(f"cambridgeinternational.org/Images/{idp}", None, limit=1000)
    hits = [r for r in rows if looks_timetable(r[1])]
    out["scans"][f"idscan-{idp}"] = {"status": st, "rows": len(rows),
                                     "timetable_hits": hits[:80], "sample": [r[1] for r in rows[:80]]}
    print(f"  idscan {idp}: rows={len(rows)} tt_hits={len(hits)}")
    for h in hits[:12]:
        print("      HIT", h[1])

# ---------- ③ 归档目录页提取 ----------
print("== ③ 归档 exam-timetables 目录页 ==")
PAGE_URL = ("https://www.cambridgeinternational.org/exam-administration/cambridge-exams-officers-guide/"
            "phase-1-preparation/timetabling-exams/exam-timetables/")
u = ("http://web.archive.org/cdx/search/cdx?url=" + quote(PAGE_URL, safe="")
     + "&output=json&fl=timestamp,statuscode&from=20140601&to=20150801&limit=200")
r = fetcher.get_text(u)
snaps = []
if r.text:
    try:
        snaps = json.loads(r.text)[1:]
    except Exception:
        snaps = []
out["scans"]["dirpage-snapshots"] = {"status": r.status, "snapshots": snaps}
print(f"  directory page snapshots 2014-06..2015-08: {len(snaps)}")
page_findings = []
for ts, code in snaps[:8]:
    if code != "200":
        continue
    for form in (f"https://web.archive.org/web/{ts}id_/{PAGE_URL}", f"https://web.archive.org/web/{ts}/{PAGE_URL}"):
        rr = fetcher.get_text(form, follow_redirects=True)
        if not rr.text:
            continue
        links = set()
        for m in re.finditer(r"(?:https?://web\.archive\.org/web/\d+\w*/)?(?:https?://www\.cambridgeinternational\.org)?(/[Ii]mages/[^\"'\\\s>]*?\.pdf)", rr.text):
            link = m.group(1)
            if looks_timetable(link):
                links.add(link)
        page_findings.append({"ts": ts, "form": form, "status": rr.status,
                              "bytes": len(rr.text), "zone5_links": sorted(links)[:20]})
        print(f"    {ts} bytes={len(rr.text)} zone5_links={sorted(links)[:8]}")
        break
out["scans"]["dirpage-findings"] = page_findings

# 域内 filter 兜底：2014-2015 时点的 exam-timetables 路径快照
u2 = ("http://web.archive.org/cdx/search/cdx?url=" + quote("cambridgeinternational.org/exam-administration/", safe="")
      + "&matchType=prefix&output=json&fl=timestamp,original&filter=" + quote("original:(?i)exam-timetables", safe="")
      + "&collapse=urlkey&limit=300")
r2 = fetcher.get_text(u2)
rows2 = []
if r2.text:
    try:
        rows2 = json.loads(r2.text)[1:]
    except Exception:
        rows2 = []
out["scans"]["dirpage-domain-scan"] = {"status": r2.status, "rows": rows2[:60]}
print(f"  domain scan exam-timetables rows: {len(rows2)}")

EV.joinpath("gap7_nov2014_scan.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print("saved gap7_nov2014_scan.json")
