"""探查失败页 HTML：找 facet/标识替代形态。只抓 3 页，走仓库 Fetcher。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "src")

from examdata.core.fetch import Fetcher  # noqa: E402

EVID = Path("C:/Users/weo/Desktop/api/tmp_materials_probe/evidence")
OUT = EVID / "failed_pages"
OUT.mkdir(exist_ok=True)

prog = json.loads((EVID / "edexcel_sweep_progress.json").read_text(encoding="utf-8"))["subjects"]

SLUGS = ["international-gcse-physics-2017", "history-b-2009", "biology-2008"]

with Fetcher() as fetcher:
    for slug in SLUGS:
        entry = prog.get(slug) or {}
        url = entry.get("page_url")
        if not url:
            print(slug, "no page_url in progress; skip")
            continue
        try:
            res = fetcher.get_text(url)
        except Exception as exc:  # noqa: BLE001
            print(slug, "FETCH FAIL", exc)
            continue
        text = res.text or ""
        (OUT / f"{slug}.html").write_text(text, encoding="utf-8")
        print("=" * 70)
        print(slug, "| HTTP", res.status, "| bytes", len(text))
        print("  Pearson-UK count:", text.count("Pearson-UK"))
        print("  'facet' count:", len(re.findall(r"facet", text, re.I)))
        print("  'coursematerials' count:", text.count("coursematerials"))
        print("  'ng-init' count:", len(re.findall(r"ng-init", text, re.I)))
        print("  'specification' count:", len(re.findall(r"specification", text, re.I)))
        for pat in ["Pearson-UK:", "facetListCtrl", "coursematerials", "Specification-Code"]:
            m = re.search(pat, text, re.I)
            if m:
                snippet = text[max(0, m.start() - 100): m.start() + 160].replace("\n", " ")
                print(f"  first[{pat}]:", snippet[:260])
        # 头部框架线索
        head = text[:1500].replace("\n", " ")
        print("  head:", head[:300])
