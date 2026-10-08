"""r8 final acceptance sample (read-only): fresh independent draw.

For each IAL subject (id >= 5), draws up to --n questions spread across
distinct years (fresh seed), and dumps: identity, DB tags (+spec point text),
stem, MS answers, and a live crop render check — for independent review.

Usage:
  ./.venv/Scripts/python.exe -X utf8 tmp_r8_sample.py --n 2 --seed 20261005

Outputs:
  tmp_r8_sample.txt    (readable, one block per question)
  tmp_r8_sample.jsonl  (machine-readable)
  tmp_r8_crops/*.png   (first crop per question, evidence of viewability)
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.query import service
from examdata.tagging.corpus import load_points

ROOT = Path(__file__).resolve().parent
DB = ROOT / '.data' / 'examdata.db'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=2, help='per subject')
    ap.add_argument('--seed', type=int, default=20261005)
    ap.add_argument('--out', default='tmp_r8_sample.txt')
    ap.add_argument('--crop-dir', default='tmp_r8_crops')
    args = ap.parse_args()

    rng = random.Random(args.seed)
    eng = create_engine(f'sqlite:///{DB}')
    crop_dir = ROOT / args.crop_dir
    crop_dir.mkdir(exist_ok=True)

    lines: list[str] = []
    items: list[dict] = []
    total = viewable = 0
    view_err: list[str] = []
    per_subject: dict[str, int] = {}

    with Session(eng) as s:
        points = load_points(s)
        by_code = {p.code.upper(): p for p in points}
        subjects = [x for x in s.scalars(select(m.Subject).order_by(m.Subject.id)) if x.id >= 5]

        for sub in subjects:
            qids_by_year: dict = defaultdict(list)
            docs = sorted(
                (d for d in s.scalars(select(m.Document).where(m.Document.subject_id == sub.id))
                 if d.doc_type == 'question_paper'),
                key=lambda d: d.id,
            )
            for d in docs:
                y = d.year if d.year is not None else 0
                for p in s.scalars(select(m.Paper).where(m.Paper.document_id == d.id)):
                    for q in s.scalars(select(m.Question).where(m.Question.paper_id == p.id)):
                        qids_by_year[y].append(q.id)
            if not qids_by_year:
                continue
            years = sorted(qids_by_year)
            for y in years:
                rng.shuffle(qids_by_year[y])
            picks: list[int] = []
            i = 0
            while len(picks) < args.n:
                added = False
                for y in years:
                    if i < len(qids_by_year[y]) and len(picks) < args.n:
                        picks.append(qids_by_year[y][i])
                        added = True
                if not added:
                    break
                i += 1

            slug = sub.slug or sub.code
            for qid in picks:
                total += 1
                q = s.get(m.Question, qid)
                paper = s.get(m.Paper, q.paper_id)
                doc = s.get(m.Document, paper.document_id)
                series = s.get(m.ExamSeries, doc.series_id) if doc.series_id else None

                tags = s.execute(
                    select(m.TaxonomyNode.code, m.TaxonomyNode.name,
                           m.QuestionTaxonomy.confidence, m.QuestionTaxonomy.assigned_by,
                           m.QuestionTaxonomy.reviewed)
                    .join(m.QuestionTaxonomy, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id)
                    .where(m.QuestionTaxonomy.question_id == qid)
                    .order_by(m.TaxonomyNode.code)
                ).all()

                stem = ' '.join((q.stem_text or '').split())
                ms = s.execute(
                    select(m.MarkSchemeEntry.answer_text, m.MarkSchemeEntry.number_path,
                           m.MarkSchemeEntry.marks)
                    .where(m.MarkSchemeEntry.question_id == qid)
                ).all()

                item = {
                    'n': total, 'slug': slug, 'qid': qid, 'paper_code': doc.paper_code,
                    'year': doc.year, 'session': series.session if series else None,
                    'number_path': q.number_path, 'marks': q.marks, 'kind': q.kind,
                    'stem': stem[:900], 'tags': [], 'ms': [], 'crop': None,
                }
                for code, name, conf, by, rev in tags:
                    pt = by_code.get((code or '').upper())
                    item['tags'].append({
                        'code': code, 'name': name, 'conf': conf,
                        'assigned_by': by, 'reviewed': rev,
                        'point_text': (pt.text if pt else '')[:600],
                    })

                lines.append('=' * 100)
                lines.append(
                    f"[{total}] {slug} | {doc.paper_code} | year={doc.year} "
                    f"session={series.session if series else None} | qid={qid} | "
                    f"{q.number_path} | marks={q.marks} | kind={q.kind}"
                )
                for t in item['tags']:
                    lines.append(
                        f"TAG: {t['code']} | by={t['assigned_by']} | "
                        f"reviewed={t['reviewed']} | conf={t['conf']}"
                    )
                    lines.append(f"  NAME: {t['name']}")
                    lines.append(f"  POINT: {t['point_text']}")
                lines.append(f"STEM: {stem[:700]}")
                for text, np, mk in ms[:2]:
                    txt = ' '.join((text or '').split())
                    item['ms'].append({'number_path': np, 'marks': mk, 'text': txt[:500]})
                    lines.append(f"MS[{np} marks={mk}]: {txt[:300]}")

                try:
                    crops = service.question_crops(s, qid, role='qp')
                    if not crops:
                        raise RuntimeError('empty crops')
                    viewable += 1
                    png_path = crop_dir / f'{qid}.png'
                    png_path.write_bytes(crops[0]['png'])
                    item['crop'] = {'ok': True, 'pages': [c['page'] for c in crops]}
                    lines.append(
                        f"CROP: OK {len(crops)} crop(s), pages "
                        f"{[c['page'] for c in crops]} -> {png_path.name}"
                    )
                except Exception as exc:
                    view_err.append(f'{qid} ({slug}): {type(exc).__name__}: {exc}')
                    item['crop'] = {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
                    lines.append(f'CROP: ERROR {type(exc).__name__}: {str(exc)[:200]}')
                lines.append('')
                items.append(item)
            per_subject[slug] = len(picks)

    summary = [
        '=' * 100,
        f'SAMPLE SUMMARY: total={total} viewable={viewable}/{total} view_errors={len(view_err)}',
    ]
    for e in view_err[:20]:
        summary.append(f'  VIEW-ERR {e}')
    for slug, n in per_subject.items():
        summary.append(f'  {slug}: n={n}')
    (ROOT / args.out).write_text('\n'.join(lines + summary) + '\n', encoding='utf-8')
    (ROOT / 'tmp_r8_sample.jsonl').write_text(
        '\n'.join(json.dumps(x, ensure_ascii=False) for x in items) + '\n', encoding='utf-8'
    )
    print('\n'.join(summary))


if __name__ == '__main__':
    main()
