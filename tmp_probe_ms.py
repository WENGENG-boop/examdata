"""逐文档版式探针：打印候选题号 token 的 x/y 与表格横线，用于人工判断列结构。

用法: python tmp_probe_ms.py <ms_doc> [pages]   # pages 形如 5-11 或 all
"""
import sqlite3
import sys

import pymupdf

sys.path.insert(0, "src")

from examdata.core.config import get_settings
from examdata.core.storage import ContentAddressedStore
import examdata.edexcel_papers.pipeline as P


def main() -> None:
    ms_doc = int(sys.argv[1])
    pages = sys.argv[2] if len(sys.argv) > 2 else "all"
    con = sqlite3.connect("file:.data/examdata.db?mode=ro", uri=True)
    row = con.execute(
        """
        select a.storage_key from document d
        join document_revision r on r.id = d.current_revision_id
        join artifact a on a.id = r.artifact_id where d.id = ?
        """,
        (ms_doc,),
    ).fetchone()
    store = ContentAddressedStore(get_settings().artifacts_dir)
    data = store.path_for_key(row[0]).read_bytes()
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        for i in range(len(pdf)):
            if pages != "all":
                lo_s, _, hi_s = pages.partition("-")
                lo = int(lo_s)
                hi = int(hi_s or lo_s)
                if not (lo - 1 <= i <= hi - 1):
                    continue
            bounds = pdf[i].rect
            rot = pdf[i].rotation_matrix
            toks = []
            for word in pdf[i].get_text("words"):
                r = pymupdf.Rect(word[:4]) * rot
                if r.x0 >= bounds.width * 0.30:
                    continue
                t = P._normalize_ms_token(word[4])
                kind = None
                if P._MS_MAIN.fullmatch(t):
                    kind = "B"
                elif P._MS_NUMBER.match(t) or P._MS_COMPACT.fullmatch(t):
                    kind = "A"
                elif P._MS_PART.fullmatch(t):
                    kind = "P"
                if kind:
                    toks.append((r.y0, r.x0, t, kind))
            rules = P._ms_rules(pdf[i], bounds, rot)
            print(f"== p{i+1} W={bounds.width:.0f} rot={pdf[i].rotation}")
            for y, x, t, k in sorted(toks):
                print(f"   {k} y={y:6.1f} x={x:6.1f} {t!r}")
            print(f"   rules: {rules}")


if __name__ == "__main__":
    main()
