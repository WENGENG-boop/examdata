"""把已审核的定位索引导入本地 examdata 服务，并做回读校验。

流程：
1. 用 validate_index 校验 `indexes/<subject>/<year>-<season>-<paper>/cie-index.json`
2. 用 subprocess（无 shell）跑 `examdata import-cie-index`，要求 exit 0 并解析它打印的 JSON
3. `GET /api/v1/indexes/cie/<qp_sha256>` 回读，逐题比较 question/parent/marks/qp/ms/
   uncertain/notes 以及 identity/documents（规范化比较，不受缩进与顺序影响）
4. 确认 `question_indexes/cie/<qp_sha256>.json` 去掉服务加的 method/reviewed 后等于本地索引
5. 成功写 papers.json（stage=imported_verified），失败写 errors.jsonl 并退出非零

**绝不覆盖已有且内容不同的服务索引**：CLI 自身也会拒绝（exit 1，
"Different index already exists; explicit review required"），本工具把它归类为 conflict。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import batchlib as B
import paperlib as P
import pipelinestate as S
import validate_index as V

CLI_EXE = B.REPO / ".venv" / "Scripts" / "examdata.exe"
DATA_DIR = B.SERVICE_DATA_DIR
SERVICE_BASE = "http://127.0.0.1:8000"
SERVICE_INDEX_SUBDIR = ("question_indexes", "cie")
SERVICE_ADDED_FIELDS = ("method", "reviewed")
COMPARE_FIELDS = ("question", "parent", "marks", "qp", "ms", "uncertain", "notes")

EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_IMPORT = 2
EXIT_CONFLICT = 3
EXIT_READBACK = 4


def _stdout_utf8() -> None:
    enc = (getattr(sys.stdout, "encoding", "") or "").replace("-", "").lower()
    if enc != "utf8" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def index_path(key: str) -> Path:
    subject, year, season, paper = key.split("/")
    return B.index_dir(subject, int(year), season, paper) / "cie-index.json"


def service_index_path(sha256: str, data_dir: Path = DATA_DIR) -> Path:
    return Path(data_dir).joinpath(*SERVICE_INDEX_SUBDIR, f"{sha256}.json")


def locate_pdf(key: str, role: str) -> Path | None:
    tmp_dir = P.paper_tmp(key)
    entry = P.load_paper(key) or {}
    recorded = (entry.get(f"{role}_document") or {}).get("filename")
    if recorded and (tmp_dir / recorded).is_file():
        return tmp_dir / recorded
    patterns = ("*_qp_*.pdf", "*qp*.pdf") if role == "qp" else ("*_ms_*.pdf", "*ms*.pdf")
    for pattern in patterns:
        hits = sorted(tmp_dir.glob(pattern))
        if hits:
            return hits[0]
    return None


def document_sha(data: dict, role: str) -> str | None:
    for doc in data.get("documents") or []:
        if isinstance(doc, dict) and doc.get("role") == role:
            return doc.get("sha256")
    return None


def normalise_questions(questions) -> list[dict]:
    out = []
    for item in questions or []:
        if not isinstance(item, dict):
            out.append({"__not_object__": repr(item)})
            continue
        row = {field: item.get(field) for field in COMPARE_FIELDS}
        row["qp"] = sorted(
            ({"page": r.get("page"), "bbox": [round(float(v), 3) for v in r.get("bbox", [])]}
             for r in (item.get("qp") or []) if isinstance(r, dict)),
            key=lambda r: (r["page"] or 0, r["bbox"]))
        row["ms"] = sorted(
            ({"page": r.get("page"), "bbox": [round(float(v), 3) for v in r.get("bbox", [])]}
             for r in (item.get("ms") or []) if isinstance(r, dict)),
            key=lambda r: (r["page"] or 0, r["bbox"]))
        out.append(row)
    return out


def normalise_documents(documents) -> list[dict]:
    rows = [{"role": d.get("role"), "sha256": d.get("sha256")}
            for d in (documents or []) if isinstance(d, dict)]
    return sorted(rows, key=lambda d: (d["role"] or "", d["sha256"] or ""))


def compare_index(local: dict, remote: dict) -> tuple[list[str], list[str]]:
    """返回 (errors, warnings)：比较 identity/documents/每题的关键字段。"""
    errors: list[str] = []
    warnings: list[str] = []
    if local.get("identity") != remote.get("identity"):
        errors.append(f"identity 不一致：本地 {local.get('identity')} 服务 {remote.get('identity')}")
    if normalise_documents(local.get("documents")) != normalise_documents(remote.get("documents")):
        errors.append("documents 不一致："
                      f"本地 {normalise_documents(local.get('documents'))} "
                      f"服务 {normalise_documents(remote.get('documents'))}")
    for field in ("schema_version", "board", "coordinate_system", "page_base"):
        if local.get(field) != remote.get(field):
            errors.append(f"{field} 不一致：本地 {local.get(field)!r} 服务 {remote.get(field)!r}")

    local_q = normalise_questions(local.get("questions"))
    remote_q = normalise_questions(remote.get("questions"))
    if len(local_q) != len(remote_q):
        errors.append(f"题数不一致：本地 {len(local_q)} 服务 {len(remote_q)}")
    for i, (a, b) in enumerate(zip(local_q, remote_q)):
        for field in COMPARE_FIELDS:
            if a.get(field) != b.get(field):
                errors.append(f"题 #{i} {a.get('question')!r} 的 {field} 不一致："
                              f"本地 {a.get(field)!r} 服务 {b.get(field)!r}")
    local_text = [q.get("text") for q in (local.get("questions") or [])]
    remote_text = [q.get("text") for q in (remote.get("questions") or [])]
    if local_text != remote_text:
        warnings.append("text 字段与服务端不完全一致（服务端可能规范化过文本）")
    return errors, warnings


def run_cli(index_file: Path, qp: Path, ms: Path | None,
            data_dir: Path = DATA_DIR) -> tuple[int, str, str, dict | None]:
    args = [str(CLI_EXE), "import-cie-index", str(index_file), "--qp", str(qp)]
    if ms is not None:
        args += ["--ms", str(ms)]
    env = dict(os.environ)
    env["EXAMDATA_DATA_DIR"] = str(data_dir)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(args, capture_output=True, env=env, text=True,
                          encoding="utf-8", errors="replace")
    parsed = None
    try:
        parsed = json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError):
        parsed = None
    return proc.returncode, proc.stdout, proc.stderr, parsed


def http_get(url: str, timeout: float = 15.0) -> tuple[int, bytes]:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def import_index(key: str, service_base: str = SERVICE_BASE,
                 data_dir: Path = DATA_DIR) -> dict:
    report: dict = {"key": key, "stage": None, "errors": [], "warnings": [],
                    "exit_code": EXIT_OK, "service_index_path": None,
                    "index_sha256": None, "question_count": 0,
                    "import_succeeded": False, "readback_verified": False}
    path = index_path(key)
    if not path.is_file():
        report["errors"].append(f"找不到永久索引 {path}")
        report["stage"] = "import_failed"
        report["exit_code"] = EXIT_VALIDATION
        return report

    qp = locate_pdf(key, "qp")
    ms = locate_pdf(key, "ms")
    validation = V.validate(path, qp=qp, ms=ms)
    report["validation_engine"] = validation["engine"]
    if validation["errors"]:
        report["errors"] += [f"校验失败：{e}" for e in validation["errors"]]
        report["stage"] = "validation_failed"
        report["exit_code"] = EXIT_VALIDATION
        return report
    report["warnings"] += validation["warnings"]

    local = json.loads(path.read_bytes().decode("utf-8"))
    report["question_count"] = len(local.get("questions") or [])
    report["index_sha256"] = B.sha256_file(path)
    qp_sha = document_sha(local, "qp")
    if not qp_sha:
        report["errors"].append("索引里没有 qp 文档的 sha256")
        report["stage"] = "import_failed"
        report["exit_code"] = EXIT_VALIDATION
        return report
    if qp is None:
        report["errors"].append("找不到 QP PDF，无法导入")
        report["stage"] = "import_failed"
        report["exit_code"] = EXIT_VALIDATION
        return report
    actual_sha = B.sha256_file(qp)
    if actual_sha != qp_sha:
        report["errors"].append(f"QP PDF 的 sha256 {actual_sha} 与索引记录的 {qp_sha} 不一致")
        report["stage"] = "import_failed"
        report["exit_code"] = EXIT_VALIDATION
        return report

    target = service_index_path(qp_sha, data_dir)
    report["service_index_path"] = str(target)
    pre_existing = target.is_file()
    if pre_existing:
        existing = json.loads(target.read_bytes().decode("utf-8"))
        same = {k: v for k, v in existing.items()
                if k not in SERVICE_ADDED_FIELDS} == local
        if not same:
            report["errors"].append(
                f"服务里已有同一 QP sha 且内容不同的索引：{target}；"
                f"按规则不覆盖，报 conflict，需要人工复核")
            report["stage"] = "conflict"
            report["exit_code"] = EXIT_CONFLICT
            return report
        report["warnings"].append("服务里已有完全相同的索引，导入是幂等的")

    code, out, err, parsed = run_cli(path, qp, ms, data_dir)
    report["cli_exit_code"] = code
    if code != 0:
        detail = (out or "").strip() or (err or "").strip() or f"exit {code}"
        if "Different index already exists" in (out or "") + (err or ""):
            report["errors"].append(f"服务端拒绝覆盖：{detail}")
            report["stage"] = "conflict"
            report["exit_code"] = EXIT_CONFLICT
            return report
        report["errors"].append(f"import-cie-index 失败（exit {code}）：{detail}")
        report["stage"] = "import_failed"
        report["exit_code"] = EXIT_IMPORT
        return report

    if parsed is None:
        report["errors"].append(f"无法解析 CLI 输出：{out[:300]!r}")
        report["stage"] = "import_failed"
        report["exit_code"] = EXIT_IMPORT
        return report
    report["cli_output"] = parsed
    if parsed.get("sha256") != qp_sha:
        report["errors"].append(f"CLI 报告的 sha256 {parsed.get('sha256')} 与本地 {qp_sha} 不一致")
    if parsed.get("questions") != report["question_count"]:
        report["errors"].append(f"CLI 报告的题数 {parsed.get('questions')} "
                                f"与本地 {report['question_count']} 不一致")
    if parsed.get("path") and Path(parsed["path"]) != target:
        report["warnings"].append(f"CLI 写入路径 {parsed['path']} 与预期 {target} 不同")
    if report["errors"]:
        report["stage"] = "import_failed"
        report["exit_code"] = EXIT_IMPORT
        return report
    report["import_succeeded"] = True

    status, body = http_get(f"{service_base}/api/v1/indexes/cie/{qp_sha}")
    if status != 200:
        report["errors"].append(f"回读失败：GET /api/v1/indexes/cie/{qp_sha} -> HTTP {status}")
        report["stage"] = "readback_failed"
        report["exit_code"] = EXIT_READBACK
        return report
    remote = json.loads(body.decode("utf-8"))
    errors, warnings = compare_index(local, remote)
    report["warnings"] += warnings
    if errors:
        report["errors"] += [f"回读比对：{e}" for e in errors]
        report["stage"] = "readback_failed"
        report["exit_code"] = EXIT_READBACK
        return report

    if not target.is_file():
        report["errors"].append(f"回读通过但服务索引文件不存在：{target}")
        report["stage"] = "readback_failed"
        report["exit_code"] = EXIT_READBACK
        return report
    stored = json.loads(target.read_bytes().decode("utf-8"))
    if {k: v for k, v in stored.items() if k not in SERVICE_ADDED_FIELDS} != local:
        report["errors"].append(f"{target} 去掉 {SERVICE_ADDED_FIELDS} 后与本地索引不同")
        report["stage"] = "readback_failed"
        report["exit_code"] = EXIT_READBACK
        return report

    report["readback_verified"] = True
    report["stage"] = "imported_verified"
    return report


def record(report: dict) -> None:
    key = report["key"]
    fields = {"service_index_path": report["service_index_path"],
              "index_sha256": report["index_sha256"],
              "question_count": report["question_count"],
              "import_succeeded": report["import_succeeded"],
              "readback_verified": report["readback_verified"],
              "service_stage_at": B.now_iso()}
    if report["stage"] == "imported_verified":
        S.set_stage(key, "imported_verified", **fields)
        B.set_checkpoint(last_import=key, last_import_at=B.now_iso())
        B.append_jsonl(B.ERRORS, {"at": B.now_iso(), "key": key,
                                  "stage": "imported_verified", "resolved": True,
                                  "note": "该 key 之前的错误记录已被本次成功导入覆盖"})
    else:
        S.set_stage(key, report["stage"], **fields)
        B.append_jsonl(B.ERRORS, {"at": B.now_iso(), "key": key,
                                  "stage": report["stage"],
                                  "exit_code": report["exit_code"],
                                  "errors": report["errors"]})


def main() -> int:
    _stdout_utf8()
    parser = argparse.ArgumentParser(description="导入定位索引并回读校验")
    parser.add_argument("key", help="subject/year/season/paper")
    parser.add_argument("--service-base", default=SERVICE_BASE)
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    parser.add_argument("--no-record", action="store_true",
                        help="只报告，不写 papers.json / errors.jsonl（自测用）")
    args = parser.parse_args()
    report = import_index(args.key, args.service_base, Path(args.data_dir))
    print(f"导入 {args.key}：{report['stage']}")
    print(f"  索引 {index_path(args.key)}  sha256 {report['index_sha256']}")
    print(f"  题数 {report['question_count']}  导入成功 {report['import_succeeded']}  "
          f"回读通过 {report['readback_verified']}")
    print(f"  服务索引 {report['service_index_path']}")
    for warning in report["warnings"]:
        print(f"  ~ {warning}")
    for error in report["errors"]:
        print(f"  ! {error}")
    if not args.no_record:
        record(report)
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
