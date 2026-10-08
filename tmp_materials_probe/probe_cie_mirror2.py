"""探测 CIE 工坊镜像：主页结构、全量角色词表、insert 原件下载验证。

1) GET 主页保存 HTML，提取所有链接/接口名
2) 对若干 (subject, year, season) 组合扫描所有非 qp/ms 文件名角色
3) 下载 0500 insert + 一份 gt/ci，验证可取回性与 SHA256
"""

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")

from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

ORIGIN = "https://cie.fraft.cn"
OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/evidence")
OUT.mkdir(parents=True, exist_ok=True)

fetcher = Fetcher(Settings())

# ---- 1) 主页 ----
home = fetcher.get_text(f"{ORIGIN}/")
(OUT / "mirror_home.html").write_text(home.text or "", encoding="utf-8")
links = re.findall(r'(?:href|src|action|url)\s*[=:]\s*["\']([^"\']+)["\']', home.text or "")
print("home status:", home.status, "len:", len(home.text or ""))
print("links sample:", sorted(set(links))[:40])

# ---- 2) 角色扫描 ----
COMBOS = [
    ("9709", "2017", "Jun"), ("9709", "2019", "Jun"), ("9709", "2021", "Jun"),
    ("9709", "2023", "Jun"), ("9709", "2025", "Jun"),
    ("0620", "2016", "Jun"), ("0620", "2019", "Jun"), ("0620", "2022", "Jun"),
    ("0500", "2016", "Jun"), ("0500", "2019", "Jun"), ("0500", "2022", "Jun"), ("0500", "2025", "Jun"),
    ("9702", "2019", "Jun"), ("9701", "2019", "Jun"), ("9701", "2022", "Jun"),
    ("5090", "2019", "Jun"), ("0610", "2019", "Jun"), ("4024", "2019", "Jun"),
    ("7707", "2019", "Jun"), ("9231", "2019", "Jun"),
]
role_re = re.compile(r"^(?P<subject>\d{4})_[msw](?P<year>\d{2})_(?P<role>[a-z]+)(?:_(?P<paper>\d+))?\.pdf$")
role_counts: Counter = Counter()
role_examples = {}
scanned = {}
for subject, year, season in COMBOS:
    key = f"{subject}_{year}_{season}"
    resp = fetcher.post_form(f"{ORIGIN}/obj/Common/Fetch/renum",
                             {"subject": subject, "year": year, "season": season},
                             follow_redirects=False)
    rec = {"http": resp.status}
    if resp.ok:
        payload = json.loads(resp.text or "")
        names = [r.get("file", "") for r in payload.get("rows", []) if isinstance(r, dict)]
        rec["total"] = payload.get("total")
        roles = Counter()
        for n in names:
            m = role_re.match(n)
            roles[m.group("role") if m else f"?unmatched:{n}"] += 1
            if m and m.group("role") not in ("qp", "ms"):
                role_examples.setdefault(m.group("role"), []).append(n)
            if not m:
                role_examples.setdefault("unmatched", []).append(n)
        rec["roles"] = dict(roles)
        role_counts.update(roles)
    scanned[key] = rec
    print(key, rec)

print("\nAll roles seen:", dict(role_counts))
print("Non qp/ms examples:", json.dumps(role_examples, indent=1)[:2000])
(OUT / "cie_mirror_roles_scan.json").write_text(json.dumps(scanned, indent=2, ensure_ascii=False), encoding="utf-8")

# ---- 3) 下载验证 ----
downloads = [
    "0500_s24_in_11.pdf",   # insert
    "9709_s24_gt.pdf",      # grade threshold
    "0620_s24_ci_51.pdf",   # confidential instructions
]
dl_report = {}
for name in downloads:
    url = f"{ORIGIN}/obj/Common/Fetch/redir/{name}"
    r = fetcher.get(url, expect_binary=True, follow_redirects=False)
    info = {"http": r.status, "error": r.error, "bytes": len(r.content or b"")}
    if r.content:
        info["sha256"] = hashlib.sha256(r.content).hexdigest()
        info["magic"] = r.content[:8].decode("latin-1")
        local = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/downloads") / name
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(r.content)
    dl_report[name] = info
    print(name, info)
(OUT / "cie_mirror_downloads.json").write_text(json.dumps(dl_report, indent=2), encoding="utf-8")
