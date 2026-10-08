"""Generate business decision report + preliminary decisions from Jev output."""
import json
import re
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, r'C:/Users/weo/Desktop/api/examdata')
from examdata.core import models as m

ROOT = r'C:/Users/weo/Desktop/api/examdata'


def clean(text, limit):
    if not text:
        return ''
    text = re.sub(r'\.{4,}', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()[:limit]


def main():
    eng = create_engine('sqlite:///C:/Users/weo/Desktop/api/examdata/.data/examdata.db')
    s = Session(eng)
    names = {}
    for n in s.execute(select(m.TaxonomyNode)).scalars():
        names[n.code] = n.name
    recs = [json.loads(l) for l in open(f'{ROOT}/tmp_jev_ial18-business.jsonl', encoding='utf-8')]
    rows = []
    n_keep = n_change = 0
    for r in recs:
        qid = r['question_id']
        cur = [c['code'] for c in r['current']]
        jc = r['choice']
        if jc in cur and len(cur) == 1:
            dec = 'keep'
        else:
            dec = 'change'
        if dec == 'keep':
            n_keep += 1
        else:
            n_change += 1
        q = s.get(m.Question, qid)
        paper = s.get(m.Paper, q.paper_id)
        doc = s.get(m.Document, paper.document_id) if paper else None
        stem = clean(q.stem_text or '', 260)
        rows.append((qid, r['batch'], r['unit'], r['number'], q.marks, cur, jc,
                     r['confidence'], dec, doc.paper_code if doc else '', stem))
    with open(f'{ROOT}/tmp_business_review.tsv', 'w', encoding='utf-8') as fh:
        for row in rows:
            qid, batch, unit, number, marks, cur, jc, conf, dec, pcode, stem = row
            fh.write(f'{qid}\t{batch}\t{unit}\t{number}\t{marks}\t{cur}\t{jc}\t'
                     f'{conf:.2f}\t{dec}\t{pcode}\t{stem}\n')
    print(f'rows {len(rows)}, keep {n_keep}, change {n_change}')
    print('report -> tmp_business_review.tsv')
    # print compact list: qid, number, marks, cur, jev, conf, decision, stem
    for row in rows:
        qid, batch, unit, number, marks, cur, jc, conf, dec, pcode, stem = row
        cur_s = ' + '.join(f"{c} {names.get(c, '?')[:46]}" for c in cur)
        print(f'{qid} | {unit} {number} m{marks} | {dec.upper()}')
        print(f'    cur: {cur_s}')
        print(f'    jev: {jc} {names.get(jc, "?")[:80]} (c{conf:.2f})')
        print(f'    q: {stem[:150]}')


if __name__ == '__main__':
    main()
