#!/usr/bin/env python
"""STEP 7 provenance recheck for review-fix run b07-reviewfix-20261007-fzgu78c6.

Recomputes, after all candidate-dependent work, what STEP 1 recorded:
1. The B06 cross-check digest (algorithm sanity).
2. The frozen B07 v1 candidate digest (221 files / 5df25984...).
3. The formal execution ledger sha256 and the frozen B07 evidence digests
   (named files + tree digests) via the same record_frozen_inputs() the STEP 1
   gate used.
4. The current v2 candidate: B07R manifest sha256, tree digest excluding the
   manifest, the three rewritten file hashes, and the on-disk file count.

Every value is compared against the STEP 1 baseline
(evidence/provenance_before_copy.json) and the recorded v2 values.  Writes
only the new evidence file; never edits frozen inputs.  Exit 0 when everything
matches, 2 on any mismatch (the report is still written).
"""
from __future__ import annotations

import json
import pathlib
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tree_digest import tree_digest, file_sha256  # noqa: E402

import b07r_provenance as prov  # noqa: E402

RUN = prov.RUN
BASELINE = RUN / "evidence/provenance_before_copy.json"
MANIFEST_INPUTS = RUN / "evidence/step6_v2_manifest_inputs.json"
B07R_MANIFEST = prov.V2_DEST / prov.V2_MANIFEST_NAME
OUT = RUN / "evidence/step7_provenance_recheck.json"

V2_MANIFEST_EXPECTED = "0a0052cd3dd433b9d675d88728acac935af0fd83660075e5a86366ea1662ea54"
V2_TREE_EXPECTED = "f0f9a3c49db995ad5934907763a4664576ee07f3280c3586d9a8670c991a022c"
V2_FILES_EXPECTED = 222
V2_ON_DISK_EXPECTED = 223


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def compare(baseline: dict, current: dict) -> tuple[bool, dict]:
    """Per-key equality between baseline and current frozen-input records."""
    detail: dict = {}
    all_equal = True
    for key in sorted(set(baseline) | set(current)):
        equal = baseline.get(key) == current.get(key)
        all_equal = all_equal and equal
        detail[key] = {"equal": equal}
        if not equal:
            detail[key]["baseline"] = baseline.get(key)
            detail[key]["current"] = current.get(key)
    return all_equal, detail


def main() -> int:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    manifest_inputs = json.loads(MANIFEST_INPUTS.read_text(encoding="utf-8"))
    observed: dict = {
        "schema": "examdata.integration.b07r_provenance_recheck/1",
        "run_id": RUN.name,
        "rechecked_at_utc": now(),
        "baseline": str(BASELINE),
        "baseline_sha256": file_sha256(BASELINE),
        "boundary": (
            "private recheck only; recomputation reads frozen inputs without "
            "modifying them; no merge, no deployment, gates closed"),
    }

    b06_obs = tree_digest(prov.B06_CAND, ("B06_CANDIDATE_MANIFEST.json",))
    b06_match = (b06_obs["files"] == prov.B06_EXPECTED["files"]
                 and b06_obs["sha256"] == prov.B06_EXPECTED["sha256"])
    observed["implementation_cross_check_b06"] = {
        "target": str(prov.B06_CAND),
        "expected": prov.B06_EXPECTED,
        "observed": b06_obs,
        "match": b06_match,
    }

    b07_obs = tree_digest(prov.B07_CAND, ("B07_CANDIDATE_MANIFEST.json",))
    b07_match = (b07_obs["files"] == prov.B07_EXPECTED["files"]
                 and b07_obs["sha256"] == prov.B07_EXPECTED["sha256"])
    v1_manifest_sha = file_sha256(prov.B07_CAND / "B07_CANDIDATE_MANIFEST.json")
    observed["frozen_b07_candidate"] = {
        "target": str(prov.B07_CAND),
        "expected": prov.B07_EXPECTED,
        "observed": b07_obs,
        "match": b07_match,
        "baseline_observed": baseline["frozen_b07_candidate"]["observed"],
        "baseline_observed_equal": b07_obs == baseline["frozen_b07_candidate"]["observed"],
        "manifest_sha256": v1_manifest_sha,
        "manifest_recorded": manifest_inputs["v1_manifest_sha256"],
        "manifest_match": v1_manifest_sha == manifest_inputs["v1_manifest_sha256"],
    }

    current_frozen = prov.record_frozen_inputs()
    frozen_equal, frozen_detail = compare(baseline["frozen_inputs"], current_frozen)
    observed["frozen_inputs"] = {
        "current": current_frozen,
        "baseline_sha256": baseline["frozen_inputs"].get("execution_ledger_sha256"),
        "per_key_equal": frozen_detail,
        "all_equal_since_step1": frozen_equal,
    }

    v2_tree = tree_digest(prov.V2_DEST, (prov.V2_MANIFEST_NAME,))
    edited = {}
    for item in json.loads(B07R_MANIFEST.read_text(encoding="utf-8"))["edited_files"]:
        live = file_sha256(prov.V2_DEST / item["path"])
        edited[item["path"]] = {
            "written_sha256": item["written_sha256"],
            "live_sha256": live,
            "match": live == item["written_sha256"],
        }
    on_disk = sum(1 for p in prov.V2_DEST.rglob("*") if p.is_file())
    v2_manifest_sha = file_sha256(B07R_MANIFEST)
    observed["reviewfix_candidate_v2"] = {
        "root": str(prov.V2_DEST),
        "manifest_sha256": v2_manifest_sha,
        "manifest_expected": V2_MANIFEST_EXPECTED,
        "manifest_match": v2_manifest_sha == V2_MANIFEST_EXPECTED,
        "tree": v2_tree,
        "tree_expected_files": V2_FILES_EXPECTED,
        "tree_expected_sha256": V2_TREE_EXPECTED,
        "tree_match": (v2_tree["files"] == V2_FILES_EXPECTED
                       and v2_tree["sha256"] == V2_TREE_EXPECTED),
        "files_on_disk": on_disk,
        "files_on_disk_expected": V2_ON_DISK_EXPECTED,
        "files_on_disk_match": on_disk == V2_ON_DISK_EXPECTED,
        "edited_files": edited,
    }

    checks = {
        "b06_cross_check": b06_match,
        "frozen_b07_digest": b07_match,
        "frozen_b07_manifest": observed["frozen_b07_candidate"]["manifest_match"],
        "baseline_digest_stable": observed["frozen_b07_candidate"]["baseline_observed_equal"],
        "frozen_inputs_unchanged_since_step1": frozen_equal,
        "v2_manifest": observed["reviewfix_candidate_v2"]["manifest_match"],
        "v2_tree": observed["reviewfix_candidate_v2"]["tree_match"],
        "v2_on_disk_count": observed["reviewfix_candidate_v2"]["files_on_disk_match"],
        "v2_edited_files": all(v["match"] for v in edited.values()),
    }
    observed["checks"] = checks
    observed["verdict"] = "unchanged" if all(checks.values()) else "CHANGED"
    OUT.write_text(json.dumps(observed, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": observed["verdict"], "checks": checks}, indent=2))
    print(f"RECHECK WRITTEN: {OUT}")
    return 0 if all(checks.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
