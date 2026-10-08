"""Compact evidence + sibling-disagreement pre-screen for an r2 pack.

usage: python tmp_r2ev2.py <pack_file> <out_file>

Output per qid (whitespace collapsed):
  [qid] p=<path> m=<marks> cur=<codes> par=<parent>
  Q: stem[:280]
  MS: answer_text[:220]
  FAM: family (parent's children if parent, else this question's children), each id:path:codes
  FLAG: <reason>            (only when a mechanical signal fires)
"""
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()

WS = re.compile(r"\s+")


def sq(t, n):
    return WS.sub(" ", (t or "").strip())[:n]


def codes(qid):
    rows = c.execute("""select tn.code from question_taxonomy qt
                        join taxonomy_node tn on tn.id = qt.node_id
                        where qt.question_id = ? order by tn.code""", (qid,)).fetchall()
    return [r[0] for r in rows]


pack = Path(sys.argv[1])
out = Path(sys.argv[2])

qids = []
for ln in pack.read_text(encoding='utf-8').splitlines():
    m = re.match(r'^\[(\d+)\]\s+(\d+)\s', ln)
    if m:
        qids.append(int(m.group(2)))
qset = set(qids)

buf = []
flags = []
for qid in qids:
    info = c.execute("""select id, parent_id, number_path, marks, stem_text
                        from question where id = ?""", (qid,)).fetchone()
    if not info:
        buf.append(f"\n[qid={qid}] MISSING FROM DB")
        continue
    _, parent, npath, marks, stem = info
    cur = codes(qid)
    buf.append(f"\n[{qid}] p={npath} m={marks} cur={','.join(cur) or '-'} par={parent}")

    if parent:
        fam = c.execute("""select id, number_path, marks, stem_text from question
                           where parent_id = ? order by id""", (parent,)).fetchall()
        famlabel = f"par={parent}"
    else:
        fam = c.execute("""select id, number_path, marks, stem_text from question
                           where parent_id = ? order by id""", (qid,)).fetchall()
        famlabel = f"children of {qid}"
    stem_show = sq(stem, 280)
    buf.append(f"Q: {stem_show}")
    for r in c.execute("""select number_path, answer_text from mark_scheme_entry
                          where question_id = ? order by number_path""", (qid,)).fetchall():
        buf.append(f"MS[{r[0]}]: {sq(r[1], 220)}")
    if fam:
        parts = []
        famcodes = {}
        for sid, sp, sm, ss in fam:
            sc = codes(sid)
            mark = "<<" if sid == qid else ""
            parts.append(f"{sid}:{sp}:{','.join(sc) or '-'}{mark}")
            if sc:
                famcodes.setdefault(",".join(sc), []).append(sid)
        buf.append(f"FAM({famlabel}): " + " | ".join(parts))
        # mechanical flags
        if len(famcodes) == 1 and list(famcodes)[0] != ",".join(cur):
            # whole family shares one code, this one differs
            fl = f"{qid}: family-uniform {list(famcodes)[0]} vs cur {','.join(cur) or '-'}"
            buf.append(f"FLAG: {fl}")
            flags.append(fl)
        elif len(famcodes) > 1:
            # majority code
            best = max(famcodes.items(), key=lambda kv: len(kv[1]))
            if len(best[1]) >= 3 and len(best[1]) > len(fam) * 0.6 and best[0] != ",".join(cur):
                fl = f"{qid}: majority {best[0]} ({len(best[1])}/{len(fam)}) vs cur {','.join(cur) or '-'}"
                buf.append(f"FLAG: {fl}")
                flags.append(fl)
    if not cur:
        fl = f"{qid}: NO CURRENT CODE"
        buf.append(f"FLAG: {fl}")
        flags.append(fl)
    if len(cur) > 1:
        fl = f"{qid}: MULTI {','.join(cur)}"
        buf.append(f"FLAG: {fl}")
        flags.append(fl)

buf.append("\n\n===== FLAG SUMMARY =====")
buf.extend(flags)

out.write_text("\n".join(buf) + "\n", encoding='utf-8')
print(f"wrote {out} ({out.stat().st_size} bytes, {len(qids)} qids, {len(flags)} flags)")
for f in flags:
    print("  " + f)
