"""r7 scope: list questions whose label unit != printed-truth unit, per affected doc.

Reads tmp_r7_truth.json (printed codes). Writes:
- tmp_r7_scope.jsonl : one line per affected question (all its rows included)
- tmp_r7_points.json : truth unit -> candidate points [{code,name,text}]
Prints per-doc counts + cross-check vs expected.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.corpus import load_points

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"

EXPECTED = {
    1728: 46, 1737: 58, 1752: 4, 1753: 42, 2342: 5, 2378: 1,
    3250: 11, 3255: 21, 3256: 12, 3257: 21, 3263: 5, 3268: 6, 3270: 15,
    3271: 3, 3273: 9, 3274: 8, 3290: 26, 3291: 4, 3294: 2, 3297: 8,
    3318: 38, 3319: 21,
    3106: 1, 3109: 1, 3112: 4, 3113: 2, 3115: 9, 3116: 9, 3117: 10,
    3118: 5, 3120: 1, 3121: 1, 3122: 1, 3123: 2, 3130: 3, 3143: 2,
    3146: 3, 3150: 10, 3155: 2, 3156: 4, 3157: 1, 3164: 1, 3167: 1, 3168: 2,
}


def main() -> None:
    truth_all = json.loads((ROOT / 'tmp_r7_truth.json').read_text(encoding='utf-8'))['truth']
    eng = create_engine(DB_URL)
    s = Session(eng)
    points = load_points(s)
    point_by_node = {p.node_id: p for p in points}
    by_unit: dict[str, list] = {}
    for p in points:
        if p.unit_code:
            by_unit.setdefault(p.unit_code.upper(), []).append(p)

    scope_lines: list[dict] = []
    used_units: set[str] = set()
    per_doc: dict[int, dict] = {}
    for doc_key, t in truth_all.items():
        did = int(doc_key)
        truth = (t.get('unit') or '').upper()
        if not truth:
            print(f'!! doc{did}: NO TRUTH UNIT, skip')
            continue
        d = s.get(m.Document, did)
        papers = list(s.scalars(select(m.Paper).where(m.Paper.document_id == d.id)))
        qs: list = []
        for p in papers:
            qs.extend(s.scalars(select(m.Question).where(m.Question.paper_id == p.id)))
        qs.sort(key=lambda q: q.id)
        wrong_rows = 0
        n_aff_q = 0
        multi_aff = 0
        partial_aff = 0
        for q in qs:
            rows = list(s.scalars(select(m.QuestionTaxonomy).where(
                m.QuestionTaxonomy.question_id == q.id)))
            if not rows:
                continue
            row_info = []
            has_wrong = False
            for r in rows:
                pt = point_by_node.get(r.node_id)
                unit = (pt.unit_code or '?').upper() if pt else '?'
                row_info.append({
                    'code': pt.code if pt else None, 'unit': unit,
                    'assigned_by': r.assigned_by, 'confidence': r.confidence,
                    'reviewed': bool(r.reviewed)})
                if unit != truth:
                    has_wrong = True
                    wrong_rows += 1
            if has_wrong:
                n_aff_q += 1
                if len(rows) > 1:
                    multi_aff += 1
                if len(rows) > 1 and any(ri['unit'] == truth for ri in row_info):
                    partial_aff += 1
                used_units.add(truth)
                scope_lines.append({
                    'subject': t['subject'], 'doc_id': did, 'doc_title': t['title'],
                    'truth_unit': truth, 'print_code': t.get('print_code'),
                    'question_id': q.id, 'number_label': q.number_label,
                    'paper_code': d.paper_code,
                    'stem': (q.stem_text or '')[:2000],
                    'rows': row_info,
                })
        per_doc[did] = {'subject': t['subject'], 'truth': truth, 'wrong_rows': wrong_rows,
                        'aff_q': n_aff_q, 'multi_aff': multi_aff, 'partial_aff': partial_aff,
                        'total_q': len(qs)}

    (ROOT / 'tmp_r7_scope.jsonl').write_text(
        '\n'.join(json.dumps(x, ensure_ascii=False) for x in scope_lines) + '\n', encoding='utf-8')

    pts_out = {}
    for unit in sorted(used_units):
        plist = by_unit.get(unit, [])
        pts_out[unit] = {
            'unit': unit,
            'n_points': len(plist),
            'points': [{'code': p.code, 'name': p.name, 'text': (p.text or '')[:500]}
                       for p in sorted(plist, key=lambda x: x.code)],
        }
    (ROOT / 'tmp_r7_points.json').write_text(
        json.dumps(pts_out, ensure_ascii=False, indent=1), encoding='utf-8')

    print(f'=== r7 scope: {len(scope_lines)} affected questions ===')
    total_wrong = 0
    total_exp = 0
    for did in sorted(per_doc):
        info = per_doc[did]
        exp = EXPECTED.get(did)
        flag = ''
        if exp is not None and exp != info['wrong_rows']:
            flag = f'  <<< MISMATCH expected={exp}'
        if exp is None:
            flag = '  <<< not in expected table'
        if info['wrong_rows'] > 0 or flag:
            print(f"  doc{did} [{info['subject']}] truth={info['truth']} "
                  f"wrong_rows={info['wrong_rows']} aff_q={info['aff_q']} "
                  f"multi_aff={info['multi_aff']} partial_aff={info['partial_aff']} "
                  f"q_total={info['total_q']}{flag}")
        if exp is not None:
            total_exp += exp
        total_wrong += info['wrong_rows']
    print(f'TOTAL wrong_rows={total_wrong} expected={total_exp} scope_questions={len(scope_lines)}')
    print('units used:', {u: len(v) for u, v in pts_out.items()})
    n_multi = sum(1 for x in scope_lines if len(x['rows']) > 1)
    n_partial = sum(1 for x in scope_lines
                    if len(x['rows']) > 1 and any(r['unit'] == x['truth_unit'] for r in x['rows']))
    print(f'multi-row affected questions: {n_multi}, partial(one row already right): {n_partial}')


if __name__ == '__main__':
    main()
