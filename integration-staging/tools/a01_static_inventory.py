"""A01 static inventory (Phase A, read-only over the workspace).

Collects, as structured evidence for packet A01:
  - component top-level layouts and metadata (pyproject, package.json);
  - Python and Node CLI entry-point candidates (static text only);
  - gateway Node-spawn facts read from the IELTS/TOEFL gateway sources;
  - frontend network call sites;
  - Python and Node environment-variable reads;
  - data-root and report facts.

Reads only. The single write destination is
docs/integration/execution/evidence/A01/statics_extract.json (plus stdout).
Never imports the original application and never executes original code.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tomllib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "docs/integration/execution/evidence/A01"

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
             "build", "wheels", ".piptmp", "pytest-of-weo"}
HASH_CAP = 2_000_000
READ_CAP = 512_000

GATEWAY_FILES = ["examdata/src/examdata/api/ielts.py", "examdata/src/examdata/api/toefl.py"]
ROUTE_FILES = [
    "examdata/src/examdata/api/app.py",
    "examdata/src/examdata/api/unified.py",
    "examdata/src/examdata/api/ielts.py",
    "examdata/src/examdata/api/toefl.py",
    "examdata/src/examdata/materials/router.py",
    "examdata/src/examdata/timetable/router.py",
]

ENV_PY_CALL = re.compile(r"os\.environ(?:\.get)?\(|os\.getenv\(")
ENV_PY_VAR = re.compile(r"[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']")
ENV_NODE = re.compile(r"process\.env(?:\.([A-Za-z_][A-Za-z0-9_]*)|\[\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\])")
FE_CALLS = re.compile(r"fetch\(|XMLHttpRequest|axios|https?://|/resources|/gateway")
GW_LINES = re.compile(r"_SCRIPT_NAME|\.mjs|EXAMDATA_[A-Z_]+|IELTS_API_DIR|TOEFL_API_DIR|"
                      r"shutil\.which|create_subprocess_exec|Semaphore|timeout=")


def stamps() -> tuple[str, str]:
    local = datetime.now().astimezone()
    utc = local.astimezone(timezone.utc)
    return local.isoformat(timespec="seconds"), utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(p: Path) -> str | None:
    try:
        b = p.read_bytes()
    except OSError:
        return None
    if len(b) > HASH_CAP:
        return None
    return hashlib.sha256(b).hexdigest()


def read_text(p: Path) -> str:
    try:
        st = p.stat()
        if st.st_size > READ_CAP:
            return ""
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def walk(root: Path, exts: tuple[str, ...] = (), cap_files: int = 8000) -> list[Path]:
    if not root.is_dir():
        return []
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith("tmp")]
        for fn in sorted(filenames):
            if exts and not fn.endswith(exts):
                continue
            out.append(Path(dirpath) / fn)
            if len(out) >= cap_files:
                return out
    return out


def top_entries(p: Path, cap: int = 40) -> dict:
    entry: dict = {"exists": p.is_dir(), "top_level": [], "truncated": False}
    if not p.is_dir():
        return entry
    items = sorted(p.iterdir(), key=lambda x: x.name)
    entry["truncated"] = len(items) > cap
    for e in items[:cap]:
        try:
            st = e.stat()
            mtime = datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds")
        except OSError:
            continue
        entry["top_level"].append({
            "name": e.name,
            "kind": "dir" if e.is_dir() else "file",
            "size": st.st_size if e.is_file() else None,
            "mtime": mtime,
        })
    return entry


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def main() -> int:
    local, utc = stamps()
    result: dict = {
        "schema": "examdata.integration.a01_static_inventory/1",
        "generated_at_local": local,
        "generated_at_utc": utc,
        "workspace_root": ROOT.as_posix(),
        "tool_path": "integration-staging/tools/a01_static_inventory.py",
        "read_only_note": "static text reads only; no original application import or execution",
    }

    # 1. component layout
    components = ["examdata", "frontend", "ielts-api", "toefl-api", "ielts-data",
                  "cie-index-batch-2026-10-01", "cie-location-batch", "cie-question-crops",
                  "gaokao-feasibility", "docs"]
    result["component_layout"] = {c: top_entries(ROOT / c) for c in components}
    sub = ROOT / "examdata/src/examdata"
    result["examdata_subpackages"] = sorted(
        x.name for x in sub.iterdir() if x.is_dir() and not x.name.startswith("__")
    ) if sub.is_dir() else []

    # 2. Python metadata and entry points
    py: dict = {}
    pp = ROOT / "examdata/pyproject.toml"
    if pp.is_file():
        data = tomllib.loads(pp.read_text(encoding="utf-8"))
        proj = data.get("project", {})
        py["project"] = {
            "name": proj.get("name"), "version": proj.get("version"),
            "requires_python": proj.get("requires-python"),
            "dependencies": proj.get("dependencies"),
            "scripts": proj.get("scripts"),
            "optional_dependencies": {k: v for k, v in proj.get("optional-dependencies", {}).items()},
        }
        py["pytest_ini_options"] = data.get("tool", {}).get("pytest", {}).get("ini_options")
        py["pyproject_sha256"] = sha256_file(pp)
    main_guards = []
    for p in walk(ROOT / "examdata/src", (".py",)) + walk(ROOT / "examdata/scripts", (".py",)):
        for i, line in enumerate(read_text(p).splitlines(), 1):
            if re.match(r"^\s*if __name__\s*==\s*['\"]__main__['\"]", line):
                main_guards.append({"file": rel(p), "line": i, "text": line.strip()[:120]})
                if len(main_guards) >= 200:
                    break
    py["main_guards"] = main_guards
    cli_py = ROOT / "examdata/src/examdata/cli.py"
    cli_commands = []
    if cli_py.is_file():
        text = read_text(cli_py)
        for m in re.finditer(r"@(\w+)\.command\(([^)\n]*)\)\s*\n(?:@[^\n]*\n)*def\s+(\w+)", text):
            cli_commands.append({"name": m.group(3), "args": m.group(2).strip(), "decorator": m.group(1)})
        py["cli_py"] = {"path": rel(cli_py), "sha256": sha256_file(cli_py),
                        "def_count": len(re.findall(r"^def |^\s{4}def ", text, re.M)),
                        "commands": cli_commands[:120]}
    result["python_metadata"] = py

    # 3. Node metadata
    node_meta = []
    for r in ["frontend/package.json", "ielts-api/package.json", "toefl-api/package.json",
              "examdata/package.json"]:
        p = ROOT / r
        if p.is_file():
            try:
                payload = json.loads(read_text(p))
            except json.JSONDecodeError:
                payload = None
            node_meta.append({"path": r, "exists": True, "sha256": sha256_file(p), "json": payload})
        else:
            node_meta.append({"path": r, "exists": False})
    result["node_metadata"] = node_meta

    # 4. Node CLI candidates (shebang or process.argv usage)
    node_cli = []
    for base in ["ielts-api", "toefl-api", "frontend"]:
        for p in walk(ROOT / base, (".mjs", ".js")):
            text = read_text(p)
            first = text.splitlines()[0] if text else ""
            shebang = first if first.startswith("#!") else ""
            has_argv = "process.argv" in text
            if shebang or has_argv:
                node_cli.append({"file": rel(p), "shebang": shebang, "has_process_argv": has_argv,
                                 "size": p.stat().st_size})
                if len(node_cli) >= 150:
                    break
    result["node_cli_candidates"] = node_cli

    # 5. gateway spawn facts
    gw = []
    for r in GATEWAY_FILES:
        p = ROOT / r
        for i, line in enumerate(read_text(p).splitlines(), 1):
            if GW_LINES.search(line):
                gw.append({"file": r, "line": i, "text": line.strip()[:160]})
                if len(gw) >= 250:
                    break
    result["gateway_spawn_facts"] = gw

    # 6. frontend network call sites
    fe = []
    fe_counts: dict[str, int] = {}
    for p in walk(ROOT / "frontend", (".js", ".mjs", ".html")):
        for i, line in enumerate(read_text(p).splitlines(), 1):
            if FE_CALLS.search(line):
                fe.append({"file": rel(p), "line": i, "text": line.strip()[:160]})
                fe_counts[rel(p)] = fe_counts.get(rel(p), 0) + 1
                if len(fe) >= 500:
                    break
    result["frontend_network_calls"] = {"hits": fe, "counts_by_file": fe_counts}

    # 7. env reads (Python)
    env_py = []
    for base in ["examdata/src", "examdata/scripts"]:
        for p in walk(ROOT / base, (".py",)):
            for i, line in enumerate(read_text(p).splitlines(), 1):
                if ENV_PY_CALL.search(line):
                    vm = ENV_PY_VAR.search(line)
                    env_py.append({"file": rel(p), "line": i, "var": vm.group(1) if vm else "",
                                   "text": line.strip()[:160]})
                    if len(env_py) >= 400:
                        break
    result["env_reads_python"] = env_py

    # 8. env reads (Node)
    env_node = []
    for base in ["ielts-api", "toefl-api", "frontend"]:
        for p in walk(ROOT / base, (".mjs", ".js")):
            for i, line in enumerate(read_text(p).splitlines(), 1):
                for m in ENV_NODE.finditer(line):
                    env_node.append({"file": rel(p), "line": i,
                                     "var": m.group(1) or m.group(2),
                                     "text": line.strip()[:160]})
                    if len(env_node) >= 400:
                        break
    result["env_reads_node"] = env_node

    # 9. env templates (names only; .env contents are never read)
    templates = []
    for base in [".", "examdata", "frontend", "ielts-api", "toefl-api"]:
        b = ROOT / base if base != "." else ROOT
        if b.is_dir():
            for e in sorted(b.iterdir()):
                if e.name.startswith(".env"):
                    templates.append({"path": rel(e), "note": "content not read (secret policy)"})
    result["env_templates"] = templates

    # 10. data roots
    dir_candidates = [".data", "examdata/.data", "examdata/.pytest_cache", "examdata/pytest-of-weo",
                      "ielts-data", "toefl-api/data", "toefl-api/audit-20261005",
                      "toefl-api/repair-20261005", "cie-location-batch/indexes",
                      "cie-location-batch/work", "cie-location-batch/.data",
                      "cie-index-batch-2026-10-01", "cie-question-crops/out",
                      "examdata/build", "examdata/research"]
    result["data_root_dirs"] = {d: top_entries(ROOT / d) for d in dir_candidates}
    db_files = ["explore-examdata.db", "proto-examdata.db", "proto2-examdata.db", "qsvc_check.db",
                "examdata/explore-examdata.db", "examdata/proto-examdata.db",
                "examdata/proto2-examdata.db", "examdata/qsvc_check.db"]
    dbs = []
    for d in db_files:
        p = ROOT / d
        if p.is_file():
            st = p.stat()
            dbs.append({"path": d, "size": st.st_size,
                        "mtime": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds")})
        else:
            dbs.append({"path": d, "exists": False})
    result["db_files"] = dbs

    # 11. reports manifest
    report_files = ["docs/PROJECT_STATUS.md", "docs/integration/MASTER_EXECUTION_PLAN_EN.md",
                    "docs/integration/EXECUTOR_PROMPT_EN.md",
                    "docs/integration/ROUTE_INVENTORY_CURRENT.json",
                    "SESSION_CONTINUATION_PLAN.md", "gaokao-feasibility/REPORT.md",
                    "gaokao-feasibility/channels.md", "gaokao-feasibility/coverage-matrix.csv",
                    "gaokao-feasibility/scope-map.md", "toefl-api/REPORT.md",
                    "toefl-api/AUDIT_REPORT_20261005.md", "toefl-api/AGENT_FIX_PROMPT_20261005.md",
                    "ielts-api/API.md", "ielts-api/AUDIT_REPORT.md", "ielts-api/DEVELOPMENT.md",
                    "examdata/README.md", "frontend/README.md"]
    reports = []
    for rf in report_files:
        p = ROOT / rf
        if p.is_file():
            st = p.stat()
            reports.append({"path": rf, "size": st.st_size,
                            "mtime": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds"),
                            "sha256": sha256_file(p)})
        else:
            reports.append({"path": rf, "exists": False})
    result["reports_manifest"] = reports
    result["report_dirs"] = {d: top_entries(ROOT / d, cap=30)
                             for d in ["examdata/docs", "cie-index-batch-2026-10-01"]}

    # 12. route-source and tool hashes
    files = {}
    for rf in ROUTE_FILES + ["docs/integration/ROUTE_INVENTORY_CURRENT.json",
                             "docs/integration/tools/inventory_routes.py",
                             "integration-staging/tools/a01_inventory_routes.py",
                             "integration-staging/tools/a01_static_inventory.py"]:
        p = ROOT / rf
        if p.is_file():
            st = p.stat()
            files[rf] = {"sha256": sha256_file(p), "size": st.st_size,
                         "mtime": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds")}
    result["source_and_tool_hashes"] = files

    # 13. git snapshot (read-only)
    git = {}
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    try:
        stat = subprocess.run(["git", "-C", str(ROOT / "examdata"), "status", "--porcelain=v1"],
                              capture_output=True, encoding="utf-8", errors="replace",
                              timeout=60, env=env)
        lines = (stat.stdout or "").splitlines()
        git["status_entries"] = len(lines)
        git["status_head"] = lines[:30]
        logp = subprocess.run(["git", "-C", str(ROOT / "examdata"), "log", "-1",
                               "--format=%H|%ad|%s", "--date=iso"],
                              capture_output=True, encoding="utf-8", errors="replace",
                              timeout=60, env=env)
        git["head"] = (logp.stdout or "").strip()
    except (OSError, subprocess.SubprocessError) as exc:
        git["error"] = str(exc)
    result["git_snapshot"] = git

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "statics_extract.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "written": rel(out),
        "components": {k: len(v["top_level"]) for k, v in result["component_layout"].items()},
        "python_main_guards": len(main_guards),
        "cli_commands": len(cli_commands),
        "node_cli_candidates": len(node_cli),
        "gateway_spawn_facts": len(gw),
        "frontend_call_hits": len(fe),
        "env_reads_python": len(env_py),
        "env_reads_node": len(env_node),
        "env_templates": len(templates),
        "data_roots": sum(1 for v in result["data_root_dirs"].values() if v["exists"]),
        "git_status_entries": git.get("status_entries"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("STATIC_INVENTORY: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
