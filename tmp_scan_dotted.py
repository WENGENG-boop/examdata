"""全库扫描: 找出所有被 _numeric_row 判定为统计表行的大题号候选（只读）。

分类: 带尾点（"4."）vs 裸数字（"12"）。用于评估「带尾点候选不算统计表行」refinement 的安全性。
输出 tmp_scan_dotted.json
"""
import json
import multiprocessing as mp
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
ART = ROOT / '.data' / 'artifacts'


def scan_one(task):
    doc_id, slug, doc_type, key = task
    role = 'qp' if doc_type == 'question_paper' else 'ms'
    out = {'doc_id': doc_id, 'slug': slug, 'role': role, 'dotted': [], 'bare': []}
    try:
        import pymupdf
        from examdata.paperqa.locator import _numeric_row, _page_bounds
        data = (ART / key).read_bytes()
        with pymupdf.open(stream=data, filetype='pdf') as pdf:
            for i, page in enumerate(pdf):
                bounds = _page_bounds(page)
                words = sorted(page.get_text("words"), key=lambda w: (round(w[1] / 3), w[0]))
                for w in words:
                    x, y, _, _, text, *_ = w
                    if not bounds.height * .04 < y < bounds.height * .9:
                        continue
                    t = text.lstrip('*')
                    if not (x < bounds.width * .125 and re.fullmatch(r'[1-9]\d{0,2}\.?', t)):
                        continue
                    if not _numeric_row(words, y):
                        continue
                    row = [tok[4] for tok in words if abs(tok[1] - y) <= 2.0]
                    item = {'page': i, 'text': text, 'row': row[:14]}
                    (out['dotted'] if t.endswith('.') else out['bare']).append(item)
    except Exception as exc:
        out['error'] = f'{type(exc).__name__}: {exc}'
    return out


def main():
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
    print(f'{len(rows)} docs to scan', flush=True)
    results = []
    with mp.Pool(14) as pool:
        for i, res in enumerate(pool.imap_unordered(scan_one, rows, chunksize=4), 1):
            results.append(res)
            if i % 500 == 0:
                print(f'  {i}/{len(rows)}', flush=True)
    with open('tmp_scan_dotted.json', 'w', encoding='utf-8') as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    dotted_docs = [r for r in results if r.get('dotted')]
    bare_docs = [r for r in results if r.get('bare')]
    err = [r for r in results if r.get('error')]
    print(f'docs with dotted rejects: {len(dotted_docs)}; with bare rejects: {len(bare_docs)}; errors: {len(err)}')
    for r in dotted_docs:
        print(f"--- {r['slug']} doc {r['doc_id']} ({r['role']}) dotted={len(r['dotted'])} bare={len(r['bare'])}")
        for it in r['dotted'][:8]:
            print(f"    p{it['page']} {it['text']!r} row={it['row'][:10]}")
    for r in err:
        print(f"ERR {r['slug']} doc {r['doc_id']}: {r['error']}")


if __name__ == '__main__':
    main()
