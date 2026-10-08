"""Read-only r2 review dump: for each qid in a pack, show current label, old label,
family info, stem and MS. Output to stdout (or a file given as 2nd arg).

usage: python tmp_r2_dump.py <pack_file> [out_file] [max_ms_chars]
"""
import json, re, sys
from pathlib import Path
import sqlite3

ROOT = Path('.')
APPLIED = ROOT / 'tmp_jev_full_decisions' / 'ial18-physics' / 'applied.jsonl'

old_map = {}
for line in open(APPLIED, encoding='utf-8'):
    e = json.loads(line)
    if e.get('status') != 'applied' or e.get('decision') != 'change':
        continue
    m = re.search(r'与原标签（(.+?)）不符', e.get('reason') or '')
    conf = re.search(r'置信度 ([\d.]+)', e.get('reason') or '')
    old_map[e['question_id']] = (m.group(1) if m else None,
                                 float(conf.group(1)) if conf else None,
                                 e.get('code'))

pack = Path(sys.argv[1])
out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
maxms = int(sys.argv[3]) if len(sys.argv) > 3 else 700

qids = []
cur = {}
for ln in pack.read_text(encoding='utf-8').splitlines():
    m = re.match(r'^\[(\d+)\]\s+(\d+)\s+#(\S+)\s+(\S+)mk\s+cur=(\S+)', ln)
    if m:
        qids.append(int(m.group(2)))
        cur[int(m.group(2))] = m.group(5)

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
c = con.cursor()

def code_name(qid):
    r = c.execute("""SELECT tn.code, tn.name FROM question_taxonomy qt
                     JOIN taxonomy_node tn ON tn.id=qt.node_id WHERE qt.question_id=?""", (qid,)).fetchall()
    return r

out = []
for i, qid in enumerate(qids, 1):
    r = c.execute("SELECT number_label, marks, parent_id, stem_text FROM question WHERE id=?", (qid,)).fetchone()
    nl, mk, pid, stem = r
    o = old_map.get(qid)
    old = o[0] if o else None
    conf = o[1] if o else None
    new = o[2] if o else None
    fam = []
    if pid:
        pr = c.execute("SELECT number_label, marks FROM question WHERE id=?", (pid,)).fetchone()
        pt = code_name(pid)
        fam.append(f"PARENT {pid} #{pr[0]} {pr[1]}mk tax={pt}")
    kids = c.execute("SELECT id, number_label, marks FROM question WHERE parent_id=? ORDER BY id", (qid,)).fetchall()
    for k in kids:
        kt = code_name(k[0])
        fam.append(f"  child {k[0]} #{k[1]} {k[2]}mk tax={kt}")
    ms = c.execute("""SELECT number_path, marks, answer_text FROM mark_scheme_entry
                      WHERE question_id=? ORDER BY id""", (qid,)).fetchall()
    lines = []
    lines.append(f"########## [{i}] qid={qid} #{nl} {mk}mk cur={cur[qid]} | OLD={old} conf={conf} jev_new={new}")
    st = re.sub(r'\s+', ' ', stem or '')
    lines.append(f"STEM: {st[:800]}")
    for f in fam:
        lines.append(f"FAM: {f}")
    for m in ms:
        t = re.sub(r'\s+', ' ', m[2] or '')
        lines.append(f"MS [{m[0]}] {m[1]}mk: {t[:maxms]}")
    out.append('\n'.join(lines))

text = '\n'.join(out) + '\n'
if out_path:
    out_path.write_text(text, encoding='utf-8')
    print(f'{pack.name}: {len(qids)} questions -> {out_path} ({len(text)} chars)')
else:
    print(text)
