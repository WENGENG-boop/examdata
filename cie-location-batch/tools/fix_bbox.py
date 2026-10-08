"""Fix one region bbox in a volume's local cie-index.json (exact single match).

Usage: python fix_bbox.py <key> <question> <role> <page> '<old bbox json>' '<new bbox json>'

- Loads indexes/<subject>/<year>-<season>-<paper>/cie-index.json
- Finds exactly one region with matching question/role/page/bbox; aborts otherwise.
- Backs up the index to work/index-backups/<key>-before-fix-<n>.json (first backup kept),
  then writes the index atomically.
- Prints old and new sha256 so the change is auditable.
No network. Safe to run with base python (no pymupdf needed).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import batchlib as B
import import_index as I


def main() -> int:
    key, question, role, page_s, old_s, new_s = sys.argv[1:7]
    page = int(page_s)
    old = [float(v) for v in json.loads(old_s)]
    new = [float(v) for v in json.loads(new_s)]
    if role not in ("qp", "ms"):
        raise SystemExit("role must be qp or ms")
    path = I.index_path(key)
    data = B.read_json(path, {})
    matches = []
    for q in data["questions"]:
        if str(q["question"]) == question:
            for r in q.get(role) or []:
                if int(r["page"]) == page and [float(v) for v in r["bbox"]] == old:
                    matches.append(r)
    if len(matches) != 1:
        raise SystemExit(f"expected exactly 1 match, got {len(matches)}")
    sha_before = B.sha256_file(path)
    backup_dir = B.WORK / "index-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{key.replace('/', '-')}-before-fix.json"
    if not backup.exists():
        shutil.copy2(path, backup)
    matches[0]["bbox"] = new
    B.atomic_write_json(path, data)
    sha_after = B.sha256_file(path)
    print(json.dumps({"key": key, "question": question, "role": role, "page": page,
                      "old": old, "new": new, "sha_before": sha_before,
                      "sha_after": sha_after, "backup": str(backup)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
