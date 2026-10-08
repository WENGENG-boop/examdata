"""Self-judgment pack generator for the pending Edexcel sets (Jev replacement).

For each (set, slug, unit) it emits compact judge packs: the unit's criteria
plus chunked question excerpts (cleaned stem, head+tail truncation), ready for
the agent to answer in a matching .ans.txt file as:
    qid OK      -> keep the single current label
    qid CODE    -> set / change to CODE
    qid ?       -> unresolved, needs a closer look
tmp_selfjudge_ingest.py converts the answers into the Jev-format jsonl that
tmp_jev_full_decisions.py / tmp_jev_full_apply.py consume.

Units with exactly one candidate point are not packed (auto-single in ingest).

Usage:
  python tmp_selfjudge_prep.py --set r2 --slug ial18-economics
  python tmp_selfjudge_prep.py --set all --slug all [--force]
"""
from __future__ import annotations

import argparse
import glob
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
OUT_ROOT = ROOT / 'tmp_selfjudge'

SETS = {
    'r2': 'tmp_jev_full_batches_r2',
    'unt': 'tmp_jev_untagged_batches',
    'r6': 'tmp_jev_full_batches_r6',
}

R2_SLUGS = ['ial18-chemistry', 'ial18-economics', 'ial18-it', 'ial18-mathematics',
            'ial18-mathematics-extra', 'ial18-physics']
R6_SLUGS = ['ial-accounting', 'ial-englang', 'ial-greek', 'ial-maths',
            'ial18-mathematics', 'ial18-mathematics-extra']
UNT_SLUGS = ['ial-accounting', 'ial-french', 'ial-geography', 'ial-german', 'ial-law',
             'ial-maths', 'ial-psychology', 'ial-spanish', 'ial18-biology',
             'ial18-business', 'ial18-chemistry', 'ial18-economics', 'ial18-it',
             'ial18-mathematics', 'ial18-mathematics-extra', 'ial18-physics']


def clean(text: str) -> str:
    if not text:
        return ''
    text = re.sub(r'_{4,}', ' ', text)
    text = re.sub(r'\.{4,}', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def excerpt(st: str, wide: bool = False) -> str:
    st = clean(st)
    if wide:
        if len(st) <= 1100:
            return st
        return st[:700].rstrip() + ' […] ' + st[-300:].lstrip()
    if len(st) <= 420:
        return st
    return st[:280].rstrip() + ' […] ' + st[-140:].lstrip()


def pack_size(n_points: int) -> int:
    if n_points <= 8:
        return 200
    return 150


def load_subject_points(session: Session, slug: str):
    points_slug = 'ial18-mathematics' if slug == 'ial18-mathematics-extra' else slug
    sub_row = session.execute(select(m.Subject).where(m.Subject.slug == points_slug)).scalar()
    keys = {(sub_row.code or '').strip().lower(), (sub_row.slug or '').strip().lower()}
    keys.discard('')
    points = [p for p in load_points(session) if (p.subject or '').strip().lower() in keys]
    by_unit: dict[str, list] = {}
    for p in points:
        by_unit.setdefault(p.unit_code, []).append(p)
    return by_unit


def context_for(session: Session, q, stem: str) -> str:
    """Context snippet for short stems.

    Priority: own children (degenerate main), longest ancestor, same-numbered
    following rows (broken parent links, e.g. '3 (a) ...'), then neighbours.
    """
    if len(stem) >= 160:
        return ''
    kids = session.execute(
        select(m.Question)
        .where(m.Question.parent_id == q.id)
        .order_by(m.Question.display_order, m.Question.id)
    ).scalars().all()
    if kids:
        parts = [clean(k.stem_text or '') for k in kids[:3]]
        joined = ' | '.join(p for p in parts if p)
        if len(joined) >= 60:
            return joined[:300]
    best = ''
    cur = q
    for _ in range(10):
        if not cur.parent_id:
            break
        par = session.get(m.Question, cur.parent_id)
        if par is None:
            break
        pst = clean(par.stem_text or '')
        if len(pst) > len(best):
            best = pst
        cur = par
    if len(best) >= 60:
        return best[:300]
    label = (q.number_label or '').strip()
    if label:
        nxt = session.execute(
            select(m.Question)
            .where(m.Question.paper_id == q.paper_id,
                   m.Question.display_order > (q.display_order or 0))
            .order_by(m.Question.display_order.asc(), m.Question.id.asc()).limit(12)
        ).scalars().all()
        parts = []
        for p in nxt:
            pst = clean(p.stem_text or '')
            if pst.startswith(label + ' ') or pst.startswith(label + '.'):
                parts.append(pst)
            if len(parts) >= 2:
                break
        joined = ' | '.join(parts)
        if len(joined) >= 40:
            return joined[:300]
    for direction in ('prev', 'next'):
        if direction == 'prev':
            cond = m.Question.display_order < (q.display_order or 0)
            order = m.Question.display_order.desc()
        else:
            cond = m.Question.display_order > (q.display_order or 0)
            order = m.Question.display_order.asc()
        near = session.execute(
            select(m.Question).where(m.Question.paper_id == q.paper_id, cond)
            .order_by(order).limit(5)
        ).scalars().all()
        for p in near:
            pst = clean(p.stem_text or '')
            if len(pst) > len(best):
                best = pst
    return best[:300] if len(best) >= 60 else ''


def collect_rows(session: Session, batch_root: Path, slug: str, by_unit: dict):
    rows = []
    for f in sorted(glob.glob(str(batch_root / slug / 'batches' / 'batch-*.jsonl'))):
        batch = re.search(r'(batch-\w+)\.jsonl$', f).group(1)
        for line in open(f, encoding='utf-8'):
            rec = json.loads(line)
            qid = rec['question_id']
            unit = rec.get('unit_code')
            q = session.get(m.Question, qid)
            if q is None:
                continue
            q_paper = session.get(m.Paper, q.paper_id)
            q_doc = session.get(m.Document, q_paper.document_id) if q_paper else None
            fresh = unit_code_from_paper(
                q_paper.attrs if q_paper else None,
                q_doc.paper_code if q_doc else None,
            )
            if fresh and fresh in by_unit:
                unit = fresh
            stem = rec.get('stem') or ''
            rows.append({
                'batch': batch,
                'qid': qid,
                'unit': unit,
                'paper_code': rec.get('paper_code'),
                'paper_id': q.paper_id,
                'number_label': rec.get('number_label') or '',
                'current': rec.get('current') or [],
                'stem': stem,
                'ctx': context_for(session, q, clean(stem)),
                'marks': q.marks,
                'display_order': q.display_order if q.display_order is not None else 0,
                'has_children': False,
            })
    return rows


def render_pack(set_name: str, slug: str, unit: str, part: int, n_parts: int,
                points: list, rows: list) -> str:
    lines = []
    lines.append(f'# SELFJUDGE PACK {set_name}/{slug}/{unit} part {part}/{n_parts} '
                 f'| {len(rows)} questions')
    lines.append(f'# answer file: {unit}-p{part:02d}.ans.txt  (qid OK | qid CODE | qid ?)')
    lines.append(f'# criteria ({unit}, {len(points)} points):')
    for p in points:
        name = clean(p.name)[:140]
        lines.append(f'#   {p.code}: {name}')
        summary = clean(getattr(p, 'text', '') or '')[:200]
        if summary and summary != name:
            lines.append(f'#       {summary}')
    lines.append('#' + '-' * 78)
    for i, r in enumerate(rows, 1):
        cur = ';'.join(c.get('code') or '?' for c in r['current']) or '-'
        cc = '[C]' if r['has_children'] else ''
        mk = f"{r['marks']}mk" if r['marks'] is not None else '?mk'
        lines.append(f"[{i}] {r['qid']} #{r['number_label']}{cc} {mk} cur={cur}")
        if r.get('ctx'):
            lines.append(f"# ctx: {r['ctx']}")
        lines.append(excerpt(r['stem'], wide=r['has_children']))
        lines.append('')
    return '\n'.join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--set', required=True, choices=['r2', 'unt', 'r6', 'all'])
    ap.add_argument('--slug', required=True)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--pack-size', type=int, default=None,
                    help='override rows per pack (default: adaptive pack_size)')
    args = ap.parse_args()

    sets = list(SETS) if args.set == 'all' else [args.set]
    eng = create_engine(DB_URL)
    session = Session(eng)

    # child map for the [C] marker
    child_rows = session.execute(select(m.Question.parent_id).where(
        m.Question.parent_id.is_not(None))).scalars().all()
    parents = set(child_rows)

    for set_name in sets:
        batch_root = ROOT / SETS[set_name]
        slugs = {'r2': R2_SLUGS, 'unt': UNT_SLUGS, 'r6': R6_SLUGS}[set_name]
        if args.slug != 'all':
            slugs = [args.slug]
        for slug in slugs:
            by_unit = load_subject_points(session, slug)
            rows = collect_rows(session, batch_root, slug, by_unit)
            for r in rows:
                r['has_children'] = r['qid'] in parents
            out_dir = OUT_ROOT / set_name / slug
            out_dir.mkdir(parents=True, exist_ok=True)
            by_unit_rows: dict[str, list] = {}
            for r in rows:
                by_unit_rows.setdefault(r['unit'], []).append(r)
            summary = [f'# {set_name}/{slug}: {len(rows)} rows']
            n_packs = 0
            n_auto = 0
            for unit in sorted(by_unit_rows):
                pts = by_unit.get(unit) or []
                urows = sorted(by_unit_rows[unit],
                               key=lambda r: (r['paper_code'] or '', r['paper_id'],
                                              r['display_order'], r['qid']))
                if len(pts) == 1:
                    n_auto += len(urows)
                    summary.append(f'  {unit}: {len(urows)} rows, 1 point -> auto-single')
                    continue
                size = args.pack_size if args.pack_size else pack_size(len(pts))
                n = (len(urows) + size - 1) // size
                summary.append(f'  {unit}: {len(urows)} rows, {len(pts)} points -> '
                               f'{n} packs of ~{size}')
                for pi in range(n):
                    chunk = urows[pi * size:(pi + 1) * size]
                    pack_path = out_dir / f'{unit}-p{pi + 1:02d}.txt'
                    if pack_path.exists() and not args.force:
                        continue
                    pack_path.write_text(
                        render_pack(set_name, slug, unit, pi + 1, n, pts, chunk),
                        encoding='utf-8')
                    n_packs += 1
            summary.append(f'  TOTAL packs written: {n_packs}, auto-single rows: {n_auto}')
            (out_dir / '_summary.txt').write_text('\n'.join(summary) + '\n', encoding='utf-8')
            print(f'{set_name}/{slug}: rows={len(rows)} packs_written={n_packs} auto={n_auto}')


if __name__ == '__main__':
    main()
