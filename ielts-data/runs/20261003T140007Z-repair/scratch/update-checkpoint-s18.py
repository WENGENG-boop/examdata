import json, io

p = r"C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/checkpoint.json"
with io.open(p, "r", encoding="utf-8") as f:
    cp = json.load(f)

cp["updated_at"] = "2026-10-05"
cp["stage"] = "S18"

cp["steps"]["S18"] = {
    "status": "done",
    "completed_at": "2026-10-05",
    "files": [
        "ielts-data/runs/20261003T140007Z-repair/official-keys/ (15 books: 1-8,10-15,17; _pages.json + test_T_{reading,listening}.json each; book12 tests 5-8; book1 test_gt_listening.json; ocr/ + visual-fixes.json)",
        "ielts-data/runs/20261003T140007Z-repair/scratch/s18/answers/ (our-side answer dumps, 21 books + _manifest.json)",
        "ielts-data/runs/20261003T140007Z-repair/scratch/s18/compare/ (119 cell compare JSON + 119 logs)",
        "ielts-data/runs/20261003T140007Z-repair/scratch/s18/compare-batch.sh",
        "ielts-data/runs/20261003T140007Z-repair/scratch/s18/aggregate-compare.py",
        "ielts-data/runs/20261003T140007Z-repair/scratch/s18/verify-book11-shift.py",
        "docs/ielts/EXECUTION_CHECKLIST.md",
        "docs/ielts/IELTS_IMPLEMENTATION_RESULT.md",
        "docs/ielts/IELTS_REMAINING_GAPS.md",
    ],
    "results": {
        "cells": "119/119 EXIT=0, error cells=0 (15 books x 8 cells; book14 t1 reading NO-PDF)",
        "totals": "total 4764 / match 2833 / conflict 985 / pdf_only 6 / answer_only 939 / missing 1 / unverified 946",
        "conflict_classes": "plain_diff 786 (pdf_superset 202 / disjoint 485 / punct_case_only 61 / idx_superset 38) + alt_match 124 + alt_no_match 68 + nonascii_ocr 7",
        "spot_checks": "book1 t2 listening N=41 (match24/conflict15/pdf_only2); book3 t2-t4 six cells all 40; book10 t1 reading Q34 pdf_only (only empty in index); all-match cells: b10 t3 L/R 40/40, b12 t6 L 40/40, b7 t3 L 40/40, b7 t4 R 40/40",
        "book10_t1_reading_strict": "match=36 / conflict=3 (Q9/Q10/Q12 variant forms) / pdf_only=1 (Q34, PDF=F) - supersedes S06 smoke (match=38 / conflict=1 Q22; Q22 now match)",
        "book11_shift": "page-to-test mapping broken: listening t1->idx t2 31/40, t2->t3 27/30, t4->t1 8/22; reading t1->t2 31/33, t2->t3 27/32, t3->t4 30/30, t4->t1 16/24; page123 (labelled t4) values = index t1 answers; 231 conflicts voided; see S18-book11-shift-check.txt",
        "index_writeback": "none (official_verifications still 2: gv-01/gv-02)",
    },
    "evidence_dir": "ielts-data/runs/20261003T140007Z-repair/evidence/",
    "evidence": [
        "S18-official-compare.json",
        "S18-official-compare.md",
        "S18-compare-batch.txt",
        "S18-book11-shift-check.txt",
    ],
}

cp["notes"]["s18_facts"] = {
    "scope": "official-key extraction for 15 books with text layer; per-cell compare vs our index answers (reading+listening)",
    "limits": "books 9/16/18/19/20 no text layer; book21 cam21 same-source; GT not indexed; book11 mapping broken -> re-extract needed (G14); compare evidence not written back to index",
    "sha256": {
        "S18-official-compare.json": "9aaa37085c811cb9280a0b971c8c1e8113baa58d41f8cbf21cbcb6e283d35db9",
        "S18-official-compare.md": "211f449a92eda1549947a140411a5d79ce03e928722ace6ab82c0d84187d6c48",
        "S18-compare-batch.txt": "5b23fba5aa86bf53e452211d6ac92e1c2094a972abf694661d1b7bb74c67007f",
        "S18-book11-shift-check.txt": "96fd90ee2de2a459b0ef18a09d7ef6740c26e3244fd18ffd3b17467a734a49a0",
    },
    "docs_updated": "EXECUTION_CHECKLIST.md (S18 section + overview row); IELTS_IMPLEMENTATION_RESULT.md (A08 + section5 + section9); IELTS_REMAINING_GAPS.md (G11 rewrite, G13 update, G14 new)",
}

with io.open(p, "w", encoding="utf-8", newline="\n") as f:
    json.dump(cp, f, ensure_ascii=False, indent=2)
    f.write("\n")

print("OK stage=", cp["stage"], "S18=", cp["steps"]["S18"]["status"], "S17=", cp["steps"]["S17"]["status"])
