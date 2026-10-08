"""只读探针：最新 parse_run 失败的文档，用修复后的 locator 在内存重跑索引，
统计各科可恢复的文档与题数（决定重跑名单）。

用法: python tmp_fix_probe.py [out.json]
"""
import json
import sqlite3
import sys

sys.path.insert(0, 'src')

from examdata.paperqa.locator import index_questions  # noqa: E402


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else 'tmp_fix_probe.json'
    db = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
    rows = db.execute("""
      select pr.id, pr.status, d.id, s.slug, d.doc_type, dr.artifact_id, pr.error
      from parse_run pr
      join document_revision dr on dr.id = pr.document_revision_id
      join document d on d.id = dr.document_id
      join subject s on s.id = d.subject_id
      where pr.parser_version = 'edexcel-papers-1'
      order by pr.id
    """).fetchall()
    latest: dict[int, dict] = {}
    for run_id, status, doc_id, slug, doc_type, art_id, error in rows:
        latest[doc_id] = {
            'run': run_id, 'status': status, 'doc': doc_id, 'slug': slug,
            'doc_type': doc_type, 'artifact_id': art_id, 'error': (error or '')[:200],
        }
    failed = [v for v in latest.values() if v['status'] == 'failed']
    failed.sort(key=lambda v: (v['slug'], v['doc_type'], v['doc']))

    for item in failed:
        role = 'qp' if item['doc_type'] == 'question_paper' else 'ms'
        item['papers_in_db'] = db.execute(
            'select count(*) from paper where document_id=?', (item['doc'],)).fetchone()[0]
        art = None
        if item['artifact_id'] is not None:
            art = db.execute('select storage_key from artifact where id=?',
                             (item['artifact_id'],)).fetchone()
        if not art:
            item['probe'] = 'no artifact'
            continue
        try:
            data = open('.data/artifacts/' + art[0], 'rb').read()
        except OSError as exc:
            item['probe'] = f'unreadable: {exc}'
            continue
        try:
            nodes = index_questions(data, role)
            item['probe'] = 'ok'
            item['n_questions'] = len(nodes)
            item['n_regions'] = sum(len(n['regions']) for n in nodes)
        except Exception as exc:  # noqa: BLE001 - 探针要如实记录一切失败
            item['probe'] = f'{type(exc).__name__}: {exc}'

    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(failed, fh, ensure_ascii=False, indent=1)

    by: dict[tuple[str, str], list] = {}
    for item in failed:
        role = 'qp' if item['doc_type'] == 'question_paper' else 'ms'
        by.setdefault((item['slug'], role), []).append(item)
    for (slug, role), items in sorted(by.items()):
        ok = [i for i in items if i.get('probe') == 'ok']
        nq = sum(i.get('n_questions', 0) for i in ok)
        no_papers = [i for i in ok if not i['papers_in_db']]
        print(f'{slug} [{role}]: failed={len(items)} recoverable={len(ok)} '
              f'(no-papers={len(no_papers)}) questions={nq}')
        for i in items:
            if i.get('probe') != 'ok':
                print(f"  doc {i['doc']}: {i.get('probe')} | was: {i['error'][:110]}")
    print(f'written {out_path}; failed docs: {len(failed)}')


if __name__ == '__main__':
    main()
