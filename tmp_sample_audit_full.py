"""Full-sample audit across all 20 subjects (run after apply).

For each subject, draws up to --n questions spread across distinct years and
prints: identity, pre-apply label(s), Jev decision + reason, post-apply DB
label(s), stem, first mark-scheme answer, and a live crop-render check via
question_crops(role='qp') — the same path the query UI uses. Saves the first
crop PNG per question under tmp_sample_crops/ as evidence.

Usage:
  python tmp_sample_audit_full.py                  # 3 per subject -> 60
  python tmp_sample_audit_full.py --n 2 --seed 7
  python tmp_sample_audit_full.py --slugs ial-law,ial-maths
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

ROOT = Path(__file__).resolve().parent
DB = ROOT / '.data' / 'examdata.db'
SLUGS = [
    'ial-accounting', 'ial-englang', 'ial-englit', 'ial-french', 'ial-geography',
    'ial-german', 'ial-greek', 'ial-history', 'ial-law', 'ial-maths',
    'ial-psychology', 'ial-spanish', 'ial18-biology', 'ial18-business',
    'ial18-chemistry', 'ial18-economics', 'ial18-it', 'ial18-mathematics',
    'ial18-mathematics-extra', 'ial18-physics',
]


def load_jsonl_dir(path: Path) -> dict:
    out = {}
    for f in sorted(path.glob('batch-*.jsonl')):
        for line in open(f, encoding='utf-8'):
            if line.strip():
                r = json.loads(line)
                out[r['question_id']] = r
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=3, help='per subject')
    ap.add_argument('--seed', type=int, default=20261004)
    ap.add_argument('--slugs', default='', help='comma list; default all')
    ap.add_argument('--out', default='tmp_sample_audit_full.txt')
    ap.add_argument('--crop-dir', default='tmp_sample_crops')
    ap.add_argument('--no-crops', action='store_true')
    args = ap.parse_args()

    slugs = [x.strip() for x in args.slugs.split(',') if x.strip()] or SLUGS
    rng = random.Random(args.seed)
    eng = create_engine(f'sqlite:///{DB}')
    crop_dir = ROOT / args.crop_dir
    crop_dir.mkdir(exist_ok=True)

    lines: list[str] = []
    total = 0
    keep_n = change_n = 0
    viewable = 0
    view_err: list[str] = []
    per_subject: dict[str, Counter] = {}

    with Session(eng) as s:
        for slug in slugs:
            dec_dir = ROOT / 'tmp_jev_full_decisions_r2' / slug
            dec_round = 'r2'
            if not dec_dir.is_dir():
                dec_dir = ROOT / 'tmp_jev_untagged_decisions' / slug
                dec_round = 'unt'
            if not dec_dir.is_dir():
                dec_dir = ROOT / 'tmp_jev_full_decisions' / slug
                dec_round = 'r1'
            decisions = load_jsonl_dir(dec_dir)
            b_dir = ROOT / 'tmp_jev_full_batches_r2' / slug / 'batches'
            if not b_dir.is_dir():
                b_dir = ROOT / 'tmp_jev_untagged_batches' / slug / 'batches'
            if not b_dir.is_dir():
                b_dir = ROOT / 'tmp_jev_full_batches' / slug / 'batches'
            batches = load_jsonl_dir(b_dir)
            qids = sorted(batches)
            if not qids:
                lines.append(f'### {slug}: NO QUESTIONS')
                continue

            # year for each qid (via paper->document)
            rows = s.execute(
                select(m.Question.id, m.Document.year)
                .join(m.Paper, m.Paper.id == m.Question.paper_id)
                .join(m.Document, m.Document.id == m.Paper.document_id)
                .where(m.Question.id.in_(qids))
            ).all()
            year_of = {qid: (year if year is not None else 0) for qid, year in rows}
            by_year: dict[int, list[int]] = defaultdict(list)
            for qid in qids:
                by_year[year_of.get(qid, 0)].append(qid)
            for y in by_year:
                rng.shuffle(by_year[y])
            years = sorted(by_year)
            picks: list[int] = []
            i = 0
            while len(picks) < args.n:
                added = False
                for y in years:
                    if i < len(by_year[y]) and len(picks) < args.n:
                        picks.append(by_year[y][i])
                        added = True
                if not added:
                    break
                i += 1

            stats = Counter()
            for qid in picks:
                total += 1
                stats['sampled'] += 1
                q = s.get(m.Question, qid)
                paper = s.get(m.Paper, q.paper_id)
                doc = s.get(m.Document, paper.document_id)
                subj = s.get(m.Subject, doc.subject_id) if doc.subject_id else None
                series = s.get(m.ExamSeries, doc.series_id) if doc.series_id else None
                item = batches[qid]
                dec = decisions.get(qid, {})

                # pre-apply labels from the batch item
                pre = item.get('current') or []
                pre_txt = '; '.join(
                    f"{c['code']}({c.get('assigned_by')},rev={c.get('reviewed')})" for c in pre
                )
                dec_txt = dec.get('decision', '?')
                if dec.get('decision') == 'change':
                    change_n += 1
                    stats['change'] += 1
                elif dec.get('decision') == 'keep':
                    keep_n += 1
                    stats['keep'] += 1

                # post-apply labels from DB
                tags = s.execute(
                    select(m.TaxonomyNode.code, m.TaxonomyNode.name,
                           m.QuestionTaxonomy.confidence, m.QuestionTaxonomy.assigned_by,
                           m.QuestionTaxonomy.reviewed)
                    .join(m.QuestionTaxonomy, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id)
                    .where(m.QuestionTaxonomy.question_id == qid)
                    .order_by(m.TaxonomyNode.code)
                ).all()

                lines.append('=' * 100)
                lines.append(
                    f"[{total}] {slug} | {doc.paper_code} | year={doc.year} "
                    f"session={series.session if series else None} | qid={qid} | "
                    f"{q.number_path} | marks={q.marks} | kind={q.kind}"
                )
                lines.append(
                    f"SUBJECT: {subj.code if subj else None} ({subj.title if subj else ''}) "
                    f"| unit={item.get('unit_code')}"
                )
                lines.append(f"PRE : {pre_txt}")
                lines.append(f"JEV({dec_round}): {dec_txt} {dec.get('code') or ''} | {dec.get('reason') or ''}")
                for code, name, conf, by, rev in tags:
                    lines.append(f"POST: {code} | by={by} | reviewed={rev} | conf={conf}")
                    lines.append(f"      NAME: {name}")
                stem = ' '.join((q.stem_text or '').split())
                lines.append(f"STEM: {stem[:700]}")

                entries = s.execute(
                    select(m.MarkSchemeEntry.answer_text, m.MarkSchemeEntry.number_path,
                           m.MarkSchemeEntry.marks)
                    .where(m.MarkSchemeEntry.question_id == qid)
                ).all()
                for text, np, mk in entries[:2]:
                    txt = ' '.join((text or '').split())
                    lines.append(f"MS[{np} marks={mk}]: {txt[:400]}")

                if not args.no_crops:
                    try:
                        crops = service.question_crops(s, qid, role='qp')
                        viewable += 1
                        stats['viewable'] += 1
                        png_path = crop_dir / f'{qid}.png'
                        png_path.write_bytes(crops[0]['png'])
                        lines.append(
                            f"CROP: OK {len(crops)} crop(s), pages "
                            f"{[c['page'] for c in crops]} -> {png_path.name}"
                        )
                    except Exception as exc:
                        view_err.append(f'{qid} ({slug}): {type(exc).__name__}: {exc}')
                        lines.append(f'CROP: ERROR {type(exc).__name__}: {str(exc)[:200]}')
                lines.append('')
            per_subject[slug] = stats
            lines.append(
                f'--- {slug}: sampled={stats["sampled"]} keep={stats["keep"]} '
                f'change={stats["change"]} viewable={stats["viewable"]}'
            )
            lines.append('')

    summary = [
        '=' * 100,
        f'SAMPLE SUMMARY: total={total} keep={keep_n} change={change_n} '
        f'viewable={viewable}/{"n/a" if args.no_crops else total}',
        f'view errors: {len(view_err)}',
    ]
    for e in view_err[:20]:
        summary.append(f'  VIEW-ERR {e}')
    for slug in slugs:
        st = per_subject.get(slug)
        if st:
            summary.append(
                f'  {slug}: n={st["sampled"]} keep={st["keep"]} change={st["change"]} '
                f'viewable={st["viewable"]}'
            )
    out = ROOT / args.out
    out.write_text('\n'.join(lines + summary) + '\n', encoding='utf-8')
    print(f'sampled {total} questions -> {out}')
    print('\n'.join(summary))


if __name__ == '__main__':
    main()
