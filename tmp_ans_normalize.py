#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Normalize *.ans.txt answer files: split trailing inline comments onto their own line.

Ingest (tmp_selfjudge_ingest.py) requires each data line to be exactly `qid CODE`
(2 tokens). Some agent-written files append a trailing `# comment` on the same line,
which makes every data line a "bad line". This script rewrites:

    59508 WFM01-5.3  # BC = product of two matrices
into:
    59508 WFM01-5.3
    # 59508: BC = product of two matrices

Lossless: comment text preserved. Lines already clean pass through unchanged.
Usage: python tmp_ans_normalize.py <dir-or-file>... [--write]
"""
import sys
from pathlib import Path

def normalize_file(path: Path, write: bool) -> tuple:
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    fixed = 0
    weird = 0
    for ln in lines:
        stripped = ln.strip()
        if not stripped or stripped.startswith("#"):
            out.append(ln)
            continue
        parts = stripped.split(None, 1)
        if len(parts) != 2:
            # no code token at all
            weird += 1
            if weird <= 3:
                print(f"  WEIRD {path.name}: {ln!r}")
            out.append(ln)
            continue
        qid, rest = parts
        idx = rest.find("#")
        if idx < 0:
            # check it is exactly one token
            if len(rest.split()) == 1:
                out.append(ln)
            else:
                weird += 1
                if weird <= 3:
                    print(f"  WEIRD {path.name}: {ln!r}")
                out.append(ln)
            continue
        code = rest[:idx].strip()
        comment = rest[idx:].strip()
        if not code:
            weird += 1
            if weird <= 3:
                print(f"  WEIRD {path.name}: {ln!r}")
            out.append(ln)
            continue
        out.append(f"{qid} {code}")
        out.append(f"# {qid}: {comment}")
        fixed += 1
    if write and fixed:
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return fixed, weird

def main():
    args = [a for a in sys.argv[1:] if a != "--write"]
    write = "--write" in sys.argv
    targets = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            targets.extend(sorted(p.glob("*.ans.txt")))
        elif p.is_file():
            targets.append(p)
        else:
            print(f"!! not found: {a}")
    if not targets:
        print("no targets")
        return 1
    total_fixed = 0
    total_weird = 0
    for t in targets:
        fixed, weird = normalize_file(t, write)
        total_fixed += fixed
        total_weird += weird
        flag = "WRITTEN" if (write and fixed) else ("dry" if fixed else "clean")
        print(f"{t}: fixed={fixed} weird={weird} [{flag}]")
    print(f"TOTAL fixed={total_fixed} weird={total_weird} write={write}")
    return 0 if total_weird == 0 else 2

if __name__ == "__main__":
    sys.exit(main())
