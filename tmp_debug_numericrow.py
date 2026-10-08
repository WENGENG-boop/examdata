"""调试: 列出某文档所有大题号候选词及 _numeric_row 判定与同行 token（只读）。"""
import re
import sqlite3
import sys

sys.path.insert(0, 'src')

import pymupdf  # noqa: E402

from examdata.paperqa.locator import _numeric_row, _page_bounds  # noqa: E402

doc_id = int(sys.argv[1])
only_pages = [int(p) for p in sys.argv[2:]] if len(sys.argv) > 2 else None

db = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
row = db.execute(
    "select dr.artifact_id from document d join document_revision dr on dr.id=d.current_revision_id"
    " where d.id=?", (doc_id,)).fetchone()
key = db.execute("select storage_key from artifact where id=?", (row[0],)).fetchone()[0]
data = open('.data/artifacts/' + key, 'rb').read()

with pymupdf.open(stream=data, filetype='pdf') as pdf:
    print(f'doc {doc_id}: {len(pdf)} pages')
    for i, page in enumerate(pdf):
        if only_pages and i not in only_pages:
            continue
        words = sorted(page.get_text("words"), key=lambda w: (round(w[1] / 3), w[0]))
        bounds = _page_bounds(page)
        for w in words:
            x, y, _, _, text, *_ = w
            if not bounds.height * .04 < y < bounds.height * .9:
                continue
            if x < bounds.width * .125 and re.fullmatch(r"[1-9]\d{0,2}\.?", text.lstrip("*")):
                n = _numeric_row(words, y)
                rowt = [t[4] for t in words if abs(t[1] - y) <= 2.0]
                flag = 'NUMROW' if n else '      '
                print(f'p{i} x={x:5.0f} y={y:6.1f} {flag} text={text!r} row={rowt[:16]}')
