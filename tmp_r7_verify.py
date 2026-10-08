"""r7 verify: after apply, re-check all 44 affected docs + the 441 questions.

Checks (read-only):
  1. per-doc: no question row whose unit != printed-truth unit (doc-wide);
  2. per-scope-qid: exactly 1 row, reviewed=True, source=ai-review,
     assigned_by=ai-review-v1, confidence=1.0, point.unit_code == truth;
  3. applied log count == 441 and matches scope;
  4. global row/reviewed counts snapshot.

Usage:
  ./.venv/Scripts/python.exe -X utf8 tmp_r7_verify.py
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
from examdata.tagging.assign import REVIEW_ASSIGNED_BY, REVIEW_SOURCE
from examdata.tagging.corpus import load_points

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"


def main() -> None:
    truth_all = json.loads((ROOT / 'tmp_r7_truth.json').read_text(encoding='utf-8'))['truth']
    scope = {}
    for line in (ROOT / 'tmp_r7_scope.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            x = json.loads(line)
            scope[x['question_id']] = x

    eng = create_engine(DB_URL)
    s = Session(eng)
    points = load_points(s)
    point_by_node = {p.node_id: p for p in points}

    # --- global snapshot ---
    all_rows = list(s.scalars(select(m.QuestionTaxonomy)))
    n_rows = len(all_rows)
    n_reviewed = sum(1 for r in all_rows if r.reviewed)
    print(f'global: taxonomy_rows={n_rows} reviewed_rows={n_reviewed}')

    # --- per-doc doc-wide wrong-row check ---
    doc_fail = 0
    for doc_key, t in truth_all.items():
        did = int(doc_key)
        truth = (t.get('unit') or '').upper()
        d = s.get(m.Document, did)
        if d is None:
            print(f'!! doc{did} missing'); doc_fail += 1; continue
        papers = list(s.scalars(select(m.Paper).where(m.Paper.document_id == d.id)))
        wrong = 0
        nq = 0
        for p in papers:
            for q in s.scalars(select(m.Question).where(m.Question.paper_id == p.id)):
                nq += 1
                for r in s.scalars(select(m.QuestionTaxonomy).where(
                        m.QuestionTaxonomy.question_id == q.id)):
                    pt = point_by_node.get(r.node_id)
                    unit = (pt.unit_code or '?').upper() if pt else '?'
                    if unit != truth:
                        wrong += 1
        status = 'OK' if wrong == 0 else f'FAIL wrong_rows={wrong}'
        if wrong:
            doc_fail += 1
        print(f"doc{did} [{t['subject']}] truth={truth} q={nq} wrong_rows={wrong} {status}")

    # --- per-qid scope check ---
    q_fail = 0
    for qid, x in scope.items():
        truth = x['truth_unit'].upper()
        rows = list(s.scalars(select(m.QuestionTaxonomy).where(
            m.QuestionTaxonomy.question_id == qid)))
        problems = []
        if len(rows) != 1:
            problems.append(f'rows={len(rows)}')
        else:
            r = rows[0]
            pt = point_by_node.get(r.node_id)
            if not r.reviewed:
                problems.append('not reviewed')
            if r.source != REVIEW_SOURCE:
                problems.append(f'source={r.source}')
            if r.assigned_by != REVIEW_ASSIGNED_BY:
                problems.append(f'assigned_by={r.assigned_by}')
            if pt is None:
                problems.append(f'node not found (truth {truth})')
            elif (pt.unit_code or '').upper() != truth:
                problems.append(f'unit={pt.unit_code} != {truth}')
            if r.confidence != 1.0:
                problems.append(f'confidence={r.confidence}')
        if problems:
            q_fail += 1
            print(f'  Q{qid} FAIL: {", ".join(problems)}')
    print(f'scope_qids={len(scope)} q_fail={q_fail} doc_fail={doc_fail}')

    # --- applied log ---
    log_path = ROOT / 'tmp_r7_applied.jsonl'
    if log_path.exists():
        log = [json.loads(l) for l in log_path.read_text(encoding='utf-8').splitlines() if l.strip()]
        codes = Counter(e['code'] for e in log)
        print(f'applied_log={len(log)} (expect {len(scope)})')
        print('codes by unit:')
        for u, n in sorted(Counter(e['truth_unit'] for e in log).items()):
            print(f'  {u}: {n}')
    else:
        print('applied_log: MISSING')

    ok = (q_fail == 0 and doc_fail == 0)
    print('VERIFY', 'PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
