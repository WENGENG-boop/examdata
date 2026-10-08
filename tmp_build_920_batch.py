"""Build review batches for the 920 unreviewed low-confidence legacy ial-maths rows.

These rows sit on documents with subject_id=16 (ial-maths legacy) but their taxonomy
nodes (shared units WST/WME/WFM01-03) now carry attrs.subject='ial18-mathematics'
because the later spec load overwrote the shared (board_id, code) rows. Both the
ial-maths and ial18-mathematics review exports therefore miss them. This script
emits a dedicated batch set under review-export/ial18-mathematics-extra/batches/
so Jev can re-adjudicate all of them.

Output item shape matches existing batches:
  {"current": [{"code", "confidence", "name"}, ...], "number_label", "paper_code",
   "question_id", "stem", "unit_code"}
"""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, r'C:/Users/weo/Desktop/api/examdata')
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.corpus import unit_code_from_paper

ROOT = Path(r'C:/Users/weo/Desktop/api/examdata')
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"
OUT_DIR = ROOT / '.data' / 'tagging' / 'review-export' / 'ial18-mathematics-extra' / 'batches'
BATCH_SIZE = 50


def main() -> None:
    eng = create_engine(DB_URL)
    s = Session(eng)
    rows = s.execute(
        select(m.QuestionTaxonomy, m.TaxonomyNode)
        .join(m.TaxonomyNode, m.TaxonomyNode.id == m.QuestionTaxonomy.node_id)
        .join(m.Question, m.Question.id == m.QuestionTaxonomy.question_id)
        .join(m.Paper, m.Paper.id == m.Question.paper_id)
        .join(m.Document, m.Document.id == m.Paper.document_id)
        .where(
            m.QuestionTaxonomy.reviewed == False,  # noqa: E712
            m.QuestionTaxonomy.assigned_by == 'edexcel-bm25-v1',
            m.QuestionTaxonomy.confidence < 0.35,
            m.Document.subject_id == 16,
        )
    ).all()
    print(f'rows: {len(rows)}')

    by_q: dict[int, list] = collections.OrderedDict()
    for qt, tn in rows:
        by_q.setdefault(qt.question_id, []).append((qt, tn))
    print(f'questions: {len(by_q)}')

    items = []
    problems = []
    for qid, pairs in by_q.items():
        q = s.get(m.Question, qid)
        if q is None:
            problems.append((qid, 'missing question'))
            continue
        paper = s.get(m.Paper, q.paper_id)
        doc = s.get(m.Document, paper.document_id) if paper else None
        unit = unit_code_from_paper(
            paper.attrs if paper else None,
            doc.paper_code if doc else None,
        )
        if not unit:
            problems.append((qid, 'no unit resolvable'))
            continue
        pairs.sort(key=lambda p: -p[0].confidence)
        item = {
            'current': [
                {'code': tn.code, 'confidence': round(qt.confidence, 4), 'name': tn.name}
                for qt, tn in pairs
            ],
            'number_label': q.number_label,
            'paper_code': doc.paper_code if doc else '',
            'question_id': qid,
            'stem': (q.stem_text or '')[:1800],
            'unit_code': unit,
        }
        items.append((doc.paper_code if doc else '', q.display_order, item))
    items.sort(key=lambda t: (t[0], t[1]))
    print(f'items: {len(items)}, problems: {len(problems)}')
    for qid, msg in problems[:20]:
        print('  PROBLEM', qid, msg)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    n = 0
    for i in range(0, len(items), BATCH_SIZE):
        n += 1
        chunk = [it[2] for it in items[i:i + BATCH_SIZE]]
        dst = OUT_DIR / f'batch-{n:03d}.jsonl'
        with open(dst, 'w', encoding='utf-8') as fh:
            for it in chunk:
                fh.write(json.dumps(it, ensure_ascii=False) + '\n')
        print(f'  batch-{n:03d}: {len(chunk)} items')
    print(f'wrote {n} batches -> {OUT_DIR}')

    units = collections.Counter(it[2]['unit_code'] for it in items)
    print('units:', dict(sorted(units.items())))


if __name__ == '__main__':
    main()
