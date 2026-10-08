"""Gap-7 复核第五探：全部 8 个「不可得」考季在旧域名（cie.org.uk）的全快照扫描。

对每个考季的 zone-5 文件，在 4 个 host 前缀变体（cie.org.uk / www.cie.org.uk × Images/images）
下做 exact 匹配、不 collapse，列出全部抓取与状态；凡有 200 + application/pdf 的标记候选。
输出：evidence/gap7_unobtainable_oldsite.json
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

EV = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/evidence")
fetcher = Fetcher(Settings())
out = {"generated_at": datetime.now(timezone.utc).isoformat(), "seasons": {}}


def cdx(url, extra=""):
    u = ("http://web.archive.org/cdx/search/cdx?url=" + quote(url, safe="")
         + "&output=json&fl=timestamp,original,statuscode,mimetype,length&" + extra)
    r = fetcher.get_text(u)
    rows = []
    if r.text:
        try:
            data = json.loads(r.text)
            rows = data[1:] if data else []
        except Exception:
            rows = []
    return rows, r.status, r.error


SEASONS = {
    "2013-11": "85678-november-2013-timetable-zone-5.pdf",
    "2014-06": "152491--june-2014-timetable-zone-5.pdf",
    "2014-11": "165822-november-2014-timetable-zone-5.pdf",
    "2015-06": "180301-june-2015-timetable-zone-5.pdf",
    "2015-11": "207027-november-2015-timetable-zone-5.pdf",
    "2016-06": "267322-june-2016-timetable-zone-5.pdf",
    "2016-11": "296275-november-2016-timetable-zone-5.pdf",
    "2019-06": "513557-june-2019-timetable-zone-5.pdf",
    "2020-11": "469286-zone-5-november-timetable.pdf",
}

HOSTS = ["cie.org.uk", "www.cie.org.uk"]
PATHS = ["Images", "images"]

for key, fname in SEASONS.items():
    rec = {"file": fname, "hosts": {}}
    for host in HOSTS:
        for p in PATHS:
            url = f"http://{host}/{p}/{fname}"
            rows, st, err = cdx(url, "matchType=exact&limit=300")
            good = [r for r in rows if r[2] == "200" and "pdf" in (r[3] or "").lower()]
            rec["hosts"][f"{host}/{p}"] = {
                "status": st, "error": err, "count": len(rows),
                "pdf200": good, "rows": rows,
            }
            mark = " *** PDF200" if good else ""
            print(f"{key} {host}/{p}: {len(rows)} rows{mark}")
            for r in rows:
                print("     ", r)
    out["seasons"][key] = rec

EV.joinpath("gap7_unobtainable_oldsite.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print("saved gap7_unobtainable_oldsite.json")
