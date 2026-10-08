"""探测C-3：下载 Edexcel 两个代表性发放资料并核验（IAL Maths 公式表 / IAL Chem Data Booklet）。"""

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
fetcher = Fetcher(Settings())

TARGETS = [
    ("edexcel_ial_maths_formula_book.pdf",
     "/content/dam/pdf/International Advanced Level/Mathematics/2018/Specification-and-Sample-Assessment/IAL-Mathematics-Formula-Book.pdf",
     "IAL Mathematics/Further Mathematics and Pure Mathematics Mathematical Formulae and Statistical Tables (Issue 2)"),
    ("edexcel_ial_chem_data_booklet.pdf",
     "/content/dam/pdf/International Advanced Level/Chemistry/2018/Teaching-and-Learning-Materials/IAL_Chemistry 2018_Data_booklet_Issue_1_March 2019.pdf",
     "Data Booklet IAL Chemistry 2018 (Issue 1 March 2019)"),
]

# URL-encode each path segment but keep slashes
def enc(path):
    return "/".join(quote(seg) for seg in path.split("/"))

import pymupdf

result = []
for fname, path, label in TARGETS:
    url = ORIGIN + enc(path)
    r = fetcher.get(url, expect_binary=True, follow_redirects=False)
    rec = {"file": fname, "label": label, "url": url, "status": r.status, "error": r.error}
    if r.status == 200 and r.content:
        dest = DL / fname
        dest.write_bytes(r.content)
        rec["bytes"] = len(r.content)
        rec["sha256"] = hashlib.sha256(r.content).hexdigest()
        rec["content_type"] = getattr(r, "content_type", None)
        try:
            doc = pymupdf.open(str(dest))
            rec["pages"] = doc.page_count
            head = ""
            for p in range(min(3, doc.page_count)):
                head += doc[p].get_text()
            doc.close()
            rec["head_snippet"] = " ".join(head.split())[:400]
            # verification keywords
            low = head.lower()
            if "formula" in fname:
                rec["verify_formulae"] = ("formulae" in low)
                rec["verify_tables"] = ("statistical tables" in low or "statistical" in low)
            else:
                rec["verify_data_booklet"] = ("data booklet" in low)
        except Exception as e:
            rec["pdf_error"] = repr(e)
    else:
        rec["note"] = "no content"
    result.append(rec)
    print(json.dumps(rec, ensure_ascii=False, indent=1)[:1200])
    print("=" * 60)

(EV / "edexcel_downloads.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
print("saved", EV / "edexcel_downloads.json")
