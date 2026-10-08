"""r8 instrument: dump every question-number candidate line the _anchors scan sees,
for the three known-bad QP PDFs (p706/p2162/p1351), to learn the visual/token
signature that separates ghost anchors (answer lines / stray numbers) from real
question numbers.

Read-only. Output: tmp_r8_anchor_dump.out
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from examdata.paperqa import locator as L  # noqa: E402

ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT / ".data/examdata.db")
con.row_factory = sqlite3.Row
cur = con.cursor()


def pdf_path_for_document(doc_id: int) -> Path:
    row = cur.execute(
        """
        SELECT a.storage_key
        FROM document d
        JOIN document_revision r ON r.id = d.current_revision_id
        JOIN artifact a ON a.id = r.artifact_id
        WHERE d.id = ?
        """,
        (doc_id,),
    ).fetchone()
    return ROOT / ".data/artifacts" / row["storage_key"]


def dump(paper_id: int, doc_id: int, label: str, out):
    path = pdf_path_for_document(doc_id)
    pdf = pymupdf.open(path)
    ciphered = L.is_ciphered(pdf)
    print(f"\n{'='*100}\n{label}  paper_id={paper_id} doc={doc_id} pages={len(pdf)} ciphered={ciphered}\n  {path.name}", file=out)

    anchors: list[L.Anchor] = []
    main = 0
    section_at, section_top = None, 0.0
    sub = ""
    end = (len(pdf) - 1, L._page_bounds(pdf[-1]).height * .9)
    for index, page in enumerate(pdf):
        if index == 0:
            continue
        bounds = L._page_bounds(page)
        words = sorted(L._page_words(page, ciphered), key=lambda w: (round(w[1] / 3), w[0]))
        banners = L._banner_rows(words, bounds)
        if banners:
            section_at, section_top = index, min(banners)
        stop = False
        previous = None
        for word in words:
            prev = previous
            previous = word
            x, y, _, _, text, *_ = word
            if L._ACKNOWLEDGEMENTS.match(text):
                if not anchors:
                    continue
                end = (index, max(0, y - 8))
                stop = True
                break
            if not bounds.height * .04 < y < bounds.height * .9:
                continue
            if (x < bounds.width * .125 or L._greek_number_after_question_word(prev, word, bounds)) and re.fullmatch(r"[1-9]\d{0,2}\.{0,2}", text.lstrip("*")) and not L._numeric_row(words, y, candidate=text.lstrip("*")):
                number = int(text.lstrip("*").rstrip("."))
                # show the whole line (words within y +-3), each token with x
                line_words = sorted((w for w in words if abs(w[1] - y) < 3), key=lambda w: w[0])
                line_repr = " | ".join(f"{w[4]}@{w[0]:.0f}" for w in line_words[:24])
                became = ""
                if section_at is not None and (index == section_at + 1 or (index == section_at and y > section_top)):
                    section_at = None
                    if number == 1 and main >= 2:
                        anchors.clear()
                        main = 0
                        sub = ""
                if number == main + 1 or (main and number == main):
                    prev_main = main
                    main = number
                    sub = ""
                    anchors.append(L.Anchor(str(main), index, y))
                    became = f"  ==> ANCHOR '{main}' (main {prev_main}->{main})"
                print(f"P{index+1:>3} y={y:7.1f} x={x:6.1f} tok={text!r:<8} line[{len(line_words)}]: {line_repr}{became}", file=out)
            elif main and x < bounds.width * .20:
                match = re.fullmatch(r"\(([a-z]+)\)", text)
                if not match:
                    continue
                part = match.group(1)
                if len(part) == 1 and (part not in {"i", "v", "x"} or not sub or ord(part) == ord(sub) + 1):
                    sub = part
                    anchors.append(L.Anchor(f"{main}({part})", index, y))
                    print(f"P{index+1:>3} y={y:7.1f} x={x:6.1f} tok={text!r:<8}  ==> SUB-ANCHOR '{main}({part})'", file=out)
                elif sub and re.fullmatch(r"[ivx]+", part):
                    anchors.append(L.Anchor(f"{main}({sub})({part})", index, y))
                    print(f"P{index+1:>3} y={y:7.1f} x={x:6.1f} tok={text!r:<8}  ==> SUB-SUB-ANCHOR '{main}({sub})({part})'", file=out)
        totals = page.search_for("TOTAL FOR PAPER") if not ciphered else []
        if ciphered:
            bottom = L._total_for_paper_bottom(words)
            if bottom is not None:
                end = (index, bottom - 4)
                break
        if totals:
            end = (index, min(rect.y0 for rect in totals) - 4)
            break
        if stop:
            break
    print(f"\n  FINAL anchors: {[a.path for a in anchors]}", file=out)
    print(f"  end={end}", file=out)
    pdf.close()


with open(ROOT / "tmp_r8_anchor_dump.out", "w", encoding="utf-8") as out:
    dump(706, 84, "p706 wbi13-01", out)
    dump(2162, 3517, "p2162 wps01-01", out)
    dump(1351, 1629, "p1351 wit11-01", out)

con.close()
print("done -> tmp_r8_anchor_dump.out")
