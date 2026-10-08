"""只读调试：对指定文档对比 _numeric_row 开启/关闭时 _anchors 的差异。

用法: python tmp_debug_anchors.py <doc_id> [<doc_id> ...]
"""
import sqlite3
import sys

sys.path.insert(0, 'src')

import pymupdf  # noqa: E402

from examdata.paperqa import locator  # noqa: E402


def anchors_for(data: bytes, role: str, numeric_row_on: bool):
    saved = locator._numeric_row
    if not numeric_row_on:
        locator._numeric_row = lambda *a, **k: False
    try:
        with pymupdf.open(stream=data, filetype='pdf') as pdf:
            anchors, end = locator._anchors(pdf, role)
        return anchors, end, None
    except Exception as exc:  # noqa: BLE001
        return [], None, f'{type(exc).__name__}: {exc}'
    finally:
        locator._numeric_row = saved


def main() -> None:
    db = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
    for doc_id in (int(x) for x in sys.argv[1:]):
        info = db.execute("""
          select s.slug, d.doc_type, dr.artifact_id
          from document d join document_revision dr on dr.id = d.current_revision_id
          join subject s on s.id = d.subject_id where d.id=?
        """, (doc_id,)).fetchone()
        slug, doc_type, art_id = info
        art = db.execute('select storage_key from artifact where id=?', (art_id,)).fetchone()[0]
        data = open('.data/artifacts/' + art, 'rb').read()
        role = 'qp' if doc_type == 'question_paper' else 'ms'
        print(f'== doc {doc_id} {slug} {role}')
        old_anchors, _, old_err = anchors_for(data, role, False)
        new_anchors, _, new_err = anchors_for(data, role, True)
        print(f'   old: n={len(old_anchors)} err={old_err}')
        print(f'   new: n={len(new_anchors)} err={new_err}')
        new_paths = [a.path for a in new_anchors]
        lost = [a for a in old_anchors if a.path not in new_paths]
        gained = [a for a in new_anchors if a.path not in [b.path for b in old_anchors]]
        print(f'   old anchors={len(old_anchors)} new anchors={len(new_anchors)} '
              f'lost={len(lost)} gained={len(gained)}')
        if gained:
            print(f'   gained paths: {[a.path for a in gained][:15]}')
        with pymupdf.open(stream=data, filetype='pdf') as pdf:
            for a in lost[:12]:
                page = pdf[a.page]
                words = sorted(page.get_text('words'), key=lambda w: (round(w[1] / 3), w[0]))
                row = [(round(w[0], 1), round(w[1], 1), w[4])
                       for w in words if abs(w[1] - a.y) <= 2.0]
                print(f'   lost {a.path} p{a.page} y={a.y:.1f} row={row}')


if __name__ == '__main__':
    main()
