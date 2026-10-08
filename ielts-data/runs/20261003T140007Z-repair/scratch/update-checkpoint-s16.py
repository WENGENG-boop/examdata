import json, io

p = r"C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/checkpoint.json"
with io.open(p, "r", encoding="utf-8") as f:
    cp = json.load(f)

cp["updated_at"] = "2026-10-05"
cp["stage"] = "S17"

cp["steps"]["S16"] = {
    "status": "done",
    "completed_at": "2026-10-05",
    "files": [
        "examdata/docs/IELTS_API.md",
        "ielts-api/DEVELOPMENT.md",
        "ielts-api/ielts-api.mjs",
        "ielts-api/lfs.mjs",
        "ielts-api/tools/verify-pdfs.mjs",
        "examdata/src/examdata/api/ielts.py",
        "docs/ielts/EXECUTION_CHECKLIST.md",
    ],
    "results": {
        "doc_diff": "6 files + ielts.py; per-file sha256 in evidence/S16-doc-diff.txt",
        "other_copy_round1": "274 pass / 8 fail / EXIT=1 (missing workspace raw sources tmp_audit_ielts/; not code defects)",
        "other_copy_round2": "309 tests / 307 pass / 0 fail / 2 skipped / EXIT=0 (tmp junctions; removed after)",
        "sync": "add 70 + overwrite 12; conflict 0; failed 0; 12 other-copy-only files preserved; changed-after-sync=0",
        "protected_recheck": "adapters/markscheme/specs changed=0/missing=0; edexcel_papers/pipeline.py changed=1 by external concurrent worker (recorded, not ours)",
        "port8000": "TCP LISTENING PID 36036; GET /api/v1/ielts/info -> 200; not restarted",
        "pytest": "19 passed / 1 skipped (exit 0)",
        "syntax": "node --check x3 + py_compile (exit 0)",
    },
    "evidence_dir": "ielts-data/runs/20261003T140007Z-repair/evidence/",
    "evidence": [
        "S16-summary.md",
        "S16-doc-diff.txt",
        "S16-sync.json",
        "S16-sync-verify.txt",
        "S16-main-tests.txt",
        "S16-other-tests.txt",
        "S16-other-tests-round2.txt",
        "S16-both-copies-tests.txt",
        "S16-protected-recheck.txt",
        "S16-port8000.txt",
        "S16-pytest.txt",
        "S16-syntax.txt",
    ],
}

cp["notes"]["s16_facts"] = {
    "doc_corrections": "IELTS_API.md answer-key calibre (reading 3360 / listening 3346 / cam21 reading160+listening147); DEVELOPMENT.md 3360/3346 + PDF 20/20 + cam21 full; ielts-api.mjs/lfs.mjs/verify-pdfs.mjs book20=Test1 fascicle; ielts.py info env dict MAX_CONCURRENT/QUEUE_TIMEOUT/DATA_DIR",
    "sync_scope": "ielts-api files only (examdata-side files belong to a different repo, not synced); backup at backup/other-copy-2026-10-05/ (12 files)",
    "deferred_to_s17": "S07 'compare-official wired into audit-all' not done (compare-official exposed via CLI in S13; audit-all not wired because per-question PDF values not persisted) -> record in checklist S17 + REMAINING_GAPS",
    "external_changes": "edexcel_papers/pipeline.py + production DB changed by external concurrent workers on 2026-10-05; recorded in evidence/S16-protected-recheck.txt",
}

with io.open(p, "w", encoding="utf-8", newline="\n") as f:
    json.dump(cp, f, ensure_ascii=False, indent=2)
    f.write("\n")

print("OK stage=", cp["stage"], "S16=", cp["steps"]["S16"]["status"], "S15=", cp["steps"]["S15"]["status"])
