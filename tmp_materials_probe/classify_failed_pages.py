"""对 page_failed 的 83 个页面分类：dead_404 / live_no_facet / fetch_error。

只读页面（每 slug 一次），走仓库 Fetcher；结果落
evidence/edexcel_failed_page_classes.json，活页 HTML 存 evidence/failed_pages/。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "src")

from examdata.core.fetch import Fetcher  # noqa: E402

EVID = Path("C:/Users/weo/Desktop/api/tmp_materials_probe/evidence")
OUT = EVID / "failed_pages"
OUT.mkdir(exist_ok=True)

# 已实测：biology-2008 / history-b-2009 均为 Pearson 站内 404 占位页，文本 SHA 相同
DEAD_SHA = "aff3fc8afbd9080cffab6d11eacfdf02c8b130fcfd18f6c5438389bd46bcb50a"

prog = json.loads((EVID / "edexcel_sweep_progress.json").read_text(encoding="utf-8"))["subjects"]
failed = {k: v for k, v in prog.items() if v.get("status") != "ok"}
print(f"classify {len(failed)} failed pages", flush=True)

report: dict[str, dict] = {}
counts: dict[str, int] = {}
with Fetcher() as fetcher:
    for i, (slug, entry) in enumerate(sorted(failed.items()), 1):
        url = entry.get("page_url", "")
        rec: dict = {"slug": slug, "family": entry.get("family"), "page_url": url}
        try:
            res = fetcher.get_text(url)
            text = res.text or ""
            rec["http"] = res.status
            rec["bytes"] = len(text)
            rec["sha256"] = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
            m = re.search(r"<title[^>]*>(.*?)</title>", text, re.S)
            rec["title"] = (m.group(1).strip()[:120] if m else None)
            if rec["sha256"] == DEAD_SHA or "Page not found" in (rec["title"] or ""):
                rec["kind"] = "dead_404"
                rec["note"] = "HTTP 200 但正文是站点 404 占位页（'Page not found | Pearson qualifications'）"
            else:
                rec["kind"] = "live_no_facet"
                (OUT / f"{slug}.html").write_text(text, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            rec["kind"] = "fetch_error"
            rec["error"] = f"{type(exc).__name__}: {exc}"
        report[slug] = rec
        counts[rec["kind"]] = counts.get(rec["kind"], 0) + 1
        print(f"[{i}/{len(failed)}] {slug}: {rec['kind']} HTTP {rec.get('http')}", flush=True)

payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "total": len(failed),
    "counts": counts,
    "pages": report,
}
(EVID / "edexcel_failed_page_classes.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
)
print("done", counts, flush=True)
