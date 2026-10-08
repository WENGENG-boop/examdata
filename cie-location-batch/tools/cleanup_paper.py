"""删除某份试卷的临时文件（PDF、渲染图、裁剪图、草稿），只在六项条件全部成立时执行。

六项条件（代码逐条检查）：
a. `indexes/<subject>/<year>-<season>-<paper>/cie-index.json` 存在且通过 validate_index
b. `verification.jsonl` 里该 key 的**每个题号、每个区域、两个角色**都有 `issues == []` 的记录
c. `papers.json` 里该 key 的 stage 是 imported_verified，且没有 conflict / validation_partial
d. `papers.json` 有 `import_succeeded: true`
e. `papers.json` 有 `readback_verified: true`
f. `errors.jsonl` 里该 key 没有未解决的错误记录

安全规则（都在代码里强制）：
- 每个目标解析成绝对路径；不在 `BATCH_ROOT/tmp/<subject>/<year>-<season>-<paper>/` 内的**拒绝**
- 逐段检查路径，遇到符号链接 / junction / 重解析点**拒绝**
- 只删白名单名字：原件 `.pdf`、`*.part`、`pages/*.png`、`crops/*.png`（含 `crops/probe*/*.png`）、
  `footers`/`ms-pages`/`probe*`/`crops2` 下的 `*.png`、`ocr`/`ocr_manual` 下的
  `*.png`/`*.txt`/`*.tsv`、OCR 中间产物
  (`_ocr_list.txt`/`_ocr_out.tsv`/`_idx_list.txt`/`_idx_out.tsv`)、该 key 的提案与页表草稿
- 一次一个 `Path.unlink()`，绝不 `rmtree`，绝不递归删 `BATCH_ROOT`
- 删完复查；有残留就写 cleanup_failed 并带残留大小、退出非零
"""
from __future__ import annotations

import argparse
import collections
import io
import json
import os
import re
import stat
import sys
from pathlib import Path

import batchlib as B
import paperlib as P
import pipelinestate as S
import validate_index as V

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_RESIDUAL = 2

CLEAN_STAGES = ("imported_verified",)
BLOCKING_STAGES = ("conflict", "validation_partial", "validation_failed", "import_failed",
                   "readback_failed")
ROMAN_ORDER = ("i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x")
# run_ocr / ocr_index 会把中间产物写在本卷 tmp 目录里，也必须随卷清掉。
SCRATCH_NAMES = frozenset({"_ocr_list.txt", "_ocr_out.tsv", "_idx_list.txt", "_idx_out.tsv"})
SCRATCH_GLOBS = ("probe_*.json", "_probe*.png", "_probe*.json")

# verification.jsonl 里自述「这一区域其实没做视觉核验」的措辞。命中即挡清理。
NO_VISUAL_CHECK_MARKERS = ("未做视觉核验", "未视觉核验", "未做视觉", "PAGE_NOT_READY",
                           "没有做视觉核验", "视觉核验未完成", "未做 page.visual.snapshot")
VISUAL_METHODS = frozenset({"browser_visual_snapshot", "local_image_visual"})


def visual_evidence(record: dict) -> bool:
    """目视核验需记录完整内容、边界、角色对应及具体观察，不以 OCR 通过替代。

    content_complete 包括题干、公式、必要图形/表格和续页；role_matches
    对 MS 表示确实对应本题评分内容。仅检查标签可见不足以完成复核。
    这些字段必须由实际查看图像的复核步骤写入，OCR 工具不得自动补为 true。
    """
    checks = record.get("checks")
    return (record.get("method") in VISUAL_METHODS
            and isinstance(checks, dict)
            and all(checks.get(k) is True for k in
                    ("content_complete", "boundary_checked", "role_matches"))
            and isinstance(checks.get("observed"), str)
            and bool(checks["observed"].strip()))


def current_index_sha256(key: str) -> str | None:
    subject, year, season, paper = key.split("/")
    path = B.index_dir(subject, int(year), season, paper) / "cie-index.json"
    return B.sha256_file(path) if path.is_file() else None


def _stdout_utf8() -> None:
    enc = (getattr(sys.stdout, "encoding", "") or "").replace("-", "").lower()
    if enc != "utf8" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            out.append(record)
    return out


def is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    attrs = getattr(info, "st_file_attributes", 0)
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def unsafe_component(root: Path, target: Path) -> str | None:
    """逐段检查 target 相对 root 的每个组件是否是符号链接/junction。"""
    try:
        rel = target.relative_to(root)
    except ValueError:
        return f"{target} 不在 {root} 内"
    current = root
    if is_reparse_point(current):
        return f"{current} 本身是链接/重解析点"
    for part in rel.parts:
        current = current / part
        if current.exists() and is_reparse_point(current):
            return f"{current} 是链接/重解析点"
    return None


def collect_targets(key: str) -> list[Path]:
    """白名单内的临时文件；不递归、不猜名字。"""
    tmp_dir = P.paper_tmp(key)
    if not tmp_dir.is_dir():
        return []
    targets: list[Path] = []
    for entry in sorted(tmp_dir.iterdir()):
        if entry.is_file() and (entry.suffix.lower() == ".pdf"
                                or entry.name.endswith(".part")
                                or entry.name in SCRATCH_NAMES
                                or any(entry.match(g) for g in SCRATCH_GLOBS)):
            targets.append(entry)
    for sub in ("pages", "crops", "crops2", "footers", "ms-pages",
                "probe", "probe2", "probe3", "probe4"):
        directory = tmp_dir / sub
        if directory.is_dir():
            targets += [p for p in sorted(directory.glob("*.png")) if p.is_file()]
    crops_dir = tmp_dir / "crops"
    if crops_dir.is_dir():
        for nested in sorted(crops_dir.glob("probe*")):
            if nested.is_dir():
                targets += [p for p in sorted(nested.glob("*.png")) if p.is_file()]
    for sub in ("ocr", "ocr_manual"):
        directory = tmp_dir / sub
        if directory.is_dir():
            for entry in sorted(directory.iterdir()):
                if entry.is_file() and entry.suffix.lower() in (".png", ".txt", ".tsv"):
                    targets.append(entry)
    subject, year, season, paper = key.split("/")
    stem = f"{year}-{season}-{paper}"
    for scratch in (B.WORK / "proposals" / subject / f"{stem}.json",
                    B.WORK / "sheets" / f"{key.replace('/', '-')}-crops-1.html"):
        if scratch.is_file():
            targets.append(scratch)
    for sheet in sorted((B.WORK / "sheets").glob(f"{key.replace('/', '-')}-*.html")):
        if sheet.is_file() and sheet not in targets:
            targets.append(sheet)
    return targets


def voided_before(key: str) -> list[str]:
    """返回该 key 的 `verification_correction` 作废时间点（升序）。

    作废是追加式的：不删也不改历史记录，而是写一条
    `{"stage":"verification_correction","key":...,"at":...}`，声明该时刻之前
    该 key 的 verification 记录全部作废（例如记录本身承认没做视觉核验）。
    """
    stamps = [str(r.get("at", "")) for r in read_jsonl(B.VERIFICATION)
              if r.get("key") == key
              and (r.get("stage") == "verification_correction"
                   or r.get("kind") == "verification_correction")]
    return sorted(s for s in stamps if s)


def bbox_key(value) -> tuple:
    try:
        return tuple(round(float(v), 2) for v in value)
    except (TypeError, ValueError):
        return ()


def record_key(record: dict) -> tuple:
    try:
        page = int(record.get("page") or 0)
    except (TypeError, ValueError):
        page = 0
    return (str(record.get("question")), str(record.get("role")), page,
            bbox_key(record.get("bbox")))


def index_regions(key: str) -> dict[tuple, dict]:
    """当前永久索引里的区域集合，键与 verification.jsonl 的记录同构。"""
    subject, year, season, paper = key.split("/")
    path = B.index_dir(subject, int(year), season, paper) / "cie-index.json"
    out: dict[tuple, dict] = {}
    if not path.is_file():
        return out
    data = json.loads(path.read_bytes().decode("utf-8"))
    for question in data.get("questions") or []:
        if not isinstance(question, dict):
            continue
        qid = str(question.get("question"))
        for role in ("qp", "ms"):
            for region in question.get(role) or []:
                if not isinstance(region, dict) or not region.get("bbox"):
                    continue
                try:
                    page = int(region.get("page"))
                except (TypeError, ValueError):
                    continue
                out[(qid, role, page, bbox_key(region["bbox"]))] = {
                    "question": qid, "role": role, "page": page,
                    "bbox": list(region["bbox"])}
    return out


def numbering_problems(key: str) -> tuple[list[str], dict]:
    """题号连续性检查：顶层题号必须 1..N 连续，每个父题的 (a)(b)… / (i)(ii)… 也必须连续。

    区域核验只检查「索引里已经有的区域」，发现不了索引本身整条漏题。实测
    0413/2026/Jun/11 就丢过第 1 题（题号列 OCR 漏读 `1`），而当时全部区域核验都过。
    未知的漏题 / 跳号按提示词算未完成，必须挡在这里。
    """
    subject, year, season, paper = key.split("/")
    path = B.index_dir(subject, int(year), season, paper) / "cie-index.json"
    if not path.is_file():
        return [], {}
    data = json.loads(path.read_bytes().decode("utf-8"))
    tops: list[int] = []
    kids: dict[str, list[str]] = collections.defaultdict(list)
    for question in data.get("questions") or []:
        if not isinstance(question, dict):
            continue
        qid = str(question.get("question"))
        parent = question.get("parent")
        if parent:
            kids[str(parent)].append(qid)
            continue
        m = re.match(r"^(\d+)$", qid)
        if m:
            tops.append(int(m.group(1)))
    problems: list[str] = []
    gaps: list[int] = []
    dups: list[int] = []
    if tops:
        gaps = sorted(set(range(1, max(tops) + 1)) - set(tops))
        if gaps:
            problems.append("顶层题号跳号/漏题：缺 "
                            + "、".join(str(g) for g in gaps)
                            + f"（现有 {len(tops)} 题，最大号 {max(tops)}）")
        # 窄条二次 OCR 是「补读」逻辑：同一行被整页 OCR 和窄条各读一次时会去重，
        # 但若坐标估计偏了就可能把同一题号补成两条。重复号意味着区域归属不可信。
        dups = sorted(k for k, v in collections.Counter(tops).items() if v > 1)
        if dups:
            problems.append("顶层题号重复："
                            + "、".join(str(d) for d in dups)
                            + f"（共 {len(tops)} 条顶层记录）")
    bad_subs: list[str] = []
    for parent in sorted(kids, key=lambda p: (len(p), p)):
        tokens = []
        for cid in kids[parent]:
            if cid.startswith(parent + "(") and cid.endswith(")"):
                tokens.append(cid[len(parent) + 1:-1])
            else:
                tokens.append(None)
        singles = [t for t in tokens if t and len(t) == 1 and t.isalpha()]
        # 单字母子题先按「纯字母序列」整段试算：a..k 这类含 i 的字母序列在真题里真实存在
        # （i 同时也是罗马数字；旧口径把 i 从 letters 里剔除后，a..k 必然与 a..j 对不上 → 误报）。
        # 只有整段不连续时，才回退到「排除罗马数字」的旧口径再判一次，真实缺口照样能抓到。
        letters_ok = sorted(singles) == [chr(ord("a") + i) for i in range(len(singles))]
        letters = [t for t in singles if t not in ROMAN_ORDER]
        if not letters_ok and letters:
            expected = [chr(ord("a") + i) for i in range(len(letters))]
            if sorted(letters) != expected:
                bad_subs.append(f"{parent} 子题号不连续 {sorted(letters)}")
        romans = [t for t in tokens if t in ROMAN_ORDER]
        if romans:
            expected = list(ROMAN_ORDER[:len(romans)])
            if sorted(romans, key=ROMAN_ORDER.index) != expected:
                bad_subs.append(f"{parent} 子子题号不连续 {romans}")
    if bad_subs:
        problems.append("子题号跳号/漏题：" + "；".join(bad_subs[:6])
                        + ("…" if len(bad_subs) > 6 else ""))
    stats = {"top_level": len(tops), "gaps": gaps, "dups": dups,
             "sub_gaps": len(bad_subs)}
    return problems, stats


def verification_state(key: str, questions: list[str]) -> tuple[list[str], dict]:
    """按**当前索引里的区域**核对每个区域的最新一条核验记录。

    `verification.jsonl` 是累积追加的：索引一旦重新生成，bbox 就会变。旧的失败记录
    如果按 (question, role, page) 粗粒度合并进来，会把已经修好的区域永远卡在
    `cleanup_refused`。所以这里只认「当前索引里存在的区域」，且每个区域只取时间戳
    最新的那一条。
    """
    voids = voided_before(key)
    regions = index_regions(key)
    latest: dict[tuple, dict] = {}
    missing: list[tuple] = []
    voided = 0
    stale = 0
    for record in read_jsonl(B.VERIFICATION):
        if record.get("key") != key:
            continue
        if record.get("stage") == "verification_correction" \
                or record.get("kind") == "verification_correction":
            continue
        stamp = str(record.get("checked_at") or record.get("at") or "")
        if any(stamp < v for v in voids):
            voided += 1
            continue
        rkey = record_key(record)
        if rkey not in regions:
            # `__documents__` 记录只在索引声明了某 role 却找不到 PDF 时才会写；
            # 它不属于「必须核验」的区域，但一旦出现就是硬失败，单独统计。
            if record.get("question") == "__documents__" and record.get("issues") != []:
                missing.append(rkey)
                continue
            stale += 1
            continue
        prev = latest.get(rkey)
        if prev is None or str(prev.get("checked_at") or prev.get("at") or "") <= stamp:
            latest[rkey] = record
    failed = [rk for rk, rec in latest.items() if rec.get("issues") != []]
    # 自我声明的「没做视觉核验」：早期几卷把占位记录也写进了 verification.jsonl，
    # issues 里自述浏览器快照不可用（PAGE_NOT_READY）或行位置没看。这类区域即便
    # issues 非空也不足以放行删除，必须单列出来挡住清理。
    current_sha = current_index_sha256(key)
    missing_visual = [rk for rk, rec in latest.items() if not visual_evidence(rec)
                      or not current_sha or rec.get("index_sha256") != current_sha]
    unverified = [rk for rk, rec in latest.items()
                  if any(n in json.dumps(rec.get("issues") or [], ensure_ascii=False)
                         + json.dumps(rec.get("notes") or "", ensure_ascii=False)
                         + str(rec.get("method") or "")
                         for n in NO_VISUAL_CHECK_MARKERS)]
    missing += [rk for rk in regions if rk not in latest]
    stats = {"regions": len(regions), "verified": len(latest),
             "passed": len(latest) - len(failed), "failed": len(failed),
             "missing": len(missing), "stale_ignored": stale, "voided": voided,
             "records": len(latest), "self_declared_unverified": len(unverified),
             "visual_evidence_missing": len(missing_visual)}
    problems = []
    if not regions:
        problems.append("永久索引里没有任何区域可核对")
        return problems, stats
    if not latest:
        problems.append("verification.jsonl 里没有该 key 当前区域的记录")
        return problems, stats
    if missing:
        shown = [f"{q}/{r}/p{p}" for q, r, p, _b in missing[:6]]
        problems.append(f"有 {len(missing)} 个区域没有核验记录：{'、'.join(shown)}"
                        + ("…" if len(missing) > 6 else ""))
    if failed:
        shown = [f"{q}/{r}/p{p}" for q, r, p, _b in failed[:6]]
        problems.append(f"有 {len(failed)} 个区域未通过：{'、'.join(shown)}"
                        + ("…" if len(failed) > 6 else ""))
    if missing_visual:
        shown = [f"{q}/{r}/p{p}" for q, r, p, _b in missing_visual[:6]]
        problems.append(f"有 {len(missing_visual)} 个区域缺少完整目视核验证据：{'、'.join(shown)}"
                        + ("…" if len(missing_visual) > 6 else ""))
    if unverified:
        shown = [f"{q}/{r}/p{p}" for q, r, p, _b in unverified[:6]]
        problems.append(f"有 {len(unverified)} 个区域自述未做视觉核验：{'、'.join(shown)}"
                        + ("…" if len(unverified) > 6 else ""))
    numbering, numbering_stats = numbering_problems(key)
    stats["numbering"] = numbering_stats
    problems += numbering
    return problems, stats


def unresolved_errors(key: str, since: str | None) -> list[dict]:
    out = []
    for record in read_jsonl(B.ERRORS):
        if record.get("key") != key:
            continue
        if record.get("resolved") is True:
            continue
        if since and str(record.get("at", "")) < since:
            continue
        out.append(record)
    return out


def check_conditions(key: str) -> tuple[list[str], dict]:
    problems: list[str] = []
    info: dict = {}

    subject, year, season, paper = key.split("/")
    index_file = B.index_dir(subject, int(year), season, paper) / "cie-index.json"
    info["index_path"] = str(index_file)
    if not index_file.is_file():
        problems.append(f"永久索引不存在：{index_file}")
        questions: list[str] = []
    else:
        report = V.validate(index_file)
        info["index_engine"] = report["engine"]
        info["index_questions"] = report["questions"]
        if report["errors"]:
            problems.append(f"永久索引校验失败：{report['errors'][:3]}")
        questions = [q.get("question") for q in
                     (json.loads(index_file.read_bytes().decode("utf-8"))
                      .get("questions") or []) if isinstance(q, dict)]

    entry, source = S.entry(key)
    info["state_source"] = source
    info["paper_entry_present"] = source != "none"
    if source == "none":
        problems.append("papers.json 与 work/state.json 里都没有该 key 的条目")
        entry = {}
    stage = entry.get("stage")
    info["stage"] = stage
    if stage not in CLEAN_STAGES:
        problems.append(f"stage 不是 {CLEAN_STAGES}，而是 {stage!r}")
    if stage in BLOCKING_STAGES:
        problems.append(f"stage {stage!r} 属于未解决状态")
    if entry.get("conflict"):
        problems.append(f"papers.json 记录了 conflict：{entry.get('conflict')!r}")
    if entry.get("validation_partial"):
        problems.append("papers.json 记录了 validation_partial")
    if entry.get("import_succeeded") is not True:
        problems.append("papers.json 没有 import_succeeded: true")
    if entry.get("readback_verified") is not True:
        problems.append("papers.json 没有 readback_verified: true")

    v_problems, v_stats = verification_state(key, questions)
    info["verification"] = v_stats
    problems += v_problems

    since = entry.get("stage_at") or entry.get("service_stage_at")
    bad = unresolved_errors(key, since)
    info["unresolved_errors"] = len(bad)
    if bad:
        problems.append(f"errors.jsonl 有 {len(bad)} 条未解决错误（最近："
                        f"{bad[-1].get('stage')} {str(bad[-1].get('errors'))[:120]}）")
    return problems, info


def delete_targets(key: str, targets: list[Path]) -> tuple[list[str], list[str], int]:
    tmp_dir = P.paper_tmp(key)
    deleted: list[str] = []
    refused: list[str] = []
    freed = 0
    for target in targets:
        absolute = Path(os.path.abspath(target))
        if not str(absolute).startswith(str(Path(os.path.abspath(tmp_dir))) + os.sep) \
                and not str(absolute).startswith(str(Path(os.path.abspath(B.WORK))) + os.sep):
            refused.append(f"{absolute} 不在允许的目录内")
            continue
        bad = unsafe_component(B.BATCH_ROOT, absolute)
        if bad:
            refused.append(bad)
            continue
        try:
            size = absolute.stat().st_size
        except OSError:
            size = 0
        try:
            absolute.unlink()
        except OSError as exc:
            refused.append(f"{absolute} 删除失败：{exc}")
            continue
        freed += size
        deleted.append(str(absolute))
    return deleted, refused, freed


def cleanup(key: str, force: bool = False) -> dict:
    report: dict = {"key": key, "stage": None, "problems": [], "deleted": [],
                    "refused": [], "residual": [], "freed_bytes": 0,
                    "exit_code": EXIT_OK, "conditions": {}}
    problems, info = check_conditions(key)
    report["conditions"] = info
    report["problems"] = problems
    if problems and not force:
        pending = collect_targets(key)
        report["target_count"] = len(pending)
        report["pending_bytes"] = sum(t.stat().st_size for t in pending if t.exists())
        report["stage"] = "cleanup_refused"
        report["exit_code"] = EXIT_REFUSED
        return report

    targets = collect_targets(key)
    report["target_count"] = len(targets)
    B.append_jsonl(B.CLEANUP, {"at": B.now_iso(), "key": key, "stage": "cleanup_pending",
                               "targets": [str(t) for t in targets],
                               "target_bytes": sum(t.stat().st_size for t in targets
                                                   if t.exists())})
    deleted, refused, freed = delete_targets(key, targets)
    report["deleted"] = deleted
    report["refused"] = refused
    report["freed_bytes"] = freed

    residual = [str(p) for p in targets if p.exists()]
    report["residual"] = residual
    if residual:
        residual_bytes = sum(Path(p).stat().st_size for p in residual if Path(p).exists())
        report["stage"] = "cleanup_failed"
        report["exit_code"] = EXIT_RESIDUAL
        B.append_jsonl(B.CLEANUP, {"at": B.now_iso(), "key": key, "stage": "cleanup_failed",
                                   "residual": residual, "residual_bytes": residual_bytes,
                                   "refused": refused})
        return report
    report["stage"] = "cleaned"
    B.append_jsonl(B.CLEANUP, {"at": B.now_iso(), "key": key, "stage": "cleaned",
                               "deleted": len(deleted), "freed_bytes": freed,
                               "refused": refused})
    S.set_stage(key, "cleaned", cleaned_at=B.now_iso(), freed_bytes=freed)
    B.set_checkpoint(last_cleanup=key, last_cleanup_at=B.now_iso())
    return report


def main() -> int:
    _stdout_utf8()
    parser = argparse.ArgumentParser(description="删除某份试卷的临时文件")
    parser.add_argument("key", help="subject/year/season/paper")
    parser.add_argument("--force", action="store_true",
                        help="跳过六项条件检查（危险，仅用于清理已知残留）")
    args = parser.parse_args()
    report = cleanup(args.key, args.force)
    print(f"清理 {args.key}：{report['stage']}")
    print(f"  条件 {json.dumps(report['conditions'], ensure_ascii=False)}")
    print(f"  目标 {report.get('target_count', 0)} 个  删除 {len(report['deleted'])} 个  "
          f"释放 {report['freed_bytes']} 字节"
          + (f"  待删 {report['pending_bytes']} 字节" if "pending_bytes" in report else ""))
    for problem in report["problems"]:
        print(f"  ! {problem}")
    for refusal in report["refused"]:
        print(f"  ! 拒绝 {refusal}")
    for residual in report["residual"]:
        print(f"  ! 残留 {residual}")
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
