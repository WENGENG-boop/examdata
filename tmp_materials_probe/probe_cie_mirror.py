"""探测 CIE 工坊镜像目录里除了 qp/ms 还有哪些文件类型。

对每个 (subject, year, season) 组合 POST renum，保存原始 JSON，并列出
所有文件名的角色/扩展名统计。
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")

from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

ORIGIN = "https://cie.fraft.cn"
OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe/evidence")
OUT.mkdir(parents=True, exist_ok=True)

COMBOS = [
    ("9709", "2024", "Jun"),
    ("9709", "2024", "Nov"),
    ("0620", "2024", "Jun"),
    ("9701", "2024", "Jun"),
    ("0500", "2024", "Jun"),
    ("9702", "2024", "Jun"),
]

settings = Settings()
fetcher = Fetcher(settings)

summary = {}
for subject, year, season in COMBOS:
    key = f"{subject}_{year}_{season}"
    resp = fetcher.post_form(
        f"{ORIGIN}/obj/Common/Fetch/renum",
        {"subject": subject, "year": year, "season": season},
        follow_redirects=False,
    )
    record = {"subject": subject, "year": year, "season": season,
              "http_status": resp.status, "error": resp.error}
    if resp.ok:
        raw_path = OUT / f"renum_{key}.json"
        raw_path.write_text(resp.text or "", encoding="utf-8")
        payload = json.loads(resp.text or "")
        rows = payload.get("rows", [])
        names = [r.get("file", "") for r in rows if isinstance(r, dict)]
        record["total"] = payload.get("total")
        record["rows_len"] = len(rows)
        record["sample_row"] = rows[0] if rows else None
        # 文件名形态统计：后缀 + 数字前缀
        suffix = Counter()
        for n in names:
            p = n.rsplit("_", 1)
            suffix[p[1].split(".")[0] if len(p) > 1 else n] += 1
        record["suffix_counts"] = dict(suffix.most_common())
        record["all_names"] = names
    summary[key] = record

(OUT / "cie_mirror_probe_summary.json").write_text(
    json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

for key, rec in summary.items():
    print(f"== {key}: HTTP {rec['http_status']} total={rec.get('total')} rows={rec.get('rows_len')} err={rec.get('error')}")
    print("   suffix:", rec.get("suffix_counts"))
    nonstandard = [n for n in rec.get("all_names", [])
                   if not (n.startswith(rec["subject"]) and ("_qp_" in n or "_ms_" in n))]
    print(f"   non qp/ms names ({len(nonstandard)}):", nonstandard[:30])
