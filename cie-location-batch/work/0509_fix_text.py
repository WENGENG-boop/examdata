"""fix3: correct two OCR-verified text errors in the 0509 index (英 -> 吴).

Evidence: zoomed crops probe/phrase-iii-p09.png, phrase-iii-p15.png,
phrase-iv-p09.png, phrase-iv-p15.png (both QP variants) read "吴氏" not "英氏".
Geometry untouched; crops do not embed text.
"""
import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDX = ROOT / "indexes/0509/2026-Jun-11/cie-index.json"
BACKUP = ROOT / "work/index-backups/0509-2026-Jun-11-before-fix3.json"
EXPECT_SHA = "88768af5f709712d75c6e54121cbc24d25c3aa79de03e200efe48a6f61b4e18a"

REPLACEMENTS = [
    ("时英氏家延师儒", "时吴氏家延师儒"),
    ("鼎遂为英氏诸子师", "鼎遂为吴氏诸子师"),
]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    raw = IDX.read_bytes()
    old_sha = sha256_bytes(raw)
    print(f"index: {IDX}")
    print(f"old sha256: {old_sha}")
    if old_sha != EXPECT_SHA:
        print("ABORT: index sha differs from expected; inspect before touching.")
        return 2
    text = raw.decode("utf-8")
    for old, new in REPLACEMENTS:
        n = text.count(old)
        print(f"count({old!r}) = {n}")
        if n != 1:
            print("ABORT: occurrence count != 1")
            return 2
    if text.count("英") != 2:
        print(f"ABORT: total '英' count {text.count('英')} != 2")
        return 2
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    if "英" in text:
        print("ABORT: residual '英' after replacement")
        return 2
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    if BACKUP.exists():
        print(f"ABORT: backup already exists: {BACKUP}")
        return 2
    BACKUP.write_bytes(raw)
    print(f"backup: {BACKUP} ({len(raw)} bytes)")
    tmp = IDX.with_suffix(".json.tmp-fix3")
    tmp.write_bytes(text.encode("utf-8"))
    os.replace(tmp, IDX)
    new_raw = IDX.read_bytes()
    new_sha = sha256_bytes(new_raw)
    print(f"new sha256: {new_sha}")
    print(f"bytes: {len(raw)} -> {len(new_raw)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
