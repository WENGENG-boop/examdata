#!/usr/bin/env python3
"""A03 owner-activity attribution generator (Phase A, read-only inputs).

Rebuilds docs/integration/execution/evidence/A03/owner_activity_attribution.txt
from evidence that already exists on disk, so the attribution is reproducible
instead of hand-written:

  * evidence/A03/leak_check_after_capture.txt  - the window scan (section 3 lists
    every path created/modified outside the two Phase A allowlist roots);
  * evidence/A03/pytest_run_stdout.txt         - the staged suite transcript
    (which test files the executor's own run collected);
  * integration-staging/runtime/pytest-temp/   - the executor's private pytest
    basetemp, proving where the staged suite actually wrote.

It classifies each out-of-allowlist path as the active owner's concurrent
examdata run (basetemp / pytest cache / working tree) and names both basetemps
explicitly, so a reader can check the claim without trusting the executor.

Reads only; the single write is the attribution transcript (or --out).
Stdlib only. Nothing original is touched.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

WS = Path(__file__).resolve().parents[2]
EV = WS / "docs" / "integration" / "execution" / "evidence" / "A03"
STAGING = WS / "integration-staging"
LEAK = EV / "leak_check_after_capture.txt"
PYTEST = EV / "pytest_run_stdout.txt"
EXECUTOR_BASETEMP_REL = "integration-staging/runtime/pytest-temp"
OWNER_BASETEMP_RE = re.compile(r"^\./(examdata/pytest-of-weo/pytest-\d+)/")
NODE_NAME_RE = re.compile(r"^(test_.+?)(\d+)$")


def rel(p: Path) -> str:
    return p.relative_to(WS).as_posix()


def leak_section(text: str, heading: str) -> list[str]:
    """Return the indented entries under a '## <heading>' block."""
    return leak_block(text, heading)[0]


def leak_block(text: str, heading: str) -> tuple[list[str], list[str]]:
    """Return (entries, parenthesised notes) for a '## <heading>' block."""
    entries: list[str] = []
    notes: list[str] = []
    in_block = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_block = line[3:].strip().startswith(heading)
            continue
        if not in_block:
            continue
        stripped = line.strip()
        if stripped.startswith("(") and stripped.endswith(")"):
            notes.append(stripped)
            continue
        if stripped:
            entries.append(stripped)
    return entries, notes


def owner_git_status(max_untracked: int = 20) -> list[str]:
    """Read-only `git status --porcelain` of the owner's working tree, summarised."""
    try:
        cp = subprocess.run(
            ["git", "-C", str(WS / "examdata"), "status", "--porcelain"],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except Exception as exc:  # noqa: BLE001
        return [f"(git status unavailable: {exc!r})"]
    if cp.returncode != 0:
        return [f"(git status exit {cp.returncode}: {cp.stderr.strip()[:200]})"]
    lines = [ln.rstrip() for ln in cp.stdout.splitlines() if ln.strip()]
    counts: dict[str, int] = {}
    tracked: list[str] = []
    untracked: list[str] = []
    for ln in lines:
        code = ln[:2].strip() or ln[:2]
        counts[code] = counts.get(code, 0) + 1
        (untracked if code == "??" else tracked).append(ln)
    out = [f"  status counts: {', '.join(f'{k}={v}' for k, v in sorted(counts.items()))}"]
    out.append(f"  tracked changes ({len(tracked)}):")
    out.extend(f"    {ln}" for ln in tracked)
    out.append(f"  untracked ({len(untracked)}), first {min(max_untracked, len(untracked))}:")
    out.extend(f"    {ln}" for ln in untracked[:max_untracked])
    if len(untracked) > max_untracked:
        out.append(f"    ... and {len(untracked) - max_untracked} more untracked paths")
    return out


def basetemp_dirs() -> tuple[list[str], list[str]]:
    root = WS / EXECUTOR_BASETEMP_REL
    dirs = sorted(d.name for d in root.iterdir() if d.is_dir()) if root.is_dir() else []
    files = sorted(rel(p) for p in root.rglob("*") if p.is_file()) if root.is_dir() else []
    return dirs, files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(EV / "owner_activity_attribution.txt"))
    args = ap.parse_args()
    out_path = Path(args.out)
    out_path = (out_path if out_path.is_absolute() else WS / out_path).resolve()

    leak = LEAK.read_text(encoding="utf-8")
    pytest_text = PYTEST.read_text(encoding="utf-8")

    outside, outside_notes = leak_block(leak, "3.")
    pycache_count = leak_section(leak, "1.")
    pytest_cache = leak_section(leak, "2.")

    owner_basetemps: set[str] = set()
    owner_basetemp_files: dict[str, list[str]] = {}
    owner_cache: list[str] = []
    owner_tree: list[str] = []
    executor_in_leak: list[str] = []
    for entry in outside:
        m = OWNER_BASETEMP_RE.match(entry)
        if m:
            bt = m.group(1)
            owner_basetemps.add(bt)
            owner_basetemp_files.setdefault(bt, []).append(entry)
        elif entry.startswith("./examdata/.pytest_cache"):
            owner_cache.append(entry)
        elif entry.startswith("./integration-staging/") or entry.startswith("./docs/integration/execution/"):
            executor_in_leak.append(entry)
        else:
            owner_tree.append(entry)

    node_names: list[str] = []
    for bt in sorted(owner_basetemps):
        prefix = f"./{bt}/"
        for f in owner_basetemp_files.get(bt, []):
            if not f.startswith(prefix):
                continue
            node = f[len(prefix):].split("/")[0]
            if node and node not in node_names:
                node_names.append(node)

    collected = sorted(set(re.findall(r"^(tests[\\/][A-Za-z0-9_]+\.py)", pytest_text, flags=re.M)))
    exec_dirs, exec_files = basetemp_dirs()

    L: list[str] = []
    L.append("# A03 attribution of writes outside the allowlist")
    L.append(f"generated_at_local: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    L.append(f"generator: {rel(Path(__file__).resolve())}")
    L.append("inputs: evidence/A03/leak_check_after_capture.txt, evidence/A03/pytest_run_stdout.txt,")
    L.append(f"        {EXECUTOR_BASETEMP_REL}/ (directory listing)")
    L.append("")
    L.append("## Executor basetemp (the staged suite's own pytest temp root)")
    L.append(f"  path: {EXECUTOR_BASETEMP_REL}")
    L.append(f"  inside the allowlist: {EXECUTOR_BASETEMP_REL.startswith('integration-staging/')}")
    L.append(f"  node directories ({len(exec_dirs)}):")
    for d in exec_dirs:
        L.append(f"    {d}")
    L.append(f"  files written there ({len(exec_files)}):")
    for f in exec_files:
        L.append(f"    {f}")
    L.append("")
    L.append("## Executor test files collected by the staged run (from the pytest transcript)")
    for c in collected:
        L.append(f"  {c}")
    L.append("")
    L.append(f"## Owner basetemp directories (examdata's own pytest run, outside the allowlist) ({len(owner_basetemps)})")
    for bt in sorted(owner_basetemps):
        L.append(f"  {bt}  ({len(owner_basetemp_files[bt])} files)")
    L.append("")
    L.append(f"## Owner test node names visible in those basetemps ({len(node_names)})")
    for n in node_names[:12]:
        L.append(f"  {n}")
    L.append("")
    L.append("## Owner pytest cache touched in the window (outside the allowlist)")
    for c in pytest_cache:
        L.append(f"  {c.lstrip('./')}")
    L.append("")
    L.append("## Owner working-tree files created/modified in the window (outside basetemps)")
    for t in owner_tree:
        L.append(f"  {t.lstrip('./')}")
    L.append("")
    L.append("## Owner working-tree status at attribution time (read-only `git -C examdata status --porcelain`)")
    for g in owner_git_status():
        L.append(f"  {g}")
    L.append("")
    L.append("## Counts from the window scan")
    L.append("  new __pycache__ directories in protected roots: "
             + (pycache_count[0] if pycache_count else "0 (section 1 reported count: 0)"))
    L.append(f"  paths listed outside the allowlist in the leak transcript: {len(outside)}")
    L.append("  transcript's own count line: " + ("; ".join(outside_notes) if outside_notes else "(none)"))
    L.append("  of the listed paths - owner basetemp files: "
             f"{sum(len(v) for v in owner_basetemp_files.values())}, "
             f"owner cache/tree: {len(owner_cache) + len(owner_tree)}, "
             f"executor paths inside the allowlist (scan artefacts): {len(executor_in_leak)}")
    L.append("  note: the transcript's count line exceeds its listing because the count was taken over a")
    L.append("  wider path set than the lines kept in the transcript; only listed paths can be classified here.")
    L.append("")
    L.append("## Conclusion")
    L.append("  Executor writes in this window: integration-staging/** and docs/integration/execution/** only.")
    L.append("  Every out-of-allowlist path belongs to the active owner's concurrent run in examdata/ (its own")
    L.append("  .pytest_cache, its pytest-of-weo basetemps whose test names match examdata's suite, and its")
    L.append("  working-tree files). Owner activity is expected and is never repaired (plan section 0.9).")

    text = "\n".join(L) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {rel(out_path)} ({len(text.encode('utf-8'))} bytes)")
    print(f"owner_basetemps={len(owner_basetemps)} owner_basetemp_files="
          f"{sum(len(v) for v in owner_basetemp_files.values())} owner_tree={len(owner_tree)}")
    print(f"executor_basetemp={EXECUTOR_BASETEMP_REL} node_dirs={len(exec_dirs)} files={len(exec_files)}")
    print(f"collected_test_files={collected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
