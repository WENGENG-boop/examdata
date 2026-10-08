"""分析 tmp_impact_audit.json + tmp_fix_probe.json, 生成按科目的精准重切计划（只读）。

计划规则:
- QP 重切 = 审计中 anchor 变化的已解析 QP + probe 可恢复的失败 QP（无 paper）。
- MS 重切 = 审计中变化的已解析 MS + 匹配到上述 QP 的 MS + probe 可恢复的失败 MS。
- 排除 old_ok_new_fail 的文档（新代码会失败, force 重切会丢数据）。

输出 tmp_resplit_plan.json; 打印摘要。
"""
import json
import sqlite3
import sys

db = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
audit = json.load(open('tmp_impact_audit.json', encoding='utf-8'))
probe = json.load(open('tmp_fix_probe.json', encoding='utf-8'))

changed = [r for r in audit if r.get('changed')]
cats = {'old_ok_new_fail': [], 'old_fail_new_ok': [], 'both_ok_diff': [], 'both_err_diff': []}
for r in changed:
    o, n = r.get('old_error'), r.get('new_error')
    if o and n:
        cats['both_err_diff'].append(r)
    elif o:
        cats['old_fail_new_ok'].append(r)
    elif n:
        cats['old_ok_new_fail'].append(r)
    else:
        cats['both_ok_diff'].append(r)

print('=== changed 分类 ===')
for k, v in cats.items():
    print(f'{k}: {len(v)}')
print()
print('=== old_ok_new_fail（排除, 不重切） ===')
for r in cats['old_ok_new_fail']:
    print(f"  doc {r['doc_id']} {r['slug']} {r['role']} old_n={r['old_n']} new_err={r['new_error']}")
print('=== old_fail_new_ok（恢复） ===')
for r in cats['old_fail_new_ok']:
    print(f"  doc {r['doc_id']} {r['slug']} {r['role']} new_n={r['new_n']} old_err={r['old_error'][:60]}")
print()

# probe 可恢复失败文档（无 paper）
rec = [p for p in probe if p.get('probe') == 'ok' and not p.get('papers_in_db')]
print(f'=== probe 可恢复失败文档: {len(rec)} ===')
from collections import Counter
print(Counter((p['slug'], 'qp' if p['doc_type'] == 'question_paper' else 'ms') for p in rec))

# 交叉引用
def ms_partners(qp_doc_id):
    return [r[0] for r in db.execute(
        'select document_id from mark_scheme where matched_paper_document_id=?', (qp_doc_id,))]

def qp_partner(ms_doc_id):
    row = db.execute(
        'select matched_paper_document_id from mark_scheme where document_id=?', (ms_doc_id,)).fetchone()
    return row[0] if row else None

def doc_title(doc_id):
    row = db.execute('select title, doc_type from document where id=?', (doc_id,)).fetchone()
    return row

def stored_q(doc_id):
    row = db.execute(
        'select count(*) from question q join paper p on p.id=q.paper_id where p.document_id=?',
        (doc_id,)).fetchone()
    return row[0]

def stored_entries(doc_id):
    row = db.execute(
        'select count(*) from mark_scheme_entry e join mark_scheme m on m.id=e.mark_scheme_id'
        ' where m.document_id=?', (doc_id,)).fetchone()
    return row[0]

plan: dict[str, dict] = {}

def bucket(slug):
    return plan.setdefault(slug, {'qp': {}, 'ms': {}})

# 1) changed docs
for r in changed:
    slug, role, doc_id = r['slug'], r['role'], r['doc_id']
    b = bucket(slug)
    if role == 'qp':
        b['qp'][doc_id] = {'reason': 'changed', 'old_n': r.get('old_n'), 'new_n': r.get('new_n'),
                           'stored_q': stored_q(doc_id)}
    else:
        b['ms'][doc_id] = {'reason': 'changed', 'old_n': r.get('old_n'), 'new_n': r.get('new_n'),
                           'stored_entries': stored_entries(doc_id)}

# 2) probe recoverable failed
for p in rec:
    slug = p['slug']
    role = 'qp' if p['doc_type'] == 'question_paper' else 'ms'
    b = bucket(slug)
    key = b['qp'] if role == 'qp' else b['ms']
    key[p['doc']] = {'reason': 'recoverable-failed', 'n_questions': p.get('n_questions')}

# 3) MS partners of all QP in plan (changed or recoverable)
for slug, b in plan.items():
    for qp_id in list(b['qp']):
        for ms_id in ms_partners(qp_id):
            if ms_id not in b['ms']:
                b['ms'][ms_id] = {'reason': f'partner-of-qp-{qp_id}',
                                  'stored_entries': stored_entries(ms_id)}

# 4) QP partners of changed MS docs: only informational (MS re-split doesn't need QP)
info = []
for r in changed:
    if r['role'] == 'ms':
        qp = qp_partner(r['doc_id'])
        if qp is not None:
            title = doc_title(qp)
            info.append((r['doc_id'], qp, title[0] if title else None,
                         qp in plan.get(r['slug'], {}).get('qp', {})))

print()
print('=== 重切计划 ===')
total_qp = total_ms = 0
for slug in sorted(plan):
    b = plan[slug]
    print(f"{slug}: qp={len(b['qp'])} ms={len(b['ms'])}")
    for doc_id, meta in sorted(b['qp'].items()):
        t = doc_title(doc_id)
        print(f"  QP {doc_id}: {meta['reason']} old_n={meta.get('old_n')} new_n={meta.get('new_n')}"
              f" stored_q={meta.get('stored_q')} | {t[0][:60] if t else ''}")
    for doc_id, meta in sorted(b['ms'].items()):
        t = doc_title(doc_id)
        print(f"  MS {doc_id}: {meta['reason']} old_n={meta.get('old_n')} new_n={meta.get('new_n')}"
              f" entries={meta.get('stored_entries')} | {t[0][:60] if t else ''}")
    total_qp += len(b['qp'])
    total_ms += len(b['ms'])
print(f'TOTAL qp={total_qp} ms={total_ms}')

print()
print('=== changed MS 的 QP 伙伴（信息） ===')
for ms_id, qp_id, title, in_plan in info:
    print(f'  ms doc {ms_id} -> qp doc {qp_id} in_plan={in_plan} | {title[:60] if title else None}')

out = {
    'changed_categories': {k: [r['doc_id'] for r in v] for k, v in cats.items()},
    'plan': {slug: {'qp': sorted(b['qp']), 'ms': sorted(b['ms'])} for slug, b in plan.items()},
    'details': {slug: {'qp': {str(k): v for k, v in b['qp'].items()},
                       'ms': {str(k): v for k, v in b['ms'].items()}} for slug, b in plan.items()},
}
with open('tmp_resplit_plan.json', 'w', encoding='utf-8') as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
print('written tmp_resplit_plan.json')
