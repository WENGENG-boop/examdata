"""Report whether a volume's codex batches are complete against the current manifest.

Exit codes:
  0 = all batches valid (records cover every expected id, sheet lists match)
  1 = incomplete (missing/invalid batch files, none marked FAILED)
  3 = at least one .FAILED.json present (worker will retry it)
  4 = stale (manifest.index_sha256 != disk index sha, or manifest/sheets missing)

Mirrors run_batches.py's validity rule (batch size 4, manifest order) so the
chain only proceeds when run_worker would also consider the volume done.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_batches.py <subject/year/season/paper>")
        return 9
    key = sys.argv[1]
    slug = key.replace("/", "-")
    mpath = OUT_DIR / f"{slug}-manifest.json"
    if not mpath.is_file():
        print(f"stale: manifest missing {mpath}")
        return 4
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    subject, year, season, paper = key.split("/")
    index_path = (OUT_DIR.parents[1] / "indexes" / subject /
                  f"{year}-{season}-{paper}" / "cie-index.json")
    if not index_path.is_file():
        print(f"stale: index missing {index_path}")
        return 4
    import hashlib
    disk_sha = hashlib.sha256(index_path.read_bytes()).hexdigest()
    if disk_sha != manifest.get("index_sha256"):
        print(f"stale: manifest {str(manifest.get('index_sha256'))[:12]} != disk {disk_sha[:12]}")
        return 4
    sheets = manifest.get("sheets") or []
    if not sheets:
        print("stale: manifest has no sheets")
        return 4
    missing_sheets = [s["path"] for s in sheets if not Path(s["path"]).is_file()]
    if missing_sheets:
        print(f"stale: {len(missing_sheets)} sheet files missing, e.g. {missing_sheets[0]}")
        return 4

    batches = [sheets[i:i + 4] for i in range(0, len(sheets), 4)]
    incomplete: list[int] = []
    failed: list[int] = []
    for bi, batch in enumerate(batches, 1):
        expected = [i for s in batch for i in s["ids"]]
        rpath = OUT_DIR / f"{slug}-batch-{bi:02d}.json"
        fpath = OUT_DIR / f"{slug}-batch-{bi:02d}.FAILED.json"
        ok = False
        if rpath.is_file():
            try:
                data = json.loads(rpath.read_text(encoding="utf-8"))
            except Exception:
                data = None
            if isinstance(data, dict) and data.get("sheets") == [str(s["path"]) for s in batch]:
                got = [r.get("id") for r in data.get("records") or [] if isinstance(r, dict)]
                if len(got) == len(set(got)) and sorted(got) == sorted(expected):
                    ok = True
        if not ok:
            (failed if fpath.is_file() else incomplete).append(bi)
    if failed:
        print(f"failed batches: {failed} (worker retries); incomplete: {incomplete}")
        return 3
    if incomplete:
        print(f"incomplete batches: {incomplete} of {len(batches)}")
        return 1
    print(f"complete: {len(batches)} batches, "
          f"{sum(len(s['ids']) for s in sheets)} ids")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
