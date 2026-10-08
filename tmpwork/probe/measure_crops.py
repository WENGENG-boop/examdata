"""量化裁剪框：对真实真题打印每题的页数与包围盒尺寸，并检查噪声。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pymupdf  # noqa: E402
from examdata.paperqa.locator import locate, crop_question  # noqa: E402

HERE = Path(__file__).resolve().parent
CASES = [("QP", "wec11.pdf", "qp", ["4", "7", "12(a)", "14", "1", "2"]),
         ("MS", "wec11_rms.pdf", "ms", ["12(a)", "4"])]

NOISE = ["DO NOT WRITE IN THIS AREA", "Turn over", "Pearson Education"]

for label, name, role, questions in CASES:
    data = (HERE / name).read_bytes()
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        print(f"== {label} {name}: {len(pdf)} pages, "
              f"{pdf[1].rect.width:.0f}x{pdf[1].rect.height:.0f}")
        for q in questions:
            try:
                clips = locate(pdf, q, role)
            except Exception as exc:
                print(f"  q{q}: {type(exc).__name__}: {exc}")
                continue
            pages = [p + 1 for p, _ in clips]
            print(f"  q{q}: {len(clips)} page(s) {pages}")
            for page, r in clips:
                # 噪声检查：裁剪区内的文本是否含页眉/页脚/水印串
                text = pdf[page].get_text(clip=r)
                hits = [n for n in NOISE if n.lower() in text.lower()]
                print(f"    p{page + 1} bbox=({r.x0:.0f},{r.y0:.0f},{r.x1:.0f},{r.y1:.0f}) "
                      f"w={r.width:.0f} h={r.height:.0f} noise={hits or 'none'}")

    # 逐题渲染，确认不抛错并统计总字节
    total = 0
    for q in questions:
        try:
            crops = crop_question(data, q, role)
            total += sum(len(c.png) for c in crops)
        except Exception as exc:
            print(f"  crop q{q}: {type(exc).__name__}: {exc}")
    print(f"  -> rendered PNG bytes for {len(questions)} questions: {total}")
