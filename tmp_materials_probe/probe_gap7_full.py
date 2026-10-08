"""Gap-7 复核第四探：165822 / 16995x 全快照追踪，确认 2014-11 zone 5 是否有 200 抓取。

① 候选 URL 全快照（全 host 变体、不 collapse）：165822 zone-5、165821 zone-4、16995x final
② 对每个含 200 的 URL 尝试 replay（id_ 原始内容），校验 PDF 头
③ 16995x 家族扫描：确定 zone-1..zone-6 的 final-timetable ID 映射
输出：evidence/gap7_nov2014_full.json
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


print("== ① 候选 URL 全快照 ==")
candidates = [
    "http://cie.org.uk/Images/165822-november-2014-timetable-zone-5.pdf",
    "http://www.cie.org.uk/Images/165822-november-2014-timetable-zone-5.pdf",
    "http://www.cie.org.uk/images/165822-november-2014-timetable-zone-5.pdf",
    "https://www.cie.org.uk/Images/165822-november-2014-timetable-zone-5.pdf",
    "https://www.cambridgeinternational.org/Images/165822-november-2014-timetable-zone-5.pdf",
    "https://www.cambridgeinternational.org/images/165822-november-2014-timetable-zone-5.pdf",
    "http://cie.org.uk/Images/165821-november-2014-timetable-zone-4.pdf",
    "http://www.cie.org.uk/Images/165821-november-2014-timetable-zone-4.pdf",
    "http://cie.org.uk/Images/169954-cambridge-zone-1-november-2014-final-timetable.pdf",
    "http://cie.org.uk/Images/169955-cambridge-zone-6-november-2014-final-timetable.pdf",
]
snaps = {}
for c in candidates:
    rows, st, err = cdx(c, "matchType=exact&limit=200")
    snaps[c] = {"status": st, "error": err, "count": len(rows), "snapshots": rows}
    print(f"  {c} -> {len(rows)}")
    for r in rows:
        print("      ", r)
out["scans"]["candidate_snapshots"] = snaps

print("== ② 16995x 家族扫描 ==")
for idp in ["16995", "169956", "169957", "169958", "169959", "169960"]:
    rows, st, err = cdx(f"cie.org.uk/Images/{idp}", "matchType=prefix&limit=200")
    print(f"  idscan {idp}: rows={len(rows)}")
    out["scans"][f"idscan::{idp}"] = {"status": st, "error": err, "rows": rows}
    for r in rows:
        print("      ", r)
for idp in ["16995", "169956", "169957", "169958", "169959", "169960"]:
    rows, st, err = cdx(f"www.cie.org.uk/Images/{idp}", "matchType=prefix&limit=200")
    print(f"  idscan www {idp}: rows={len(rows)}")
    out["scans"][f"idscan-www::{idp}"] = {"status": st, "error": err, "rows": rows}
    for r in rows:
        print("      ", r)

print("== ③ replay 测试（仅对含 200 的候选） ==")
replays = {}
for c, info in snaps.items():
    ok = [r for r in info["snapshots"] if r[2] == "200"]
    for r in ok[:2]:
        ts, orig, code = r[0], r[1], r[2]
        url = f"https://web.archive.org/web/{ts}id_/{orig}"
        rr = fetcher.get_bytes(url)
        head = rr.data[:8] if rr.data else b""
        replays[f"{c}|{ts}"] = {"status": rr.status, "bytes": len(rr.data or b""),
                                "head": head.decode("latin-1"), "error": rr.error}
        print(f"  {ts} {orig} -> {rr.status} {len(rr.data or b'')}B head={head!r}")
out["scans"]["replays"] = replays

EV.joinpath("gap7_nov2014_full.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print("saved gap7_nov2014_full.json")
