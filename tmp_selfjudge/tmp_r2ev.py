"""Dump read-only evidence for an r2 selfjudge pack.

usage: python tmp_r2ev.py <pack_file> [out_file]

For each qid in the pack: current codes, stem, marks, parent, siblings (with
their current codes), and mark-scheme entries.
"""
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()


def codes(qid):
    rows = c.execute("""select tn.code from question_taxonomy qt
                        join taxonomy_node tn on tn.id = qt.node_id
                        where qt.question_id = ? order by tn.code""", (qid,)).fetchall()
    return [r[0] for r in rows]


def qinfo(qid):
    return c.execute("""select id, parent_id, number_path, marks, kind, stem_text
                        from question where id = ?""", (qid,)).fetchone()


def ms(qid):
    return c.execute("""select number_path, answer_text, acceptable_answers, guidance
                        from mark_scheme_entry where question_id = ?
                        order by number_path""", (qid,)).fetchall()


pack = Path(sys.argv[1])
out = Path(sys.argv[2]) if len(sys.argv) > 2 else None

qids = []
for ln in pack.read_text(encoding='utf-8').splitlines():
    m = re.match(r'^\[(\d+)\]\s+(\d+)\s', ln)
    if m:
        qids.append(int(m.group(2)))

buf = []
for qid in qids:
    info = qinfo(qid)
    if not info:
        buf.append(f"\n===== qid={qid} MISSING FROM DB\n")
        continue
    _, parent, npath, marks, kind, stem = info
    cur = codes(qid)
    buf.append(f"\n===== qid={qid} path={npath!r} marks={marks} kind={kind} parent={parent}")
    buf.append(f"CUR: {', '.join(cur) if cur else '(none)'}")
    buf.append(f"STEM: {(stem or '').strip()}")
    for r in ms(qid):
        np_, at, aa, gd = r
        buf.append(f"MS[{np_}]: {(at or '').strip()}")
        if aa:
            buf.append(f"  acc: {aa}")
        if gd:
            buf.append(f"  gd: {gd}")
    if parent:
        sibs = c.execute("""select id, number_path, marks, stem_text from question
                            where parent_id = ? order by id""", (parent,)).fetchall()
        buf.append(f"SIBS of parent {parent}:")
        for sid, sp, sm, ss in sibs:
            sc = codes(sid)
            tag = " <<<" if sid == qid else ""
            buf.append(f"  [{sid}] {sp!r} {sm}mk cur={','.join(sc) if sc else '(none)'}{tag}")
            buf.append(f"      {(ss or '').strip()[:300]}")
    else:
        # top-level: show sibling top-level questions in same paper
        pinfo = c.execute("select paper_id from question where id = ?", (qid,)).fetchone()
        if pinfo:
            sibs = c.execute("""select id, number_path, marks, stem_text from question
                                where paper_id = ? and parent_id is null
                                order by display_order""", (pinfo[0],)).fetchall()
            buf.append(f"TOP-LEVEL in paper {pinfo[0]}: {len(sibs)}")
            for sid, sp, sm, ss in sibs[:25]:
                sc = codes(sid)
                tag = " <<<" if sid == qid else ""
                buf.append(f"  [{sid}] {sp!r} {sm}mk cur={','.join(sc) if sc else '(none)'}{tag}")

text = "\n".join(buf) + "\n"
if out:
    out.write_text(text, encoding='utf-8')
    print(f"wrote {out} ({len(text)} chars, {len(qids)} qids)")
else:
    print(text)
