#!/usr/bin/env python
"""W5 rehearsal driver: run the whole synthetic migration/restore scenario set.

``run``
    Executes scenarios ``01..13`` in order.  Every scenario is a sequence of
    *real* tool invocations (subprocess, real CLI, real exit codes).  Per
    scenario this writes ``<run>/evidence/w5/runs/<stamp>/<NN-name>.json``
    (checks, exits, projections) and ``.../logs/<NN-name>.log`` (full stdout /
    stderr of every step); every single command is also appended to
    ``<run>/evidence/w5/COMMANDS.md`` (append-only - existing sections are
    never overwritten).

``replay``
    Re-runs the same scenario code in a fresh namespace (``--work-subdir``,
    default ``replay-<stamp>``) over the same read-only source stores, then
    compares every step exit code and every recorded projection with the first
    run.  Any divergence is a finding (exit 8) and is written to
    ``comparison.json``.

The destination roots, manifests, race work dirs and probe work dirs live
under the rehearsal base (``<run>/migration`` for the primary run, a fresh
``<run>/migration/replay-<stamp>`` for a replay); the synthetic source stores
are read-only inputs shared by both runs.

Exit codes: ``0`` ok | ``1`` error | ``8`` findings.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w5_common as w5  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
MIGRATION_ROOT = w5.MIGRATION_ROOT
EVIDENCE_ROOT = w5.EVIDENCE_ROOT
COMMANDS_MD = EVIDENCE_ROOT / "COMMANDS.md"
PYTHON = sys.executable

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_FINDINGS = 8

DEFAULT_TIMEOUT = 1800.0
MAX_SNIPPET = 1600


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _extract_json(text: str) -> Any:
    idx = text.find("{")
    if idx < 0:
        return None
    try:
        return json.JSONDecoder().raw_decode(text, idx)[0]
    except ValueError:
        return None


def _rel_run(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(w5.RUN_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _reset_dir(path: Path) -> None:
    path = w5.guard_within(path, MIGRATION_ROOT)
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def _capped_json(payload: Any, limit: int = 400) -> Any:
    """Projection values must stay comparable; cap long lists deterministically."""
    if isinstance(payload, list):
        return [_capped_json(v, limit) for v in payload[:limit]] + (
            [f"...({len(payload)} total)"] if len(payload) > limit else [])
    if isinstance(payload, dict):
        return {k: _capped_json(v, limit) for k, v in sorted(payload.items())}
    return payload


class ScenarioFailed(Exception):
    """A precondition of a scenario is missing; the scenario cannot run."""


# --------------------------------------------------------------------------- #
# context
# --------------------------------------------------------------------------- #
class Ctx:
    def __init__(self, base: Path, stamp: str, label: str) -> None:
        self.base = base
        self.stamp = stamp
        self.label = label
        self.out_dir = EVIDENCE_ROOT / "runs" / stamp
        self.scenario_name = ""
        self.scenario_dir = self.out_dir
        self.checks: list[dict[str, Any]] = []
        self.commands: list[dict[str, Any]] = []
        self.log_parts: list[str] = []

    # -- paths --------------------------------------------------------------
    def _root_for(self, name: str) -> Path:
        """Source stores are read-only inputs shared by every rehearsal run."""
        if name.startswith("source-store"):
            return MIGRATION_ROOT
        return self.base

    def p(self, name: str) -> str:
        """A path relative to the rehearsal base, rendered relative to migration/."""
        target = (self._root_for(name) / name).resolve()
        w5.guard_within(target, MIGRATION_ROOT)
        return target.relative_to(MIGRATION_ROOT.resolve()).as_posix()

    def abs(self, name: str) -> Path:
        target = (self._root_for(name) / name).resolve()
        w5.guard_within(target, MIGRATION_ROOT)
        return target

    def art(self, fname: str) -> Path:
        return self.scenario_dir / fname

    # -- lifecycle -----------------------------------------------------------
    def begin(self, name: str) -> None:
        self.scenario_name = name
        self.scenario_dir = self.out_dir / name
        self.scenario_dir.mkdir(parents=True, exist_ok=True)
        self.checks = []
        self.commands = []
        self.log_parts = []

    def reset(self, *names: str) -> None:
        for name in names:
            _reset_dir(self.abs(name))

    def require(self, name: str) -> Path:
        path = self.abs(name)
        if not path.exists():
            raise ScenarioFailed(f"required artifact missing: {name}")
        return path

    # -- checks / commands ----------------------------------------------------
    def check(self, cid: str, ok: bool, detail: str) -> bool:
        self.checks.append({"id": cid, "ok": bool(ok), "detail": detail})
        return bool(ok)

    def run(self, step: str, tool: str, args: list[str], *,
            artifacts: list[Path] | None = None) -> dict[str, Any]:
        argv = [PYTHON, "-B", str(TOOLS_DIR / tool), *args]
        display = "python -B tools/" + tool + " " + shlex.join(args)
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        t0 = time.time()
        rc: int | None = None
        text = err = ""
        try:
            proc = subprocess.run(argv, cwd=str(MIGRATION_ROOT), env=env,
                                  capture_output=True, timeout=DEFAULT_TIMEOUT)
            rc = proc.returncode
            text = proc.stdout.decode("utf-8", "replace")
            err = proc.stderr.decode("utf-8", "replace")
        except subprocess.TimeoutExpired as exc:
            text = (exc.stdout or b"").decode("utf-8", "replace")
            err = (exc.stderr or b"").decode("utf-8", "replace") + "\n[timeout]"
        entry = {
            "step": step, "cmd": display, "exit": rc, "seconds": round(time.time() - t0, 1),
            "json": _extract_json(text),
            "artifacts": [_rel_run(p) for p in (artifacts or [])],
        }
        self.commands.append(entry)
        self.log_parts.append(
            f"===== [{self.scenario_name}] {step}: {display}\n"
            f"cwd: {MIGRATION_ROOT}\nexit: {rc}\n"
            f"--- stdout ---\n{text}--- stderr ---\n{err}\n")
        self._append_commands(step, display, rc, entry["artifacts"], text, err)
        return entry

    def _append_commands(self, step: str, display: str, rc: int | None,
                         artifacts: list[str], text: str, err: str) -> None:
        snippet = text if len(text) <= MAX_SNIPPET else (
            text[:MAX_SNIPPET] +
            f"\n... [truncated; full output: evidence/w5/runs/{self.stamp}/logs/"
            f"{self.scenario_name}.log]")
        parts = [
            f"## {self.stamp} / {self.scenario_name} / {step}",
            f"- time: {w5.now_utc()}",
            f"- cwd: `{MIGRATION_ROOT}`",
            f"- cmd: `{display}`",
            f"- exit: {rc}",
        ]
        if artifacts:
            parts.append("- artifacts: " + ", ".join(f"`{a}`" for a in artifacts))
        parts.append("- stdout:")
        parts.append("```text")
        parts.append(snippet.rstrip("\n"))
        parts.append("```")
        if err.strip():
            parts.append("- stderr:")
            parts.append("```text")
            parts.append(err.strip("\n"))
            parts.append("```")
        with COMMANDS_MD.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(parts) + "\n\n")

    # -- results ---------------------------------------------------------------
    def finish(self, projection: dict[str, Any]) -> dict[str, Any]:
        ok = all(c["ok"] for c in self.checks)
        result = {
            "schema": "w5.rehearsal-scenario/1",
            "stamp": self.stamp,
            "label": self.label,
            "name": self.scenario_name,
            "ok": ok,
            "exits": {c["step"]: c["exit"] for c in self.commands},
            "checks": self.checks,
            "projection": _capped_json(projection),
            "commands": [{k: c[k] for k in ("step", "cmd", "exit", "seconds", "artifacts")}
                         for c in self.commands],
        }
        w5.write_json(self.out_dir / f"{self.scenario_name}.json", result)
        logs = self.out_dir / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / f"{self.scenario_name}.log").write_text(
            "\n".join(self.log_parts), encoding="utf-8", newline="\n")
        return result


def run_scenario(ctx: Ctx, name: str, func: Callable[[Ctx], dict[str, Any]],
                 *, keep_going_on_error: bool) -> dict[str, Any]:
    ctx.begin(name)
    error = None
    projection: dict[str, Any] = {}
    try:
        projection = func(ctx) or {}
    except Exception:  # noqa: BLE001 - recorded as the scenario's finding
        error = traceback.format_exc()
        if not keep_going_on_error:
            raise
    result = ctx.finish(projection)
    if error:
        result["ok"] = False
        result["error"] = error
        w5.write_json(ctx.out_dir / f"{name}.json", result)
    return result


# --------------------------------------------------------------------------- #
# scenarios
# --------------------------------------------------------------------------- #
def sc_clean_migrate(ctx: Ctx) -> dict[str, Any]:
    ctx.reset("dest-store", "manifests/run-clean")
    r = ctx.run("run", "migrate.py",
                ["run", "--source", ctx.p("source-store"), "--dest", ctx.p("dest-store"),
                 "--manifest-dir", ctx.p("manifests/run-clean")])
    j = r["json"] or {}
    ctx.check("run_exit_0", r["exit"] == 0, f"exit {r['exit']}")
    ctx.check("run_status_ok", j.get("status") == "ok", f"status {j.get('status')!r}")
    rev = j.get("dataset_revision")
    digest_local = {k: v["sha256"] for k, v in w5.both_digests(ctx.abs("dest-store")).items()}
    ctx.check("recorded_digest_matches_recomputed",
              j.get("dest_digests") == digest_local,
              f"recorded {j.get('dest_digests')} recomputed {digest_local}")
    v = ctx.run("verify-destination", "verify.py",
                ["destination", "--dest", ctx.p("dest-store"), "--source", ctx.p("source-store"),
                 "--manifest-dir", ctx.p("manifests/run-clean"),
                 "--out", str(ctx.art("verify-destination.json"))],
                artifacts=[ctx.art("verify-destination.json")])
    vj = v["json"] or {}
    ctx.check("verify_destination_ok", v["exit"] == 0 and vj.get("ok") is True,
              f"exit {v['exit']} failures {vj.get('failures')}")
    s = ctx.run("store-check", "verify.py",
                ["store-check", "--store", ctx.p("dest-store"),
                 "--expect-revision", str(rev),
                 "--out-evidence", str(ctx.art("query-evidence.json"))],
                artifacts=[ctx.art("query-evidence.json")])
    sj = s["json"] or {}
    ctx.check("store_check_ok", s["exit"] == 0 and sj.get("ok") is True,
              f"exit {s['exit']} revision {sj.get('revision')}")
    counts = (j.get("counts") or {})
    ctx.check("counts_total_21", counts.get("total") == 21, f"counts {counts}")
    return {"revision": rev, "counts": counts, "dest_digests": j.get("dest_digests"),
            "files": j.get("summary", {}).get("rows")}


def sc_repeatability(ctx: Ctx) -> dict[str, Any]:
    ctx.reset("dest-store-2", "manifests/run-dest2")
    r = ctx.run("run", "migrate.py",
                ["run", "--source", ctx.p("source-store"), "--dest", ctx.p("dest-store-2"),
                 "--manifest-dir", ctx.p("manifests/run-dest2")])
    j = r["json"] or {}
    ctx.check("run_exit_0", r["exit"] == 0, f"exit {r['exit']}")
    t = ctx.run("tree-diff", "verify.py",
                ["tree-diff", "--a", ctx.p("dest-store"), "--b", ctx.p("dest-store-2")])
    tj = t["json"] or {}
    ctx.check("trees_identical", t["exit"] == 0 and tj.get("equal") is True,
              f"exit {t['exit']} equal {tj.get('equal')}")
    return {"revision": j.get("dataset_revision"),
            "digest_a": tj.get("digests", {}).get("a", {}).get("historical"),
            "equal": tj.get("equal")}


def sc_interruption_resume(ctx: Ctx) -> dict[str, Any]:
    ctx.reset("dest-store-retry", "manifests/run-retry")
    r1 = ctx.run("run-partial", "migrate.py",
                 ["run", "--source", ctx.p("source-store"), "--dest", ctx.p("dest-store-retry"),
                  "--manifest-dir", ctx.p("manifests/run-retry"), "--fail-after-copies", "3"])
    j1 = r1["json"] or {}
    ctx.check("first_run_exit_5", r1["exit"] == 5, f"exit {r1['exit']}")
    ctx.check("first_run_copied_3", j1.get("copied") == 3, f"copied {j1.get('copied')}")
    ctx.check("first_run_not_published", j1.get("published") is False,
              f"published {j1.get('published')!r}")
    p1 = ctx.run("catalog-absent", "verify.py",
                 ["path-state", "--path", ctx.p("dest-store-retry") + "/catalog",
                  "--expect", "not-exists"])
    ctx.check("no_pointer_after_interruption", p1["exit"] == 0, f"exit {p1['exit']}")
    r2 = ctx.run("run-resume", "migrate.py",
                 ["run", "--source", ctx.p("source-store"), "--dest", ctx.p("dest-store-retry"),
                  "--manifest-dir", ctx.p("manifests/run-retry")])
    j2 = r2["json"] or {}
    summ = j2.get("summary") or {}
    ctx.check("resume_exit_0", r2["exit"] == 0, f"exit {r2['exit']}")
    ctx.check("resume_copied_12_idempotent_3",
              summ.get("copied") == 12 and summ.get("idempotent_skip") == 3,
              f"copied {summ.get('copied')} idempotent_skip {summ.get('idempotent_skip')}")
    t = ctx.run("tree-diff", "verify.py",
                ["tree-diff", "--a", ctx.p("dest-store"), "--b", ctx.p("dest-store-retry")])
    tj = t["json"] or {}
    ctx.check("resumed_tree_equals_clean", t["exit"] == 0 and tj.get("equal") is True,
              f"exit {t['exit']} equal {tj.get('equal')}")
    return {"exit_partial": r1["exit"], "copied_partial": j1.get("copied"),
            "exit_resume": r2["exit"], "resume_summary": summ,
            "tree_equal": tj.get("equal"), "revision": j2.get("dataset_revision")}


def sc_interrupt_before_swap(ctx: Ctx) -> dict[str, Any]:
    ctx.reset("dest-store-noswap", "manifests/run-noswap")
    r1 = ctx.run("run-build-only", "migrate.py",
                 ["run", "--source", ctx.p("source-store"), "--dest", ctx.p("dest-store-noswap"),
                  "--manifest-dir", ctx.p("manifests/run-noswap"),
                  "--fail-before-pointer-swap"])
    j1 = r1["json"] or {}
    ctx.check("first_run_exit_5", r1["exit"] == 5, f"exit {r1['exit']}")
    ctx.check("first_run_copied_all", j1.get("copied") == 15, f"copied {j1.get('copied')}")
    p1 = ctx.run("catalog-absent", "verify.py",
                 ["path-state", "--path", ctx.p("dest-store-noswap") + "/catalog",
                  "--expect", "not-exists"])
    ctx.check("no_revision_visible_after_interruption", p1["exit"] == 0, f"exit {p1['exit']}")
    pub = w5.read_json(ctx.abs("manifests/run-noswap/publish.json"))
    ctx.check("publish_report_injected",
              pub.get("status") == "injected_fault" and pub.get("published") is False
              and pub.get("build_ok") is True,
              f"status {pub.get('status')!r} published {pub.get('published')!r} "
              f"build_ok {pub.get('build_ok')!r}")
    r2 = ctx.run("run-resume", "migrate.py",
                 ["run", "--source", ctx.p("source-store"), "--dest", ctx.p("dest-store-noswap"),
                  "--manifest-dir", ctx.p("manifests/run-noswap")])
    j2 = r2["json"] or {}
    summ = j2.get("summary") or {}
    ctx.check("resume_exit_0", r2["exit"] == 0, f"exit {r2['exit']}")
    ctx.check("resume_copied_0_idempotent_15",
              summ.get("copied") == 0 and summ.get("idempotent_skip") == 15,
              f"copied {summ.get('copied')} idempotent_skip {summ.get('idempotent_skip')}")
    t = ctx.run("tree-diff", "verify.py",
                ["tree-diff", "--a", ctx.p("dest-store"), "--b", ctx.p("dest-store-noswap")])
    tj = t["json"] or {}
    ctx.check("resumed_tree_equals_clean", t["exit"] == 0 and tj.get("equal") is True,
              f"exit {t['exit']} equal {tj.get('equal')}")
    return {"exit_build_only": r1["exit"], "copied_build_only": j1.get("copied"),
            "publish_status": pub.get("status"), "exit_resume": r2["exit"],
            "resume_summary": summ, "tree_equal": tj.get("equal"),
            "revision": j2.get("dataset_revision")}


def sc_failed_publication(ctx: Ctx) -> dict[str, Any]:
    ctx.reset("dest-store-defects", "manifests/run-defects")
    r = ctx.run("run", "migrate.py",
                ["run", "--source", ctx.p("source-store-defects"),
                 "--dest", ctx.p("dest-store-defects"),
                 "--manifest-dir", ctx.p("manifests/run-defects")])
    j = r["json"] or {}
    ctx.check("run_exit_4", r["exit"] == 4, f"exit {r['exit']}")
    ctx.check("run_not_ok", j.get("status") != "ok", f"status {j.get('status')!r}")
    p = ctx.run("catalog-absent", "verify.py",
                ["path-state", "--path", ctx.p("dest-store-defects") + "/catalog",
                 "--expect", "not-exists"])
    ctx.check("pointer_unchanged_absent", p["exit"] == 0, f"exit {p['exit']}")
    pub = w5.read_json(ctx.abs("manifests/run-defects/publish.json"))
    codes = sorted({pr.get("code") for pr in pub.get("problems", [])})
    ctx.check("publish_report_refused",
              pub.get("published") is False and pub.get("build_ok") is False,
              f"published {pub.get('published')!r} build_ok {pub.get('build_ok')!r}")
    ctx.check("problem_codes_exact", codes == ["identity_unresolved", "unresolved_identity"],
              f"codes {codes}")
    return {"exit": r["exit"], "status": j.get("status"),
            "publish_status": pub.get("status"), "problem_codes": codes}


def sc_collision_refusal(ctx: Ctx) -> dict[str, Any]:
    ctx.reset("dest-store-conflict", "manifests/run-conflict", "manifests/conflict-copy")
    r = ctx.run("run", "migrate.py",
                ["run", "--source", ctx.p("source-store"),
                 "--dest", ctx.p("dest-store-conflict"),
                 "--manifest-dir", ctx.p("manifests/run-conflict")])
    ctx.check("seed_run_exit_0", r["exit"] == 0, f"exit {r['exit']}")
    cache = ctx.p("dest-store-conflict") + "/payload/caches/cie/parse-cache.json"
    raw = ctx.p("dest-store-conflict") + "/payload/raw/cie/index-cie-0580.json"
    poke1 = ctx.run("poke-rebuildable", "restore.py",
                    ["poke", "--file", cache, "--write-text", '{"synthetic":"tampered"}'])
    pj1 = poke1["json"] or {}
    ctx.check("poke1_ok", poke1["exit"] == 0 and pj1.get("ok") is True,
              f"exit {poke1['exit']}")
    c1 = ctx.run("copy-regenerate", "migrate.py",
                 ["copy", "--source", ctx.p("source-store"),
                  "--dest", ctx.p("dest-store-conflict"),
                  "--manifest-out", ctx.p("manifests/conflict-copy/copy_manifest.json")])
    cj1 = c1["json"] or {}
    s1 = cj1.get("summary") or {}
    ctx.check("rebuildable_regenerated",
              c1["exit"] == 0 and s1.get("regenerated_over_rebuildable") == 1
              and s1.get("collision_refused") == 0,
              f"exit {c1['exit']} summary {s1}")
    e1 = ctx.run("bytes-restored", "verify.py",
                 ["path-state", "--path", cache,
                  "--equal-file", ctx.p("source-store") + "/caches/cie/parse-cache.json"])
    ctx.check("rebuildable_bytes_restored", e1["exit"] == 0, f"exit {e1['exit']}")
    poke2 = ctx.run("poke-authority", "restore.py",
                    ["poke", "--file", raw, "--write-text", '{"synthetic":"tampered-authority"}'])
    pj2 = poke2["json"] or {}
    ctx.check("poke2_ok", poke2["exit"] == 0 and pj2.get("ok") is True,
              f"exit {poke2['exit']}")
    c2 = ctx.run("copy-refuse", "migrate.py",
                 ["copy", "--source", ctx.p("source-store"),
                  "--dest", ctx.p("dest-store-conflict"),
                  "--manifest-out", ctx.p("manifests/conflict-copy/copy_manifest2.json")])
    cj2 = c2["json"] or {}
    s2 = cj2.get("summary") or {}
    ctx.check("authority_collision_refused",
              c2["exit"] == 3 and s2.get("collision_refused") == 1
              and (cj2.get("collision") or {}).get("path") == "raw/cie/index-cie-0580.json",
              f"exit {c2['exit']} summary {s2} collision {cj2.get('collision')}")
    e2 = ctx.run("authority-bytes-preserved", "verify.py",
                 ["path-state", "--path", raw, "--sha256", str(pj2.get("after_sha256"))])
    ctx.check("authority_bytes_unchanged", e2["exit"] == 0, f"exit {e2['exit']}")
    return {"copy_regenerate_exit": c1["exit"], "regenerated": s1.get(
                "regenerated_over_rebuildable"),
            "copy_refuse_exit": c2["exit"],
            "collision_path": (cj2.get("collision") or {}).get("path"),
            "authority_sha_preserved": pj2.get("after_sha256")}


def sc_pointer_rollback(ctx: Ctx) -> dict[str, Any]:
    ctx.reset("dest-store-rollback", "manifests/run-rollback")
    r1 = ctx.run("run", "migrate.py",
                 ["run", "--source", ctx.p("source-store"),
                  "--dest", ctx.p("dest-store-rollback"),
                  "--manifest-dir", ctx.p("manifests/run-rollback")])
    j1 = r1["json"] or {}
    rev_a = j1.get("dataset_revision")
    ctx.check("run_exit_0", r1["exit"] == 0, f"exit {r1['exit']}")
    r2 = ctx.run("publish-mvp", "migrate.py",
                 ["publish", "--source", ctx.p("source-store"),
                  "--dest", ctx.p("dest-store-rollback"),
                  "--select-scope", "mvp", "--expect-current", str(rev_a)])
    j2 = r2["json"] or {}
    pointer = j2.get("pointer") or {}
    rev_b = j2.get("candidate_revision")
    ctx.check("mvp_published_cas", r2["exit"] == 0 and j2.get("published") is True,
              f"exit {r2['exit']} published {j2.get('published')!r}")
    ctx.check("pointer_previous_is_clean_revision", pointer.get("previous") == rev_a,
              f"previous {pointer.get('previous')} vs {rev_a}")
    r3 = ctx.run("rollback", "restore.py",
                 ["pointer-rollback", "--store", ctx.p("dest-store-rollback"),
                  "--out-evidence", str(ctx.art("rollback-query-evidence.json"))],
                 artifacts=[ctx.art("rollback-query-evidence.json")])
    j3 = r3["json"] or {}
    ctx.check("rollback_ok", r3["exit"] == 0 and j3.get("ok") is True,
              f"exit {r3['exit']} checks {[c['id'] for c in j3.get('checks', []) if not c['ok']]}")
    ctx.check("rollback_after_revision",
              j3.get("after", {}).get("revision") == rev_a
              and j3.get("after", {}).get("previous") == rev_b,
              f"after {j3.get('after')}")
    r4 = ctx.run("store-check", "verify.py",
                 ["store-check", "--store", ctx.p("dest-store-rollback"),
                  "--expect-revision", str(rev_a)])
    ctx.check("rolled_back_store_consistent", r4["exit"] == 0, f"exit {r4['exit']}")
    return {"revision_a": rev_a, "revision_b": rev_b,
            "rollback_ok": j3.get("ok"), "after": j3.get("after")}


def sc_content_restore(ctx: Ctx) -> dict[str, Any]:
    ctx.reset("restore-store")
    ctx.require("manifests/run-clean/copy_manifest.json")
    ctx.require("manifests/run-clean/query_evidence.json")
    r = ctx.run("content-restore", "restore.py",
                ["content-restore", "--source", ctx.p("source-store"),
                 "--manifest", ctx.p("manifests/run-clean/copy_manifest.json"),
                 "--dest", ctx.p("restore-store"),
                 "--reference", ctx.p("dest-store"),
                 "--out-evidence", str(ctx.art("restored-query-evidence.json"))],
                artifacts=[ctx.art("restored-query-evidence.json")])
    j = r["json"] or {}
    ctx.check("content_restore_ok", r["exit"] == 0 and j.get("ok") is True,
              f"exit {r['exit']} tree_equal {j.get('tree', {}).get('equal')} "
              f"evidence_equal {j.get('query_evidence_equal')}")
    ctx.check("restored_all_files", j.get("restored_files") == 15,
              f"restored_files {j.get('restored_files')}")
    v = ctx.run("verify-destination", "verify.py",
                ["destination", "--dest", ctx.p("restore-store"),
                 "--source", ctx.p("source-store"),
                 "--manifest-dir", ctx.p("manifests/run-clean")])
    vj = v["json"] or {}
    ctx.check("restored_destination_verified", v["exit"] == 0 and vj.get("ok") is True,
              f"exit {v['exit']} failures {vj.get('failures')}")
    e = ctx.run("evidence-diff", "verify.py",
                ["evidence-diff", "--a", ctx.p("manifests/run-clean/query_evidence.json"),
                 "--b", str(ctx.art("restored-query-evidence.json"))])
    ctx.check("restored_evidence_equals_original", e["exit"] == 0,
              f"exit {e['exit']} differing {(e['json'] or {}).get('differing_keys')}")
    return {"ok": j.get("ok"), "tree_equal": j.get("tree", {}).get("equal"),
            "evidence_equal": j.get("query_evidence_equal"),
            "restored_files": j.get("restored_files")}


def sc_sqlite_restore(ctx: Ctx) -> dict[str, Any]:
    ctx.reset("sqlite-export", "sqlite-restore", "sqlite-bare-copy")
    r = ctx.run("sqlite-restore", "restore.py",
                ["sqlite-restore", "--db", ctx.p("source-store") + "/index/aggregate-index.db",
                 "--export", ctx.p("sqlite-export"), "--restore", ctx.p("sqlite-restore")])
    j = r["json"] or {}
    ctx.check("sqlite_restore_ok", r["exit"] == 0 and j.get("ok") is True,
              f"exit {r['exit']} checks {[c['id'] for c in j.get('checks', []) if not c['ok']]}")
    b = ctx.run("bare-copy-probe", "restore.py",
                ["bare-copy-probe", "--work", ctx.p("sqlite-bare-copy")])
    bj = b["json"] or {}
    ctx.check("bare_copy_probe_ok", b["exit"] == 0 and bj.get("ok") is True,
              f"exit {b['exit']} bare {bj.get('bare_copy_while_open')} "
              f"backup {bj.get('backup_export')}")
    return {"sqlite_ok": j.get("ok"),
            "content_sha256": j.get("summaries", {}).get("source", {}).get("content_sha256"),
            "byte_equality": j.get("byte_equality"),
            "bare_copy_ok": bj.get("ok")}


def sc_tamper_reconcile(ctx: Ctx) -> dict[str, Any]:
    ctx.reset("dest-store-tamper")
    ctx.require("dest-store")
    t = ctx.run("tamper-probe", "restore.py",
                ["tamper-probe", "--store", ctx.p("dest-store"),
                 "--work", ctx.p("dest-store-tamper")])
    tj = t["json"] or {}
    ctx.check("tamper_probe_ok", t["exit"] == 0 and tj.get("ok") is True,
              f"exit {t['exit']} checks "
              f"{[c['id'] for c in tj.get('checks', []) if not c['ok']]}")
    ctx.check("v1_and_v2_detected",
              tj.get("v1_edit_body_keep_name", {}).get("detected") is True
              and tj.get("v2_self_consistent_swap", {}).get("detected") is True,
              "both tamper modes must be caught by the reader")
    r = ctx.run("reconcile-tampered", "reconcile.py",
                ["--source", ctx.p("source-store"), "--dest", ctx.p("dest-store-tamper"),
                 "--manifest", ctx.p("manifests/run-clean/copy_manifest.json"),
                 "--out", str(ctx.art("reconcile-tampered.json"))],
                artifacts=[ctx.art("reconcile-tampered.json")])
    rj = r["json"] or {}
    counts = rj.get("counts") or {}
    ctx.check("reconcile_tampered_exit_8", r["exit"] == 8, f"exit {r['exit']}")
    ctx.check("tampered_store_unreadable",
              rj.get("verdict") == "fail"
              and any(str(x).startswith("destination_unreadable") for x in rj.get("reasons", []))
              and counts.get("missing") == counts.get("expected"),
              f"verdict {rj.get('verdict')} reasons {rj.get('reasons')} counts {counts}")
    return {"tamper_ok": tj.get("ok"), "v1": tj.get("v1_edit_body_keep_name", {}).get("detected"),
            "v2": tj.get("v2_self_consistent_swap", {}).get("detected"),
            "reconcile_exit": r["exit"], "verdict": rj.get("verdict"), "counts": counts,
            "reasons": _capped_json(rj.get("reasons"))}


def sc_concurrent_race(ctx: Ctx) -> dict[str, Any]:
    ctx.reset("dest-store-race", "dest-store-race--race")
    r = ctx.run("race", "publish_concurrent.py",
                ["race", "--source", ctx.p("source-store"),
                 "--dest", ctx.p("dest-store-race"),
                 "--out", str(ctx.art("race.json"))],
                artifacts=[ctx.art("race.json")])
    j = r["json"] or {}
    findings = j.get("findings") or []
    counts = j.get("counts") or {}
    readers = j.get("readers") or {}
    late = j.get("late_writer") or {}
    expected_exit = 8 if findings else 0
    ctx.check("exit_matches_findings_rule", r["exit"] == expected_exit,
              f"exit {r['exit']} findings {len(findings)}")
    ctx.check("at_least_one_writer_won", counts.get("success", 0) >= 1, f"counts {counts}")
    ctx.check("readers_never_failed", readers.get("failures") == 0,
              f"failures {readers.get('failures')}")
    ctx.check("late_writer_stale", late.get("status") == "stale",
              f"status {late.get('status')!r}")
    ctx.check("late_writer_pointer_untouched", late.get("pointer_unchanged") is True,
              f"pointer_unchanged {late.get('pointer_unchanged')!r}")
    ctx.check("final_store_readable", (j.get("final") or {}).get("revision") is not None,
              f"final revision {(j.get('final') or {}).get('revision')}")
    return {"counts": counts, "readers_failures": readers.get("failures"),
            "late_writer_status": late.get("status"),
            "late_pointer_unchanged": late.get("pointer_unchanged"),
            "cas_honored_under_race": j.get("cas_honored_under_race"),
            "findings_count": len(findings),
            "temp_files_count": len((j.get("final") or {}).get("temp_files") or []),
            "final_revision": (j.get("final") or {}).get("revision")}


def sc_window_probe(ctx: Ctx) -> dict[str, Any]:
    ctx.reset("window-probe-work")
    r = ctx.run("window-probe", "publish_concurrent.py",
                ["window-probe", "--source", ctx.p("source-store"),
                 "--work", ctx.p("window-probe-work"),
                 "--out", str(ctx.art("window-probe.json"))],
                artifacts=[ctx.art("window-probe.json")])
    j = r["json"] or {}
    checks = {c["id"]: c["ok"] for c in (j.get("checks") or [])} if isinstance(
        j.get("checks"), list) else j.get("checks", {})
    ctx.check("window_probe_exit_0", r["exit"] == 0, f"exit {r['exit']}")
    ctx.check("lost_update_demonstrated", j.get("lost_update_demonstrated") is True,
              f"demonstrated {j.get('lost_update_demonstrated')!r} checks {checks}")
    cand = j.get("candidate_module") or {}
    ctx.check("candidate_file_unchanged",
              cand.get("sha256_before") == cand.get("sha256_after"),
              f"sha {cand.get('sha256_before')} -> {cand.get('sha256_after')}")
    return {"demonstrated": j.get("lost_update_demonstrated"),
            "checks": _capped_json(checks),
            "revisions": j.get("revisions")}


def sc_reconcile_systems(ctx: Ctx) -> dict[str, Any]:
    ctx.require("dest-store")
    ctx.require("dest-store-defects")
    r1 = ctx.run("reconcile-clean", "reconcile.py",
                 ["--source", ctx.p("source-store"), "--dest", ctx.p("dest-store"),
                  "--manifest", ctx.p("manifests/run-clean/copy_manifest.json"),
                  "--publish-report", ctx.p("manifests/run-clean/publish.json"),
                  "--out", str(ctx.art("reconcile-clean.json"))],
                 artifacts=[ctx.art("reconcile-clean.json")])
    j1 = r1["json"] or {}
    c1 = j1.get("counts") or {}
    ctx.check("clean_reconcile_pass",
              r1["exit"] == 0 and j1.get("verdict") == "pass" and c1.get("missing") == 0
              and c1.get("extra") == 0 and c1.get("rejected") == 0
              and c1.get("flagged") == 1 and c1.get("published") == 21,
              f"exit {r1['exit']} verdict {j1.get('verdict')} counts {c1} "
              f"reasons {j1.get('reasons')}")
    ctx.check("clean_flagged_cross_check",
              (j1.get("flagged_cross_check") or {}).get("match") is True,
              f"cross_check {j1.get('flagged_cross_check')}")
    r2 = ctx.run("reconcile-defects", "reconcile.py",
                 ["--source", ctx.p("source-store-defects"),
                  "--dest", ctx.p("dest-store-defects"),
                  "--manifest", ctx.p("manifests/run-defects/copy_manifest.json"),
                  "--publish-report", ctx.p("manifests/run-defects/publish.json"),
                  "--out", str(ctx.art("reconcile-defects.json"))],
                 artifacts=[ctx.art("reconcile-defects.json")])
    j2 = r2["json"] or {}
    c2 = j2.get("counts") or {}
    reasons = sorted({r["reason"] for r in j2.get("rejected", [])})
    ctx.check("defects_reconcile_exit_8",
              r2["exit"] == 8 and j2.get("verdict") == "fail", f"exit {r2['exit']}")
    ctx.check("defects_rejected_exact",
              c2.get("rejected") == 4 and reasons == [
                  "asset_hash_mismatch", "invalid_identity",
                  "source_payload_missing", "unresolved_container_ref"],
              f"rejected {c2.get('rejected')} reasons {reasons}")
    ctx.check("defects_no_publication",
              any("publication_refused" in str(x) for x in j2.get("reasons", []))
              and any(str(x).startswith("destination_unreadable") for x in j2.get("reasons", [])),
              f"reasons {j2.get('reasons')}")
    v = ctx.run("verify-clean-destination", "verify.py",
                ["destination", "--dest", ctx.p("dest-store"),
                 "--source", ctx.p("source-store"),
                 "--manifest-dir", ctx.p("manifests/run-clean"),
                 "--out", str(ctx.art("verify-destination.json"))],
                artifacts=[ctx.art("verify-destination.json")])
    vj = v["json"] or {}
    ctx.check("final_destination_verified", v["exit"] == 0 and vj.get("ok") is True,
              f"exit {v['exit']} failures {vj.get('failures')}")
    return {"clean_verdict": j1.get("verdict"), "clean_counts": c1,
            "defects_verdict": j2.get("verdict"), "defects_counts": c2,
            "defects_rejected_reasons": reasons,
            "flagged_cross_check": (j1.get("flagged_cross_check") or {}).get("match")}


SCENARIOS: list[tuple[str, Callable[[Ctx], dict[str, Any]]]] = [
    ("01-clean-migrate", sc_clean_migrate),
    ("02-repeatability", sc_repeatability),
    ("03-interruption-resume", sc_interruption_resume),
    ("04-interrupt-before-swap", sc_interrupt_before_swap),
    ("05-failed-publication", sc_failed_publication),
    ("06-collision-refusal", sc_collision_refusal),
    ("07-pointer-rollback", sc_pointer_rollback),
    ("08-content-restore", sc_content_restore),
    ("09-sqlite-restore", sc_sqlite_restore),
    ("10-tamper-reconcile", sc_tamper_reconcile),
    ("11-concurrent-publish-race", sc_concurrent_race),
    ("12-lost-update-window-probe", sc_window_probe),
    ("13-reconcile-systems", sc_reconcile_systems),
]


# --------------------------------------------------------------------------- #
# run / replay
# --------------------------------------------------------------------------- #
def _ensure_commands_md() -> None:
    if not COMMANDS_MD.exists():
        COMMANDS_MD.parent.mkdir(parents=True, exist_ok=True)
        COMMANDS_MD.write_text(
            "# W5 rehearsal command log\n\n"
            "Append-only: every tool invocation of every rehearsal run is recorded "
            "here with its exact command line, working directory, exit code, "
            "artifacts and a stdout snippet.  Full output lives in "
            "`runs/<stamp>/logs/<scenario>.log`.\n\n",
            encoding="utf-8", newline="\n")


def run_all(base: Path, stamp: str, label: str, *,
            keep_going_on_error: bool, only: list[str] | None = None) -> dict[str, Any]:
    _ensure_commands_md()
    ctx = Ctx(base, stamp, label)
    ctx.out_dir.mkdir(parents=True, exist_ok=True)
    started = w5.now_utc()
    results: list[dict[str, Any]] = []
    for name, func in SCENARIOS:
        if only and not any(name.startswith(p) for p in only):
            continue
        results.append(run_scenario(ctx, name, func,
                                    keep_going_on_error=keep_going_on_error))
    summary = {
        "schema": "w5.rehearsal-run/1",
        "stamp": stamp,
        "label": label,
        "base": _rel_run(base),
        "python": PYTHON,
        "fixed_now": w5.FIXED_NOW,
        "started_at": started,
        "finished_at": w5.now_utc(),
        "ok": all(s["ok"] for s in results),
        "scenarios": [{"name": s["name"], "ok": s["ok"], "exits": s["exits"],
                       "projection": s["projection"], "checks_failed":
                           [c["id"] for c in s["checks"] if not c["ok"]]}
                      for s in results],
    }
    w5.write_json(ctx.out_dir / "summary.json", summary)
    return summary


# step exits / projection keys that vary across identical runs because the
# race scenario outcome depends on OS scheduling; its deterministic invariants
# (readers_failures, late_writer_status, late_pointer_unchanged) are asserted
# inside the scenario and stay compared.
VOLATILE_EXITS = {"11-concurrent-publish-race": {"race"}}
VOLATILE_PROJECTION_KEYS = {"11-concurrent-publish-race": {
    "cas_honored_under_race", "counts", "findings_count", "temp_files_count",
    "final_revision"}}


def _diff_projection(a: Any, b: Any, scenario: str, path: str,
                     mismatches: list[dict[str, Any]], *,
                     skip_keys: set[str] | None = None) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if not path and skip_keys and key in skip_keys:
                continue
            _diff_projection(a.get(key), b.get(key), scenario,
                             f"{path}.{key}" if path else key, mismatches)
        return
    if a != b:
        mismatches.append({"kind": "projection", "scenario": scenario,
                           "path": path, "first": a, "replay": b})


def compare_runs(first: dict[str, Any], second: dict[str, Any]) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    first_by = {s["name"]: s for s in first.get("scenarios", [])}
    for s in second.get("scenarios", []):
        f = first_by.get(s["name"])
        if f is None:
            mismatches.append({"kind": "missing_in_first", "scenario": s["name"]})
            continue
        skip_steps = VOLATILE_EXITS.get(s["name"], set())
        fa, fb = f.get("exits", {}), s.get("exits", {})
        for step in sorted(set(fa) | set(fb)):
            if step in skip_steps:
                continue
            if fa.get(step) != fb.get(step):
                mismatches.append({"kind": "exit", "scenario": s["name"], "step": step,
                                   "first": fa.get(step), "replay": fb.get(step)})
        _diff_projection(f.get("projection"), s.get("projection"), s["name"], "",
                         mismatches, skip_keys=VOLATILE_PROJECTION_KEYS.get(s["name"]))
    return mismatches


def cmd_run(args: argparse.Namespace) -> int:
    stamp = args.stamp or _stamp()
    sub = args.work_subdir or ""
    base = (MIGRATION_ROOT / sub) if sub else MIGRATION_ROOT
    if sub:
        base = w5.guard_within(base, MIGRATION_ROOT)
        if base.exists():
            shutil.rmtree(base)
        base.mkdir(parents=True)
    summary = run_all(base, stamp, label=sub or "migration",
                      keep_going_on_error=not args.fail_fast, only=args.only)
    w5.dump(summary | {"scenarios": [
        {"name": s["name"], "ok": s["ok"], "checks_failed": s["checks_failed"]}
        for s in summary["scenarios"]]})
    return EXIT_OK if summary["ok"] else EXIT_FINDINGS


def cmd_replay(args: argparse.Namespace) -> int:
    first = w5.read_json(args.summary)
    if first.get("schema") != "w5.rehearsal-run/1":
        w5.dump({"status": "error",
                 "reason": f"unexpected summary schema {first.get('schema')!r}"})
        return EXIT_ERROR
    _ensure_commands_md()
    stamp = args.stamp or _stamp()
    sub = args.work_subdir or f"replay-{stamp}"
    base = w5.guard_within(MIGRATION_ROOT / sub, MIGRATION_ROOT)
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    second = run_all(base, stamp, label=sub, keep_going_on_error=True,
                     only=args.only)
    mismatches = compare_runs(first, second)
    comparison = {
        "schema": "w5.rehearsal-comparison/1",
        "first_summary": _rel_run(Path(args.summary)),
        "replay_summary": _rel_run(EVIDENCE_ROOT / "runs" / stamp / "summary.json"),
        "replay_base": _rel_run(base),
        "matched": not mismatches,
        "mismatches": mismatches,
        "first_ok": first.get("ok"),
        "replay_ok": second.get("ok"),
    }
    w5.write_json(EVIDENCE_ROOT / "runs" / stamp / "comparison.json", comparison)
    with COMMANDS_MD.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"## {stamp} / replay / comparison\n"
                 f"- time: {w5.now_utc()}\n"
                 f"- first: `{_rel_run(Path(args.summary))}`\n"
                 f"- replay: `{_rel_run(EVIDENCE_ROOT / 'runs' / stamp / 'summary.json')}`\n"
                 f"- mismatches: {len(mismatches)}\n\n")
    w5.dump(comparison)
    return EXIT_OK if not mismatches else EXIT_FINDINGS


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run all scenarios; capture evidence per step")
    p_run.add_argument("--stamp", default=None)
    p_run.add_argument("--work-subdir", default=None,
                       help="rehearsal base below migration/ (default: migration/ itself)")
    p_run.add_argument("--only", action="append", default=None,
                       help="run only scenarios whose name starts with this prefix")
    p_run.add_argument("--fail-fast", action="store_true",
                       help="stop at the first crashing scenario (default: record and continue)")
    p_run.set_defaults(func=cmd_run)

    p_replay = sub.add_parser("replay", help="re-run in a fresh namespace and compare")
    p_replay.add_argument("--summary", required=True,
                          help="the summary.json of the first run")
    p_replay.add_argument("--stamp", default=None)
    p_replay.add_argument("--work-subdir", default=None,
                          help="default: replay-<stamp>")
    p_replay.add_argument("--only", action="append", default=None)
    p_replay.set_defaults(func=cmd_replay)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
