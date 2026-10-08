"""Collect codex batch replies into merge-ready verification records for one volume.

Usage: python collect_records.py <subject/year/season/paper> [--out PATH]

Maps every manifest region id to its codex observation and writes
<slug>-records.json for merge_agent_visual.py. The gate booleans are derived
from the reviewer's explicit judgments (never blind trues):
  boundary_checked = not edge_cut
  content_complete = (not edge_cut) and issues == []
  role_matches     = (codex role == region role)
Aborts (exit 2) on stale index hash, missing batch files, or uncovered ids.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import batchlib as B

OUT_DIR = B.WORK / "codex_verify"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    key = args.key
    slug = key.replace("/", "-")

    mpath = OUT_DIR / f"{slug}-manifest.json"
    if not mpath.is_file():
        print(f"ABORT: manifest missing: {mpath}")
        return 2
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    subject, year, season, paper = key.split("/")
    idx = B.index_dir(subject, int(year), season, paper) / "cie-index.json"
    idx_sha = B.sha256_file(idx)
    if idx_sha != manifest["index_sha256"]:
        print(f"ABORT: index changed since render "
              f"(manifest {manifest['index_sha256'][:12]} != disk {idx_sha[:12]})")
        return 2

    replies: dict[str, tuple[dict, str]] = {}
    batch_files = sorted(p for p in OUT_DIR.glob(f"{slug}-batch-*.json")
                         if not p.name.endswith(".FAILED.json"))
    if not batch_files:
        print("ABORT: no batch results")
        return 2
    for bf in batch_files:
        data = json.loads(bf.read_text(encoding="utf-8"))
        for rec in data.get("records") or []:
            rid = rec.get("id")
            if rid in replies:
                print(f"ABORT: duplicate id {rid} in {bf.name}")
                return 2
            replies[rid] = (rec, bf.name)

    regions = manifest["regions"]
    missing = [r["id"] for r in regions if r["id"] not in replies]
    if missing:
        print(f"ABORT: {len(missing)} regions lack a codex record: {missing[:8]}")
        return 2

    stamp = B.now_iso()
    sheet_sha: dict[str, str] = {}
    out_records: list[dict] = []
    for r in regions:
        rec, bfile = replies[r["id"]]
        role = r["role"]
        crole = rec.get("role")
        edge_cut = rec.get("edge_cut") is True
        raw_issues = rec.get("issues")
        if not isinstance(raw_issues, list):
            issues = ["codex issues 字段缺失或类型错误"]
        else:
            issues = [str(i) for i in raw_issues]
        observed = str(rec.get("observed") or "").strip()
        if not observed:
            issues = issues + ["codex observed 为空"]
            observed = "(codex 未给出观察描述)"
        sheet = r["sheet"]
        if sheet not in sheet_sha:
            sheet_sha[sheet] = B.sha256_file(sheet)
        out_records.append({
            "key": key, "question": r["question"], "role": role, "page": r["page"],
            "bbox": r["bbox"],
            "method": "local_image_visual",
            "checked_at": stamp,
            "issues": issues,
            "image": sheet, "image_sha256": sheet_sha[sheet],
            "index_sha256": idx_sha,
            "checks": {"content_complete": (not edge_cut) and not issues,
                       "boundary_checked": not edge_cut,
                       "role_matches": crole == role,
                       "observed": observed},
            "codex": {"batch": bfile, "role": crole, "edge_cut": edge_cut,
                      "question_numbers": rec.get("question_numbers"),
                      "marks_visible": rec.get("marks_visible"),
                      "diagram_present": rec.get("diagram_present"),
                      "text_head": rec.get("text_head")},
        })

    outp = Path(args.out) if args.out else OUT_DIR / f"{slug}-records.json"
    B.atomic_write_json(outp, out_records)
    nbad = sum(1 for r in out_records if r["issues"])
    nrole = sum(1 for r in out_records if not r["checks"]["role_matches"])
    print(f"{key}: records={len(out_records)} with_issues={nbad} "
          f"role_mismatch={nrole} -> {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
