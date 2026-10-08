"""Jev (TypeSafe System One) tagging for psy batch-007 — 43 questions.

Usage:
  python examdata/tmp_jev_tag.py --preflight        # DB checks only, no network
  python examdata/tmp_jev_tag.py                    # run all missing questions
  python examdata/tmp_jev_tag.py --only 65939,65977 # rerun subset
  python examdata/tmp_jev_tag.py --force            # redo everything
"""
import argparse
import json
import os
import re
import sys
import time

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, r'C:/Users/weo/Desktop/api/examdata')
from examdata.core import models as m
from examdata.tagging.corpus import unit_code_from_paper

DB = 'sqlite:///C:/Users/weo/Desktop/api/examdata/.data/examdata.db'
OUT = r'C:/Users/weo/Desktop/api/examdata/tmp_jev_psy007.jsonl'
URL = 'https://api.typesafe.ai/v1/systemone'
MODEL = 'jev-latest'

IDS = [65939, 65977, 65998, 65999, 66006, 66030, 66036, 66040, 66042, 66057,
       66058, 66059, 66067, 66068, 66069, 66103, 66104, 66106, 66111, 66112,
       66113, 66114, 66115, 66122, 66123, 66126, 66150, 66154, 66170, 66180,
       66196, 66203, 66209, 66214, 66241, 66257, 66258, 66259, 66262, 66268,
       66270, 66281, 66283]

INSTRUCTIONS = (
    "You are assigning a specification tag to one exam question from a Pearson Edexcel "
    "International A Level Psychology past paper (specification WPS01-WPS04).\n"
    "Choose the SINGLE specification content point, from the criteria list, that this question "
    "primarily assesses. The state gives the paper title, the question number and marks, the "
    "shared scenario text ('context'), and the question text ('question').\n"
    "Guidance used consistently across this project:\n"
    "1. Data questions: if the question asks candidates to calculate, present or interpret data "
    "(mean, ratio, percentage, range, reading a table or graph, choice of statistical test, "
    "conclusions from data), choose the 'analysis of quantitative data' / 'descriptive statistics' / "
    "'decision making and interpretation of data' content point of the topic the scenario belongs to.\n"
    "2. Methods questions: if the question asks about research methods, design, sampling, ethics, "
    "validity, reliability, or improvements to a study, choose the research-methods / "
    "practical-issues content point of the relevant topic.\n"
    "3. Content questions: if the question asks about a theory, model, explanation, study, or "
    "therapy, choose the specific content point for that theory/study/therapy.\n"
    "4. Every option name is a specification code. Each option description is the specification "
    "wording followed by its place in the specification hierarchy in the form "
    "'[unit > topic > section]'. Several topics contain content points with nearly identical "
    "wording (e.g. 'Analysis of quantitative data'), so you MUST use the hierarchy to pick the "
    "point in the topic (social / cognitive / biological / learning / developmental / "
    "criminological / health / clinical psychology) that matches the scenario. Answer with "
    "exactly one option name.\n"
)

UNIT_NAMES = {
    'WPS01': 'Social and cognitive psychology',
    'WPS02': 'Biological psychology, learning theories and development',
    'WPS03': 'Applications of psychology',
    'WPS04': 'Clinical psychology and psychological skills',
}

PAT = re.compile(r'^WPS0([1-4])-\d+\.\d+\.\d+$')


def clean(text, limit):
    if not text:
        return ''
    text = re.sub(r'\.{4,}', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()[:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preflight', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--only', default='')
    args = ap.parse_args()

    eng = create_engine(DB)
    s = Session(eng)

    # candidate leaf nodes per unit (normal codes only, no I5 variants)
    nodes = s.execute(select(m.TaxonomyNode).where(m.TaxonomyNode.code.like('WPS%'))
                      .order_by(m.TaxonomyNode.code)).scalars().all()
    by_id = {n.id: n for n in nodes}
    by_unit = {}
    desc_by_code = {}
    for n in nodes:
        mm = PAT.match(n.code)
        if mm:
            by_unit.setdefault('WPS0' + mm.group(1), []).append(n)
            parts = []
            p = n.parent_id
            depth = 0
            while p is not None and depth < 6:
                pn = by_id.get(p)
                if not pn:
                    break
                parts.append(pn.name)
                p = pn.parent_id
                depth += 1
            hier = ' > '.join(reversed(parts))
            desc_by_code[n.code] = f'{n.name or ""} [{hier}]'
    print('candidates per unit:', {k: len(v) for k, v in sorted(by_unit.items())})

    questions = []
    problems = []
    for qid in IDS:
        q = s.get(m.Question, qid)
        if not q:
            problems.append((qid, 'missing question'))
            continue
        paper = s.get(m.Paper, q.paper_id)
        doc = s.get(m.Document, paper.document_id) if paper else None
        unit = unit_code_from_paper(paper.attrs if paper else None,
                                    doc.paper_code if doc else None)
        rows = s.execute(select(m.QuestionTaxonomy, m.TaxonomyNode).join(
            m.TaxonomyNode, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id
        ).where(m.QuestionTaxonomy.question_id == qid)).all()
        tags = [(n.code, qt.reviewed, qt.assigned_by) for qt, n in rows]
        bad = [t for t in tags if t[1] or t[2] != 'edexcel-bm25-v1']
        if bad:
            problems.append((qid, f'non-algo/reviewed rows: {bad}'))
        if unit is None:
            problems.append((qid, 'unit unresolved'))
        if unit and unit not in by_unit:
            problems.append((qid, f'no candidates for unit {unit}'))
        questions.append((qid, q, paper, doc, unit, tags))

    print(f'questions: {len(questions)}, problems: {len(problems)}')
    for qid, msg in problems:
        print('  PROBLEM', qid, msg)
    if args.preflight:
        for qid, q, paper, doc, unit, tags in questions:
            print(f'  {qid} {unit} {q.number_label} marks={q.marks} '
                  f'tags={[t[0] for t in tags]}')
        return
    if problems:
        print('preflight problems -> abort')
        return

    done = set()
    records = []
    if os.path.exists(OUT) and not args.force:
        with open(OUT, encoding='utf-8') as fh:
            for line in fh:
                rec = json.loads(line)
                records.append(rec)
                if rec.get('choice'):
                    done.add(rec['question_id'])
    if args.only:
        only = {int(x) for x in args.only.split(',') if x.strip()}
    else:
        only = set()

    key = os.environ['TYPESAFE_API_KEY']
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}

    todo = [t for t in questions if (t[0] not in done and (not only or t[0] in only))]
    print(f'todo: {len(todo)} (already done: {len(done)})')

    for qid, q, paper, doc, unit, tags in todo:
        parent = s.get(m.Question, q.parent_id) if q.parent_id else None
        state = {
            'exam': 'Pearson Edexcel International A Level Psychology',
            'unit': unit,
            'unit_name': UNIT_NAMES.get(unit, ''),
            'paper': doc.title if doc else '',
            'question_number': q.number_label,
            'marks': q.marks,
            'context': clean(parent.stem_text if parent else '', 1800),
            'question': clean(q.stem_text, 1500),
        }
        criteria = {n.code: desc_by_code[n.code][:900] for n in by_unit[unit]}
        payload = {
            'state': state,
            'model': MODEL,
            'questions': {'q': {'type': 'choice', 'instructions': INSTRUCTIONS,
                                'criteria': criteria}},
        }
        resp = None
        delay = 2.0
        for attempt in range(7):
            try:
                r = httpx.post(URL, headers=headers, json=payload, timeout=180)
                if r.status_code in (429, 529, 500, 502, 503, 504):
                    print(f'  {qid} HTTP {r.status_code}, retry in {delay:.0f}s')
                    time.sleep(delay)
                    delay *= 2
                    continue
                r.raise_for_status()
                resp = r.json()
                break
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                print(f'  {qid} {type(exc).__name__}, retry in {delay:.0f}s')
                time.sleep(delay)
                delay *= 2
        if resp is None:
            print(f'  {qid} FAILED after retries')
            records.append({'question_id': qid, 'error': 'request failed'})
            continue
        ans = (resp.get('answers') or {}).get('q') or {}
        rec = {
            'question_id': qid,
            'unit': unit,
            'paper': state['paper'],
            'number': q.number_label,
            'marks': q.marks,
            'current_tags': [t[0] for t in tags],
            'choice': ans.get('choice'),
            'confidence': ans.get('confidence'),
            'probabilities': ans.get('probabilities'),
            'model': resp.get('model'),
            'usage': resp.get('usage'),
            'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        }
        records.append(rec)
        print(f"  {qid} {unit} -> {rec['choice']} conf={rec['confidence']}")
        time.sleep(0.4)

    # rewrite file: keep one record per question (latest wins)
    latest = {}
    order = []
    for rec in records:
        qid = rec['question_id']
        if qid not in latest:
            order.append(qid)
        latest[qid] = rec
    with open(OUT, 'w', encoding='utf-8') as fh:
        for qid in order:
            fh.write(json.dumps(latest[qid], ensure_ascii=False) + '\n')
    ok = sum(1 for r in latest.values() if r.get('choice'))
    print(f'saved {len(latest)} records, {ok} with choice -> {OUT}')


if __name__ == '__main__':
    main()
