"""全库影响审计（只读）: 对每个已解析的 Edexcel QP/MS 文档, 比较旧版 vs 新版 `_anchors`。

旧版 = 把 `locator._numeric_row` monkeypatch 成恒 False（等价于修复前行为）。
新版 = 默认（带统计表行过滤）。

anchor 序列相同 ⇒ index_questions 输出必然相同; 不同 ⇒ 该文档可能被旧代码污染,
列入 force 重切候选。

Usage: python tmp_impact_audit.py [out.json] [workers] [limit]
"""
import json
import multiprocessing as mp
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

ART = ROOT / '.data' / 'artifacts'


def load_tasks(limit=None):
    db = sqlite3.connect(f'file:{ROOT / ".data" / "examdata.db"}?mode=ro', uri=True)
    rows = db.execute("""
      select d.id, s.slug, d.doc_type, a.storage_key
      from document d
      join document_revision dr on dr.id = d.current_revision_id
      join subject s on s.id = d.subject_id
      join artifact a on a.id = dr.artifact_id
      where s.qualification_id = 4
        and dr.parse_status = 'parsed' and dr.artifact_id is not null
        and d.doc_type in ('question_paper', 'mark_scheme')
      order by s.slug, d.doc_type, d.id
    """).fetchall()
    db.close()
    if limit:
        rows = rows[:limit]
    return rows


def _sig(pdf, role, locator, old):
    orig = locator._numeric_row
    try:
        if old:
            locator._numeric_row = lambda *a, **k: False
        anchors, _ = locator._anchors(pdf, role)
        return [(a.path, a.page) for a in anchors], None
    except Exception as exc:
        return None, f'{type(exc).__name__}: {exc}'
    finally:
        locator._numeric_row = orig


def audit_one(task):
    doc_id, slug, doc_type, key = task
    role = 'qp' if doc_type == 'question_paper' else 'ms'
    out = {'doc_id': doc_id, 'slug': slug, 'role': role}
    try:
        import pymupdf
        from examdata.paperqa import locator
        data = (ART / key).read_bytes()
        with pymupdf.open(stream=data, filetype='pdf') as pdf:
            old_sig, old_err = _sig(pdf, role, locator, old=True)
            new_sig, new_err = _sig(pdf, role, locator, old=False)
    except Exception as exc:
        out['error'] = f'{type(exc).__name__}: {exc}'
        return out
    out['changed'] = old_sig != new_sig or old_err != new_err
    out['old_n'] = len(old_sig) if old_sig is not None else None
    out['new_n'] = len(new_sig) if new_sig is not None else None
    if old_err:
        out['old_error'] = old_err
    if new_err:
        out['new_error'] = new_err
    if old_sig is not None and new_sig is not None and old_sig != new_sig:
        os_, ns_ = set(old_sig), set(new_sig)
        out['lost'] = sorted(f'{p}@p{g}' for p, g in os_ - ns_)[:15]
        out['gained'] = sorted(f'{p}@p{g}' for p, g in ns_ - os_)[:15]
    return out


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else 'tmp_impact_audit.json'
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 14
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else None
    tasks = load_tasks(limit)
    print(f'{len(tasks)} docs to audit; workers={workers}', flush=True)
    results = []
    with mp.Pool(workers) as pool:
        for i, res in enumerate(pool.imap_unordered(audit_one, tasks, chunksize=4), 1):
            results.append(res)
            if i % 200 == 0:
                print(f'  {i}/{len(tasks)}', flush=True)
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    from collections import Counter
    by, changed_by, err_by = Counter(), Counter(), Counter()
    for r in results:
        key = (r['slug'], r['role'])
        by[key] += 1
        if r.get('changed'):
            changed_by[key] += 1
        if r.get('error'):
            err_by[key] += 1
    print('--- changed by slug/role ---')
    for key in sorted(changed_by):
        print(f"{key[0]:<22} {key[1]:<3} changed={changed_by[key]:>3} / {by[key]:>3}  err={err_by[key]}")
    print(f'total docs={len(results)}, changed={sum(changed_by.values())}, errors={sum(err_by.values())}')


if __name__ == '__main__':
    main()
