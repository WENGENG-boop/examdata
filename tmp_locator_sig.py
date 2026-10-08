"""Capture locator signatures for a stratified sample of parsed docs (read-only).

Usage: python tmp_locator_sig.py <out.json>
"""
import json
import sqlite3
import sys

sys.path.insert(0, 'src')

from examdata.paperqa.locator import index_questions  # noqa: E402


def main() -> None:
    out = sys.argv[1]
    db = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
    rows = db.execute("""
      select d.id, s.slug, d.doc_type, dr.artifact_id
      from document d
      join document_revision dr on dr.id = d.current_revision_id
      join subject s on s.id = d.subject_id
      where s.qualification_id = 4
        and dr.parse_status = 'parsed' and dr.artifact_id is not null
      order by s.slug, d.doc_type, d.id
    """).fetchall()
    # stratified sample: up to 3 QP + 2 MS per subject
    picked: dict[tuple[str, str], list] = {}
    for doc_id, slug, doc_type, art_id in rows:
        bucket = picked.setdefault((slug, doc_type), [])
        cap = 3 if doc_type == 'question_paper' else 2
        if len(bucket) < cap:
            bucket.append((doc_id, art_id))
    results = []
    for (slug, doc_type), items in picked.items():
        role = 'qp' if doc_type == 'question_paper' else 'ms'
        for doc_id, art_id in items:
            art = db.execute("select storage_key from artifact where id=?", (art_id,)).fetchone()
            if not art:
                results.append({'doc_id': doc_id, 'slug': slug, 'role': role, 'error': 'no artifact'})
                continue
            path = '.data/artifacts/' + art[0]
            try:
                data = open(path, 'rb').read()
                nodes = index_questions(data, role)
                paths = [n['question'] for n in nodes]
                results.append({
                    'doc_id': doc_id, 'slug': slug, 'role': role, 'ok': True,
                    'n_paths': len(paths),
                    'first': paths[:6], 'last': paths[-3:],
                    'n_regions': sum(len(n['regions']) for n in nodes),
                })
            except Exception as exc:
                results.append({'doc_id': doc_id, 'slug': slug, 'role': role,
                                'error': f'{type(exc).__name__}: {exc}'})
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    ok = sum(1 for r in results if r.get('ok'))
    print(f'wrote {out}: {len(results)} docs, {ok} ok')


if __name__ == '__main__':
    main()
