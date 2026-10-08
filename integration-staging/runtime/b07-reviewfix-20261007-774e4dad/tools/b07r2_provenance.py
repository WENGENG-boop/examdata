#!/usr/bin/env python
"""STEP 1 provenance gate for review-fix run b07-reviewfix-20261007-774e4dad.

Second private review-fix run of the B07 independent-review findings.  This run
is independent of the earlier review-fix run (b07-reviewfix-20261007-fzgu78c6):
the new candidate is copied solely from the frozen B07 v1 candidate, and the
earlier run's artifacts are recorded here as frozen inputs that must stay
byte-for-byte unchanged.

Actions, in order:
1. Cross-check the digest reimplementation against the recorded B06 parent
   digest (208 files / ffe774db...).
2. Recompute the frozen B07 candidate digest with the documented algorithm and
   require the recorded 221-file value 5df25984... .
3. Record sha256 of the formal execution ledger and of the frozen B07 evidence:
   named files plus tree digests of the frozen B07 run root, the frozen docs
   evidence directory, the independent-review directory, and the earlier
   review-fix run root.
4. Only if both digests match: copy the frozen B07 candidate verbatim into
   <run>/candidates/b07-operations-v2 and record the copy digest.
   On any mismatch: write reports/B07R2_DIGEST_DISCREPANCY.json and exit 2
   without copying or doing any further candidate-dependent work.

Writes only inside the run root.  Never edits the frozen inputs.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tree_digest import tree_digest, file_sha256  # noqa: E402

RUN = pathlib.Path(__file__).resolve().parents[1]
API = RUN.parents[2]  # integration-staging/runtime/<run> -> api root
assert API.name == "api" and (API / "docs").is_dir(), f"unexpected API root: {API}"

B06_CAND = API / "integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1"
B07_CAND = API / "integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1"
B07_RUN = API / "integration-staging/runtime/b07-rehearsal-2026-10-07"
INDEP_REVIEW = API / "integration-staging/runtime/b07-independent-review-20261007-hf7_6xwr"
PRIOR_REVIEWFIX = API / "integration-staging/runtime/b07-reviewfix-20261007-fzgu78c6"
DOCS_EVIDENCE = API / "docs/integration/execution/evidence/B07/b07-rehearsal-2026-10-07"
LEDGER = API / "docs/integration/execution/execution-ledger.json"

V2_DEST = RUN / "candidates/b07-operations-v2"
V2_MANIFEST_NAME = "B07R2_CANDIDATE_MANIFEST.json"

B06_EXPECTED = {"files": 208, "sha256": "ffe774db608ff9d86246458a38265f9baa760b40880e48197e84d887f85d53f4"}
B07_EXPECTED = {"files": 221, "sha256": "5df259843b26792910de697b2c646fc413c5b936edf3d95d04baf7afa482c179"}

DIGEST_RULE = (
    "sha256 over 'path\\0sha256\\n' for every file under the root, sorted by path, "
    "excluding __pycache__/.pytest_cache and excluding the named manifest itself"
)

NAMED_FILES = [
    LEDGER,
    API / "docs/integration/execution/B07_REHEARSAL_REPORT.md",
    API / "docs/integration/execution/B07_PROGRESS_LEDGER.json",
    API / "docs/integration/execution/B07_PROGRESS_LEDGER.md",
    API / "docs/integration/execution/B07_MERGE_PROPOSAL.json",
    API / "docs/integration/execution/B07_MERGE_PROPOSAL.md",
    API / "docs/integration/execution/B07_ROLLBACK_PROPOSAL.json",
    API / "docs/integration/execution/B07_ROLLBACK_PROPOSAL.md",
    API / "docs/integration/execution/B07_INDEPENDENT_REVIEW_2026-10-07.md",
    INDEP_REVIEW / "results.json",
    B07_CAND / "B07_CANDIDATE_MANIFEST.json",
    API / "docs/integration/execution/B07R_FINAL_REPORT.md",
    API / "docs/integration/execution/B07R_DIFF_FROM_V1.md",
    API / "docs/integration/execution/B07R_MERGE_PROPOSAL.json",
    API / "docs/integration/execution/B07R_MERGE_PROPOSAL.md",
    API / "docs/integration/execution/B07R_ROLLBACK_PROPOSAL.json",
    API / "docs/integration/execution/B07R_ROLLBACK_PROPOSAL.md",
    API / "docs/integration/execution/B07R_EVIDENCE_INDEX.json",
    API / "docs/integration/execution/B07R_FINDINGS_TO_TESTS_MATRIX.md",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record_frozen_inputs() -> dict:
    named = [{"path": str(p), "sha256": file_sha256(p)} for p in NAMED_FILES]
    return {
        "execution_ledger": str(LEDGER),
        "execution_ledger_sha256": file_sha256(LEDGER),
        "frozen_b07_run_root": tree_digest(B07_RUN),
        "frozen_b07_docs_evidence_dir": tree_digest(DOCS_EVIDENCE),
        "independent_review_dir": tree_digest(INDEP_REVIEW),
        "prior_reviewfix_run_root": tree_digest(PRIOR_REVIEWFIX),
        "named_files": named,
    }


def main() -> int:
    run_id = RUN.name
    observed: dict = {"run_id": run_id, "recorded_at_utc": now(), "digest_rule": DIGEST_RULE}

    b06_obs = tree_digest(B06_CAND, ("B06_CANDIDATE_MANIFEST.json",))
    b06 = {
        "target": str(B06_CAND),
        "expected": B06_EXPECTED,
        "observed": b06_obs,
        "match": b06_obs["files"] == B06_EXPECTED["files"] and b06_obs["sha256"] == B06_EXPECTED["sha256"],
    }
    observed["implementation_cross_check_b06"] = b06

    b07_obs = tree_digest(B07_CAND, ("B07_CANDIDATE_MANIFEST.json",))
    b07 = {
        "target": str(B07_CAND),
        "expected": B07_EXPECTED,
        "observed": b07_obs,
        "match": b07_obs["files"] == B07_EXPECTED["files"] and b07_obs["sha256"] == B07_EXPECTED["sha256"],
    }
    observed["frozen_b07_candidate"] = b07

    observed["frozen_inputs"] = record_frozen_inputs()

    if not (b06["match"] and b07["match"]):
        observed["verdict"] = "stop-discrepancy"
        discrepancy = {
            "schema": "examdata.integration.b07r2_discrepancy/1",
            "run_id": run_id,
            "recorded_at_utc": now(),
            "title": "Frozen B07 digest recomputation did not match the recorded value",
            "detail": observed,
            "action": "candidate-dependent work stopped; no candidate copied",
        }
        out = RUN / "reports/B07R2_DIGEST_DISCREPANCY.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(discrepancy, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(observed, indent=2))
        print(f"DISCREPANCY WRITTEN: {out}", file=sys.stderr)
        return 2

    # Both digests match: copy the frozen candidate verbatim, then verify.
    if V2_DEST.exists():
        print(f"refusing to overwrite existing {V2_DEST}", file=sys.stderr)
        return 3
    V2_DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(B07_CAND, V2_DEST)
    copy_digest = tree_digest(V2_DEST, (V2_MANIFEST_NAME,))
    source_after = tree_digest(B07_CAND, ("B07_CANDIDATE_MANIFEST.json",))
    observed["copy"] = {
        "source": str(B07_CAND),
        "destination": str(V2_DEST),
        "files_on_disk": sum(1 for p in V2_DEST.rglob("*") if p.is_file()),
        "digest_excluding_future_manifest": copy_digest,
        "source_digest_after_copy": source_after,
        "source_unchanged_by_copy": source_after == b07_obs,
    }
    observed["verdict"] = "proceed"
    out = RUN / "evidence/provenance_before_copy.json"
    out.write_text(json.dumps(observed, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(observed, indent=2))
    print(f"PROVENANCE OK: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
