# -*- coding: utf-8 -*-
"""Add the two family-consistency rows (32585, 29351 -> WCH14-15.12) to the
chem r2 batch + answer files, so the normal ingest/decisions/apply chain
picks them up. Flagged by the r2 judge; decided by the main agent:
- 32585 (role of H+ in aspirin ester synthesis): 15.15 (hydrolysis) is the
  wrong direction; family 32583/32584 -> 15.12; precedent 33501 = 15.12.
- 29351 (yield calc anchored on Reaction 1 = LiAlH4 reduction of the acid):
  sibling 29350 -> 15.12 i; 15.11 is the opposite direction.
Backups: *.bak-append next to each modified file.
"""
import json
import shutil
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BATCH_ROOT = ROOT / 'tmp_jev_full_batches_r2' / 'ial18-chemistry' / 'batches'
ANS_DIR = ROOT / 'tmp_selfjudge' / 'r2' / 'ial18-chemistry'

MANUAL = {32585: 'WCH14-15.12', 29351: 'WCH14-15.12'}
SIBLING = {32585: 32584, 29351: 29350}   # locate target batch via sibling

conn = sqlite3.connect(ROOT / '.data' / 'examdata.db')
conn.row_factory = sqlite3.Row


def row_for(qid: int, choice: str) -> dict:
    q = conn.execute(
        "SELECT number_label, stem_text FROM question WHERE id=?", (qid,)).fetchone()
    p = conn.execute(
        "SELECT d.paper_code FROM paper p JOIN document d ON d.id=p.document_id "
        "WHERE p.id=(SELECT paper_id FROM question WHERE id=?)", (qid,)).fetchone()
    t = conn.execute(
        "SELECT tn.code, tn.name FROM question_taxonomy qt "
        "JOIN taxonomy_node tn ON tn.id=qt.node_id WHERE qt.question_id=?", (qid,)).fetchone()
    assert t is not None, f'no current label for {qid}'
    assert t['code'] != choice, f'{qid} already at {choice}?'
    return {
        'current': [{'assigned_by': 'ai-review-v1', 'code': t['code'],
                     'confidence': 1.0, 'name': t['name'], 'reviewed': True}],
        'number_label': q['number_label'],
        'paper_code': p['paper_code'],
        'question_id': qid,
        'stem': q['stem_text'],
        'unit_code': 'WCH14',
    }


# 1) locate batch file per qid via sibling
targets: dict[Path, list] = {}
for qid, choice in MANUAL.items():
    sib = SIBLING[qid]
    hit = None
    for bf in sorted(BATCH_ROOT.glob('batch-*.jsonl')):
        for line in open(bf, encoding='utf-8'):
            if line.strip() and json.loads(line)['question_id'] == sib:
                hit = bf
                break
        if hit:
            break
    assert hit, f'sibling {sib} not found in any batch'
    # ensure qid itself is not already present
    for line in open(hit, encoding='utf-8'):
        if line.strip() and json.loads(line)['question_id'] == qid:
            raise SystemExit(f'{qid} already present in {hit.name}')
    targets.setdefault(hit, []).append(row_for(qid, choice))

for bf, rows in targets.items():
    shutil.copyfile(bf, str(bf) + '.bak-append')
    with open(bf, 'a', encoding='utf-8') as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f'{bf.name}: +{len(rows)} rows {[r["question_id"] for r in rows]}')

# 2) append answer lines
ANS = {32585: 'WCH14-p03.ans.txt', 29351: 'WCH14-p02.ans.txt'}
for qid, fname in ANS.items():
    ap = ANS_DIR / fname
    shutil.copyfile(ap, str(ap) + '.bak-append')
    with open(ap, 'a', encoding='utf-8') as fh:
        fh.write(f'# manual family-consistency fix (main agent): {qid} -> {MANUAL[qid]}\n')
        fh.write(f'{qid} {MANUAL[qid]}\n')
    print(f'{fname}: +{qid} {MANUAL[qid]}')

print('done')
