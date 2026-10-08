"""重切前预检（只读）: 对 tmp_resplit_plan.json 的每个文档, 用新代码在内存跑完整切分路径,
确认不会抛错, 并记录预期计数（供重切后核对）。

QP: index_questions(data, 'qp')
MS: index_ms_questions(data, wanted) — wanted = 伙伴 QP 的路径:
    优先用本次 QP 预检的新路径（QP 在计划里）, 否则用 DB 当前题目路径。

输出 tmp_preflight.json
"""
import json
import multiprocessing as mp
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
ART = ROOT / '.data' / 'artifacts'


def probe_qp(task):
    doc_id, slug, key = task
    from examdata.paperqa.locator import index_questions
    try:
        data = (ART / key).read_bytes()
        nodes = index_questions(data, 'qp')
        return {'doc_id': doc_id, 'slug': slug, 'role': 'qp', 'ok': True,
                'n_paths': len(nodes), 'paths': [n['question'] for n in nodes]}
    except Exception as exc:
        return {'doc_id': doc_id, 'slug': slug, 'role': 'qp', 'ok': False,
                'error': f'{type(exc).__name__}: {exc}'}


def probe_ms(task):
    doc_id, slug, key, wanted = task
    from examdata.edexcel_papers.pipeline import index_ms_questions
    try:
        data = (ART / key).read_bytes()
        index, source = index_ms_questions(data, wanted)
        return {'doc_id': doc_id, 'slug': slug, 'role': 'ms', 'ok': True, 'source': source,
                'n_paths': len(index), 'paths': [it['question'] for it in index]}
    except Exception as exc:
        return {'doc_id': doc_id, 'slug': slug, 'role': 'ms', 'ok': False,
                'error': f'{type(exc).__name__}: {exc}'}


def main():
    plan = json.load(open('tmp_resplit_plan.json', encoding='utf-8'))['plan']
    db = sqlite3.connect(f'file:{ROOT / ".data" / "examdata.db"}?mode=ro', uri=True)

    def storage_key(doc_id):
        row = db.execute(
            "select a.storage_key from document d"
            " join document_revision dr on dr.id = d.current_revision_id"
            " join artifact a on a.id = dr.artifact_id where d.id=?", (doc_id,)).fetchone()
        return row[0] if row else None

    def partner(ms_doc_id):
        row = db.execute(
            'select matched_paper_document_id from mark_scheme where document_id=?',
            (ms_doc_id,)).fetchone()
        return row[0] if row else None

    def db_qp_paths(qp_doc_id):
        rows = db.execute(
            'select q.number_path from question q join paper p on p.id=q.paper_id'
            ' where p.document_id=? order by q.display_order', (qp_doc_id,)).fetchall()
        return [r[0] for r in rows]

    qp_tasks, ms_meta = [], []
    for slug, b in plan.items():
        for doc_id in b['qp']:
            key = storage_key(doc_id)
            if key is None:
                print(f'!! QP doc {doc_id} no storage key')
                continue
            qp_tasks.append((doc_id, slug, key))
        for doc_id in b['ms']:
            key = storage_key(doc_id)
            if key is None:
                print(f'!! MS doc {doc_id} no storage key')
                continue
            ms_meta.append((doc_id, slug, key))

    print(f'probing {len(qp_tasks)} QP + {len(ms_meta)} MS docs', flush=True)
    with mp.Pool(14) as pool:
        qp_results = pool.map(probe_qp, qp_tasks)
    qp_paths = {r['doc_id']: r['paths'] for r in qp_results if r['ok']}

    ms_tasks = []
    wanted_src = {}
    for doc_id, slug, key in ms_meta:
        p = partner(doc_id)
        if p is not None and p in qp_paths:
            wanted, src = qp_paths[p], f'qp-preflight-{p}'
        elif p is not None:
            paths = db_qp_paths(p)
            wanted, src = paths, f'db-qp-{p}' if paths else f'db-qp-{p}-empty'
        else:
            wanted, src = [], 'no-partner'
        wanted_src[doc_id] = src
        ms_tasks.append((doc_id, slug, key, wanted))
    with mp.Pool(14) as pool:
        ms_results = pool.map(probe_ms, ms_tasks)

    for r in ms_results:
        r['wanted_source'] = wanted_src[r['doc_id']]

    out = {'qp': qp_results, 'ms': ms_results}
    with open('tmp_preflight.json', 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

    print('--- failures ---')
    bad = [r for r in qp_results + ms_results if not r['ok']]
    for r in bad:
        print(f"  {r['role']} doc {r['doc_id']} {r['slug']}: {r['error']}")
    print(f'failures: {len(bad)}')
    print('--- expected counts (ok docs) ---')
    from collections import Counter
    cnt = Counter()
    for r in qp_results:
        if r['ok']:
            cnt[(r['slug'], 'qp', 'ok')] += 1
    for r in ms_results:
        if r['ok']:
            cnt[(r['slug'], 'ms', 'ok')] += 1
    for k in sorted(cnt):
        print(f'  {k[0]:<22} {k[1]}: {cnt[k]}')
    print('written tmp_preflight.json')


if __name__ == '__main__':
    main()
