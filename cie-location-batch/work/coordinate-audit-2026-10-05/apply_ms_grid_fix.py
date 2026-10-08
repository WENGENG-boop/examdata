"""按"答案网格行 band"修正某卷 MS 区域（解析遗漏补建 / 吞并行收窄 / 页眉误区域移除）。

只对"答案网格型 MS"（每题的评分项就是表格里自己那一行）生效，否则拒绝执行。
证据：analyze_ms_grid.py 从 MS 页文本层取到的行文本（`N X M`）与其 y 带。
副作用：uncertain 由 true 改 false（仅限本次补齐区域的题），notes 写明依据。

用法: python apply_ms_grid_fix.py <key> [--dry-run] [--keep-uncertain]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time

sys.path.insert(0, r"C:/Users/weo/Desktop/api/cie-location-batch/tools")
import analyze_ms_grid as A  # noqa: E402
import batchlib as B  # noqa: E402
import import_index as I  # noqa: E402

DELIV = os.path.join(A.BATCH, "work", "coordinate-audit-2026-10-05", "deliverables")
BACKUP = os.path.join(A.BATCH, "work", "coordinate-audit-2026-10-05", "index-backups")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-uncertain", action="store_true")
    args = ap.parse_args()
    key = args.key

    res = A.analyze(key)
    if res.get("error"):
        print(f"拒绝：{res['error']}")
        return 2
    v = res["verdict"]
    bands = res["bands"]
    grid_qs = [q for q in bands if len(bands[q]) >= 1]
    multi = [q for q in bands if len(bands[q]) != 1]
    guards = {
        "grid_rows>0": res["grid_rows"] > 0,
        "每題恰好 1 行": not multi,
        "所有索引区域 y0 均能对上行": not v["band_mismatch_rows"],
        "没有找不到行的索引区域": not v["index_regions_without_row"],
        "网格题号集合 == 索引题号集合":
            set(bands) == {str(q["question"]) for q in
                           json.load(open(A.index_path(key), encoding="utf-8"))["questions"]},
    }
    bad = [k for k, ok in guards.items() if not ok]
    if bad:
        print("拒绝：结构不满足答案网格前提 " + "；".join(bad))
        return 2

    path = I.index_path(key)
    data = B.read_json(path, {})
    old_sha = A.sha256_file(path)

    changes = []
    for q in data["questions"]:
        qn = str(q["question"])
        want = sorted(({"page": b["page"], "bbox": [round(v, 2) for v in b["bbox"]]}
                       for b in bands.get(qn, [])), key=lambda r: (r["page"], r["bbox"][1]))
        have = sorted(({"page": int(r["page"]), "bbox": [round(float(x), 2) for x in r["bbox"]]}
                       for r in (q.get("ms") or [])), key=lambda r: (r["page"], r["bbox"][1]))
        old_snapshot = [dict(h) for h in have]
        kept = [dict(h) for h in have]
        actions = []
        removed_keys = set()
        # 1) 解析遗漏：有行但索引没有该题区域 -> 用行 band 补建
        for w in want:
            if not any(h["page"] == w["page"] and abs(h["bbox"][1] - w["bbox"][1]) < 3.0
                       for h in have):
                actions.append({"op": "add", "region": dict(w)})
                kept.append(dict(w))
        # 2) 吞并下一题：y1 明显超过本行 band -> 收窄到 band 的 y1（保留原 x、y0）
        for i, h in enumerate(kept):
            m = [w for w in want if w["page"] == h["page"]
                 and abs(w["bbox"][1] - h["bbox"][1]) < 3.0]
            if m and h["bbox"][3] - m[0]["bbox"][3] > 3.0:
                old = dict(h)
                kept[i] = {**h, "bbox": [h["bbox"][0], h["bbox"][1], h["bbox"][2],
                                         m[0]["bbox"][3]]}
                actions.append({"op": "replace", "old": old, "new": dict(kept[i])})
        # 3) 无法解释的区域（页眉/表格标题被当成续页）-> 移除
        for h in have:
            if not any(w["page"] == h["page"] and abs(w["bbox"][1] - h["bbox"][1]) < 3.0
                       for w in want):
                actions.append({"op": "remove", "region": dict(h)})
                removed_keys.add((h["page"], tuple(h["bbox"])))
        if removed_keys:
            kept = [k for k in kept
                    if (k["page"], tuple(k["bbox"])) not in removed_keys]
        if not actions:
            continue
        changes.append({"question": qn, "actions": actions, "old": old_snapshot,
                        "new": sorted(kept, key=lambda r: (r["page"], r["bbox"][1])),
                        "evidence": "; ".join(
                            f"MS p{b['page']} 行 \"{b['text']}\" y={b['row_y']}"
                            for b in bands[qn])})

    changed = {c["question"]: c for c in changes}
    total_before = sum(len(q.get("ms") or []) for q in data["questions"])
    total_after = sum(len(changed[str(q["question"])]["new"])
                      if str(q["question"]) in changed else len(q.get("ms") or [])
                      for q in data["questions"])
    print(f"{key}: 待改 {len(changes)} 题；原 ms 区域 {total_before} → {total_after}")
    ops = {}
    for c in changes:
        for a in c["actions"]:
            ops[a["op"]] = ops.get(a["op"], 0) + 1
    print("操作统计:", ops)
    log = {"key": key, "ms_sha256": res["ms_sha256"], "index_sha256_before": old_sha,
           "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "guards": guards, "ops": ops, "changes": changes}
    if args.dry_run:
        print(json.dumps({"dry_run": True, "changes": len(changes), "ops": ops},
                         ensure_ascii=False))
        return 0

    os.makedirs(BACKUP, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%S")
    bpath = os.path.join(BACKUP, f"{key.replace('/', '-')}-before-msgrid-{ts}.json")
    shutil.copy2(path, bpath)

    for c in changes:
        q = next(x for x in data["questions"] if str(x["question"]) == c["question"])
        q["ms"] = [{"page": r["page"], "bbox": [round(float(x), 2) for x in r["bbox"]]}
                   for r in c["new"]]
        if not args.keep_uncertain and c["actions"]:
            if all(a["op"] in ("add", "replace") for a in c["actions"]):
                q["uncertain"] = False
    # 未变更但已确定的题（原有区域且 y0 匹配）不动 uncertain

    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    new_sha = A.sha256_file(path)
    log["index_sha256_after"] = new_sha
    log["backup"] = bpath.replace("\\", "/")
    out = os.path.join(DELIV, f"ms-grid-fix-{key.replace('/', '_')}-{ts}.json")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=1)
    print(json.dumps({"key": key, "changed_questions": len(changes), "ops": ops,
                      "before": old_sha[:12], "after": new_sha[:12],
                      "backup": log["backup"], "log": out.replace("\\", "/")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
