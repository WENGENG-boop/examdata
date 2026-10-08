import json, io

p = r"C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/checkpoint.json"
with io.open(p, "r", encoding="utf-8") as f:
    cp = json.load(f)

cp["updated_at"] = "2026-10-05"

s18 = cp["steps"]["S18"]
s18["results"]["book11_shift"] += (
    "; follow-up 2026-10-05: rotation confirmed source-side (pte-N holds book t(N-1) answers, wrap at t4); "
    "index mapping exact cell-by-cell (0 diffs); 231 conflicts voided as verification evidence; see S18-book11-remap.md"
)
s18["followup"] = {
    "name": "book11 remap follow-up (G14)",
    "status": "done",
    "completed_at": "2026-10-05",
    "files": [
        "ielts-data/runs/20261003T140007Z-repair/scratch/s18/check-align.py + .txt (four-way alignment check, 83 lines)",
        "ielts-data/runs/20261003T140007Z-repair/scratch/s18/index-rotation-check.py + .txt (index rotation check)",
        "ielts-data/runs/20261003T140007Z-repair/scratch/s18/book11-mismatches.py + .txt (three-way per-question diffs, 372 lines)",
        "ielts-data/runs/20261003T140007Z-repair/scratch/s18/book11-deepdump.py + .txt (full dump, 1173 lines)",
        "ielts-data/runs/20261003T140007Z-repair/scratch/s18/page12{1,3,4}-crop-*.png (13 visual crops)",
        "ielts-data/runs/20261003T140007Z-repair/scratch/update-checkpoint-s18b.py",
    ],
    "results": {
        "rotation": "pte-N holds book t(N-1) answers (wrap: pte-1 -> book t4); book t4L==pte-1L (all), book t4R==pte-1R (1-18,27-40), book t3R==pte-4R 30/30",
        "index_mapping": "INDEX tN == pte-N exact cell-by-cell (34/34,40/40,40/40,33/33,30/30,33/33,36/36,40/40; 0 diffs) => index tN holds book t(N-1) answers; index contains values missing from pte JSON (t1L 21-26=B,D,A,B,B,E; t4L 21-24=B,D,A,E, matches book t4L B,D,A,B on 21-23 only)",
        "visual": "p121=t3L full 40 rows; p123=t4L (pairs 21&22/23&24/25&26 IN EITHER ORDER; expanded == INDEX t1L S3); p124=t4R full 40 rows",
        "preserved_conflicts": "t4R Q9 (book A vs pte B); t4R 19-26 (book [D,TRUE,TRUE,NG,TRUE,FALSE,C,A] vs pte [NG,T,NG,T,F,D,A,E]; book[21..24]==pte[20..23]); t2R Q5 (book FALSE vs pte C)",
        "pte4l_orphan": "pte-11-4-listening content matches no book listening key/prompt; 0 hits across books and full PDF scans; books 9/16/18/19/20 have no text layer",
        "extraction_defects": "t4L S2 +1 shift; t4R 1-9 -1 shift; t4L S1 fully dropped; t4R 14-26/29/31 missing; t4R 27 'VJ'->vi; 37 'ZO'->no; t2L Q38 'cuved'; t2R Q16 'vili'; Q36 'ZO'; t3L birds/flowers dropped; mushrooms mis-mapped Q3; t4L Q40 'paymentpayments'; p124 raw layer 15/16 swapped",
        "decision": "rotation is source-side; index faithfully copies source; mapping recorded only; no index data change; no re-extraction",
    },
    "evidence": ["S18-book11-remap.md"],
}
cp["notes"]["s18_facts"]["limits"] = (
    "books 9/16/18/19/20 no text layer; book21 cam21 same-source; GT not indexed; "
    "book11 rotation confirmed source-side + mapping recorded (G14 follow-up 2026-10-05); "
    "unresolved: t4R 19-26 conflict, pte-4L orphan; compare evidence not written back to index"
)
cp["notes"]["s18_facts"]["book11_followup"] = {
    "scope": "G14 book11 page->test misalignment re-comparison (pure local; no code/data/audio changes)",
    "findings": "rotation confirmed source-side (pte-N -> book t(N-1), wrap at t4); index mapping exact; 231 conflicts voided as verification evidence; 3 preserved conflicts kept with dual values; pte-4L orphan unresolved; extraction defects listed",
    "sha256": {
        "S18-book11-remap.md": "1e58248cd19b986175a3c9f00268aa969b5486cc4b138efb9771629cedd9e6aa",
    },
    "docs_updated": "IELTS_REMAINING_GAPS.md (G14 rewrite + G11 row); EXECUTION_CHECKLIST.md (S18 section + overview row); IELTS_IMPLEMENTATION_RESULT.md (A08 + section5 + section9)",
}

with io.open(p, "w", encoding="utf-8", newline="\n") as f:
    json.dump(cp, f, ensure_ascii=False, indent=2)
    f.write("\n")

print("OK stage=", cp["stage"], "S18=", cp["steps"]["S18"]["status"], "followup=", cp["steps"]["S18"]["followup"]["status"])
