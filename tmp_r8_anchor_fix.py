"""r8: validate the dot-answer-line filter for _anchors.

Hypothesis (from tmp_r8_anchor_dump.out): ghost question anchors come from
numbered answer lines "1 ..........", "2 .........." whose digit is a lone
left-column number followed by a run of dots on the same visual line. Real
question headings carry text instead.

patched _anchors = original + skip candidate when a dot-run word (>=4 dots)
sits immediately to the right on the same visual line.

Usage:
  python tmp_r8_anchor_fix.py check 706 2162 1351 767 729 713 741 1373 1381 1407 2092 1197 1327
  python tmp_r8_anchor_fix.py scan           # all edexcel QP/specimen docs -> tmp_r8_anchor_scan.json/.out
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from examdata.paperqa import locator as L  # noqa: E402

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".data/examdata.db"


def _dot_answer_digit(words, word):
    """True when a run of dots starts right next to this left-column digit on
    the same visual line -> numbered answer line, not a question number."""
    x, y, x1, y1, text, *_ = word
    for w in words:
        if w is word:
            continue
        wx0, wy0, wx1, wy1, wtext, *_ = w
        if wx0 >= x1 - 2 and wx0 - x1 < 24 and wy0 < y1 and wy1 > y and re.fullmatch(r"\.{4,}", wtext):
            return True
    return False


def patched_anchors(pdf, role, *, ciphered=None):
    if ciphered is None:
        ciphered = L.is_ciphered(pdf)
    anchors = []
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
            if (
                (x < bounds.width * .125 or L._greek_number_after_question_word(prev, word, bounds))
                and re.fullmatch(r"[1-9]\d{0,2}\.{0,2}", text.lstrip("*"))
                and not L._numeric_row(words, y, candidate=text.lstrip("*"))
                and not _dot_answer_digit(words, word)
            ):
                number = int(text.lstrip("*").rstrip("."))
                if section_at is not None and (index == section_at + 1 or (index == section_at and y > section_top)):
                    section_at = None
                    if number == 1 and main >= 2:
                        anchors.clear()
                        main = 0
                        sub = ""
                if number == main + 1 or (main and number == main):
                    main = number
                    sub = ""
                    anchors.append(L.Anchor(str(main), index, y))
            elif main and x < bounds.width * .20:
                match = re.fullmatch(r"\(([a-z]+)\)", text)
                if not match:
                    continue
                part = match.group(1)
                if len(part) == 1 and (part not in {"i", "v", "x"} or not sub or ord(part) == ord(sub) + 1):
                    sub = part
                    anchors.append(L.Anchor(f"{main}({part})", index, y))
                elif sub and re.fullmatch(r"[ivx]+", part):
                    anchors.append(L.Anchor(f"{main}({sub})({part})", index, y))
        totals = page.search_for("TOTAL FOR PAPER") if role == "qp" and not ciphered else []
        if role == "qp" and ciphered:
            bottom = L._total_for_paper_bottom(words)
            if bottom is not None:
                end = (index, bottom - 4)
                break
        if totals:
            end = (index, min(rect.y0 for rect in totals) - 4)
            break
        if stop:
            break
    if not anchors or main < 1:
        raise L.LocationError("No reliable left-column question numbering; scanned/unsupported PDF layout")
    return anchors, end


def skipped_candidates(pdf, ciphered):
    """Re-walk pages collecting digits that the patched filter would skip."""
    out = []
    for index, page in enumerate(pdf):
        if index == 0:
            continue
        bounds = L._page_bounds(page)
        words = sorted(L._page_words(page, ciphered), key=lambda w: (round(w[1] / 3), w[0]))
        for word in words:
            x, y, _, _, text, *_ = word
            if not bounds.height * .04 < y < bounds.height * .9:
                continue
            if (
                x < bounds.width * .125
                and re.fullmatch(r"[1-9]\d{0,2}\.{0,2}", text.lstrip("*"))
                and not L._numeric_row(words, y, candidate=text.lstrip("*"))
                and _dot_answer_digit(words, word)
            ):
                line = sorted((w for w in words if abs(w[1] - y) < 8), key=lambda w: w[0])
                out.append(
                    {
                        "page": index + 1,
                        "y": round(y, 1),
                        "tok": text,
                        "line": [w[4][:20] for w in line[:6]],
                    }
                )
    return out


def artifact_path(cur, doc_id):
    row = cur.execute(
        """
        SELECT a.storage_key FROM document d
        JOIN document_revision r ON r.id = d.current_revision_id
        JOIN artifact a ON a.id = r.artifact_id WHERE d.id = ?
        """,
        (doc_id,),
    ).fetchone()
    return ROOT / ".data/artifacts" / row["storage_key"] if row else None


def check(paper_ids):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    for pid in paper_ids:
        row = cur.execute(
            "SELECT p.id, p.paper_no, p.document_id, p.question_count, d.title FROM paper p JOIN document d ON d.id=p.document_id WHERE p.id=?",
            (pid,),
        ).fetchone()
        if row is None:
            print(f"paper {pid}: not found")
            continue
        path = artifact_path(cur, row["document_id"])
        pdf = pymupdf.open(path)
        ciphered = L.is_ciphered(pdf)
        old_anchors, _ = L._anchors(pdf, "qp", ciphered=ciphered)
        new_anchors, _ = patched_anchors(pdf, "qp", ciphered=ciphered)
        old_paths = list(dict.fromkeys(a.path for a in old_anchors))
        new_paths = list(dict.fromkeys(a.path for a in new_anchors))
        db_paths = [
            r["number_path"]
            for r in cur.execute(
                "SELECT number_path FROM question WHERE paper_id=? ORDER BY display_order", (pid,)
            )
        ]
        skipped = skipped_candidates(pdf, ciphered)
        print(f"\n{'='*90}\npaper {pid} {row['paper_no']} doc={row['document_id']} qc={row['question_count']} {row['title'][:60]}")
        print(f"  db_paths({len(db_paths)}): {db_paths}")
        print(f"  old({len(old_paths)}): {old_paths}")
        print(f"  new({len(new_paths)}): {new_paths}")
        print(f"  skipped({len(skipped)}):")
        for s in skipped:
            print(f"    p{s['page']} y={s['y']} tok={s['tok']!r} line={s['line']}")
        pdf.close()
    con.close()


def scan():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    docs = cur.execute(
        """
        SELECT d.id, d.title, d.doc_type FROM document d JOIN board b ON b.id=d.board_id
        WHERE b.key='edexcel' AND d.doc_type IN ('question_paper','specimen_paper')
        ORDER BY d.id
        """
    ).fetchall()
    report = []
    t0 = time.time()
    for i, d in enumerate(docs):
        path = artifact_path(cur, d["id"])
        if path is None or not path.exists():
            report.append({"doc": d["id"], "title": d["title"], "error": "artifact missing"})
            continue
        try:
            pdf = pymupdf.open(path)
            ciphered = L.is_ciphered(pdf)
            old_anchors, _ = L._anchors(pdf, "qp", ciphered=ciphered)
            new_anchors, _ = patched_anchors(pdf, "qp", ciphered=ciphered)
            old_paths = list(dict.fromkeys(a.path for a in old_anchors))
            new_paths = list(dict.fromkeys(a.path for a in new_anchors))
            pdf.close()
        except Exception as exc:
            report.append({"doc": d["id"], "title": d["title"], "error": f"{type(exc).__name__}: {exc}"})
            continue
        if old_paths != new_paths:
            report.append(
                {
                    "doc": d["id"],
                    "title": d["title"],
                    "doc_type": d["doc_type"],
                    "old_only": [p for p in old_paths if p not in new_paths],
                    "new_only": [p for p in new_paths if p not in old_paths],
                    "n_old": len(old_paths),
                    "n_new": len(new_paths),
                }
            )
        if (i + 1) % 200 == 0:
            print(f"  ...{i+1}/{len(docs)} ({time.time()-t0:.0f}s)", flush=True)
    (ROOT / "tmp_r8_anchor_scan.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    changed = [r for r in report if "old_only" in r]
    errors = [r for r in report if "error" in r]
    with open(ROOT / "tmp_r8_anchor_scan.out", "w", encoding="utf-8") as out:
        print(f"docs scanned={len(docs)} changed={len(changed)} errors={len(errors)} time={time.time()-t0:.0f}s", file=out)
        for r in changed:
            print(f"\ndoc {r['doc']} {r['title'][:70]} ({r['n_old']}->{r['n_new']})", file=out)
            print(f"  old_only: {r['old_only']}", file=out)
            print(f"  new_only: {r['new_only']}", file=out)
        for r in errors:
            print(f"\nERROR doc {r['doc']} {r['title'][:70]}: {r['error']}", file=out)
    print(f"done scanned={len(docs)} changed={len(changed)} errors={len(errors)} time={time.time()-t0:.0f}s")
    con.close()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if mode == "check":
        ids = [int(a) for a in sys.argv[2:]] or [706, 2162, 1351]
        check(ids)
    elif mode == "scan":
        scan()
