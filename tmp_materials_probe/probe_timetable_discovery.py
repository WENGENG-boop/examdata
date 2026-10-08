"""探测D-3：Zone 5 时间表历年候选 URL 全量发现 + 在线可得性测试。

1) CDX 多模式查询收集候选（zone-5 / zone5 / zone 5，含大小写与 /images 前缀）
2) 每个候选先测官网在线（HEAD/GET status）
3) 输出 candidates json（live 状态 + 存档快照）
"""

import json
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

EV = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/evidence")
fetcher = Fetcher(Settings())


def cdx(query_url, fl="timestamp,original,statuscode", limit=500):
    url = ("http://web.archive.org/cdx/search/cdx?url=" + quote(query_url, safe="")
           + f"&matchType=prefix&output=json&fl={fl}&collapse=urlkey&limit={limit}")
    r = fetcher.get_text(url)
    if not r.text:
        print("CDX fail", query_url, r.status, r.error)
        return []
    try:
        rows = json.loads(r.text)
    except Exception as e:
        print("CDX parse fail", e, r.text[:200])
        return []
    return rows[1:] if rows else []


candidates = {}  # url -> {snapshots: [...], sources: set()}


def add(url, ts, src):
    key = url.lower()
    if key not in candidates:
        candidates[key] = {"url": url, "snapshots": [], "sources": []}
    if ts:
        candidates[key]["snapshots"].append(ts)
    if src not in candidates[key]["sources"]:
        candidates[key]["sources"].append(src)


# 模式1：/Images/ 下 zone-5 命名

# 简化：分别用带 filter 的 CDX 端点（filter 作为独立参数）
def cdx_filtered(prefix, flt):
    url = ("http://web.archive.org/cdx/search/cdx?url=" + quote(prefix, safe="")
           + f"&matchType=prefix&output=json&fl=timestamp,original,statuscode&collapse=urlkey&limit=1000"
           + "&filter=" + quote("original:" + flt, safe=""))
    r = fetcher.get_text(url)
    if not r.text:
        print("CDX fail", prefix, flt, r.status, r.error)
        return []
    try:
        rows = json.loads(r.text)
    except Exception as e:
        print("CDX parse fail", e, r.text[:200])
        return []
    return rows[1:] if rows else []


for prefix in ["cambridgeinternational.org/Images/", "cambridgeinternational.org/images/"]:
    for flt in [r"(?i)zone-?5", r"(?i)zone%205", r"(?i)zone\+5"]:
        rows = cdx_filtered(prefix, flt)
        print(f"CDX {prefix} filter={flt} -> {len(rows)} rows")
        for ts, orig, status in rows:
            add(orig, ts, "cdx")

# 模式2：用更宽的 timetable 过滤，人工筛查 zone 5
for prefix in ["cambridgeinternational.org/Images/", "cambridgeinternational.org/images/"]:
    rows = cdx_filtered(prefix, r"(?i)timetable")
    print(f"CDX {prefix} filter=timetable -> {len(rows)} rows（筛查 zone）")
    for ts, orig, status in rows:
        if "zone" in orig.lower():
            add(orig, ts, "cdx-wide")

print("\n== 候选总数:", len(candidates))
for key, info in sorted(candidates.items()):
    print(" ", info["url"], "| snapshots:", sorted(info["snapshots"])[:3], "...")

# 在线可得性
print("\n== 在线状态 ==")
for key, info in sorted(candidates.items()):
    url = info["url"]
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    url = url.replace(":80/", "/")
    r = fetcher.get(url, expect_binary=True, follow_redirects=True)
    info["live_url"] = url
    info["live_status"] = r.status
    info["live_bytes"] = len(r.content or b"")
    info["live_is_pdf"] = bool(r.content and r.content[:4] == b"%PDF")
    info["live_err"] = r.error
    print(f"  HTTP {r.status} {len(r.content or b''):>9}B pdf={info['live_is_pdf']} {url}")

EV.joinpath("zone5_candidates.json").write_text(
    json.dumps(list(candidates.values()), indent=2, ensure_ascii=False), encoding="utf-8")
print("\nsaved zone5_candidates.json")
