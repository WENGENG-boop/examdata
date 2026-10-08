"""Gap-7 复核第三探：旧域名 cie.org.uk + 别名模式扫描，确认 2014-11 zone 5 是否真的无档。

① cie.org.uk / www.cie.org.uk 前缀 + timetable 过滤（全量清单）
② cambridgeinternational.org/Images/ 前缀 + zone 过滤 + 2014 过滤（别名命名）
③ cie.org.uk 域内 exam-timetables 目录页快照（2014-2015 时点）
输出：evidence/gap7_cieorguk_scan.json
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


print("== ① 旧域名 cie.org.uk 全量 timetable 清单 ==")
seen = set()
for prefix in [
    "cie.org.uk/Images/", "cie.org.uk/images/",
    "www.cie.org.uk/Images/", "www.cie.org.uk/images/",
]:
    rows, st, err = cdx(prefix, "matchType=prefix&filter=" + quote("original:.*timetable.*", safe="")
                        + "&collapse=urlkey&limit=2000")
    print(f"  {prefix}: rows={len(rows)} status={st} err={err}")
    key = f"cieorguk::{prefix}"
    out["scans"][key] = {"status": st, "error": err, "count": len(rows), "rows": rows}
    for r in rows:
        seen.add((r[0], r[1], r[2]))
    for r in rows:
        if re.search(r"201[34]", r[1]):
            print("     2013/2014:", r)

print("== ② cambridgeinternational.org 别名命名扫描 ==")
for label, flt in [
    ("zone-any", ".*zone.*"),
    ("2014-any", ".*2014.*"),
    ("nov-timetable", ".*nov.*timetable.*"),
]:
    rows, st, err = cdx("cambridgeinternational.org/Images/",
                        "matchType=prefix&filter=" + quote("original:" + flt, safe="")
                        + "&collapse=urlkey&limit=3000")
    print(f"  {label}: rows={len(rows)} status={st} err={err}")
    out["scans"][f"alias::{label}"] = {"status": st, "error": err, "count": len(rows), "rows": rows}
    for r in rows:
        if re.search(r"2014", r[1]) and re.search(r"timetable|zone", r[1], re.I):
            print("     ", r)

print("== ③ 旧域名目录页快照 ==")
for page in [
    "http://www.cie.org.uk/programmes-and-qualifications/",
    "http://www.cie.org.uk/exam-administration/",
]:
    rows, st, err = cdx(page, "matchType=prefix&limit=100&collapse=urlkey")
    print(f"  {page}: rows={len(rows)} status={st} err={err}")
    out["scans"][f"dir::{page}"] = {"status": st, "error": err, "rows": rows[:100]}

EV.joinpath("gap7_cieorguk_scan.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print("saved gap7_cieorguk_scan.json")
