#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按 window15 四卷 verdict JSON 应用索引编辑：幂等 + 先断言后修改 + 全或无写入。

覆盖：8386/2025/Jun/11、8386/2026/Jun/12、8386/2026/Jun/13、0495/2026/Jun/11。
任何 mismatch（前置值不符）→ 该文件整体不写；未写文件统计进 log。

用法（从 C:/Users/weo/Desktop/api 执行）：
  examdata/.venv/Scripts/python.exe cie-location-batch/work/coordinate-audit-2026-10-05/edit_4_indexes.py [--dry-run]

输出：编辑日志 work/coordinate-audit-2026-10-05/edit-log-<ts>.json
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BATCH = Path("C:/Users/weo/Desktop/api/cie-location-batch")
A = BATCH / "work" / "coordinate-audit-2026-10-05"
TZ = timezone(timedelta(hours=8))

FILES = {
    "8386/2025/Jun/11": BATCH / "indexes/8386/2025-Jun-11/cie-index.json",
    "8386/2026/Jun/12": BATCH / "indexes/8386/2026-Jun-12/cie-index.json",
    "8386/2026/Jun/13": BATCH / "indexes/8386/2026-Jun-13/cie-index.json",
    "0495/2026/Jun/11": BATCH / "indexes/0495/2026-Jun-11/cie-index.json",
}
PRE_SHA = {
    "8386/2025/Jun/11": "973c2a8f66c76b1be5afe485a3cca28418e7043884eddddab581d74d07aab395",
    "8386/2026/Jun/12": "a3ddeac074053a128bb948dfe111351a026268da108acc329081ce65b782a25e",
    "8386/2026/Jun/13": "ff027e92fb1632232e8ef07bd7cb5b2085c06ed3d37070914514e49da29eef7d",
    "0495/2026/Jun/11": "7e56051c33295238015a405b626fd05d3df2e178bb802dee910f3c8a86c462d8",
}

V25 = "work/coordinate-audit-2026-10-05/8386-2025-11-numbering-verdict.json"
V12 = "work/coordinate-audit-2026-10-05/8386-2026-12-numbering-verdict.json"
V13 = "work/coordinate-audit-2026-10-05/8386-2026-13-numbering-verdict.json"
V0495 = "work/coordinate-audit-2026-10-05/0495-2026-11-numbering-verdict.json"

LOG: list[dict] = []


def rec(key: str, action: str, status: str, detail: str = "") -> None:
    LOG.append({"key": key, "action": action, "status": status, "detail": detail})
    print(f"  [{status:8s}] {key} | {action} | {detail}", flush=True)


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def region(page: int, bbox: list) -> dict:
    return {"page": page, "bbox": list(bbox)}


def find_q(qs: list, name: str):
    for q in qs:
        if q.get("question") == name:
            return q
    return None


def region_replace(q: dict, role: str, page: int, before: list, after: list) -> str:
    regions = q.get(role)
    if not isinstance(regions, list):
        return "mismatch"
    for r in regions:
        if r.get("page") == page and r.get("bbox") == list(before):
            r["bbox"] = list(after)
            return "applied"
    for r in regions:
        if r.get("page") == page and r.get("bbox") == list(after):
            return "skipped"
    return "mismatch"


def region_delete(q: dict, role: str, page: int, bbox: list) -> str:
    regions = q.get(role)
    if not isinstance(regions, list):
        return "mismatch"
    for i, r in enumerate(regions):
        if r.get("page") == page and r.get("bbox") == list(bbox):
            del regions[i]
            return "applied"
    if any(r.get("page") == page for r in regions):
        return "mismatch"
    return "skipped"


def set_ms_list(q: dict, before: list, after: list) -> str:
    cur = q.get("ms")
    if cur == after:
        return "skipped"
    if cur == before:
        q["ms"] = after
        return "applied"
    return "mismatch"


def fix_empty_ms(q: dict, target: list, notes_new: str) -> str:
    """空 ms + uncertain=true → 补区域并解除 uncertain；幂等。"""
    if q.get("ms") == target and q.get("uncertain") is False and q.get("notes") == notes_new:
        return "skipped"
    if q.get("ms") == [] and q.get("uncertain") is True:
        q["ms"] = target
        q["uncertain"] = False
        q["notes"] = notes_new
        return "applied"
    return "mismatch"


def ensure_block(qs: list, records: list, before_name: str | None = None,
                 at_start: bool = False) -> list[str]:
    """整块幂等插入。全存在且全等 → skipped；全不存在 → 插入；混合 → mismatch。"""
    existing = [find_q(qs, r["question"]) for r in records]
    if all(e is not None for e in existing):
        ok = all(e == r for e, r in zip(existing, records))
        return ["skipped" if ok else "mismatch"] * len(records)
    if any(e is not None for e in existing):
        return ["mismatch"] * len(records)
    if at_start:
        qs[0:0] = records
    elif before_name is not None:
        for i, q in enumerate(qs):
            if q.get("question") == before_name:
                qs[i:i] = records
                break
        else:
            return ["mismatch"] * len(records)
    return ["applied"] * len(records)


def summarize_diff(old_qs: list, new_qs: list) -> list[str]:
    changes: list[str] = []
    old_map = {q.get("question"): q for q in old_qs}
    new_map = {q.get("question"): q for q in new_qs}
    for name, nq in new_map.items():
        if name not in old_map:
            changes.append(f"+{name}")
            continue
        oq = old_map[name]
        for f in ("parent", "text", "marks", "qp", "ms", "uncertain", "notes"):
            if oq.get(f) != nq.get(f):
                changes.append(f"~{name}.{f}")
    for name in old_map:
        if name not in new_map:
            changes.append(f"-{name}")
    return changes


def check_p9_qp(qs: list) -> bool:
    found = []
    for q in qs:
        for r in q.get("qp") or []:
            if r.get("page") == 9:
                found.append((q.get("question"), r.get("bbox")))
    expected = [("2", [239.6, 16.4, 541.2, 748.4]), ("2(e)", [239.6, 16.4, 541.2, 748.4])]
    print(f"  12/13 qp page==9 区域: {found}")
    if not found:
        return True
    return sorted(repr(x) for x in found) == sorted(repr(x) for x in expected)


# ---------------------------------------------------------------- 2025-11 ---

def new_25_records() -> list[dict]:
    return [
        {"question": "1", "parent": None,
         "text": "(a) The diagram shows a … / (b) A coach may use rein…",
         "marks": None,
         "qp": [region(2, [70.4, 58.8, 541.2, 761.6])],
         "ms": [region(7, [102.1, 61.6, 354.4, 729.2])],
         "uncertain": False,
         "notes": f"text 为 OCR 前缀片段拼接（不完整：(a) 与 (b) 各一段）；2026-10-06 补建卷内缺失的顶层题 1（QP p2、MS p7）；判词与测量见 {V25}"},
        {"question": "1(a)", "parent": "1",
         "text": "(a) The diagram shows a",
         "marks": 6,
         "qp": [region(2, [70.4, 58.8, 541.2, 490.0])],
         "ms": [region(7, [102.1, 61.6, 244.9, 729.2])],
         "uncertain": False,
         "notes": f"text 为 OCR 前缀片段（不完整）；2026-10-06 补建顶层题 1 子题 (a)（marks=6，QP p2 上半、MS p7 左列）；见 {V25}"},
        {"question": "1(b)", "parent": "1",
         "text": "(b) A coach may use rein",
         "marks": 3,
         "qp": [region(2, [70.4, 490.0, 541.2, 761.6])],
         "ms": [region(7, [244.9, 61.6, 354.4, 729.2])],
         "uncertain": False,
         "notes": f"text 为 OCR 前缀片段（不完整）；2026-10-06 补建顶层题 1 子题 (b)（marks=3，QP p2 下半、MS p7 右列）；见 {V25}"},
    ]


NOTES_25_FIX = {
    "3(a)(i)": f"text 来自 Windows.Media.Ocr(zh-Hans-CN) 转录，可能有识别噪声（说明继承自父题 3(a)）；2026-10-06 复核：MS p7 x∈[474.4,497.2] 为其独立评分条带，已补建 ms 区域并解除 uncertain；见 {V25}",
    "4(a)(i)": f"text 来自 Windows.Media.Ocr(zh-Hans-CN) 转录，可能有识别噪声（说明继承自父题 4(a)）；2026-10-06 复核：MS p9 x∈[102.1,160.4] 为其独立评分条带，已补建 ms 区域并解除 uncertain；见 {V25}",
    "5(a)(i)": f"text 来自 Windows.Media.Ocr(zh-Hans-CN) 转录，可能有识别噪声（说明继承自父题 5(a)）；2026-10-06 复核：MS p10 第二表 x∈[461.6,523.6] 为其独立评分行，已补建 ms 区域并解除 uncertain；见 {V25}",
}


def edit_2025(d: dict, key: str) -> bool:
    qs = d["questions"]
    ok = True

    print("  -- 新增 1 / 1(a) / 1(b)（插到最前）")
    for name, status in zip([r["question"] for r in new_25_records()],
                            ensure_block(qs, new_25_records(), at_start=True)):
        rec(key, f"ensure {name}", status)
        ok &= status in ("applied", "skipped")

    mods = [
        ("2", "ms", 7, [354.4, 61.6, 497.2, 729.2], [354.4, 61.6, 474.4, 729.2]),
        ("2(c)", "ms", 7, [412.4, 61.6, 497.2, 729.2], [412.4, 61.6, 474.4, 729.2]),
        ("3", "ms", 7, [497.2, 61.6, 534.0, 729.2], [474.4, 61.6, 534.0, 729.2]),
        ("3(a)", "ms", 7, [497.2, 61.6, 534.0, 729.2], [474.4, 61.6, 534.0, 729.2]),
        ("4(a)", "ms", 9, [160.4, 61.6, 254.0, 729.2], [102.1, 61.6, 254.0, 729.2]),
        ("4", "ms", 9, [160.4, 61.6, 458.4, 729.2], [102.1, 61.6, 458.4, 729.2]),
        ("4(c)", "ms", 10, [102.0, 61.6, 523.6, 729.2], [102.0, 61.6, 438.4, 729.2]),
        ("4", "ms", 10, [78.8, 61.6, 523.6, 729.2], [78.8, 61.6, 438.4, 729.2]),
    ]
    print("  -- 区域 x0/x1 修正")
    for name, role, page, before, after in mods:
        q = find_q(qs, name)
        status = "mismatch" if q is None else region_replace(q, role, page, before, after)
        rec(key, f"x-fix {name} {role} p{page} {before}→{after}", status)
        ok &= status in ("applied", "skipped")

    print("  -- 删除错误传播条带")
    for name, role, page, bbox in [
        ("3", "ms", 9, [78.8, 61.6, 160.4, 729.2]),
        ("3(d)", "ms", 9, [78.8, 61.6, 160.4, 729.2]),
    ]:
        q = find_q(qs, name)
        status = "mismatch" if q is None else region_delete(q, role, page, bbox)
        rec(key, f"del {name} {role} p{page} {bbox}", status)
        ok &= status in ("applied", "skipped")

    print("  -- 5 / 5(a) ms 整表追加 p10")
    for name, before, after in [
        ("5", [region(11, [102.0, 61.6, 352.8, 729.2])],
         [region(10, [461.6, 61.6, 523.6, 729.2]), region(11, [102.0, 61.6, 352.8, 729.2])]),
        ("5(a)", [region(11, [102.0, 61.6, 136.8, 729.2])],
         [region(10, [461.6, 61.6, 523.6, 729.2]), region(11, [102.0, 61.6, 136.8, 729.2])]),
    ]:
        q = find_q(qs, name)
        status = "mismatch" if q is None else set_ms_list(q, before, after)
        rec(key, f"ms-set {name} +p10", status)
        ok &= status in ("applied", "skipped")

    print("  -- 空 ms 补独立评分区（uncertain→false）")
    for name, target in [
        ("3(a)(i)", [region(7, [474.4, 61.6, 497.2, 729.2])]),
        ("4(a)(i)", [region(9, [102.1, 61.6, 160.4, 729.2])]),
        ("5(a)(i)", [region(10, [461.6, 61.6, 523.6, 729.2])]),
    ]:
        q = find_q(qs, name)
        status = "mismatch" if q is None else fix_empty_ms(q, target, NOTES_25_FIX[name])
        rec(key, f"ms-add {name} +uncertain→false", status)
        ok &= status in ("applied", "skipped")

    return ok


# ------------------------------------------------------------ 2026-12 / 13 ---

def new_26_records(verdict_path: str) -> list[dict]:
    tail = f"见 {verdict_path}"
    parent_note = f"text 为 OCR 转录片段（不完整）；2026-10-06 补建卷内缺失的顶层题 1（QP p2–p5、MS p7–p11）；判词与测量见 {verdict_path}"
    base = [
        ("1", None, "(a) The photographs show a goalkeeper in association football … (h) Explain factors that lead to high levels of participatio…", None,
         [region(2, [92.4, 58.8, 540.4, 709.6]), region(3, [92.4, 58.8, 541.2, 748.4]),
          region(4, [92.4, 58.8, 540.4, 537.2]), region(5, [92.4, 58.8, 541.2, 748.4])],
         [region(7, [102.1, 67.9, 434.7, 729.2]), region(8, [102.1, 62.3, 423.6, 729.2]),
          region(9, [102.1, 89.6, 434.7, 729.2]), region(10, [102.1, 61.4, 351.4, 729.2]),
          region(11, [102.1, 62.3, 506.9, 729.2])],
         parent_note),
        ("1(a)", "1", "(a) The photographs show a goalkeeper in association football", 6,
         [region(2, [92.4, 58.8, 540.4, 549.2])], [region(7, [102.1, 67.9, 232.2, 729.2])],
         f"text 为 OCR 转录片段（不完整）；2026-10-06 补建顶层题 1 子题 (a)；{tail}"),
        ("1(b)", "1", "(b) Suggest strategies that could be used to improve the re…", 3,
         [region(2, [92.4, 549.2, 540.4, 709.6])], [region(7, [232.2, 67.9, 434.7, 729.2])],
         f"text 为 OCR 转录片段（不完整）；2026-10-06 补建顶层题 1 子题 (b)；{tail}"),
        ("1(c)", "1", "(c) Explain the use of Schmidt's schema theory to develop go…", 5,
         [region(3, [92.4, 58.8, 541.2, 389.2])], [region(8, [102.1, 62.3, 423.6, 729.2])],
         f"text 为 OCR 转录片段（不完整）；2026-10-06 补建顶层题 1 子题 (c)；{tail}"),
        ("1(d)", "1", "(d) A goalkeeper may kick a ball along the ground. Describe…", 4,
         [region(3, [92.4, 389.2, 541.2, 748.4])], [region(9, [102.1, 89.6, 244.1, 729.2])],
         f"text 为 OCR 转录片段（不完整）；2026-10-06 补建顶层题 1 子题 (d)；{tail}"),
        ("1(e)", "1", "(e) A goalkeeper may also kick a stationary ball high into t…", 4,
         [region(4, [92.4, 58.8, 540.4, 425.6])], [region(9, [244.1, 89.6, 434.7, 729.2])],
         f"text 为 OCR 转录片段（不完整）；2026-10-06 补建顶层题 1 子题 (e)；{tail}"),
        ("1(f)", "1", "(f) State three factors affecting the horizontal displacement…", 3,
         [region(4, [92.4, 425.6, 540.4, 537.2])], [region(10, [102.1, 61.4, 244.1, 729.2])],
         f"text 为 OCR 转录片段（不完整）；2026-10-06 补建顶层题 1 子题 (f)；{tail}"),
        ("1(g)", "1", "(g) Many aspects of the sport of association football are pr…", 5,
         [region(5, [92.4, 58.8, 541.2, 364.4])], [region(10, [244.1, 61.4, 351.4, 729.2])],
         f"text 为 OCR 转录片段（不完整）；2026-10-06 补建顶层题 1 子题 (g)；{tail}"),
        ("1(h)", "1", "(h) Explain factors that lead to high levels of participatio…", 5,
         [region(5, [92.4, 364.4, 541.2, 748.4])], [region(11, [102.1, 62.3, 506.9, 729.2])],
         f"text 为 OCR 转录片段（不完整）；2026-10-06 补建顶层题 1 子题 (h)；{tail}"),
    ]
    out = []
    for name, parent, text, marks, qp, ms, notes in base:
        out.append({"question": name, "parent": parent, "text": text, "marks": marks,
                    "qp": qp, "ms": ms, "uncertain": False, "notes": notes})
    return out


def edit_2026(d: dict, key: str, verdict_path: str) -> bool:
    qs = d["questions"]
    ok = True

    if not check_p9_qp(qs):
        rec(key, "precheck qp page==9", "mismatch", "p9 区域集合与预期不符，拒绝编辑")
        return False
    rec(key, "precheck qp page==9", "skipped", "预期仅 2 / 2(e) 各一条")

    print("  -- 新增 1 / 1(a)–1(h)（插到最前）")
    recs = new_26_records(verdict_path)
    for name, status in zip([r["question"] for r in recs], ensure_block(qs, recs, at_start=True)):
        rec(key, f"ensure {name}", status)
        ok &= status in ("applied", "skipped")

    print("  -- 删除空白页 p9 错误区域")
    for name in ("2", "2(e)"):
        q = find_q(qs, name)
        status = "mismatch" if q is None else region_delete(q, "qp", 9, [239.6, 16.4, 541.2, 748.4])
        rec(key, f"del {name} qp p9 [239.6,16.4,541.2,748.4]", status)
        ok &= status in ("applied", "skipped")

    return ok


# ----------------------------------------------------------------- 0495 ---

def edit_0495(d: dict, key: str) -> bool:
    qs = d["questions"]
    ok = True

    print("  -- 新增 2(a)(i) / 3(a)(i)")
    n2ai = {"question": "2(a)(i)", "parent": "2(a)", "text": "(i) lifestyle [ 2 ]", "marks": 2,
            "qp": [region(4, [70.4, 134.5, 539.2, 162.4])],
            "ms": [region(24, [101.6, 65.2, 222.8, 729.2])],
            "uncertain": False,
            "notes": f"text 为卷面 OCR 前缀片段；2026-10-06 补建 2(a)(i)（旧索引仅建 (ii)）；MS p24 实为两行独立评分，行分界线 x=222.8，目视核验；见 {V0495}"}
    n3ai = {"question": "3(a)(i)", "parent": "3(a)", "text": "(i) open society [ 2 ]", "marks": 2,
            "qp": [region(5, [70.8, 109.2, 539.2, 137.2])],
            "ms": [region(33, [101.6, 65.2, 222.8, 729.2])],
            "uncertain": False,
            "notes": f"text 为卷面 OCR 前缀片段；2026-10-06 补建 3(a)(i)（旧索引仅建 (ii)）；MS p33 实为两行独立评分，行分界线 x=222.8，目视核验；见 {V0495}"}

    for rec_dict, before_name in ((n2ai, "2(a)(ii)"), (n3ai, "3(a)(ii)")):
        status = ensure_block(qs, [rec_dict], before_name=before_name)[0]
        rec(key, f"ensure {rec_dict['question']}（before {before_name}）", status)
        ok &= status in ("applied", "skipped")

    return ok


# ------------------------------------------------------------------ main ---

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只演练，不写文件不写日志")
    args = ap.parse_args()

    ts = datetime.now(TZ).strftime("%Y%m%dT%H%M%S")
    results = {}
    all_ok = True

    for key, path in FILES.items():
        print(f"== {key} ({path.name})")
        if not path.exists():
            rec(key, "load", "mismatch", "文件不存在")
            all_ok = False
            continue
        cur_sha = sha256_file(path)
        if cur_sha != PRE_SHA[key]:
            rec(key, "pre-sha guard", "mismatch",
                f"当前 sha={cur_sha[:16]}… 与 pre={PRE_SHA[key][:16]}… 不符，拒绝编辑")
            all_ok = False
            continue
        rec(key, "pre-sha guard", "skipped", f"sha={cur_sha[:16]}…（=pre）")

        d = json.loads(path.read_bytes().decode("utf-8"))
        old_qs = json.loads(json.dumps(d["questions"]))  # deep copy for diff
        n_before = len(d["questions"])

        if key == "8386/2025/Jun/11":
            ok = edit_2025(d, key)
        elif key == "8386/2026/Jun/12":
            ok = edit_2026(d, key, V12)
        elif key == "8386/2026/Jun/13":
            ok = edit_2026(d, key, V13)
        else:
            ok = edit_0495(d, key)

        n_after = len(d["questions"])
        print(f"  -- 题数 {n_before} → {n_after}")

        if not ok:
            rec(key, "WRITE", "mismatch", "存在 mismatch，该文件整体不写")
            all_ok = False
            continue

        if args.dry_run:
            rec(key, "WRITE", "skipped", f"dry-run：将写 {n_before}→{n_after} 条")
            continue

        out = json.dumps(d, indent=2, ensure_ascii=False) + "\n"
        path.write_bytes(out.encode("utf-8"))
        json.loads(path.read_bytes().decode("utf-8"))  # re-parse guard
        new_sha = sha256_file(path)
        diff = summarize_diff(old_qs, d["questions"])
        rec(key, "WRITE", "applied",
            f"{n_before}→{n_after} 条；post_sha={new_sha}")
        rec(key, "diff", "applied", "; ".join(diff) if diff else "无字段差异")
        results[key] = {"pre_sha": cur_sha, "post_sha": new_sha,
                        "before": n_before, "after": n_after, "diff": diff}

    log_dir = A
    if not args.dry_run:
        logfile = log_dir / f"edit-log-{ts}.json"
        logfile.write_text(json.dumps(
            {"at": datetime.now(TZ).isoformat(timespec="seconds"),
             "dry_run": False, "files": results, "operations": LOG},
            indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\n日志: {logfile}")

    mismatches = [x for x in LOG if x["status"] == "mismatch"]
    print(f"\n结论: {'全部完成' if not mismatches else f'{len(mismatches)} 个 mismatch'} "
          f"（{'dry-run' if args.dry_run else '实写'}）")
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
