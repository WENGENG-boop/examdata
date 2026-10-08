"""r10: run the SEVERE heuristic (from tmp_r8_classify.py) on the 22 remaining
severe papers in BOTH current DB and pre-r8 backup, to decide whether each is
pre-existing or introduced by r8. Read-only.

Outputs tmp_r10_sev_cmp.out / tmp_r10_sev_cmp.json
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAPERS = [1197, 1324, 1327, 1339, 1402, 2122, 2153, 2157, 2167, 2168, 2169,
          2170, 2174, 2176, 2180, 2186, 2187, 2190, 2197, 2205, 2207, 2208]


def norm(s):
    return re.sub(r'\s+', ' ', s or '').strip()


def severe_for(con, papers):
    cur = con.cursor()
    allq = {}
    kids = {}
    for r in cur.execute(
        "SELECT id, paper_id, parent_id, number_path, stem_text FROM question WHERE stem_text IS NOT NULL"
    ):
        allq[r[0]] = r
        if r[2]:
            kids.setdefault(r[2], []).append(r[0])
    out = {}
    rows = cur.execute(
        "SELECT id, paper_id, number_path, stem_text FROM question "
        "WHERE stem_text LIKE '%Total for Question%' AND paper_id IN ("
        + ','.join('?' * len(papers)) + ")",
        papers,
    ).fetchall()
    for qid, pid, own, stem in rows:
        m = re.match(r'^(\d+)', own or '')
        if not m:
            continue
        ownN = int(m.group(1))
        nstem = norm(stem)
        markers = [(int(t.group(1)), t.start()) for t in re.finditer(r'Total for Question (\d+)', nstem)]
        others = [(M, pos) for M, pos in markers if M != ownN]
        if not others:
            continue
        first_other = min(others, key=lambda x: x[1])
        before = []
        for cid in kids.get(qid, []):
            cstem = norm(allq[cid][4])
            if not cstem:
                continue
            pos = nstem.find(cstem)
            if pos is not None and pos < first_other[1]:
                before.append((allq[cid][3], pos))
        if before:
            out.setdefault(pid, []).append({
                'qid': qid, 'path': own, 'ownN': ownN,
                'first_other': first_other, 'before': before[:6],
            })
    return out


def main():
    cur_con = sqlite3.connect(ROOT / '.data/examdata.db')
    bak_con = sqlite3.connect(ROOT / '.data/examdata.db.bak-pre-r8')
    cur_sev = severe_for(cur_con, PAPERS)
    bak_sev = severe_for(bak_con, PAPERS)

    lines = []
    js = []
    for pid in PAPERS:
        c = cur_sev.get(pid, [])
        b = bak_sev.get(pid, [])
        bpaths = {x['path'] for x in b}
        for x in c:
            pre = x['path'] in bpaths
            verdict = 'PRE-EXISTING' if pre else 'NEW-POST-R8'
            line = (f"paper {pid} q{x['qid']} [{x['path']}] marker={x['first_other']} "
                    f"before={[(p, pos) for p, pos in x['before']]} -> {verdict}")
            lines.append(line)
            js.append({'paper': pid, 'qid': x['qid'], 'path': x['path'],
                       'verdict': verdict, 'before': x['before'],
                       'backup_paths': sorted(bpaths)})
        # also report backup severe not in current
        cpaths = {x['path'] for x in c}
        for x in b:
            if x['path'] not in cpaths:
                lines.append(f"paper {pid} [{x['path']}] backup-severe but current-clean (FIXED)")

    txt = '\n'.join(lines)
    print(txt)
    (ROOT / 'tmp_r10_sev_cmp.out').write_text(txt + '\n', encoding='utf-8')
    (ROOT / 'tmp_r10_sev_cmp.json').write_text(
        json.dumps(js, ensure_ascii=False, indent=1), encoding='utf-8')
    n_pre = sum(1 for x in js if x['verdict'] == 'PRE-EXISTING')
    print(f"\nsummary: current-severe={len(js)} pre-existing={n_pre} new={len(js)-n_pre}")
    cur_con.close()
    bak_con.close()


if __name__ == '__main__':
    main()
