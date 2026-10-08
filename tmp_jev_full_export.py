"""Full second-pass export: ALL tagged questions (bm25 + ai-review) for Jev re-check.

Unlike review-export (low-confidence, unreviewed only), this exports every tagged
question once, with its current label(s), so Jev can independently re-classify and
we can compare.

Unit resolution per question:
  1. fresh = unit_code_from_paper(paper.attrs, paper_code)
  2. if fresh is in the target point units -> use it
  3. else -> unit of the current taxonomy node(s) (climb parent chain)
  4. still unresolved (junk paper_code + cross-unit rows) -> sibling vote: the most
     common unit among resolved questions on the same document
  5. unresolved after that -> problem (skipped, logged)

Special split: subject 'ial-maths' questions whose effective unit belongs to the
ial18-mathematics point set go to slug 'ial18-mathematics-extra' (same split used
by the 920-row fix).

Output: tmp_jev_full_batches/{slug}/batch-XXX.jsonl (50 per batch), same record
shape as review-export batches: question_id, number_label, paper_code, unit_code,
stem, current[{code,name,confidence,assigned_by,reviewed}].
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, r'C:/Users/weo/Desktop/api/examdata')
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.corpus import load_points, unit_code_from_paper

ROOT = Path(r'C:/Users/weo/Desktop/api/examdata')
DB_URL = f'sqlite:///{ROOT / ".data" / "examdata.db"}'
OUT_ROOT = ROOT / 'tmp_jev_full_batches'
BATCH_SIZE = 50
ASSIGNED = ['edexcel-bm25-v1', 'ai-review-v1']

# slug -> points subject (defaults to slug itself)
POINTS_SUBJECT = {'ial18-mathematics-extra': 'ial18-mathematics'}

# 5 questions whose rows span units and whose paper resolves to junk; unit taken
# from the document title (Paper 2 (YLA0/02) -> YLA0-P2; Paper M3 (WME03) -> WME03).
MANUAL_FIX = {
    56292: ('ial-law', 'YLA0-P2'),
    56301: ('ial-law', 'YLA0-P2'),
    56305: ('ial-law', 'YLA0-P2'),
    56306: ('ial-law', 'YLA0-P2'),
    60427: ('ial18-mathematics-extra', 'WME03'),
}


def main() -> None:
    eng = create_engine(DB_URL)
    s = Session(eng)

    points = load_points(s)
    by_subj: dict[str, dict] = defaultdict(lambda: {'units': set(), 'by_node': {}})
    for p in points:
        key = (p.subject or '').strip().lower()
        by_subj[key]['units'].add(p.unit_code)
        by_subj[key]['by_node'][p.node_id] = p
    all_nodes = {p.node_id: p for p in points}

    # node -> unit code (climb parents), cached
    node_cache: dict[int, str | None] = {}

    def node_unit(node_id: int) -> str | None:
        if node_id in node_cache:
            return node_cache[node_id]
        seen = set()
        cur = s.get(m.TaxonomyNode, node_id)
        unit = None
        while cur is not None and cur.id not in seen:
            seen.add(cur.id)
            if cur.node_type == 'unit':
                unit = cur.code
                break
            cur = s.get(m.TaxonomyNode, cur.parent_id) if cur.parent_id else None
        node_cache[node_id] = unit
        return unit

    # all tagged rows
    rows_stmt = (
        select(
            m.QuestionTaxonomy.question_id,
            m.QuestionTaxonomy.node_id,
            m.QuestionTaxonomy.confidence,
            m.QuestionTaxonomy.assigned_by,
            m.QuestionTaxonomy.reviewed,
        )
        .where(m.QuestionTaxonomy.assigned_by.in_(ASSIGNED))
        .order_by(m.QuestionTaxonomy.question_id)
    )
    row_map: dict[int, list] = defaultdict(list)
    for qid, node_id, conf, ab, rv in s.execute(rows_stmt):
        row_map[qid].append((node_id, conf, ab, rv))

    # question metadata
    q_stmt = (
        select(
            m.Question.id,
            m.Question.number_label,
            m.Question.stem_text,
            m.Document.paper_code,
            m.Paper.attrs,
            m.Subject.slug,
            m.Document.id,
        )
        .join(m.Paper, m.Paper.id == m.Question.paper_id)
        .join(m.Document, m.Document.id == m.Paper.document_id)
        .join(m.Subject, m.Subject.id == m.Document.subject_id)
        .where(m.Question.id.in_(
            select(m.QuestionTaxonomy.question_id)
            .where(m.QuestionTaxonomy.assigned_by.in_(ASSIGNED))
            .distinct()
        ))
    )
    meta = {}
    for qid, number_label, stem, paper_code, attrs, slug, doc_id in s.execute(q_stmt):
        meta[qid] = {
            'number_label': number_label or '',
            'stem': stem or '',
            'paper_code': paper_code,
            'attrs': attrs,
            'slug': slug,
            'doc_id': doc_id,
        }

    maths18_units = by_subj['ial18-mathematics']['units']
    groups: dict[str, list[dict]] = defaultdict(list)
    unresolved: list[tuple[int, str]] = []
    problems: list[tuple[int, str]] = []

    def target_unit_for(slug: str, unit: str) -> tuple[str, str] | None:
        if slug == 'ial-maths':
            own = by_subj['ial-maths']['units']
            if unit in maths18_units:
                return 'ial18-mathematics-extra', unit
            if unit in own:
                return 'ial-maths', unit
            return None
        own = by_subj[slug]['units']
        return (slug, unit) if unit in own else None

    def add_item(qid: int, info: dict, target: str, unit: str, rows: list) -> bool:
        current = []
        for node_id, conf, ab, rv in rows:
            p = all_nodes.get(node_id)
            if p is None:
                return False
            current.append({
                'code': p.code,
                'name': p.name,
                'confidence': round(conf, 4) if conf is not None else None,
                'assigned_by': ab,
                'reviewed': bool(rv),
            })
        groups[target].append({
            'question_id': qid,
            'number_label': info['number_label'],
            'paper_code': info['paper_code'],
            'unit_code': unit,
            'stem': info['stem'],
            'current': current,
        })
        return True

    # pass A: fresh / single node-unit resolution
    for qid in sorted(row_map):
        rows = row_map[qid]
        info = meta.get(qid)
        if info is None:
            problems.append((qid, 'no question meta'))
            continue
        if qid in MANUAL_FIX:
            target, unit = MANUAL_FIX[qid]
            if not add_item(qid, info, target, unit, rows):
                problems.append((qid, 'manual fix node not in any points'))
            continue
        slug = info['slug']
        fresh = unit_code_from_paper(info['attrs'], info['paper_code'])
        node_units = {node_unit(nid) for nid, *_ in rows}
        node_units.discard(None)

        resolved = None
        if fresh is not None and target_unit_for(slug, fresh) is not None:
            resolved = fresh
        elif len(node_units) == 1:
            resolved = next(iter(node_units))
        if resolved is None:
            unresolved.append((qid, f'unresolved fresh={fresh!r} node_units={sorted(node_units)}'))
            continue
        hit = target_unit_for(slug, resolved)
        if hit is None:
            problems.append((qid, f'unit {resolved!r} (fresh {fresh!r}) not in {slug} points'))
            continue
        target, unit = hit
        if not add_item(qid, info, target, unit, rows):
            problems.append((qid, f'node not in any points ({[nid for nid, *_ in rows]})'))

    # pass B: sibling vote per document for unresolved questions
    doc_votes: dict[int, Counter] = defaultdict(Counter)
    for items in groups.values():
        for item in items:
            doc_votes[meta[item['question_id']]['doc_id']][item['unit_code']] += 1
    still: list[tuple[int, str]] = []
    for qid, msg in unresolved:
        info = meta.get(qid)
        votes = doc_votes.get(info['doc_id']) if info else None
        chosen = None
        if votes:
            top = votes.most_common(2)
            if len(top) == 1 or top[0][1] > top[1][1]:
                chosen = top[0][0]
        if chosen is None:
            still.append((qid, msg + f' | no sibling vote {dict(votes) if votes else {}}'))
            continue
        hit = target_unit_for(info['slug'], chosen)
        if hit is None:
            still.append((qid, msg + f' | sibling unit {chosen!r} invalid'))
            continue
        target, unit = hit
        if not add_item(qid, info, target, unit, row_map[qid]):
            still.append((qid, msg + f' | node not in any points'))
            continue
        print(f'  sibling-resolved {qid} -> {target} {unit} (votes {dict(votes)})')
    problems.extend(still)

    manifest = {}
    for slug in sorted(groups):
        items = sorted(groups[slug], key=lambda r: r['question_id'])
        out_dir = OUT_ROOT / slug / 'batches'
        out_dir.mkdir(parents=True, exist_ok=True)
        for old in out_dir.glob('batch-*.jsonl'):
            old.unlink()
        units = defaultdict(int)
        for item in items:
            units[item['unit_code']] += 1
        for index in range(0, len(items), BATCH_SIZE):
            path = out_dir / f'batch-{index // BATCH_SIZE + 1:03d}.jsonl'
            with path.open('w', encoding='utf-8') as fh:
                for item in items[index:index + BATCH_SIZE]:
                    fh.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + '\n')
        manifest[slug] = {
            'questions': len(items),
            'batches': (len(items) + BATCH_SIZE - 1) // BATCH_SIZE,
            'units': dict(sorted(units.items())),
        }
        print(f'{slug}: {len(items)} questions, {manifest[slug]["batches"]} batches, '
              f'{len(units)} units')

    prob_path = OUT_ROOT / 'problems.jsonl'
    with prob_path.open('w', encoding='utf-8') as fh:
        for qid, msg in problems:
            fh.write(json.dumps({'question_id': qid, 'problem': msg}, ensure_ascii=False) + '\n')
    total = sum(v['questions'] for v in manifest.values())
    print(f'TOTAL: {total} questions across {len(manifest)} slugs; problems: {len(problems)}')
    print(f'problems -> {prob_path}')
    (OUT_ROOT / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + '\n',
        encoding='utf-8')


if __name__ == '__main__':
    main()
