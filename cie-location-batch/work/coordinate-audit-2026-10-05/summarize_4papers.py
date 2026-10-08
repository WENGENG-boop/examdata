# -*- coding: utf-8 -*-
"""Summarize the four papers with numbering anomalies: index questions, region pages, coverage gaps."""
import sys, json
from pathlib import Path

BATCH = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
sys.path.insert(0, str(BATCH / "tools"))
import batchlib as B  # noqa: E402

CASES = [
    ("8386", 2025, "Jun", "11"),
    ("8386", 2026, "Jun", "12"),
    ("8386", 2026, "Jun", "13"),
    ("0495", 2026, "Jun", "11"),
]

def page_count(pdf: Path):
    try:
        import fitz
        with fitz.open(str(pdf)) as doc:
            return doc.page_count
    except Exception as e:
        return f"ERR {e}"

for subj, year, season, paper in CASES:
    key = f"{subj}/{year}/{season}/{paper}"
    print("=" * 78)
    print(key)
    idx = B.index_dir(subj, year, season, paper) / "cie-index.json"
    print(f"index: {idx}  exists={idx.is_file()}")
    if not idx.is_file():
        continue
    data = json.loads(idx.read_text(encoding="utf-8"))
    print(f"top keys: {sorted(data.keys())}")
    qs = data.get("questions", [])
    print(f"questions: {len(qs)}")
    # page coverage
    qp_pages, ms_pages = set(), set()
    for q in qs:
        for r in q.get("regions", []):
            role = r.get("role")
            pg = r.get("page")
            if role == "qp":
                qp_pages.add(pg)
            elif role == "ms":
                ms_pages.add(pg)
    print(f"qp region pages: {sorted(p for p in qp_pages if isinstance(p,int))}")
    print(f"ms region pages: {sorted(p for p in ms_pages if isinstance(p,int))}  count_ms_regions={sum(1 for q in qs for r in q.get('regions',[]) if r.get('role')=='ms')}")
    for q in qs:
        num = q.get("question")
        par = q.get("parent")
        regs = q.get("regions", [])
        qpg = sorted({r.get("page") for r in regs if r.get("role") == "qp" and isinstance(r.get("page"), int)})
        mpg = sorted({r.get("page") for r in regs if r.get("role") == "ms" and isinstance(r.get("page"), int)})
        print(f"  q={num!r:14} parent={par!r:14} qp_pages={qpg} ms_pages={mpg}")
    # qp/ms pdfs
    pd = B.paper_dir(subj, year, season, paper)
    print(f"paper_dir: {pd}  exists={pd.is_dir()}")
    if pd.is_dir():
        for f in sorted(pd.iterdir()):
            if f.suffix.lower() == ".pdf":
                print(f"  pdf: {f.name}  pages={page_count(f)}")
