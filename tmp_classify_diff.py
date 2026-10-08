"""before/after 分类扫描对比：回归、改善、翻转、不可读清单。"""
import json
from collections import Counter

def load(p):
    return {r['doc_id']: r for r in (json.loads(l) for l in open(p, encoding='utf-8'))}
# 注意：doc_id 可能有多行（多 revision），改用 key 作主键
def load_by_key(p):
    d = {}
    for l in open(p, encoding='utf-8'):
        r = json.loads(l)
        d[(r['doc_id'], r['key'])] = r
    return d

before = load_by_key('tmp_classify_before.jsonl')
after = load_by_key('tmp_classify_after.jsonl')
print(f"rows before={len(before)} after={len(after)}")
assert set(before) == set(after), "行集合不一致"

regressions = []   # before 有类型 -> after None
improvements = []  # before None -> after 有类型
flips = []         # before 类型A -> after 类型B
unreadable = []
for k, b in before.items():
    a = after[k]
    if b['doc_type'] and not a['doc_type']:
        regressions.append((k, b, a))
    elif not b['doc_type'] and a['doc_type']:
        improvements.append((k, b, a))
    elif b['doc_type'] and a['doc_type'] and b['doc_type'] != a['doc_type']:
        flips.append((k, b, a))
    if not a['doc_type']:
        unreadable.append((k, a))

print(f"\n== regressions (typed -> None): {len(regressions)}")
for k, b, a in regressions[:30]:
    print(f"  doc={k[0]} {b['subject']} before={b['doc_type']} after_err={a['error']} title={b['title'][:60]!r}")

print(f"\n== improvements (None -> typed): {len(improvements)}")
print("   by new type:", dict(Counter(a['doc_type'] for _, _, a in improvements)))
print("   by db_type:", dict(Counter(b['db_type'] for _, b, _ in improvements)))

print(f"\n== flips (typeA -> typeB): {len(flips)}")
for k, b, a in flips:
    print(f"  doc={k[0]} {b['subject']} {b['doc_type']} -> {a['doc_type']} db={b['db_type']} conf={a['confidence']} title={b['title'][:60]!r}")

print(f"\n== unreadable after: {len(unreadable)}")
for k, a in unreadable:
    print(f"  doc={k[0]} {a['subject']} db={a['db_type']} err={a['error']} title={a['title'][:60]!r}")

# 汇总：after 与 db_type 不一致（排除 specimen 具体化）
SPEC = {'specimen_paper': 'question_paper', 'specimen_mark_scheme': 'mark_scheme'}
mismatch = []
for k, a in after.items():
    if not a['doc_type']:
        continue
    if a['db_type'] and a['doc_type'] != a['db_type'] and SPEC.get(a['doc_type']) != a['db_type']:
        mismatch.append((k, a))
print(f"\n== after doc_type vs db_type mismatch: {len(mismatch)}")
for k, a in mismatch[:40]:
    print(f"  doc={k[0]} {a['subject']} db={a['db_type']} -> {a['doc_type']} conf={a['confidence']} title={a['title'][:60]!r}")
