"""Sweep rendered images for visually verified volumes; keep PDFs and indexes.

Usage: python sweep_volume_images.py <subject/year/season/paper> [...] [--apply]

Per key:
- C.verification_state must be clean (no problems) -- otherwise skip and report.
- Deletes only tmp/<key>/pages/*.png and tmp/<key>/crops/*.png through
  C.delete_targets (whitelist + reparse-point checks). Never C.cleanup:
  the conflict volumes keep their PDFs until the six cleanup conditions pass.
- Appends cleanup.jsonl stage=images_swept and patches papers.json with
  images_swept_at / images_swept_bytes.

Dry-run without --apply prints the plan only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import batchlib as B
import cleanup_paper as C
import paperlib as P

NOTE = "视觉核验完成；PDF 保留（conflict 六条件未满足）"


def image_targets(key: str) -> list[Path]:
    tmp = P.paper_tmp(key)
    targets: list[Path] = []
    for sub in ("pages", "crops"):
        directory = tmp / sub
        if directory.is_dir():
            targets += [p for p in sorted(directory.glob("*.png")) if p.is_file()]
    return targets


def sweep(key: str, apply: bool) -> dict:
    subject, year, season, paper = key.split("/")
    idx = B.index_dir(subject, int(year), season, paper) / "cie-index.json"
    questions = []
    if idx.is_file():
        questions = [q.get("question") for q in
                     json.loads(idx.read_bytes().decode("utf-8")).get("questions") or []]
    problems, stats = C.verification_state(key, questions)
    targets = image_targets(key)
    total = sum(t.stat().st_size for t in targets if t.exists())
    out = {"key": key, "problems": problems, "verification": stats,
           "targets": len(targets), "bytes": total, "deleted": 0,
           "refused": [], "residual": [], "freed_bytes": 0, "stage": "dry_run"}
    if not apply:
        return out
    if problems:
        out["stage"] = "sweep_refused"
        return out
    if not targets:
        out["stage"] = "nothing_to_sweep"
        return out
    deleted, refused, freed = C.delete_targets(key, targets)
    residual = [str(p) for p in targets if p.exists()]
    out.update({"deleted": len(deleted), "refused": refused, "residual": residual,
                "freed_bytes": freed})
    if residual:
        out["stage"] = "sweep_failed"
        B.append_jsonl(B.CLEANUP, {"at": B.now_iso(), "key": key,
                                   "stage": "images_sweep_failed",
                                   "residual": residual, "refused": refused,
                                   "note": NOTE})
        return out
    out["stage"] = "images_swept"
    B.append_jsonl(B.CLEANUP, {"at": B.now_iso(), "key": key,
                               "stage": "images_swept", "deleted": len(deleted),
                               "freed_bytes": freed, "refused": refused,
                               "conditions": {"verification": stats,
                                              "problems": problems},
                               "note": NOTE})
    papers = B.read_json(B.PAPERS, {})
    if key in papers:
        papers[key]["images_swept_at"] = B.now_iso()
        papers[key]["images_swept_bytes"] = freed
        B.atomic_write_json(B.PAPERS, papers)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="+")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    rc = 0
    for key in args.keys:
        out = sweep(key, args.apply)
        print(f"{key}: stage={out['stage']} targets={out['targets']} "
              f"bytes={out['bytes']} deleted={out['deleted']} "
              f"freed={out['freed_bytes']} problems={len(out['problems'])}",
              flush=True)
        for p in out["problems"][:4]:
            print(f"  ! {p}", flush=True)
        if out["stage"] in ("sweep_failed",):
            rc = 2
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
