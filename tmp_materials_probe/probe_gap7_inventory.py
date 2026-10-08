"""Gap-7 复核第二探：修正 CDX filter 锚定问题后，拉全量 timetable 清单，定位 2014-11 zone 5。

① 全量清单：/Images/ 前缀 + filter original:.*timetable.* （.* 前后缀，避免 re.match 锚定）
② 候选 URL 全快照：165821-november-2014-timetable-zone-4.pdf 等，列出全部 status
③ 2014-2015 时点 exam-timetables 目录页快照提取链接
输出：evidence/gap7_inventory_scan.json
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


def cdx(url, extra=""):
    u = ("http://web.archive.org/cdx/search/cdx?url=" + quote(url, safe="")
         + "&output=json&fl=timestamp,original,statuscode&" + extra)
    r = fetcher.get_text(u)
    rows = []
    if r.text:
        try:
            data = json.loads(r.text)
            rows = data[1:] if data else []
        except Exception:
            rows = []
    return rows, r.status, r.error


print("== ① 全量 timetable 清单（/Images/ 前缀） ==")
all_rows = []
for prefix in ["cambridgeinternational.org/Images/", "cambridgeinternational.org/images/"]:
    rows, st, err = cdx(prefix, "matchType=prefix&filter=" + quote("original:.*timetable.*", safe="")
                        + "&collapse=urlkey&limit=4000")
    print(f"  prefix {prefix}: rows={len(rows)} status={st} err={err}")
    all_rows += [(r[0], r[1], r[2], prefix) for r in rows]
    for r in rows:
        if re.search(r"2014", r[1], re.I) or re.search(r"zone[-_ ]?5", r[1], re.I) and re.search(r"201[3-5]", r[1]):
            pass
seen = set()
uniq = []
for ts, u, code, pf in all_rows:
    if u in seen:
        continue
    seen.add(u)
    uniq.append([ts, u, code])
out["scans"]["inventory"] = {"count": len(uniq), "rows": uniq}
print(f"  unique timetable URLs: {len(uniq)}")
nov2014 = [r for r in uniq if re.search(r"nov(ember)?[-_ ]?2014", r[1], re.I)]
print("  nov2014 candidates:")
for r in nov2014:
    print("    ", r)
z5 = [r for r in uniq if re.search(r"zone[-_ ]?5", r[1], re.I)]
print("  all zone-5 URLs:", len(z5))

print("== ② 候选 URL 全快照 ==")
cand = [
    "https://www.cambridgeinternational.org/Images/165821-november-2014-timetable-zone-4.pdf",
    "https://www.cambridgeinternational.org/images/165820-november-2013-timetable-zone-3.pdf",
]
# 从清单中补充 2014/2015 相关候选
for ts, u, code in uniq:
    if re.search(r"201[45]", u) and ("zone" in u.lower() or "timetable" in u.lower()):
        if u not in cand:
            cand.append(u)
snaps = {}
for c in cand:
    rows, st, err = cdx(c, "matchType=exact&limit=200")
    snaps[c] = {"status": st, "error": err, "snapshots": rows}
    print(f"  {c} -> {len(rows)} snapshots")
    for r in rows:
        print("      ", r)
out["scans"]["candidate_snapshots"] = snaps

print("== ③ 目录页快照 ==")
PAGE_URL = ("https://www.cambridgeinternational.org/exam-administration/cambridge-exams-officers-guide/"
            "phase-1-preparation/timetabling-exams/exam-timetables/")
rows, st, err = cdx(PAGE_URL, "matchType=exact&limit=500")
print(f"  dirpage all snapshots: {len(rows)} status={st} err={err}")
out["scans"]["dirpage_snapshots"] = {"status": st, "error": err, "rows": rows}
page_findings = []
for ts, u, code in rows:
    if not (ts.startswith("2014") or ts.startswith("2015")):
        continue
    for form in (f"https://web.archive.org/web/{ts}id_/{PAGE_URL}",
                 f"https://web.archive.org/web/{ts}/{PAGE_URL}"):
        rr = fetcher.get_text(form, follow_redirects=True)
        if not rr.text:
            continue
        links = set()
        for m in re.finditer(r"(?:https?://web\.archive\.org/web/\d+\w*/)?(?:https?://www\.cambridgeinternational\.org)?(/[Ii]mages/[^\"'\\\s>]*?\.pdf)", rr.text):
            link = m.group(1)
            if "timetable" in link.lower():
                links.add(link)
        page_findings.append({"ts": ts, "form": form, "status": rr.status,
                              "bytes": len(rr.text), "links": sorted(links)[:40]})
        print(f"    {ts} bytes={len(rr.text)} links={sorted(links)[:10]}")
        break
out["scans"]["dirpage_findings"] = page_findings

EV.joinpath("gap7_inventory_scan.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print("saved gap7_inventory_scan.json")
