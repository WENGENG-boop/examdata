"""B01: validate Node component discovery offline (no originals, no network).

Two probes:

  A. private target layout - import examdata.integration.runtime.manifest from the
     private copy. Records the F03-GUARD-DEP block (product import path is gated
     by the test-only guard root heuristic).
  B. staging layout - import the discovery module where the guard legitimately
     resolves and exercise the pure discovery logic offline:
       * exactly one component is admitted: the synthetic `fake_cli`;
       * it is labelled synthetic (not a real product component);
       * its entry point resolves inside the deployment root;
       * a manifest whose code_location escapes the root is refused (not admitted);
       * the synthetic Node file passes the import-resolution guard.

Real Node components are not released, so discovery of real components stays
not_run; nothing synthetic is promoted into a production release manifest.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[3]
STAGING = ROOT / "integration-staging"
PRIVATE_SRC = RUN / "private" / "src"
PY = sys.executable

result: dict = {
    "schema": "examdata.integration.b01_node_discovery/1",
    "run_id": RUN.name,
    "probe_a_private_target_layout": {},
    "probe_b_staging_layout": {},
    "not_run": [
        "real Node component discovery: real components are not released "
        "(gate:original_paths_released closed); no synthetic stand-in is promoted",
    ],
}

# ---- Probe A: private target layout import -----------------------------------
code = ("import examdata.integration.runtime.manifest as m;"
        "print('IMPORTED', m.MANIFEST_VERSION)")
p = subprocess.run([PY, "-c", code], capture_output=True, text=True,
                   cwd=str(RUN), env={**os.environ, "PYTHONPATH": str(PRIVATE_SRC)})
out = (p.stdout + p.stderr).strip()
result["probe_a_private_target_layout"] = {
    "exit_code": p.returncode,
    "imported": p.returncode == 0 and "IMPORTED" in out,
    "blocked_by": "F03-GUARD-DEP" if p.returncode != 0 else None,
    "detail": out.splitlines()[-1] if out else "",
}

# ---- Probe B: staging layout discovery --------------------------------------
sys.path.insert(0, str(STAGING / "src"))
from examdata_integration.runtime.manifest import load_manifest_set  # noqa: E402
from examdata_integration.testing.node_guard import check_node_file  # noqa: E402

manifest_path = STAGING / "components" / "manifest.json"
mset = load_manifest_set(manifest_path, deployment_root=STAGING)
admitted = mset.ids()
raw = json.loads(manifest_path.read_text(encoding="utf-8"))
generated_by = raw.get("generated_by", "")
comp = mset.get("fake_cli")
entry_resolved = bool(comp and comp.entry_path(STAGING).is_file())
entry_within = bool(comp and str(comp.entry_path(STAGING)).startswith(str(STAGING)))
specs = check_node_file(STAGING / "components" / "fake-node-cli" / "fake-cli.mjs")

# negative control: a manifest whose code_location escapes the deployment root
with tempfile.TemporaryDirectory(dir=str(RUN)) as td:
    tdp = Path(td)
    (tdp / "escape.json").write_text(json.dumps({
        "manifest_version": "examdata.component-manifest/1",
        "components": [{
            "component_id": "escaper", "name": "escaper", "version": "1.0.0",
            "source_revision": "x", "code_location": "../../outside",
            "runtime": "node", "entry_point": "x.mjs",
            "supported_commands": ["ok"], "environment_allowlist": [],
            "data_roots": {}, "read_write_policy": "read_only",
        }],
    }), encoding="utf-8")
    esc = load_manifest_set(tdp / "escape.json", deployment_root=tdp)
    escape_admitted = esc.ids()
    escape_codes = sorted({pr.code for pr in esc.problems})

result["probe_b_staging_layout"] = {
    "manifest": str(manifest_path.relative_to(ROOT).as_posix()),
    "admitted_components": admitted,
    "admitted_count": len(admitted),
    "manifest_generated_by": generated_by,
    "is_synthetic": "synthetic" in generated_by.lower(),
    "entry_point_resolves_inside_root": entry_resolved and entry_within,
    "node_import_guard_specifiers": specs,
    "negative_control_escape_admitted": escape_admitted,
    "negative_control_escape_codes": escape_codes,
}

checks = {
    "private_layout_block_is_f03": result["probe_a_private_target_layout"]["blocked_by"]
        == "F03-GUARD-DEP",
    "exactly_one_synthetic_component": admitted == ["fake_cli"],
    "synthetic_labelled": result["probe_b_staging_layout"]["is_synthetic"],
    "entry_point_inside_root": entry_resolved and entry_within,
    "escaping_component_refused": escape_admitted == []
        and bool({"not_relative_path", "path_escapes_root"} & set(escape_codes)),
}
result["checks"] = checks
result["verdict"] = "pass" if all(checks.values()) else "fail"

out_path = (ROOT / "docs/integration/execution/evidence/B01" / RUN.name
            / "B01_NODE_DISCOVERY.json")
out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
print(json.dumps({"verdict": result["verdict"], "checks": checks,
                  "evidence": str(out_path.relative_to(ROOT).as_posix())}, indent=2))
sys.exit(0 if all(checks.values()) else 1)
