"""对比旧/新 locator 在真实 Edexcel 试卷上的裁剪结果。仅临时验证用。"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tmpwork"))

import pymupdf

import examdata.paperqa.locator as new_loc
import old_locator_ref as old_loc

QP = ROOT / "tmpwork" / "probe" / "wec11.pdf"
MS = ROOT / "tmpwork" / "probe" / "wec11_rms.pdf"

NOISE = {
    "DO NOT WRITE": re.compile(r"DO NOT WRITE", re.I),
    "SECTION": re.compile(r"\bSECTION\b", re.I),
    "PAPER CODE": re.compile(r"\bP\d{5}[A-Z]\b"),
    "Turn over": re.compile(r"turn over", re.I),
    "BARCODE": re.compile(r"\*P[A-Z0-9]{4,}\*"),
    "COPYRIGHT": re.compile(r"©|Pearson Education", re.I),
}


def noise_in(text):
    return [name for name, rx in NOISE.items() if rx.search(text)]


def run(loc, pdf, question, role):
    try:
        return loc.locate(pdf, question, role), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def report(label, path, role, questions):
    print(f"\n{'='*100}\n{label}  ({path.name}, {role})\n{'='*100}")
    with pymupdf.open(path) as pdf:
        print(f"pages={len(pdf)}  page0={pdf[0].rect.width:.2f}x{pdf[0].rect.height:.2f}")
        for q in questions:
            old_clips, old_err = run(old_loc, pdf, q, role)
            new_clips, new_err = run(new_loc, pdf, q, role)
            print(f"\n--- Q {q} ---")
            for tag, clips, err in (("OLD", old_clips, old_err), ("NEW", new_clips, new_err)):
                if err:
                    print(f"  {tag}: {err}")
                    continue
                print(f"  {tag}: {len(clips)} clip(s)")
                for page, rect in clips:
                    text = pdf[page].get_text(clip=rect)
                    nz = noise_in(text)
                    first = " ".join(text.split())[:70]
                    print(f"    p{page+1} bbox=({rect.x0:.1f},{rect.y0:.1f},{rect.x1:.1f},{rect.y1:.1f})"
                          f" h={rect.height:.1f} w={rect.width:.1f}")
                    print(f"       text: {first!r}")
                    print(f"       noise: {nz if nz else 'clean'}")


if __name__ == "__main__":
    report("QP", QP, "qp", ["1", "2", "3", "4", "5", "7", "9", "11", "12", "12(a)", "12(b)", "12(c)",
                            "12(d)", "12(e)", "13", "14"])
    report("MS", MS, "ms", ["12(a)", "12(b)", "12(c)", "13"])
