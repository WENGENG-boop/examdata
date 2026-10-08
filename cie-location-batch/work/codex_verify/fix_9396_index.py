# -*- coding: utf-8 -*-
"""9396 (2023-Nov-11) index MS-region fix per verified row-map plan.

Dry-run by default. `--apply` backs up the old index to
work/codex_verify/archive-9396/ and atomically rewrites the index.

Touches ONLY: questions[].ms (all 40 questions), and marks/uncertain/notes
for the 11 previously-unlocated subquestions. Never touches documents,
identity, or qp regions.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile

BR = r"C:/Users/weo/Desktop/api/cie-location-batch"
IDX = BR + "/indexes/9396/2023-Nov-11/cie-index.json"
ARCH = BR + "/work/codex_verify/archive-9396"
Y0, Y1 = 57.2, 735.6

# question -> final MS regions [(page, x0, x1)], y always [57.2, 735.6]
TARGET = {
    "1": [(5, 102.0, 552.8), (6, 46.0, 552.8)],
    "1(a)": [(5, 102.0, 160.7)],
    "1(b)": [(5, 160.7, 219.4)],
    "1(c)": [(5, 219.4, 290.1)],
    "1(d)": [(5, 290.1, 372.5)],
    "1(e)": [(5, 372.5, 529.1), (6, 102.0, 208.4)],
    "1(e)(i)": [(5, 372.5, 478.9)],
    "1(e)(ii)": [(5, 478.9, 529.1)],
    "1(e)(iii)": [(6, 102.0, 208.4)],
    "1(f)": [(6, 208.4, 302.7)],
    "1(g)": [(6, 302.7, 506.2)],
    "1(g)(i)": [(6, 302.7, 409.1)],
    "1(g)(ii)": [(6, 408.8, 552.8)],
    "2": [(7, 102.0, 364.2), (8, 46.0, 552.8), (9, 46.0, 552.8), (10, 46.0, 554.0)],
    "2(a)": [(7, 102.0, 267.1)],
    "2(a)(i)": [(7, 102.0, 160.7)],
    "2(a)(ii)": [(7, 160.4, 266.8)],
    "2(b)": [(7, 266.8, 552.8)],
    "2(c)": [(8, 102.0, 291.7)],
    "2(c)(i)": [(8, 102.0, 291.7)],
    "2(c)(ii)": [(8, 291.6, 552.8)],
    "2(d)": [(9, 102.0, 256.4)],
    "2(e)": [(9, 256.4, 363.0)],
    "2(e)(i)": [(9, 256.4, 363.0)],
    "2(e)(ii)": [(9, 362.8, 552.8)],
    "2(f)": [(10, 102.0, 172.7)],
    "2(g)": [(10, 172.7, 316.5)],
    "2(g)(i)": [(10, 172.7, 219.4)],
    "2(g)(ii)": [(10, 219.2, 554.0)],
    "3": [(11, 267.6, 554.0), (12, 46.0, 554.0), (13, 46.0, 554.0), (14, 46.0, 554.0)],
    "3(a)": [(11, 267.6, 554.0)],
    "3(a)(i)": [(11, 102.0, 267.8)],
    "3(a)(ii)": [(11, 267.6, 554.0)],
    "3(b)": [(12, 256.0, 554.0), (13, 102.0, 246.8)],
    "3(b)(i)": [(12, 102.0, 256.0)],
    "3(b)(ii)": [(12, 256.0, 554.0)],
    "3(b)(iii)": [(13, 102.0, 256.0)],
    "3(c)": [(13, 256.0, 554.0)],
    "3(d)": [(14, 102.0, 351.2)],
    "3(e)": [(14, 351.2, 554.0)],
}

MARK_FILL = {"2(a)(i)": 2, "2(c)(i)": 4, "2(e)(i)": 2, "2(g)(i)": 1}
UNCERTAIN_FIX = ["1(b)", "1(c)", "1(e)(i)", "1(f)", "1(g)(i)",
                 "2(a)(i)", "2(c)(i)", "2(e)(i)", "2(g)(i)",
                 "3(a)(i)", "3(b)(i)"]

NEW_NOTE_TAIL = "；MS 该子题评分行已单独定位"


def fix_note(n):
    i = n.find("；MS ")
    return n[:i] + NEW_NOTE_TAIL if i >= 0 else n


def main():
    apply = "--apply" in sys.argv
    raw = open(IDX, "rb").read()
    old_sha = hashlib.sha256(raw).hexdigest()
    d = json.loads(raw.decode("utf-8"))
    qs = d["questions"]
    assert len(qs) == 40, len(qs)

    n_keep = n_mod = n_del = n_add = 0
    for q in qs:
        tq = q["question"]
        assert tq in TARGET, tq
        old = [(r["page"], r["bbox"][0], r["bbox"][2]) for r in q.get("ms", [])]
        new = TARGET[tq]
        old_by_page = {p: (x0, x1) for (p, x0, x1) in old}
        new_by_page = {p: (x0, x1) for (p, x0, x1) in new}
        parts = []
        for (p, x0, x1) in old:
            if p in new_by_page:
                nx0, nx1 = new_by_page[p]
                if abs(nx0 - x0) < 1e-9 and abs(nx1 - x1) < 1e-9:
                    parts.append(f"keep p{p}[{x0},{x1}]")
                    n_keep += 1
                else:
                    parts.append(f"MOD p{p}[{x0},{x1}]->[{nx0},{nx1}]")
                    n_mod += 1
            else:
                parts.append(f"DEL p{p}[{x0},{x1}]")
                n_del += 1
        for (p, x0, x1) in new:
            if p not in old_by_page:
                parts.append(f"ADD p{p}[{x0},{x1}]")
                n_add += 1
        extra = []
        if tq in MARK_FILL:
            cur = q.get("marks")
            assert cur is None, (tq, cur)
            extra.append(f"marks None->{MARK_FILL[tq]}")
        if tq in UNCERTAIN_FIX:
            assert q.get("uncertain") is True, tq
            old_note = q.get("notes") or ""
            new_note = fix_note(old_note)
            assert new_note != old_note, tq
            extra.append("uncertain True->False")
            extra.append(f"notes: {new_note}")
        line = f"Q {tq}: " + (" ".join(parts) if parts else "(no ms regions)")
        if extra:
            line += "  | " + " ; ".join(extra)
        print(line)

    total_old = sum(len(q.get("ms", [])) for q in qs)
    total_new = sum(len(v) for v in TARGET.values())
    print()
    print(f"regions: old={total_old} keep={n_keep} mod={n_mod} del={n_del} add={n_add} -> new={total_new}")
    assert total_old == 54 and total_new == 49, "unexpected totals"
    assert n_del == 16 and n_add == 11, "unexpected del/add"

    if not apply:
        print("dry-run only; pass --apply to write")
        return

    os.makedirs(ARCH, exist_ok=True)
    bak = os.path.join(ARCH, f"cie-index.pre-fix.{old_sha[:12]}.json")
    shutil.copy2(IDX, bak)
    print("backup:", bak)

    for q in qs:
        tq = q["question"]
        q["ms"] = [{"page": p, "bbox": [x0, Y0, x1, Y1]} for (p, x0, x1) in TARGET[tq]]
        if tq in MARK_FILL:
            q["marks"] = MARK_FILL[tq]
        if tq in UNCERTAIN_FIX:
            q["uncertain"] = False
            q["notes"] = fix_note(q.get("notes") or "")

    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(IDX), prefix=".cie-index.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, IDX)
    new_sha = hashlib.sha256(open(IDX, "rb").read()).hexdigest()
    print("APPLIED old_sha:", old_sha)
    print("APPLIED new_sha:", new_sha)


if __name__ == "__main__":
    main()
