"""Record or compare SHA256 for TOEFL repair boundary files.

Usage:
  python hash_files.py record <out.json>
  python hash_files.py compare <before.json>
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ALLOWED = [
    "toefl-api/lib/catalog.mjs",
    "toefl-api/lib/detail.mjs",
    "toefl-api/lib/jj.mjs",
    "toefl-api/lib/kmf.mjs",
    "toefl-api/lib/search.mjs",
    "toefl-api/lib/sources.mjs",
    "toefl-api/lib/util.mjs",
    "toefl-api/toefl-cli.mjs",
    "toefl-api/tools/build_coverage.py",
    "toefl-api/tools/build_jj_index.py",
    "toefl-api/tools/build_kmf_index.py",
    "toefl-api/tools/live_evidence.sh",
    "toefl-api/tools/prefetch_jj.mjs",
    "toefl-api/tools/prefetch_kmf.mjs",
    "toefl-api/tools/prefetch_kmf_sw.mjs",
    "toefl-api/tools/verify_live_evidence.mjs",
    "examdata/src/examdata/api/toefl.py",
    "examdata/docs/TOEFL_API.md",
    "toefl-api/REPORT.md",
]

CONTROL = [
    "examdata/src/examdata/adapters/cambridge/__init__.py",
    "examdata/src/examdata/adapters/cambridge/adapter.py",
    "examdata/src/examdata/adapters/cambridge/classify.py",
    "examdata/src/examdata/adapters/edexcel/__init__.py",
    "examdata/src/examdata/adapters/edexcel/adapter.py",
    "examdata/src/examdata/adapters/edexcel/classify.py",
    "examdata/src/examdata/adapters/edexcel/servlet.py",
    "examdata/src/examdata/api/ielts.py",
    "examdata/src/examdata/api/unified.py",
    "examdata/src/examdata/api/app.py",
    "examdata/src/examdata/api/security.py",
    "ielts-api/ielts-api.mjs",
    "ielts-api/ielts-cli.mjs",
    "ielts-api/answer-matcher.mjs",
    "ielts-api/audio-matcher.mjs",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot() -> dict:
    out = {"allowed": {}, "control": {}}
    for group, files in (("allowed", ALLOWED), ("control", CONTROL)):
        for rel in files:
            path = ROOT / rel
            out[group][rel] = sha256(path) if path.is_file() else None
    return out


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in {"record", "compare"}:
        print(__doc__)
        return 2
    mode, target = sys.argv[1], Path(sys.argv[2])
    current = snapshot()
    if mode == "record":
        target.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        n = sum(len(v) for v in current.values())
        missing = [p for g in current.values() for p, h in g.items() if h is None]
        print(f"recorded {n} files -> {target}")
        if missing:
            print("MISSING:", *missing, sep="\n  ")
            return 1
        return 0
    before = json.loads(target.read_text(encoding="utf-8"))
    diffs = []
    for group in ("allowed", "control"):
        keys = sorted(set(before.get(group, {})) | set(current[group]))
        for rel in keys:
            old, new = before.get(group, {}).get(rel), current[group].get(rel)
            if old != new:
                diffs.append((group, rel, old, new))
    if not diffs:
        print(f"all files unchanged vs {target}")
        return 0
    for group, rel, old, new in diffs:
        print(f"[{group}] {rel}\n  before: {old}\n  after:  {new}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
