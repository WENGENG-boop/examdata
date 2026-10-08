"""缺口 3 补证：Edexcel 记录级未实测项逐份 Fetcher 实测（5 个公开 URL）。

对 build_subjects_edexcel.py registry 中标 uncertain 的 5 项
（al15 化学数据手册、周期表 2008、物理清单、统计表格、心理统计表格）
各取 1 个 gated=false 记录行，经仓库 Fetcher 实测下载核验，
记录 HTTP / 字节 / sha256 / 页数 / 首页文本，PDF 验证后删除。

输出：evidence/edexcel_gap3_supplement.json
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
    ("al15_chemistry_data_booklet", "9CH0",
     "/content/dam/pdf/A Level/Chemistry/2015/teaching-and-learning-materials/a-level-chemistry-data-booklet-9ch0.pdf"),
    ("chemistry_periodic_table", "chemistry-2008",
     "/content/dam/pdf/A Level/Chemistry/2013/Teaching and learning materials/periodic_table_black.pdf"),
    ("physics_data_formulae_list", "physics-2015 A level",
     "/content/dam/pdf/A Level/Physics/2015/Specification and sample assessments/a-level-physics-data-formulae-relationships.pdf"),
    ("statistics_formulae_tables", "statistics-2017",
     "/content/dam/pdf/A Level/statistics/2017/Specification and Sample assessment material/Statistical-formulae-and-tables.pdf"),
    ("statistics_formulae_tables", "psychology-2015 amended",
     "/content/dam/pdf/A Level/Psychology/2015/specification-and-sample-assessments/amended-formulae-and-statistical-tables-for-summer-2026.pdf"),
]


def enc(path: str) -> str:
    return "/".join(quote(seg) for seg in path.split("/"))


fetcher = Fetcher(Settings())
result = []
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
        fname.unlink(missing_ok=True)  # 版权原件：验证后清理
    else:
        rec["note"] = "no content"
    result.append(rec)
    print(json.dumps(rec, ensure_ascii=False, indent=1)[:900])
    print("=" * 60)

(EV / "edexcel_gap3_supplement.json").write_text(
    json.dumps({"generated_at": "2026-10-05", "source": "gap3 record-level fetch via repo Fetcher", "items": result},
               ensure_ascii=False, indent=1),
    encoding="utf-8")
print("saved", EV / "edexcel_gap3_supplement.json")
