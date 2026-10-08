"""缺口 3 补证（第二批）：剩余 4 条 gated=false 公开记录行逐份实测。

补测：8CH0 化学数据手册、8PH0 物理数据手册、statistics-2017 A3/A4 大字版。
结果并入 evidence/edexcel_gap3_supplement.json（items 追加，去重按 url）。
PDF 验证后删除。
"""

import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

ORIGIN = "https://qualifications.pearson.com"
OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe")
EV, DL = OUT / "evidence", OUT / "downloads"
DL.mkdir(parents=True, exist_ok=True)

TARGETS = [
    ("al15_chemistry_data_booklet", "8CH0 AS",
     "/content/dam/pdf/A Level/Chemistry/2015/teaching-and-learning-materials/GCE_Chemistry_Data_Booklet_8CH0_Advanced_Subsidiary.pdf"),
    ("physics_data_formulae_list", "physics-2015 8PH0",
     "/content/dam/pdf/A Level/Physics/2015/Specification and sample assessments/P53451A_GCE_Physics_Data_Booklet_8PH0.pdf"),
    ("statistics_formulae_tables", "statistics-2017 A3 24pt",
     "/content/dam/pdf/A Level/statistics/2017/Specification and Sample assessment material/q-24pt-a3-mathematical-formulae-and-statistics-tables.pdf"),
    ("statistics_formulae_tables", "statistics-2017 A4 18pt",
     "/content/dam/pdf/A Level/statistics/2017/Specification and Sample assessment material/x-18pt-a4-mathematical-formulae-and-statistics-tables.pdf"),
]


def enc(path: str) -> str:
    return "/".join(quote(seg) for seg in path.split("/"))


fetcher = Fetcher(Settings())
new_items = []
for key, ref, path in TARGETS:
    url = ORIGIN + enc(path)
    r = fetcher.get(url, expect_binary=True, follow_redirects=False)
    rec = {"key": key, "ref": ref, "url": url, "status": r.status, "error": r.error}
    if r.status == 200 and r.content:
        rec["bytes"] = len(r.content)
        rec["sha256"] = hashlib.sha256(r.content).hexdigest()
        rec["content_type"] = getattr(r, "content_type", None)
        fname = DL / (hashlib.sha256(url.encode()).hexdigest()[:12] + ".pdf")
        fname.write_bytes(r.content)
        try:
            import pymupdf

            doc = pymupdf.open(str(fname))
            rec["pages"] = doc.page_count
            head = "".join(doc[p].get_text() for p in range(min(2, doc.page_count)))
            rec["head_snippet"] = " ".join(head.split())[:300]
            doc.close()
        except Exception as e:  # noqa: BLE001
            rec["pdf_error"] = repr(e)
        fname.unlink(missing_ok=True)
    else:
        rec["note"] = "no content"
    new_items.append(rec)
    print(json.dumps(rec, ensure_ascii=False, indent=1)[:900])
    print("=" * 60)

sup = EV / "edexcel_gap3_supplement.json"
d = json.loads(sup.read_text(encoding="utf-8"))
seen = {i.get("url") for i in d["items"]}
for rec in new_items:
    if rec["url"] not in seen:
        d["items"].append(rec)
d["source"] = "gap3 record-level fetch via repo Fetcher (two batches: 5+4 URLs)"
sup.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
print("saved", sup, "items:", len(d["items"]))
