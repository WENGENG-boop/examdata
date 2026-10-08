"""按阶段驱动单份试卷的确定性流程，可安全重跑。

阶段：
- `fetch`   本地 PDF 不齐时经 fetch_paper.py 下载（跨进程互斥、扫描中会拒绝），再核对 sha256
- `propose` 要求 PDF 存在且 sha256 与 papers.json 记录一致，然后跑 propose.py
- `import`  要求提案与已审核索引存在，然后跑 validate + import_index
- `cleanup` 跑 cleanup_paper.py
- `status`  打印该 key 的当前状态

每次都更新 papers.json 的 stage 与 checkpoint.json；失败追加到 errors.jsonl。
重跑已完成阶段是幂等的，不会重新下载。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import batchlib as B
import paperlib as P
import pipelinestate as S
import cleanup_paper as C
import import_index as I
import propose as R

EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_FAILED = 2


def _stdout_utf8() -> None:
    enc = (getattr(sys.stdout, "encoding", "") or "").replace("-", "").lower()
    if enc != "utf8" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def proposal_path(key: str) -> Path:
    subject, year, season, paper = key.split("/")
    return B.WORK / "proposals" / subject / f"{year}-{season}-{paper}.json"


def seed_entry(key: str) -> dict:
    """确保 papers.json 里有该 key 的条目。

    扫描进程会整体重写 papers.json，本工具写入的条目可能已被丢弃；
    因此先用 `work/state.json` 的镜像恢复，再退回扫描发现的临时 PDF 重建。
    """
    entry = P.load_paper(key)
    if entry:
        return entry
    mirrored = S.load(key)
    if mirrored:
        return S.restore(key)
    subject, year, season, paper = key.split("/")
    tmp_dir = P.paper_tmp(key)
    qp = ms = None
    for candidate in sorted(tmp_dir.glob("*.pdf")):
        name = candidate.name.lower()
        if "_qp_" in name or name.endswith("qp.pdf"):
            qp = qp or candidate
        elif "_ms_" in name or name.endswith("ms.pdf"):
            ms = ms or candidate
    fields = {"subject": subject, "year": int(year), "season": season,
              "paper": paper, "stage": "discovered", "kind": "paper",
              "seeded_by": "run_paper.py"}
    if qp is not None:
        fields["qp"] = [qp.name]
    if ms is not None:
        fields["ms"] = [ms.name]
    return S.patch(key, **fields)


def pdf_report(key: str, seed: bool = True) -> tuple[dict, list[str]]:
    tmp_dir = P.paper_tmp(key)
    problems: list[str] = []
    info: dict = {"tmp_dir": str(tmp_dir), "exists": tmp_dir.is_dir()}
    if not tmp_dir.is_dir():
        problems.append(f"没有临时目录 {tmp_dir}")
        return info, problems
    entry = seed_entry(key) if seed else S.entry(key)[0]
    if not entry:
        problems.append("papers.json 与 work/state.json 里都没有该 key 的条目")
    for role in ("qp", "ms"):
        path = I.locate_pdf(key, role)
        if path is None:
            info[role] = None
            if role == "qp":
                problems.append("找不到 QP PDF")
            continue
        sha = B.sha256_file(path)
        recorded = (entry.get(f"{role}_document") or {}).get("sha256")
        if not recorded:
            names = entry.get(role) or []
            if path.name not in names and names:
                problems.append(f"{role} PDF {path.name} 不在 papers.json 记录的 {names} 里")
        elif recorded != sha:
            problems.append(f"{role} PDF sha256 {sha[:16]} 与 papers.json 记录的 "
                            f"{recorded[:16]} 不一致")
        info[role] = {"filename": path.name, "sha256": sha, "recorded": recorded,
                      "bytes": path.stat().st_size}
    return info, problems


def _doc_record(key: str, role: str, info: dict) -> dict | None:
    value = info.get(role)
    if not isinstance(value, dict):
        return None
    path = P.paper_tmp(key) / value["filename"]
    return {"filename": value["filename"], "sha256": value["sha256"],
            "pages": P.validate_pdf(path)["pages"]}


def stage_fetch(key: str) -> int:
    info, problems = pdf_report(key)
    if problems:
        # 本地原件不齐 -> 真正下载（fetch_paper 内部有跨进程互斥体和扫描守卫）
        print(f"fetch {key}: 本地原件不齐，转为下载")
        for problem in problems:
            print(f"  - {problem}")
        code = subprocess.run(
            [sys.executable, str(B.TOOLS / "fetch_paper.py"), key],
            cwd=str(B.TOOLS), env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        ).returncode
        if code != 0:
            print(f"  下载失败，退出码 {code}")
            return EXIT_BLOCKED if code == 3 else code
        info, problems = pdf_report(key)

    print(f"fetch {key}")
    for role in ("qp", "ms"):
        value = info.get(role)
        if isinstance(value, dict):
            print(f"  {role.upper()} {value['filename']} {value['bytes']} 字节 "
                  f"sha256 {value['sha256'][:16]}")
        else:
            print(f"  {role.upper()} 缺失")
    for problem in problems:
        print(f"  ! {problem}")
    if problems:
        B.append_jsonl(B.ERRORS, {"at": B.now_iso(), "key": key, "stage": "fetch",
                                  "errors": problems})
        S.set_stage(key, "fetch_incomplete")
        return EXIT_BLOCKED
    S.set_stage(key, "fetched",
                qp_sha256=info["qp"]["sha256"],
                ms_sha256=(info["ms"] or {}).get("sha256"),
                qp_document=_doc_record(key, "qp", info),
                ms_document=_doc_record(key, "ms", info))
    B.set_checkpoint(last_fetch=key, last_fetch_at=B.now_iso())
    print("  阶段 fetched")
    return EXIT_OK


def stage_propose(key: str, force: bool) -> int:
    info, problems = pdf_report(key)
    if problems:
        print(f"propose {key} 被拒绝：")
        for problem in problems:
            print(f"  ! {problem}")
        B.append_jsonl(B.ERRORS, {"at": B.now_iso(), "key": key, "stage": "propose",
                                  "errors": problems})
        return EXIT_BLOCKED
    code = R.build(key, force)
    if code != 0:
        B.append_jsonl(B.ERRORS, {"at": B.now_iso(), "key": key, "stage": "propose",
                                  "errors": ["propose.py 返回非零"]})
        S.set_stage(key, "propose_failed")
        return EXIT_FAILED
    S.set_stage(key, "proposed",
                proposal_path=str(proposal_path(key)),
                proposal_at=B.now_iso())
    B.set_checkpoint(last_propose=key, last_propose_at=B.now_iso())
    return EXIT_OK


def stage_import(key: str) -> int:
    proposal = proposal_path(key)
    index_file = I.index_path(key)
    if not proposal.is_file():
        print(f"import {key} 被拒绝：没有提案 {proposal}，先跑 propose")
        B.append_jsonl(B.ERRORS, {"at": B.now_iso(), "key": key, "stage": "import",
                                  "errors": [f"没有提案 {proposal}"]})
        return EXIT_BLOCKED
    if not index_file.is_file():
        print(f"import {key} 被拒绝：没有已审核的索引 {index_file}")
        B.append_jsonl(B.ERRORS, {"at": B.now_iso(), "key": key, "stage": "import",
                                  "errors": [f"没有已审核的索引 {index_file}"]})
        return EXIT_BLOCKED
    report = I.import_index(key)
    print(f"import {key}：{report['stage']}  题数 {report['question_count']}  "
          f"回读通过 {report['readback_verified']}")
    for warning in report["warnings"]:
        print(f"  ~ {warning}")
    for error in report["errors"]:
        print(f"  ! {error}")
    I.record(report)
    return EXIT_OK if report["exit_code"] == 0 else EXIT_FAILED


def stage_cleanup(key: str) -> int:
    report = C.cleanup(key)
    print(f"cleanup {key}：{report['stage']}  删除 {len(report['deleted'])} 个  "
          f"释放 {report['freed_bytes']} 字节")
    for problem in report["problems"]:
        print(f"  ! {problem}")
    return report["exit_code"]


def stage_status(key: str) -> int:
    info, problems = pdf_report(key, seed=False)
    entry, source = S.entry(key)
    print(f"status {key}")
    print(f"  状态来源: {source}")
    print(f"  stage: {entry.get('stage')!r}  "
          f"import_succeeded={entry.get('import_succeeded')}  "
          f"readback_verified={entry.get('readback_verified')}")
    print(f"  临时目录: {info['tmp_dir']}  存在={info['exists']}")
    for role in ("qp", "ms"):
        value = info.get(role)
        print(f"  {role.upper()}: " + (f"{value['filename']} {value['bytes']} 字节"
                                       if isinstance(value, dict) else "缺失"))
    print(f"  提案: {proposal_path(key)}  存在={proposal_path(key).is_file()}")
    print(f"  永久索引: {I.index_path(key)}  存在={I.index_path(key).is_file()}")
    problems2, _ = C.check_conditions(key)
    if problems2:
        print("  清理条件未满足：")
        for problem in problems2:
            print(f"    - {problem}")
    else:
        print("  清理条件全部满足")
    for problem in problems:
        print(f"  ~ {problem}")
    return EXIT_OK


def main() -> int:
    _stdout_utf8()
    parser = argparse.ArgumentParser(description="按阶段驱动单份试卷的流程")
    parser.add_argument("key", help="subject/year/season/paper")
    parser.add_argument("--stage", required=True,
                        choices=["fetch", "propose", "import", "cleanup", "status"])
    parser.add_argument("--force", action="store_true", help="propose 阶段强制重渲染")
    args = parser.parse_args()
    try:
        if args.stage == "fetch":
            return stage_fetch(args.key)
        if args.stage == "propose":
            return stage_propose(args.key, args.force)
        if args.stage == "import":
            return stage_import(args.key)
        if args.stage == "cleanup":
            return stage_cleanup(args.key)
        return stage_status(args.key)
    except (ValueError, OSError) as exc:
        print(f"[失败] {exc}")
        B.append_jsonl(B.ERRORS, {"at": B.now_iso(), "key": args.key,
                                  "stage": args.stage, "errors": [str(exc)]})
        return EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
