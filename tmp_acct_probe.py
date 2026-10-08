"""Probe: replicate prep/ingest unit resolution for ial-accounting self-judge packs."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.corpus import load_points, unit_code_from_paper

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"
eng = create_engine(DB_URL)
session = Session(eng)

sub_row = session.execute(select(m.Subject).where(m.Subject.slug == 'ial-accounting')).scalar()
keys = {(sub_row.code or '').strip().lower(), (sub_row.slug or '').strip().lower()}
keys.discard('')
points = [p for p in load_points(session) if (p.subject or '').strip().lower() in keys]
by_unit: dict[str, list] = {}
for p in points:
    by_unit.setdefault(p.unit_code, []).append(p)

print('subject:', sub_row.slug, sub_row.code)
for u in sorted(by_unit):
    print(f'  unit {u}: {len(by_unit[u])} points')

# dump full point text per unit
with open('tmp_acct_points.txt', 'w', encoding='utf-8') as fh:
    for u in sorted(by_unit):
        fh.write(f'===== {u} =====\n')
        for p in by_unit[u]:
            fh.write(f'{p.code} | {p.name}\n')
            fh.write(f'TEXT: {p.text}\n\n')

# resolve per pack
for pack in ['WAC01', 'WAC02', 'WAC11', 'WAC12']:
    path = ROOT / 'tmp_selfjudge' / 'unt' / 'ial-accounting' / f'{pack}-p01.txt'
    qids = []
    for line in open(path, encoding='utf-8'):
        mm = re.match(r'^\[(\d+)\]\s+(\d+)\s', line)
        if mm:
            qids.append(int(mm.group(2)))
    print(f'== pack {pack}: {len(qids)} qids')
    bad = 0
    for qid in qids:
        q = session.get(m.Question, qid)
        p = session.get(m.Paper, q.paper_id) if q else None
        d = session.get(m.Document, p.document_id) if p else None
        attrs_unit = (p.attrs or {}).get('unit_code') if p and isinstance(p.attrs, dict) else None
        fresh = unit_code_from_paper(p.attrs if p else None, d.paper_code if d else None)
        resolved = fresh if (fresh and fresh in by_unit) else None
        flag = '' if resolved == pack else '  <<< MISMATCH'
        if resolved != pack:
            bad += 1
        print(f'  {qid} paper={q.paper_id if q else None} code={d.paper_code if d else None} '
              f'attrs_unit={attrs_unit} fresh={fresh} resolved={resolved}{flag}')
    print(f'  -> mismatches: {bad}')
