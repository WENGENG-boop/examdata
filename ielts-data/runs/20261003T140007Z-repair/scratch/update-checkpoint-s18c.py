import json, io

p = r"C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/checkpoint.json"
with io.open(p, "r", encoding="utf-8") as f:
    cp = json.load(f)

cp["updated_at"] = "2026-10-05"

s18 = cp["steps"]["S18"]
if "follow-up2" not in s18["results"]["book11_shift"]:
    s18["results"]["book11_shift"] += (
        "; follow-up2 2026-10-05: G14 closed to local-evidence ceiling "
        "(t4R 19-26 partially adjudicated; pte-4L unverified, 512-page OCR 0 true hits); "
        "see S18-book11-remap-followup.md"
    )
s18["followup2"] = {
    "name": "G14 closure (t4R 19-26 + pte-4L)",
    "status": "done",
    "completed_at": "2026-10-05",
    "files": [
        "ielts-data/runs/20261003T140007Z-repair/scratch/s18/g14b*/g14b2* (45 files: OCR sweep scripts/outputs, feature-word search, four-channel page reads, semantic checks; sha256 table in evidence section 4)",
        "ielts-data/runs/20261003T140007Z-repair/scratch/s18/g14c-hash-check.py (hash verification of the 45 g14b files + associated inputs)",
        "ielts-data/runs/20261003T140007Z-repair/evidence/S18-book11-remap-followup.md",
        "ielts-data/runs/20261003T140007Z-repair/scratch/update-checkpoint-s18c.py",
    ],
    "results": {
        "t4r_19_26": "layout anomaly confirmed (shift model: printed block[21..26]==intent[20..25] 6/6 + two illegal values in group: printed 19=D, 24=FALSE); intent values rebuilt [19 NG,20 T,21 NG,22 T,23 F,24 C,25 A,26 E] (20-23/25 triple-consistent: shift model + pte-1R + semantics); Q24 dual value kept (C = shift model + semantics primary vs D = pte-1R only); not officially verified (single printing on this machine; official-keys t4R only 24 entries, 19-26 all absent)",
        "pte4l": "unverified; OCR 300dpi over 512 text-layer-less pages (book9 165 / 16 74 / 18 71 / 19 72 / book20 t1-t4 34+35+31+30) + 31 PRIMARY + 20 SECONDARY pattern search across all resources; 0 true hits (2 PRIMARY false positives: book18 p12 'car'+'Goes' argo bus form; book20-t2 p19 North Carolina MLB/ABS baseball text); object = practicepteonline 'IELTS Listening Test 80' (page_id 2943, audio 80_we.mp3)",
        "correction": "S18-book11-remap.md p124 raw-layer 15/16 swap = extraction tool pairing artifact (text layer 315.0->Q14=B, 325.9->Q15=A, 336.9->Q16=B consistent with visual + pte), not a book anomaly",
    },
    "evidence": ["S18-book11-remap-followup.md"],
    "docs_updated": "IELTS_REMAINING_GAPS.md (G14 + cambridge:11 row); EXECUTION_CHECKLIST.md (S18 overview + section); IELTS_IMPLEMENTATION_RESULT.md (A08 + section5 + section9)",
}

cp["notes"]["s18_facts"]["limits"] = cp["notes"]["s18_facts"]["limits"].replace(
    "unresolved: t4R 19-26 conflict, pte-4L orphan;",
    "G14 closed to local-evidence ceiling (t4R 19-26 partially adjudicated, Q24 dual C/D; pte-4L unverified, 512-page OCR 0 true hits);",
)
cp["notes"]["s18_facts"]["g14_closure"] = {
    "scope": "G14 follow-up: t4R 19-26 print check + pte-4L provenance (pure local; no index/data/audio changes)",
    "findings": "t4R 19-26: layout anomaly confirmed, intent rebuilt, Q24 dual C/D kept, not officially verified (single printing); pte-4L: unverified after 512-page OCR + full-resource search, 0 true hits; correction: p124 15/16 swap was an extraction artifact",
    "sha256": {
        "S18-book11-remap-followup.md": "3b877380b5dac7a5eb98cbf0abcc36abe2a27ffcbaacfbc8a783e2bb621da96e",
        "g14c-hash-check.py": "05508f1317542c5b53235c63331533ec663be8f01cfbea1a85706af050f86a70",
    },
    "docs_updated": "IELTS_REMAINING_GAPS.md (G14 + cambridge:11 row); EXECUTION_CHECKLIST.md (S18 overview + section); IELTS_IMPLEMENTATION_RESULT.md (A08 + section5 + section9)",
}

with io.open(p, "w", encoding="utf-8", newline="\n") as f:
    json.dump(cp, f, ensure_ascii=False, indent=2)
    f.write("\n")

print("OK stage=", cp["stage"], "S18=", cp["steps"]["S18"]["status"], "followup2=", cp["steps"]["S18"]["followup2"]["status"])
