"""Jev batch-mode test: rerun 6 psy-007 questions in ONE call, shared state,
per-question instructions. Compare choices vs known single-mode results.
"""
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

DB = 'sqlite:///C:/Users/weo/Desktop/api/examdata/.data/examdata.db'
URL = 'https://api.typesafe.ai/v1/systemone'
MODEL = 'jev-latest'
IDS = [66103, 66104, 66106, 66111, 66112, 66113]
OUT = r'C:/Users/weo/Desktop/api/examdata/tmp_jev_batchtest.json'
KNOWN_FILE = r'C:/Users/weo/Desktop/api/examdata/tmp_jev_psy007.jsonl'

BASE = (
    "You are assigning a specification tag to one exam question from a Pearson Edexcel "
    "International A Level Psychology past paper (specification WPS01-WPS04).\n"
    "Choose the SINGLE specification content point, from the criteria list, that this question "
    "primarily assesses. The shared state gives the exam and unit. The other fields of THIS "
    "question's instructions give `paper` (paper title), `question_number`, `marks`, `context` "
    "(shared scenario text) and `question_text` (the question itself).\n"
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
    eng = create_engine(DB)
    s = Session(eng)

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

    known = {}
    for line in open(KNOWN_FILE, encoding='utf-8'):
        rec = json.loads(line)
        known[rec['question_id']] = rec

    questions = {}
    meta = {}
    for qid in IDS:
        q = s.get(m.Question, qid)
        paper = s.get(m.Paper, q.paper_id)
        doc = s.get(m.Document, paper.document_id)
        unit = (paper.attrs or {}).get('unit_code')
        parent = s.get(m.Question, q.parent_id) if q.parent_id else None
        assert unit == 'WPS03', (qid, unit)
        instructions = {
            'task': BASE,
            'paper': doc.title if doc else '',
            'question_number': q.number_label,
            'marks': q.marks,
            'context': clean(parent.stem_text if parent else '', 1800),
            'question_text': clean(q.stem_text, 1500),
        }
        criteria = {n.code: desc_by_code[n.code][:900] for n in by_unit[unit]}
        questions[f'q{qid}'] = {'type': 'choice', 'instructions': instructions,
                                'criteria': criteria}
        meta[qid] = {'unit': unit, 'number': q.number_label, 'marks': q.marks}

    state = {'exam': 'Pearson Edexcel International A Level Psychology',
             'unit': 'WPS03', 'unit_name': UNIT_NAMES['WPS03']}
    payload = {'state': state, 'model': MODEL, 'questions': questions}
    print(f'payload questions: {len(questions)}; approx bytes: {len(json.dumps(payload))}')

    key = os.environ['TYPESAFE_API_KEY']
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}

    t0 = time.time()
    resp = None
    delay = 2.0
    for attempt in range(7):
        try:
            r = httpx.post(URL, headers=headers, json=payload, timeout=300)
            if r.status_code in (429, 529, 500, 502, 503, 504):
                print(f'HTTP {r.status_code}, retry in {delay:.0f}s')
                time.sleep(delay)
                delay *= 2
                continue
            r.raise_for_status()
            resp = r.json()
            break
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            print(f'{type(exc).__name__}, retry in {delay:.0f}s')
            time.sleep(delay)
            delay *= 2
    dt = time.time() - t0
    if resp is None:
        print('FAILED after retries')
        return

    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(resp, fh, ensure_ascii=False, indent=1)

    print(f'latency: {dt:.1f}s; usage: {resp.get("usage")}; model: {resp.get("model")}')
    print(f'{"qid":>7} {"batch_choice":<18} {"conf":>5}  {"single_choice":<18} {"sconf":>5}  match')
    answers = resp.get('answers') or {}
    nmatch = 0
    for qid in IDS:
        ans = answers.get(f'q{qid}') or {}
        k = known.get(qid) or {}
        match = ans.get('choice') == k.get('choice')
        nmatch += bool(match)
        print(f'{qid:>7} {str(ans.get("choice")):<18} {ans.get("confidence", 0):>5.2f}  '
              f'{str(k.get("choice")):<18} {k.get("confidence", 0):>5.2f}  {match}')
    print(f'matched {nmatch}/{len(IDS)}')


if __name__ == '__main__':
    main()
