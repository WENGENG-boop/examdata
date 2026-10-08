"""临时诊断：打印某卷某页的 content 框、事件首行，以及索引里该题的 qp 区域。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

import batchlib as B
import ocr_index as O
import paperlib as P


def main() -> int:
    key = sys.argv[1]
    role = sys.argv[2]
    page_no = int(sys.argv[3])
    want = sys.argv[4:] or []

    tmp = P.paper_tmp(key)
    pdf = sorted(tmp.glob(f"*_{role}_*.pdf"))[0]
    pages_dir = tmp / "pages"
    pages_dir.mkdir(exist_ok=True)

    import pymupdf

    with pymupdf.open(pdf) as doc:
        total = doc.page_count
    images = []
    for pno in range(1, total + 1):
        out = pages_dir / f"{role}-p{pno:03d}-z{O.DEFAULT_ZOOM:g}.png"
        if not out.exists():
            P.render_page(pdf, pno, out, zoom=O.DEFAULT_ZOOM)
        images.append(out)
    ocr = O.run_ocr(images, tmp)
    pages, events, errors = O.collect(role, pdf, tmp, pages_dir, O.DEFAULT_ZOOM, ocr, False)

    pg = pages[page_no]
    print(f"page {page_no}: content={pg['content']} disp={pg['disp']} ocr_errors={errors}")
    print("all OCR lines on page:")
    for line in pg["lines"][:14]:
        print(f"   y0={line['y0']:.1f} y1={line['y1']:.1f} x0={line['x0']:.1f} "
              f"x1={line['x1']:.1f}  {line['text'][:70]!r}")
    evs = [e for e in events if e["page"] == page_no]
    print(f"events on page: {len(evs)}")
    for e in evs[:10]:
        print(f"   y0={e['y0']:.1f} y1={e['y1']:.1f} x0={e['x0']:.1f}  {e['text'][:70]!r}")

    idx = B.read_json(Path(B.INDEXES) / key.split("/")[0] / f"{'-'.join([key.split('/')[1], key.split('/')[2], key.split('/')[3]])}" / "cie-index.json")
    for q in idx["questions"]:
        if not want or q["question"] in want:
            print(f"  {q['question']} parent={q['parent']}")
            for r in q[role]:
                print(f"     p{r['page']} {r['bbox']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
