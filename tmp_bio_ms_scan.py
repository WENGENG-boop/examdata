"""Comprehensive scan of the 9 stuck bio MS docs.

For each doc:
- page rotations (which pages are /Rotate != 0)
- left-column tokens in VISIBLE space (transform words with rotation_matrix),
  matching compact (`1bii`) or paren (`1(b)(ii)`) formats, with x,y,next-word
- whether merged tokens (token + following roman continuation) occur
"""
import re
import sqlite3
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, "src")
from examdata.edexcel_papers.pipeline import _MS_LEAD  # noqa: E402

DB = "file:.data/examdata.db?mode=ro"
DOCS = [97, 117, 119, 171, 175, 211, 242, 245, 286]
COMPACT = re.compile(r"^[1-9]\d{0,2}[a-z]{1,10}$")
PAREN = re.compile(r"^[1-9]\d{0,2}(?:\([a-z]{1,4}\))+$")
ROMAN = re.compile(r"i{1,3}|iv|v|vi{1,3}|ix|x")


def main() -> int:
    con = sqlite3.connect(DB, uri=True)
    cur = con.cursor()
    for doc_id in DOCS:
        row = cur.execute(
            "SELECT ms.id, ms.matched_paper_document_id FROM mark_scheme ms WHERE ms.document_id = ?",
            (doc_id,),
        ).fetchone()
        ms_id, qp_doc = row
        key = cur.execute(
            """SELECT a.storage_key FROM document d
            JOIN document_revision dr ON dr.id = d.current_revision_id
            JOIN artifact a ON a.id = dr.artifact_id WHERE d.id = ?""",
            (doc_id,),
        ).fetchone()[0]
        qp_paths = [
            r[0]
            for r in cur.execute(
                """SELECT q.number_path FROM question q JOIN paper p ON p.id = q.paper_id
                WHERE p.document_id = ?""",
                (qp_doc,),
            )
        ]
        wanted = set(qp_paths)
        compact = {p.replace("(", "").replace(")", ""): p for p in qp_paths}
        data = Path(f".data/artifacts/{key}").read_bytes()
        print(f"=== doc {doc_id} (ms={ms_id}, qp={qp_doc}, {len(qp_paths)} qpaths) ===")
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            rots = [p.rotation for p in pdf]
            print(f"  rotations: {rots}")
            for index, page in enumerate(pdf):
                rot = page.rotation_matrix
                bounds = page.rect
                words = []
                for w in page.get_text("words"):
                    r = pymupdf.Rect(w[:4]) * rot
                    words.append((r, w[4]))
                lines: dict[int, list] = {}
                for r, text in words:
                    if not bounds.height * 0.04 < r.y0 < bounds.height * 0.9:
                        continue
                    lines.setdefault(round(r.y0 / 3), []).append((r, text))
                for line in lines.values():
                    line.sort(key=lambda item: item[0].x0)
                    for pos, (r, text) in enumerate(line[:2]):
                        if r.x0 >= bounds.width * 0.16:
                            break
                        tok = _MS_LEAD.sub("", text)
                        if not (COMPACT.fullmatch(tok) or PAREN.fullmatch(tok)):
                            continue
                        direct = tok in wanted
                        mapped = compact.get(tok)
                        nxt = ""
                        merged = ""
                        if pos + 1 < len(line):
                            nr, ntext = line[pos + 1]
                            if ROMAN.fullmatch(ntext) and nr.x0 - r.x1 < 12:
                                merged = tok + ntext
                                nxt = f"{ntext}@{nr.x0:.0f}"
                        flag = ""
                        if not direct and mapped is None and not merged:
                            flag = " !NOMAP"
                        if merged and merged in compact:
                            flag = " MERGE"
                        print(
                            f"  p{index} x={r.x0:.0f} y={r.y0:.0f} {tok!r}"
                            f" direct={direct} map={mapped!r} next={nxt!r}"
                            f" merged={merged!r}{flag}"
                        )
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
