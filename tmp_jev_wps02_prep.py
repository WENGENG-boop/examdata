"""Prep the WPS02 targeted mini-review batch (4 IV/DV questions).

Targets 61530/61531/65108/66196 (see tmp_audit_5items_conclusion.md [32]).
Writes tmp_jev_wps02/ial-psychology/batches/batch-001.jsonl in the same record
shape as the untagged export so the standard three-script chain can consume it:

  ./.venv/Scripts/python.exe -X utf8 tmp_jev_batch.py --subject ial-psychology \
      --batches-dir tmp_jev_wps02/ial-psychology/batches \
      --out tmp_jev_wps02_ial-psychology.jsonl --skip-problems
  ./.venv/Scripts/python.exe -X utf8 tmp_jev_full_decisions.py --subject ial-psychology \
      --write --batch-root tmp_jev_wps02 --out-root tmp_jev_wps02_dec \
      --jev-template tmp_jev_wps02_{slug}.jsonl
  ./.venv/Scripts/python.exe -X utf8 tmp_jev_full_apply.py --subject ial-psychology \
      --batch-root tmp_jev_wps02 --decisions-root tmp_jev_wps02_dec [--write]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB_URL = f'sqlite:///{ROOT / ".data" / "examdata.db"}'
QIDS = [61530, 61531, 65108, 66196]
OUT_DIR = ROOT / 'tmp_jev_wps02' / 'ial-psychology' / 'batches'


def main() -> None:
    eng = create_engine(DB_URL)
    s = Session(eng)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for qid in QIDS:
        q = s.get(m.Question, qid)
        if q is None:
            print(f'{qid}: MISSING')
            continue
        paper = s.get(m.Paper, q.paper_id)
        doc = s.get(m.Document, paper.document_id) if paper else None
        tax = s.execute(
            select(m.TaxonomyNode.code, m.QuestionTaxonomy.confidence)
            .join(m.TaxonomyNode, m.TaxonomyNode.id == m.QuestionTaxonomy.node_id)
            .where(m.QuestionTaxonomy.question_id == qid)
        ).all()
        cur = [{'code': c, 'confidence': conf} for c, conf in tax]
        unit = cur[0]['code'].split('-', 1)[0] if cur else None
        rec = {
            'question_id': qid,
            'number_label': q.number_label or '',
            'paper_code': doc.paper_code if doc else None,
            'unit_code': unit,
            'stem': (q.stem_text or '')[:400],
            'current': cur,
        }
        rows.append(rec)
        print(f"{qid} {doc.paper_code if doc else '?'} {q.number_label!r} "
              f"unit={unit} cur={[c['code'] for c in cur]} marks={q.marks} "
              f"title={(doc.title if doc else '')[:52]!r}")
    path = OUT_DIR / 'batch-001.jsonl'
    with open(path, 'w', encoding='utf-8') as fh:
        for rec in rows:
            fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
    print(f'wrote {len(rows)} records -> {path}')


if __name__ == '__main__':
    main()
