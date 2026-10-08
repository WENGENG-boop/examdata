"""WME02 r2 probe: full stems + MS for uncertain qids (read-only, retries)."""
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'wme02_probe.txt'
log = open(OUT, 'w', encoding='utf-8')


def q(sql, args=()):
    last = None
    for i in range(80):
        try:
            con = sqlite3.connect(f'file:{ROOT / ".data" / "examdata.db"}?mode=ro',
                                  uri=True, timeout=30)
            try:
                return con.execute(sql, args).fetchall()
            finally:
                con.close()
        except sqlite3.OperationalError as e:
            last = e
            time.sleep(5)
    raise SystemExit(f'db fail {last}')


def label_of(qid):
    r = q('''select tn.code from question_taxonomy qt
             join taxonomy_node tn on tn.id = qt.node_id where qt.question_id = ?''', (qid,))
    return ','.join(x[0] for x in r) or '-'


def p(*a):
    print(*a, file=log, flush=True)


QIDS = [56745, 57475, 57969, 59689, 60251, 59261, 57468, 57118, 57119, 57470,
        58517, 58520, 58526, 58528, 59270, 59272, 59693, 59698, 59873, 60262,
        60628, 58698, 57540, 57960, 57962, 58167, 59880, 57107, 56747, 58694,
        58525, 59259]

for qid in QIDS:
    row = q('select id, parent_id, number_label, marks, stem_text from question where id=?', (qid,))
    if not row:
        p(f'Q {qid} NOT FOUND'); continue
    r = row[0]
    par = r[1]
    parlab = label_of(par) if par else '-'
    p(f'===== Q {qid} cur={label_of(qid)} parent={par}[{parlab}] #{r[2]} {r[3]}mk')
    p((r[4] or '')[:1000].replace('\n', ' '))
    for ms in q('''select number_path, answer_text from mark_scheme_entry
                   where question_id=? order by id limit 6''', (qid,)):
        p(f'  MS[{ms[0]}]: {(ms[1] or "")[:500]}'.replace('\n', ' '))
    p('')

log.close()
print('done ->', OUT)
