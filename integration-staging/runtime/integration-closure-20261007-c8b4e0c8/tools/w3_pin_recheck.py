"""W3 supplementary pin re-check (read-only, run in W3 only).

Re-checks the operations probe-pin bullets of the W3 brief against the
closure candidate, without running the frozen ``b07_route_probe.py``:
its copy in this run keeps the b07-reviewfix layout and cannot resolve its
baseline (``<run>/b06-rehearsal-2026-10-07`` does not exist here), and the
frozen ``b07_smoke_import.py`` hardcodes ``candidates/b07-operations-v2``,
which this run does not contain. The full frozen probe is re-checked in W7;
this script covers only the pins W3 could plausibly disturb:

* exactly 7 job briefs keyed by ``(public_id, freshness)``, with the six exact
  ``(public_id, freshness) -> stage`` mappings pinned by the W3 brief
  (Addendum A1), the seventh ``("job:ielts:synthetic-run-ok", "current")``
  brief present, and the 5 current / 2 superseded split;
* public ``checkpoints["conflicts"] == []``;
* a missing operations root reports ``root_kind == "missing"`` with problems
  exactly ``[{"code": "operations_root_missing"}]`` in the public projection;
* no public name in ``operations/jobs.py`` or ``operations/published.py``
  starts with resume/write/start/cancel/enqueue/delete/remove;
* building and serving the views writes nothing into the candidate tree
  (whole-tree digest before/after).

Exit code 0 = every check held; 1 = at least one check failed. The script
writes nothing except its stdout document.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parent.parent
CANDIDATE = RUN / "candidates" / "closure-v1"
OPS_ROOT = CANDIDATE / "fixtures" / "synthetic" / "operations" / "operations-root"

WRITE_SURFACE_PREFIXES = ("resume", "write", "start", "cancel", "enqueue",
                          "delete", "remove")

PINNED_MAPPINGS = {
    ("job:cie:cie-batch:9191", "current"): "stopped_requires_resume",
    ("job:cie:cie-batch:8888", "current"): "running",
    ("job:cie:cie-batch:8888", "superseded"): "stopped",
    ("job:ielts:synthetic-run-ok", "superseded"): "partial",
    ("job:ielts:synthetic-run-partial", "current"): "partial",
    ("job:unknown:unknown:unsupported:checkpoint.json", "current"): "unknown",
}
SEVENTH_BRIEF = ("job:ielts:synthetic-run-ok", "current")

SKIP_PARTS = {"__pycache__", ".pytest_cache"}


def _digest_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if SKIP_PARTS & set(path.parts):
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> int:
    os.environ["EXAMDATA_INTEGRATION_ROOT"] = str(CANDIDATE)
    os.environ["EXAMDATA_OPERATIONS_ROOT"] = str(OPS_ROOT)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(CANDIDATE / "src"))

    before = _digest_tree(CANDIDATE)

    import examdata.integration.api.links as links
    from examdata.integration.api.app import create_app
    from examdata.integration.api.dataset import default_dataset, operations_view
    from examdata.integration.operations import jobs as jobs_mod
    from examdata.integration.operations import published as published_mod
    from fastapi.testclient import TestClient

    dataset = default_dataset()
    client = TestClient(create_app(dataset=dataset))
    response = client.get(links.spec_for("coverage.get").full_path)
    operations = response.json()["data"]["operations"]
    briefs = operations["jobs"]

    mapping = {(row["public_id"], row["freshness"]): row["stage"]
               for row in briefs}
    checks: dict[str, bool] = {}
    checks["brief_count_is_seven"] = len(briefs) == 7
    checks["six_pinned_mappings"] = all(mapping.get(key) == stage
                                        for key, stage in PINNED_MAPPINGS.items())
    checks["seventh_brief_present"] = SEVENTH_BRIEF in mapping
    checks["freshness_split_5_current_2_superseded"] = (
        sum(1 for row in briefs if row["freshness"] == "current") == 5
        and sum(1 for row in briefs if row["freshness"] == "superseded") == 2)
    checks["public_conflicts_empty"] = operations["checkpoints"]["conflicts"] == []

    missing_root = RUN / "tmp" / "w3-pin-recheck-missing-root"
    checks["missing_root_absent"] = not missing_root.exists()
    view = operations_view(entries=[], root=missing_root)
    checks["missing_root_kind"] = view is not None and view.root_kind == "missing"
    checks["missing_root_problems"] = (
        [problem.get("code") for problem in view.problems]
        == ["operations_root_missing"])
    public_missing = view.to_public(secrets=())
    checks["missing_root_public_problems"] = (
        public_missing["root"]["problems"] == [{"code": "operations_root_missing"}])

    public_names = set()
    for module in (jobs_mod, published_mod):
        public_names.update(name for name in dir(module)
                            if not name.startswith("_"))
    bad_names = sorted(name for name in public_names
                       if name.lower().startswith(WRITE_SURFACE_PREFIXES))
    checks["no_write_surface_public_names"] = not bad_names

    after = _digest_tree(CANDIDATE)
    checks["candidate_tree_unchanged"] = before == after

    document = {
        "candidate": str(CANDIDATE),
        "operations_root": str(OPS_ROOT),
        "checks": checks,
        "briefs": [{"public_id": row["public_id"], "freshness": row["freshness"],
                    "stage": row["stage"]} for row in briefs],
        "bad_public_names": bad_names,
        "candidate_digest_before": before,
        "candidate_digest_after": after,
        "ok": all(checks.values()),
    }
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if document["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
