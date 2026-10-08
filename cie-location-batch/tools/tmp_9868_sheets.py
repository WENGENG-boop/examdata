"""临时脚本：为 9868/2026/Jun/12 生成高分辨率区域核验表。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stacksheet as S  # noqa: E402

KEY = "9868/2026/Jun/12"


def q(x0, y0, x1, y1, role="qp", page=1, label=""):
    return {"label": label, "role": role, "page": page, "bbox": [x0, y0, x1, y1]}


GROUPS = {
    "s1": [
        q(45, 128, 557, 448, page=2, label="Q1-Q4 p2"),
        q(45, 105, 557, 245, page=3, label="Q5 p3"),
    ],
    "s2": [
        q(45, 245, 557, 400, page=3, label="Q6 p3"),
        q(45, 30, 557, 262, page=4, label="Q7-Q12 p4"),
        q(45, 128, 557, 191, page=5, label="Q13 p5"),
        q(45, 191, 557, 253, page=5, label="Q14 p5"),
    ],
    "s3": [
        q(45, 253, 557, 315, page=5, label="Q15 p5"),
        q(45, 315, 557, 377, page=5, label="Q16 p5"),
        q(45, 377, 557, 439, page=5, label="Q17 p5"),
        q(45, 439, 557, 501, page=5, label="Q18 p5"),
        q(45, 501, 557, 563, page=5, label="Q19 p5"),
        q(45, 563, 557, 600, page=5, label="Q20 p5"),
    ],
    "s4": [
        q(45, 129, 557, 169, page=6, label="Q21 p6"),
        q(45, 169, 557, 209, page=6, label="Q22 p6"),
        q(45, 209, 557, 249, page=6, label="Q23 p6"),
        q(45, 249, 557, 289, page=6, label="Q24 p6"),
        q(45, 289, 557, 329, page=6, label="Q25 p6"),
        q(45, 329, 557, 369, page=6, label="Q26 p6"),
        q(45, 369, 557, 409, page=6, label="Q27 p6"),
        q(45, 409, 557, 449, page=6, label="Q28 p6"),
    ],
    "s5": [
        q(45, 449, 557, 489, page=6, label="Q29 p6"),
        q(45, 489, 557, 529, page=6, label="Q30 p6"),
        q(45, 529, 557, 569, page=6, label="Q31 p6"),
        q(45, 569, 557, 600, page=6, label="Q32 p6"),
        q(45, 129, 557, 283, page=7, label="Q33 p7"),
    ],
    "s6": [
        q(45, 283, 557, 438, page=7, label="Q34 p7"),
        q(45, 438, 557, 592, page=7, label="Q35 p7"),
        q(45, 592, 557, 730, page=7, label="Q36 p7"),
    ],
    "s7": [
        q(45, 61, 557, 214, page=8, label="Q37 p8"),
        q(45, 214, 557, 367, page=8, label="Q38 p8"),
        q(45, 367, 557, 520, page=8, label="Q39 p8"),
    ],
    "s8": [
        q(45, 520, 557, 668, page=8, label="Q40 p8"),
    ],
    "ms1": [
        q(65, 55, 550, 400, role="ms", page=2, label="MS p2 rows1-13"),
    ],
    "ms2": [
        q(65, 400, 550, 730, role="ms", page=2, label="MS p2 rows14-28"),
    ],
    "ms3": [
        q(65, 55, 550, 375, role="ms", page=3, label="MS p3 rows29-40"),
    ],
}


def main() -> int:
    only = sys.argv[1:]
    for name, spec in GROUPS.items():
        if only and name not in only:
            continue
        pages = S.build(KEY, spec, "9868v-" + name, None)
        print(f"== {name}: {len(pages)} 张")
        for p in pages:
            print(f"http://127.0.0.1:8792/work/sheets/{p.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
