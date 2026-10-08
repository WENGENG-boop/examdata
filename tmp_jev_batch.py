"""Generic batch-mode Jev tagging for Edexcel review batches.

One Jev call per chunk of questions; shared state = exam only; per-question
instructions carry unit/paper/text; criteria = that unit's spec points.

Usage:
  python examdata/tmp_jev_batch.py --subject ial18-business --preflight
  python examdata/tmp_jev_batch.py --subject ial18-business
  python examdata/tmp_jev_batch.py --subject ial18-business --only 001,002 --force
"""
import argparse
import glob
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
from examdata.tagging.corpus import load_points, unit_code_from_paper

DB_URL = 'sqlite:///C:/Users/weo/Desktop/api/examdata/.data/examdata.db'
URL = 'https://api.typesafe.ai/v1/systemone'
MODEL = 'jev-latest'
ROOT = 'C:/Users/weo/Desktop/api/examdata'
REVIEW = ROOT + '/.data/tagging/review-export'

BUSINESS_INSTR = (
    "You are assigning a specification tag to one exam question from a Pearson Edexcel "
    "International A Level Business past paper (specification WBS11-WBS14).\n"
    "Choose the SINGLE specification content point, from the criteria list, that this question "
    "primarily assesses. The shared state gives the exam. This question's own fields give "
    "`unit`, `unit_name`, `paper`, `question_number`, `marks`, `context` (scenario/extract "
    "text from the paper) and `question_text` (the question itself).\n"
    "Guidance used consistently across this project:\n"
    "1. Every option name is a specification code. Its description is the specification "
    "wording followed by its place in the hierarchy in the form '[unit > topic > subtopic]'. "
    "Choose the content point whose wording best matches what the question asks candidates to do.\n"
    "2. Data/numerical questions (calculate or interpret figures from a table or extract, e.g. "
    "ratios, revenue, elasticity, market share, cash flow): choose the content point about that "
    "specific calculation/financial concept in the matching topic.\n"
    "3. 'Assess/Evaluate/Discuss/Analyse' questions about a business or context: choose the "
    "content point for the concept the question centres on (the specific strategy, objective, "
    "factor or model named in the question), using the scenario to disambiguate.\n"
    "4. Definitions ('Define the term X'): choose the content point that defines X.\n"
    "5. When similar wording appears under several topics, use `unit`/`unit_name` and the "
    "scenario to pick the correct topic. Answer with exactly one option name.\n"
)

def mk_instructions(subject_label, spec_range, *, practical=False):
    text = (
        f"You are assigning a specification tag to one exam question from a Pearson Edexcel "
        f"International A Level {subject_label} past paper (specification {spec_range}).\n"
        "Choose the SINGLE specification content point, from the criteria list, that this question "
        "primarily assesses. The shared state gives the exam. This question's own fields give "
        "`unit`, `unit_name`, `paper`, `question_number`, `marks`, `context` (scenario/context "
        "text from the paper) and `question_text` (the question itself).\n"
        "Guidance used consistently across this project:\n"
        "1. Every option name is a specification code. Its description is the specification "
        "wording followed by its place in the hierarchy in the form '[unit > topic > subtopic]'. "
        "Choose the content point whose wording best matches what the question asks candidates to do.\n"
        "2. Data/numerical/calculation questions: choose the content point about that specific "
        "concept or calculation in the matching topic.\n"
        "3. Explain/Describe/Discuss/Analyse/Evaluate questions: choose the content point for the "
        "concept the question centres on (the specific idea named in the question), using the "
        "scenario to disambiguate.\n"
        "4. Definitions ('Define/State what is meant by X'): choose the content point that defines X.\n"
        "5. When similar wording appears under several topics, use `unit`/`unit_name` and the "
        "scenario to pick the correct topic. Answer with exactly one option name.\n"
    )
    if practical:
        text += (
            "6. Practical-skills questions (planning an investigation, describing measurements "
            "or implementation, processing or analysing experimental data, suggesting "
            "improvements): choose the practical-skills section (Planning / Implementation and "
            "measurements / Processing results or Analysis) that matches what the question asks.\n"
        )
    return text


SUBJECTS = {
    'ial18-business': {
        'exam': 'Pearson Edexcel International A Level Business',
        'instructions': BUSINESS_INSTR,
        'chunk': 5,
    },
    'ial-spanish': {
        'exam': 'Pearson Edexcel International A Level Spanish',
        'instructions': mk_instructions('Spanish', 'WSP01-WSP04'),
        'chunk': 15,
    },
    'ial18-biology': {
        'exam': 'Pearson Edexcel International A Level Biology',
        'instructions': mk_instructions('Biology', 'WBI11-WBI16', practical=True),
        'chunk': 6,
    },
    'ial18-chemistry': {
        'exam': 'Pearson Edexcel International A Level Chemistry',
        'instructions': mk_instructions('Chemistry', 'WCH11-WCH16', practical=True),
        'chunk': 3,
    },
    'ial18-economics': {
        'exam': 'Pearson Edexcel International A Level Economics',
        'instructions': mk_instructions('Economics', 'WEC11-WEC14'),
        'chunk': 15,
    },
    'ial18-physics': {
        'exam': 'Pearson Edexcel International A Level Physics',
        'instructions': mk_instructions('Physics', 'WPH11-WPH16', practical=True),
        'chunk': 7,
    },
    'ial18-it': {
        'exam': 'Pearson Edexcel International A Level Information Technology',
        'instructions': mk_instructions('Information Technology', 'WIT11-WIT14'),
        'chunk': 4,
    },
    'ial-accounting': {
        'exam': 'Pearson Edexcel International A Level Accounting',
        'instructions': mk_instructions('Accounting', 'WAC01, WAC02, WAC11, WAC12'),
        'chunk': 5,
    },
    'ial-german': {
        'exam': 'Pearson Edexcel International A Level German',
        'instructions': mk_instructions('German', 'WGN01-WGN04'),
        'chunk': 15,
    },
    'ial-maths': {
        'exam': 'Pearson Edexcel International A Level Mathematics (legacy)',
        'instructions': mk_instructions('Mathematics', 'WMA01, WMA02, WDM01'),
        'chunk': 15,
    },
    'ial18-mathematics': {
        'exam': 'Pearson Edexcel International A Level Mathematics/Further Mathematics',
        'instructions': mk_instructions(
            'Mathematics/Further Mathematics',
            'WMA11-WMA14, WFM01-WFM03, WME01-WME03, WST01-WST03, WDM11',
        ),
        'chunk': 12,
    },
    'ial18-mathematics-extra': {
        'exam': 'Pearson Edexcel International A Level Mathematics (legacy papers on shared units)',
        'instructions': mk_instructions(
            'Mathematics',
            'WMA11-WMA14, WFM01-WFM03, WME01-WME03, WST01-WST03, WDM11',
        ),
        'chunk': 15,
        'points_subject': 'ial18-mathematics',
    },
    'ial-psychology': {
        'exam': 'Pearson Edexcel International A Level Psychology',
        'instructions': mk_instructions('Psychology', 'WPS01-WPS04'),
        'chunk': 6,
    },
    'ial-history': {
        'exam': 'Pearson Edexcel International A Level History',
        'instructions': mk_instructions('History', 'WHI01-WHI04'),
        'chunk': 15,
    },
    'ial-french': {
        'exam': 'Pearson Edexcel International A Level French',
        'instructions': mk_instructions('French', 'WFR01-WFR04'),
        'chunk': 15,
    },
    'ial-geography': {
        'exam': 'Pearson Edexcel International A Level Geography',
        'instructions': mk_instructions('Geography', 'WGE01-WGE04'),
        'chunk': 15,
    },
    'ial-greek': {
        'exam': 'Pearson Edexcel International A Level Greek',
        'instructions': mk_instructions('Greek', 'WGK01-WGK02'),
        'chunk': 15,
    },
    'ial-law': {
        'exam': 'Pearson Edexcel International A Level Law',
        'instructions': mk_instructions('Law', 'YLA0-P1, YLA0-P2, YLA1-01, YLA1-02'),
        'chunk': 8,
    },
    'ial-englang': {
        'exam': 'Pearson Edexcel International A Level English Language',
        'instructions': mk_instructions('English Language', 'WEN01-WEN04'),
        'chunk': 15,
    },
    'ial-englit': {
        'exam': 'Pearson Edexcel International A Level English Literature',
        'instructions': mk_instructions('English Literature', 'WET01-WET04'),
        'chunk': 15,
    },
}


def clean(text, limit):
    if not text:
        return ''
    text = re.sub(r'\.{4,}', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()[:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--subject', required=True)
    ap.add_argument('--only', default='')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--preflight', action='store_true')
    ap.add_argument('--chunk', type=int, default=0)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument(
        '--auto-single',
        action='store_true',
        help='units with exactly one candidate point: auto-pick it without a Jev call',
    )
    ap.add_argument(
        '--skip-problems',
        action='store_true',
        help='skip rows whose unit cannot be resolved; log them to tmp_jev_{slug}.problems.jsonl',
    )
    ap.add_argument('--batches-dir', default='', help='override batches directory')
    ap.add_argument('--out', default='', help='override output jsonl path')
    args = ap.parse_args()

    slug = args.subject
    cfg = SUBJECTS[slug]
    chunk = args.chunk or cfg['chunk']
    batch_dir = args.batches_dir or f'{REVIEW}/{slug}/batches'
    out_path = args.out or f'{ROOT}/tmp_jev_{slug}.jsonl'

    eng = create_engine(DB_URL)
    s = Session(eng)
    points_slug = cfg.get('points_subject', slug)
    sub_row = s.execute(select(m.Subject).where(m.Subject.slug == points_slug)).scalar()
    keys = {(sub_row.code or '').strip().lower(), (sub_row.slug or '').strip().lower()}
    keys.discard('')
    points = [p for p in load_points(s) if (p.subject or '').strip().lower() in keys]
    by_unit = {}
    desc = {}
    for p in points:
        by_unit.setdefault(p.unit_code, []).append(p)
        hier = ' > '.join(reversed(p.ancestors))
        desc[p.code] = f'{p.name} [{hier}]'[:600]
    print(f'subject {slug}: {len(points)} points; units: '
          f'{ {k: len(v) for k, v in sorted(by_unit.items())} }')

    files = sorted(glob.glob(batch_dir + '/batch-*.jsonl'))
    if args.only:
        wanted = {x.strip() for x in args.only.split(',') if x.strip()}
        files = [f for f in files if re.search(r'batch-(\w+)\.jsonl$', f).group(1) in wanted]
    print('batches:', [f.split('/')[-1] for f in files])

    # load rows
    all_rows = []
    problems = []
    for f in files:
        batch = re.search(r'(batch-\w+)\.jsonl$', f).group(1)
        for line in open(f, encoding='utf-8'):
            rec = json.loads(line)
            qid = rec['question_id']
            unit = rec.get('unit_code')
            q = s.get(m.Question, qid)
            if q is None:
                problems.append((qid, 'missing question'))
                continue
            q_paper = s.get(m.Paper, q.paper_id)
            q_doc = s.get(m.Document, q_paper.document_id) if q_paper else None
            fresh = unit_code_from_paper(
                q_paper.attrs if q_paper else None,
                q_doc.paper_code if q_doc else None,
            )
            if fresh and fresh in by_unit:
                unit = fresh
            elif unit not in by_unit:
                problems.append((qid, f'no candidates for unit {unit!r} (fresh {fresh!r})'))
                continue
            all_rows.append({
                'batch': batch, 'qid': qid, 'unit': unit,
                'paper_code': rec.get('paper_code'),
                'number_label': rec.get('number_label') or '',
                'current': rec.get('current') or [],
                'q': q,
            })
    if args.limit:
        all_rows = all_rows[:args.limit]
    print(f'rows: {len(all_rows)}, problems: {len(problems)}')
    for qid, msg in problems[:20]:
        print('  PROBLEM', qid, msg)

    if args.preflight:
        for r in all_rows[:60]:
            q = r['q']
            print(f"  {r['qid']} {r['batch']} {r['unit']} {r['number_label']!r} "
                  f"marks={q.marks} cur={[c['code'] for c in r['current']]}")
        print('preflight done')
        return
    if problems:
        if not args.skip_problems:
            print('problems present -> abort (use --skip-problems to skip and log)')
            return
        out = f'{ROOT}/tmp_jev_{slug}.problems.jsonl'
        with open(out, 'w', encoding='utf-8') as fh:
            for qid, msg in problems:
                fh.write(json.dumps({'question_id': qid, 'problem': msg}, ensure_ascii=False) + '\n')
        print(f'skipped {len(problems)} problem rows -> {out}')

    done = set()
    records = []
    if os.path.exists(out_path) and not args.force:
        for line in open(out_path, encoding='utf-8'):
            rec = json.loads(line)
            records.append(rec)
            if rec.get('choice'):
                done.add(rec['question_id'])

    def save():
        latest = {}
        order = []
        for rec in records:
            qid = rec['question_id']
            if qid not in latest:
                order.append(qid)
            latest[qid] = rec
        with open(out_path, 'w', encoding='utf-8') as fh:
            for qid in order:
                fh.write(json.dumps(latest[qid], ensure_ascii=False) + '\n')

    if args.auto_single:
        singles = [r for r in all_rows if len(by_unit[r['unit']]) == 1]
        new_singles = [r for r in singles if r['qid'] not in done]
        for r in new_singles:
            code = by_unit[r['unit']][0].code
            records.append({
                'question_id': r['qid'],
                'batch': r['batch'],
                'unit': r['unit'],
                'paper_code': r['paper_code'],
                'number': r['number_label'],
                'marks': r['q'].marks,
                'current': [{'code': c['code'], 'confidence': c.get('confidence')}
                            for c in r['current']],
                'choice': code,
                'confidence': 1.0,
                'top_probs': [[code, 1.0]],
                'model': 'auto-single-candidate',
                'usage': None,
                'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
            })
            done.add(r['qid'])
        if new_singles:
            save()
        print(f'auto-single: {len(singles)} rows in single-candidate units, '
              f'{len(new_singles)} newly auto-picked')

    todo = [r for r in all_rows if r['qid'] not in done]
    print(f'todo: {len(todo)} (already done: {len(done)})')

    key = os.environ['TYPESAFE_API_KEY']
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}

    # group todo by batch preserving order, then chunk
    chunks = []
    cur = []
    for r in todo:
        cur.append(r)
        if len(cur) >= chunk:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    print(f'chunks: {len(chunks)} (chunk size {chunk})')

    def build_payload(rows):
        questions = {}
        for r in rows:
            q = r['q']
            paper = s.get(m.Paper, q.paper_id)
            doc = s.get(m.Document, paper.document_id) if paper else None
            parent = s.get(m.Question, q.parent_id) if q.parent_id else None
            unit_name = next((p.ancestors[-1] for p in by_unit[r['unit']] if p.ancestors), '')
            questions[f"q{r['qid']}"] = {
                'type': 'choice',
                'instructions': {
                    'task': cfg['instructions'],
                    'unit': r['unit'],
                    'unit_name': unit_name,
                    'paper': doc.title if doc else '',
                    'question_number': r['number_label'],
                    'marks': q.marks,
                    'context': clean(parent.stem_text if parent else '', 1500),
                    'question_text': clean(q.stem_text, 1800),
                },
                'criteria': {p.code: desc[p.code] for p in by_unit[r['unit']]},
            }
        return {'state': {'exam': cfg['exam']}, 'model': MODEL, 'questions': questions}

    def send(rows, depth=0):
        payload = build_payload(rows)
        tag = f'chunk {len(rows)}q ~{len(json.dumps(payload)) // 1024}KB'
        resp = None
        delay = 2.0
        for attempt in range(7):
            try:
                rr = httpx.post(URL, headers=headers, json=payload, timeout=300)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                print(f'  {tag}: {type(exc).__name__}, retry in {delay:.0f}s')
                time.sleep(delay)
                delay *= 2
                continue
            if rr.status_code in (429, 529, 500, 502, 503, 504):
                print(f'  {tag}: HTTP {rr.status_code}, retry in {delay:.0f}s')
                time.sleep(delay)
                delay *= 2
                continue
            if rr.status_code != 200:
                print(f'  {tag}: HTTP {rr.status_code} non-retryable {rr.text[:160]!r}')
                if len(rows) > 1:
                    mid = len(rows) // 2
                    print(f'  {tag}: splitting into {mid}+{len(rows) - mid}')
                    send(rows[:mid], depth + 1)
                    send(rows[mid:], depth + 1)
                else:
                    records.append({'question_id': rows[0]['qid'], 'batch': rows[0]['batch'],
                                    'error': f'HTTP {rr.status_code}'})
                    save()
                return
            resp = rr.json()
            break
        if resp is None:
            print(f'  {tag}: FAILED after retries; recording errors')
            for r in rows:
                records.append({'question_id': r['qid'], 'batch': r['batch'],
                                'error': 'request failed'})
            save()
            return

        answers = resp.get('answers') or {}
        for r in rows:
            ans = answers.get(f"q{r['qid']}") or {}
            probs = ans.get('probabilities') or {}
            top = sorted(probs.items(), key=lambda kv: -kv[1])[:10]
            rec = {
                'question_id': r['qid'],
                'batch': r['batch'],
                'unit': r['unit'],
                'paper_code': r['paper_code'],
                'number': r['number_label'],
                'marks': r['q'].marks,
                'current': [{'code': c['code'], 'confidence': c.get('confidence')}
                            for c in r['current']],
                'choice': ans.get('choice'),
                'confidence': ans.get('confidence'),
                'top_probs': top,
                'model': resp.get('model'),
                'usage': resp.get('usage'),
                'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
            }
            records.append(rec)
            print(f"  {r['qid']} {r['unit']} {r['number_label']!r} -> {rec['choice']} "
                  f"conf={rec['confidence']}")
        save()

    for ci, rows in enumerate(chunks):
        print(f'chunk {ci + 1}/{len(chunks)}: {len(rows)} questions')
        send(rows)

    ok = sum(1 for r in records if r.get('choice'))
    print(f'saved {len(records)} records, {ok} with choice -> {out_path}')


if __name__ == '__main__':
    main()
