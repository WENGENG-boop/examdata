"""探测D-6：按 Image ID 前缀扫描 Wayback 全部快照，按时点还原各年份 Zone 5 版本。

Image ID 复用是 CIE 的惯例（同一 URL 每季覆盖），因此必须靠快照时点区分考季。
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

def series_of(pdf_bytes):
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    txt = "".join(p.get_text() for p in doc[:3])
    txt1 = re.sub(r"\s+", " ", txt)
    m = re.search(r"(?:Final Exam Timetable|Exam Timetable)\s+((?:June|November|March|May|October)\s+20\d\d)", txt1)
    if not m:
        m = re.search(r"\b((?:June|November|March|May|October)\s+20\d\d)\b", txt1)
    return m.group(1) if m else None

def snapshots_for_id(id_prefix):
    seen = []
    for prefix in (f"cambridgeinternational.org/Images/{id_prefix}",
                   f"cambridgeinternational.org/images/{id_prefix}"):
        u = ("http://web.archive.org/cdx/search/cdx?url=" + quote(prefix, safe="")
             + "&matchType=prefix&output=json&fl=timestamp,original,statuscode&collapse=digest&limit=200")
        r = fetcher.get_text(u)
        if not r.text:
            continue
        try:
            rows = json.loads(r.text)[1:]
        except Exception:
            continue
        for ts, orig, code in rows:
            if code == "200" and orig not in [s[1] for s in seen]:
                seen.append((ts, orig, code))
    return seen

TARGET_IDS = ["469286", "513557", "638139"]
findings = {}
for idp in TARGET_IDS:
    snaps = snapshots_for_id(idp)
    print(f"== ID {idp}: {len(snaps)} 个 200 快照")
    entry = []
    for ts, orig, code in snaps:
        form = f"https://web.archive.org/web/{ts}id_/{orig}"
        r = fetcher.get(form, expect_binary=True, follow_redirects=True)
        ok = bool(r.content and r.content[:4] == b"%PDF")
        row = {"ts": ts, "url": orig, "ok": ok, "bytes": len(r.content or b"")}
        if ok:
            row["series"] = series_of(r.content)
            row["sha256"] = hashlib.sha256(r.content).hexdigest()[:16]
            fp = DL / f"archive_{idp}_{ts}.pdf"
            fp.write_bytes(r.content)
        print(f"   {ts} {orig.split('/')[-1][:46]:46s} pdf={ok} series={row.get('series')}")
        entry.append(row)
    findings[idp] = entry

EV.joinpath("zone5_id_scan.json").write_text(json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8")
print("saved zone5_id_scan.json")
