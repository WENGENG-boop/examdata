"""把子代理的逐项观察（obs-sXX.jsonl）编译成可落盘的复核记录。

输入：
  review/worklist-sXX.json   工作清单（含 paper/role/index_sha256/items）
  review/obs-sXX.jsonl       子代理逐项观察（region + page_pair）

输出：
  review/staged-sXX.jsonl        region 记录，格式与 verification.jsonl 完全一致
  review/pair-evidence-sXX.jsonl page_pair 旁证（不写 verification.jsonl）
  review/compile-report-sXX.json 机器可读编译报告

校验（任一失败即 exit 2，不产出 staged）：
  - obs 覆盖 worklist 全部 seq，不重不漏，kind/file/题号/页码/bbox 一致
  - region：checks 全 true、observed >= 30 字、issues 空
  - staged 的 (question, role, page, bbox) 必须存在于当前永久索引区域集合
  - 绑定 worklist.index_sha256，落盘前由 apply_review.py 复核 sha 未变
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REVIEW = Path(__file__).resolve().parent / "review"
BATCH_TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(BATCH_TOOLS))

import batchlib as B  # noqa: E402
import cleanup_paper as C  # noqa: E402


def bbox2(value) -> tuple:
    try:
        return tuple(round(float(v), 2) for v in value)
    except (TypeError, ValueError):
        return ()


def load_obs(path: Path) -> tuple[dict, list[str]]:
    rows: dict[int, dict] = {}
    problems: list[str] = []
    if not path.exists():
        return {}, [f"观察文件不存在：{path}"]
    for lineno, line in enumerate(path.read_bytes().decode("utf-8", "replace").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"第 {lineno} 行不是合法 JSON：{exc}")
            continue
        seq = row.get("seq")
        if not isinstance(seq, int):
            problems.append(f"第 {lineno} 行缺少 int seq")
            continue
        if seq in rows:
            problems.append(f"seq {seq} 重复出现（第 {lineno} 行）")
            continue
        rows[seq] = row
    return rows, problems


def main() -> int:
    parser = argparse.ArgumentParser(description="编译 review 观察为 staged 记录")
    parser.add_argument("slice_id", help="如 s07")
    args = parser.parse_args()
    slice_id = args.slice_id

    worklist = B.read_json(REVIEW / f"worklist-{slice_id}.json")
    if not worklist:
        print(f"工作清单不存在或为空：worklist-{slice_id}.json")
        return 2
    paper = worklist["paper"]
    sha = worklist["index_sha256"]
    items = {int(i["seq"]): i for i in worklist["items"]}

    obs, problems = load_obs(REVIEW / f"obs-{slice_id}.jsonl")
    missing = sorted(set(items) - set(obs))
    extra = sorted(set(obs) - set(items))
    if missing:
        problems.append(f"缺少 {len(missing)} 个 seq：{missing[:20]}")
    if extra:
        problems.append(f"多出未知 seq：{extra[:20]}")

    staged: list[dict] = []
    pairs: list[dict] = []
    warnings: list[str] = []
    seen_keys: set[tuple] = set()

    for seq in sorted(set(items) & set(obs)):
        item, row = items[seq], obs[seq]
        ctx = f"seq {seq}"
        ctx_problems: list[str] = []
        if row.get("kind") != item["kind"]:
            ctx_problems.append(f"{ctx}: kind 不一致 {row.get('kind')!r} != {item['kind']!r}")
        if row.get("file") != item["file"]:
            ctx_problems.append(f"{ctx}: file 不一致 {row.get('file')!r}")
        if row.get("role") != item["role"]:
            ctx_problems.append(f"{ctx}: role 不一致")
        if ctx_problems:
            problems.extend(ctx_problems)
            continue

        if item["kind"] == "region":
            for field in ("question", "page"):
                if row.get(field) != item[field]:
                    ctx_problems.append(f"{ctx}: {field} 不一致 {row.get(field)!r} != {item[field]!r}")
            if bbox2(row.get("bbox")) != bbox2(item.get("bbox")):
                ctx_problems.append(f"{ctx}: bbox 不一致 {row.get('bbox')!r}")
            checks = row.get("checks") or {}
            for key in ("content_complete", "boundary_checked", "role_matches"):
                if checks.get(key) is not True:
                    ctx_problems.append(f"{ctx}: checks.{key} 非 true")
            observed = row.get("observed")
            if not isinstance(observed, str):
                observed = checks.get("observed")
            if not isinstance(observed, str) or len(observed.strip()) < 30:
                ctx_problems.append(f"{ctx}: observed 缺失或过短（<30 字）")
            if row.get("issues") != []:
                ctx_problems.append(f"{ctx}: issues 缺失或非空：{row.get('issues')!r}")
            if ctx_problems:
                problems.extend(ctx_problems)
                continue
            record = {
                "key": paper,
                "question": str(item["question"]),
                "role": item["role"],
                "page": int(item["page"]),
                "bbox": [round(float(v), 2) for v in item["bbox"]],
                "method": "browser_visual_snapshot",
                "checks": {
                    "content_complete": True,
                    "boundary_checked": True,
                    "role_matches": True,
                    "observed": observed,
                },
                "issues": [],
                "checked_at": B.now_iso(),
                "index_sha256": sha,
            }
            rkey = C.record_key(record)
            if rkey in seen_keys:
                warnings.append(f"{ctx}: staged 区域键重复 {rkey}")
            seen_keys.add(rkey)
            staged.append(record)

        elif item["kind"] == "page_pair":
            if row.get("pages") != item.get("pages"):
                problems.append(f"{ctx}: pages 不一致 {row.get('pages')!r}")
            observed = row.get("observed")
            if not isinstance(observed, str) or len(observed.strip()) < 30:
                problems.append(f"{ctx}: observed 缺失或过短（<30 字）")
            if row.get("issues") != []:
                warnings.append(f"{ctx}: page_pair issues 非空：{row.get('issues')!r}")
            mq = row.get("missing_questions") or []
            if mq:
                warnings.append(f"{ctx}: missing_questions 非空：{mq}")
            pairs.append({
                "key": paper,
                "role": item["role"],
                "pages": item.get("pages"),
                "file": item["file"],
                "observed": observed,
                "missing_questions": mq,
                "issues": row.get("issues"),
                "checked_at": B.now_iso(),
                "index_sha256": sha,
            })
        else:
            problems.append(f"{ctx}: 未知 kind {item['kind']!r}")

    # staged 区域键必须存在于当前永久索引区域集合；顺带报告整卷区域覆盖数
    problems_now = list(problems)
    regions = C.index_regions(paper)
    unknown = [C.record_key(r) for r in staged if C.record_key(r) not in regions]
    if unknown:
        problems_now.append(f"staged 有 {len(unknown)} 个键不在当前索引区域集合：{unknown[:8]}")

    report = {
        "slice": slice_id,
        "paper": paper,
        "index_sha256": sha,
        "items_total": len(items),
        "regions_staged": len(staged),
        "pairs_recorded": len(pairs),
        "index_regions_total": len(regions),
        "staged_unique_keys": len(seen_keys),
        "warnings": warnings,
        "problems": problems_now,
    }
    if problems_now:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"编译失败：{len(problems_now)} 个问题，未产出 staged 文件。")
        B.atomic_write_json(REVIEW / f"compile-report-{slice_id}.json", report)
        return 2

    out = REVIEW / f"staged-{slice_id}.jsonl"
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        for record in staged:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    with open(REVIEW / f"pair-evidence-{slice_id}.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for record in pairs:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    B.atomic_write_json(REVIEW / f"compile-report-{slice_id}.json", report)
    print(json.dumps({k: report[k] for k in
                      ("slice", "paper", "items_total", "regions_staged", "pairs_recorded",
                       "index_regions_total", "warnings")}, ensure_ascii=False, indent=2))
    print(f"编译通过：staged {len(staged)} 条 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
