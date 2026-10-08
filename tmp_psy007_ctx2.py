import sys, json, glob, os
from sqlalchemy import select, create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, r'C:/Users/weo/Desktop/api/examdata')
from examdata.core import models as m

eng = create_engine('sqlite:///C:/Users/weo/Desktop/api/examdata/.data/examdata.db')
s = Session(eng)
out = []

dec_dir = r'C:/Users/weo/Desktop/api/examdata/.data/tagging/review-export/ial-psychology/decisions'
all_rows = []
for f in glob.glob(dec_dir + '/*.jsonl'):
    for line in open(f, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        all_rows.append((os.path.basename(f), r))

def search(label, keywords, cap=30):
    out.append(f'--- {label} ---')
    cnt = 0
    seen = set()
    for fn, r in all_rows:
        txt = json.dumps(r, ensure_ascii=False)
        if any(k in txt for k in keywords):
            key = (r.get('question_id'), r.get('code'), r.get('decision'))
            if key in seen:
                continue
            seen.add(key)
            cnt += 1
            if cnt <= cap:
                out.append(f'  {txt[:250]}')
    out.append(f'  [total {cnt}]')

search('改进/improvement', ['改进'])
search('样本/抽样', ['样本', '抽样'])
search('定量/定性', ['定量', '定性'])
search('开放式/问卷', ['开放式', '问卷'])
search('效度/信度', ['效度', '信度'])
search('9.3.2 usage', ['"9.3.2"'])
search('9.3.4 usage', ['"9.3.4"'])
search('9.2.1 usage', ['"9.2.1"'])
search('9.1.13 usage', ['"9.1.13"'])
search('9.1.6 usage', ['"9.1.6"'])
search('1.2.6 usage', ['"1.2.6"'])
search('2.2.11 usage', ['"2.2.11"'])
search('4.1.2 usage', ['"4.1.2"'])
search('4.1.4 usage', ['"4.1.4"'])

# pull texts of comparison questions
def ctx(qid, n=450):
    q = s.get(m.Question, qid)
    if not q:
        out.append(f'[{qid}] MISSING')
        return
    paper = s.get(m.Paper, q.paper_id) if q.paper_id else None
    doc = s.get(m.Document, paper.document_id) if paper else None
    out.append(f'[{qid}] {doc.title if doc else "?"} | {q.number_label} | m={q.marks}')
    out.append('  OWN: ' + (q.stem_text or '')[:n].replace(chr(10), ' '))
    if q.parent_id:
        par = s.get(m.Question, q.parent_id)
        if par:
            out.append('  PAR: ' + (par.stem_text or '')[:600].replace(chr(10), ' '))

out.append('##### comparison question texts #####')
for qid in [65559, 65892, 64910, 64900, 65704, 65712, 65735, 64727, 65906, 65918,
            64760, 65021, 65977, 65975, 65976, 66103, 66104, 66106, 66040, 66042,
            66030, 66170, 66180, 65939, 66262, 66268, 66270, 66281, 66283]:
    ctx(qid)
    out.append('')

open(r'C:/Users/weo/Desktop/api/examdata/tmp_psy007_ctx2.txt', 'w', encoding='utf-8').write('\n'.join(out))
print('written', len(out), 'lines')
