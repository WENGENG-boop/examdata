"""r6 export: Edexcel IAL questions that still have 0 reviewed taxonomy rows.

Scope: questions in the 21 IAL slugs with >=1 taxonomy row but no reviewed row
(679 expected). Same record shape as the full export, with current label rows.

Unit resolution cascade per question:
  1. fresh = unit_code_from_paper(attrs, pcode); valid for subject -> use
     (ial-maths questions whose unit belongs to the ial18-mathematics point set
      are routed to slug 'ial18-mathematics-extra')
  2. title bracket r'\\(([A-Z]{2,4}\\d{2,3})\\)' e.g. '(WST01)' -> valid -> use
  3. german 'Unit 1' title -> WGN01
  4. legacy unit alias from fresh: 6663A/6664A/6665A -> WMA01/WMA02,
     6666A -> WMA02, 6667A -> WFM01
  5. pcode alias: yla1-01 -> YLA1-01, yla1-02 -> YLA1-02
  6. unique node-unit of the question's own taxonomy rows
  7. sibling vote per document (existing taxonomy unit labels of the doc's
     other questions + in-run resolved ones); unique top wins
  8. else -> problem (logged, skipped)

Output: tmp_jev_full_batches_r6/{slug}/batches/batch-NNN.jsonl (50 per batch),
manifest.json, problems.jsonl, stats.json.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.corpus import load_points, unit_code_from_paper

ROOT = Path(__file__).resolve().parent
DB_URL = f'sqlite:///{ROOT / ".data" / "examdata.db"}'
OUT_ROOT = ROOT / 'tmp_jev_full_batches_r6'
BATCH_SIZE = 50

IAL_SLUGS = {
    'ial-accounting', 'ial-arabic', 'ial-englang', 'ial-englit', 'ial-french',
    'ial-geography', 'ial-german', 'ial-greek', 'ial-history', 'ial-law',
    'ial-maths', 'ial-psychology', 'ial-spanish', 'ial18-biology', 'ial18-business',
    'ial18-chemistry', 'ial18-economics', 'ial18-it', 'ial18-mathematics',
    'ial18-physics', 'ial26-computer-science',
}

TITLE_RE = re.compile(r'\(([A-Z]{2,4}\d{2,3})\)')
GERMAN_UNIT1_RE = re.compile(r'Unit\s*1\b', re.I)

UNIT_ALIAS = {'6663A': 'WMA01', '6664A': 'WMA01', '6665A': 'WMA02',
              '6666A': 'WMA02', '6667A': 'WFM01'}
PCODE_ALIAS = {'yla1-01': 'YLA1-01', 'yla1-02': 'YLA1-02'}


def main() -> None:
    eng = create_engine(DB_URL)
    s = Session(eng)

    points = load_points(s)
    by_subj: dict[str, dict] = defaultdict(lambda: {'units': set()})
    all_nodes = {p.node_id: p for p in points}
    for p in points:
        key = (p.subject or '').strip().lower()
        by_subj[key]['units'].add(p.unit_code)
    maths18_units = by_subj['ial18-mathematics']['units']

    def target_unit_for(slug: str, unit: str | None):
        if not unit:
            return None
        if slug == 'ial-maths':
            if unit in maths18_units:
                return 'ial18-mathematics-extra', unit
            if unit in by_subj['ial-maths']['units']:
                return 'ial-maths', unit
            return None
        if slug == 'ial18-mathematics' and unit not in maths18_units:
            if unit in by_subj['ial-maths']['units']:
                return 'ial-maths', unit
            return None
        return (slug, unit) if unit in by_subj[slug]['units'] else None

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

    # taxonomy rows for the whole IAL scope
    tax_rows = s.execute(
        select(m.QuestionTaxonomy.question_id, m.QuestionTaxonomy.node_id,
               m.QuestionTaxonomy.confidence, m.QuestionTaxonomy.assigned_by,
               m.QuestionTaxonomy.reviewed)
    ).all()
    row_map: dict[int, list] = defaultdict(list)
    reviewed_ids: set[int] = set()
    for qid, node_id, conf, ab, rv in tax_rows:
        row_map[qid].append((node_id, conf, ab, rv))
        if rv:
            reviewed_ids.add(qid)
    print(f'questions with >=1 taxonomy row: {len(row_map)}; reviewed: {len(reviewed_ids)}')

    rows = s.execute(
        select(
            m.Question.id, m.Question.number_label, m.Question.stem_text,
            m.Paper.attrs, m.Document.paper_code, m.Document.title,
            m.Subject.slug, m.Document.id,
        )
        .join(m.Paper, m.Paper.id == m.Question.paper_id)
        .join(m.Document, m.Document.id == m.Paper.document_id)
        .join(m.Subject, m.Subject.id == m.Document.subject_id)
        .order_by(m.Question.id)
    ).all()

    scope = []
    for qid, number_label, stem, attrs, pcode, title, slug, doc_id in rows:
        if slug not in IAL_SLUGS or qid not in row_map or qid in reviewed_ids:
            continue
        scope.append({
            'qid': qid, 'number_label': number_label or '', 'stem': stem or '',
            'attrs': attrs, 'pcode': pcode, 'title': title or '',
            'slug': slug, 'doc_id': doc_id,
        })
    print(f'unreviewed tagged scope: {len(scope)} questions')

    # existing sibling unit votes per document (all taxonomy rows of the doc)
    doc_votes: dict[int, Counter] = defaultdict(Counter)
    doc_ids = {r['doc_id'] for r in scope}
    sib_rows = s.execute(
        select(m.QuestionTaxonomy.question_id, m.TaxonomyNode.code, m.Paper.document_id)
        .join(m.TaxonomyNode, m.TaxonomyNode.id == m.QuestionTaxonomy.node_id)
        .join(m.Question, m.Question.id == m.QuestionTaxonomy.question_id)
        .join(m.Paper, m.Paper.id == m.Question.paper_id)
        .where(m.Paper.document_id.in_(doc_ids))
    ).all()
    for _qid, code, did in sib_rows:
        unit = (code or '').split('-', 1)[0]
        if unit:
            doc_votes[did][unit] += 1

    groups: dict[str, list[dict]] = defaultdict(list)
    problems: list[tuple[int, str]] = []
    method_count: Counter = Counter()
    method_sample: dict[str, list] = defaultdict(list)
    per_slug_units: dict[str, Counter] = defaultdict(Counter)
    unresolved: list[dict] = []

    def note(method: str, r: dict, target: str, unit: str) -> None:
        method_count[method] += 1
        if len(method_sample[method]) < 5:
            method_sample[method].append((r['qid'], r['slug'], target, unit,
                                          r['pcode'], r['title'][:60]))

    def current_rows(r: dict) -> list[dict]:
        out = []
        for node_id, conf, ab, rv in sorted(row_map[r['qid']]):
            node = s.get(m.TaxonomyNode, node_id)
            out.append({
                'code': node.code if node else f'#{node_id}',
                'name': node.name if node else '',
                'confidence': round(conf, 4) if conf is not None else None,
                'assigned_by': ab,
                'reviewed': bool(rv),
            })
        return out

    def add_item(r: dict, target: str, unit: str) -> None:
        groups[target].append({
            'question_id': r['qid'],
            'number_label': r['number_label'],
            'paper_code': r['pcode'],
            'unit_code': unit,
            'stem': r['stem'],
            'current': current_rows(r),
        })
        per_slug_units[target][unit] += 1

    # pass A: non-sibling resolutions
    for r in scope:
        slug, fresh = r['slug'], unit_code_from_paper(r['attrs'], r['pcode'])
        hit = target_unit_for(slug, fresh)
        if hit:
            add_item(r, *hit)
            note('fresh', r, *hit)
            continue
        mm = TITLE_RE.search(r['title'])
        if mm:
            hit = target_unit_for(slug, mm.group(1))
            if hit:
                add_item(r, *hit)
                note('title', r, *hit)
                continue
        if slug == 'ial-german' and GERMAN_UNIT1_RE.search(r['title']):
            hit = target_unit_for(slug, 'WGN01')
            if hit:
                add_item(r, *hit)
                note('german-unit1', r, *hit)
                continue
        alias = UNIT_ALIAS.get(fresh or '')
        if alias:
            hit = target_unit_for(slug, alias)
            if hit:
                add_item(r, *hit)
                note('unit-alias', r, *hit)
                continue
        alias = PCODE_ALIAS.get((r['pcode'] or '').lower())
        if alias:
            hit = target_unit_for(slug, alias)
            if hit:
                add_item(r, *hit)
                note('pcode-alias', r, *hit)
                continue
        node_units = {node_unit(nid) for nid, *_ in row_map[r['qid']]}
        node_units.discard(None)
        if len(node_units) == 1:
            hit = target_unit_for(slug, next(iter(node_units)))
            if hit:
                add_item(r, *hit)
                note('node-unit', r, *hit)
                continue
        unresolved.append(r)

    # merge in-run resolved units into doc votes
    qid_doc = {r['qid']: r['doc_id'] for r in scope}
    for _target, items in groups.items():
        for item in items:
            doc_votes[qid_doc[item['question_id']]][item['unit_code']] += 1

    # pass B: sibling vote (existing labels + in-run resolved)
    still: list[dict] = []
    for r in unresolved:
        votes = Counter(doc_votes.get(r['doc_id'], Counter()))
        chosen = None
        if votes:
            top = votes.most_common(2)
            if len(top) == 1 or top[0][1] > top[1][1]:
                chosen = top[0][0]
        if chosen is None:
            still.append(r)
            problems.append((r['qid'], f'no resolution: fresh={unit_code_from_paper(r["attrs"], r["pcode"])!r} '
                                       f'pcode={r["pcode"]!r} title={r["title"][:60]!r} votes={dict(votes)}'))
            continue
        hit = target_unit_for(r['slug'], chosen)
        if hit is None:
            still.append(r)
            problems.append((r['qid'], f'sibling unit {chosen!r} invalid for {r["slug"]}; '
                                       f'votes={dict(votes)}'))
            continue
        add_item(r, *hit)
        note('sibling', r, *hit)
        print(f'  sibling-resolved {r["qid"]} {r["slug"]} -> {hit[0]} {hit[1]} (votes {dict(votes)})')

    manifest = {}
    for slug in sorted(groups):
        items = sorted(groups[slug], key=lambda x: x['question_id'])
        out_dir = OUT_ROOT / slug / 'batches'
        out_dir.mkdir(parents=True, exist_ok=True)
        for old in out_dir.glob('batch-*.jsonl'):
            old.unlink()
        for index in range(0, len(items), BATCH_SIZE):
            path = out_dir / f'batch-{index // BATCH_SIZE + 1:03d}.jsonl'
            with path.open('w', encoding='utf-8') as fh:
                for item in items[index:index + BATCH_SIZE]:
                    fh.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + '\n')
        manifest[slug] = {
            'questions': len(items),
            'batches': (len(items) + BATCH_SIZE - 1) // BATCH_SIZE,
            'units': dict(sorted(per_slug_units[slug].items())),
        }
        print(f'{slug}: {len(items)} questions, {manifest[slug]["batches"]} batches, '
              f'units={manifest[slug]["units"]}')

    (OUT_ROOT / 'problems.jsonl').write_text(
        ''.join(json.dumps({'question_id': q, 'problem': msg}, ensure_ascii=False) + '\n'
                for q, msg in problems), encoding='utf-8')
    total = sum(v['questions'] for v in manifest.values())
    stats = {
        'scope': len(scope),
        'total_exported': total,
        'problems': len(problems),
        'methods': dict(method_count),
        'method_samples': {k: v for k, v in method_sample.items()},
    }
    (OUT_ROOT / 'stats.json').write_text(
        json.dumps(stats, ensure_ascii=False, indent=1, sort_keys=True) + '\n',
        encoding='utf-8')
    (OUT_ROOT / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + '\n',
        encoding='utf-8')

    print(f'TOTAL: {total} questions across {len(manifest)} slugs; problems: {len(problems)}')
    print('methods:', dict(method_count))
    for mth in sorted(method_sample):
        print(f'--- {mth} samples:')
        for row in method_sample[mth]:
            print('   ', row)


if __name__ == '__main__':
    main()
