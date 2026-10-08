"""Gap-7 修复：从 Wayback 下载 7 个旧考季（2013-11 … 2016-11）zone-5 时间表 PDF。

背景：第 2 轮审计复核发现，旧域名 cie.org.uk / www.cie.org.uk 上有 2013-2016 各季
zone-5 时间表 PDF 的 200 抓取（新域名 cambridgeinternational.org 上为 0 条）。
证据：evidence/gap7_unobtainable_oldsite.json。

每季取最新 200 抓取（与既有 18 季「取最终可用版本」惯例一致），经
https://web.archive.org/web/{ts}id_/{orig} 取原始字节。2014-11 额外下载最早抓取
用于版本对比。输出：downloads/zone5_gap7/*.pdf + evidence/gap7_downloads.json
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

ROOT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe")
EV = ROOT / "evidence"
OUT = ROOT / "downloads" / "zone5_gap7"
OUT.mkdir(parents=True, exist_ok=True)

# key -> (ts, original_url)；主版本 = 最新 200 抓取
TARGETS = {
    "2013-11": ("20160705193821", "http://www.cie.org.uk:80/images/85678-november-2013-timetable-zone-5.pdf"),
    "2014-06": ("20150421091020", "http://www.cie.org.uk:80/images/152491--june-2014-timetable-zone-5.pdf"),
    "2014-11": ("20150501000531", "http://www.cie.org.uk:80/images/165822-november-2014-timetable-zone-5.pdf"),
    "2015-06": ("20150908205915", "http://www.cie.org.uk:80/images/180301-june-2015-timetable-zone-5.pdf"),
    "2015-11": ("20151227120507", "http://www.cie.org.uk:80/images/207027-november-2015-timetable-zone-5.pdf"),
    "2016-06": ("20161130182415", "http://www.cie.org.uk:80/images/267322-june-2016-timetable-zone-5.pdf"),
    "2016-11": ("20161213083253", "http://www.cie.org.uk:80/images/296275-november-2016-timetable-zone-5.pdf"),
}
ALT_2014_11 = ("20140707043945", "http://cie.org.uk/images/165822-november-2014-timetable-zone-5.pdf")

fetcher = Fetcher(Settings())
evidence = {"generated_at": datetime.now(timezone.utc).isoformat(), "downloads": {}, "alt_2014_11": {}}


def download(tag: str, ts: str, orig: str, dest_name: str) -> dict:
    replay = f"https://web.archive.org/web/{ts}id_/{orig}"
    rec = {"ts": ts, "original_url": orig, "replay_url": replay}
    r = fetcher.get(replay, expect_binary=True)
    rec.update(status=r.status, error=r.error, content_type=r.content_type, bytes=len(r.content or b""))
    if r.ok and (r.content or b"").startswith(b"%PDF"):
        (OUT / dest_name).write_bytes(r.content)
        rec["sha256"] = hashlib.sha256(r.content).hexdigest()
        rec["ok"] = True
    else:
        head = (r.content or b"")[:80]
        rec["ok"] = False
        rec["head"] = head.decode("latin-1", errors="replace")
    print(f"[{tag}] status={r.status} err={r.error} bytes={rec['bytes']} ok={rec['ok']}")
    return rec


for key, (ts, orig) in TARGETS.items():
    evidence["downloads"][key] = download(key, ts, orig, f"{key}.pdf")

ts, orig = ALT_2014_11
evidence["alt_2014_11"] = download("2014-11.alt", ts, orig, "2014-11.alt-20140707043945.pdf")

EV.joinpath("gap7_downloads.json").write_text(
    json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8"
)
print("saved evidence/gap7_downloads.json")
