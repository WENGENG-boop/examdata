"""只读扫描：MS 文档中 compact 形态 token 的字母后缀分布 + 新 x 限界(0.16→0.20)新纳 token。"""
import collections
import re
import sqlite3
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, "src")
from examdata.core.config import get_settings  # noqa: E402
from examdata.core.storage import ContentAddressedStore  # noqa: E402
from examdata.edexcel_papers.pipeline import _MS_LEAD  # noqa: E402

OLD = re.compile(r"^[1-9]\d{0,2}[a-z]{1,10}$")
NEW = re.compile(r"^[1-9]\d{0,2}[a-jivx]{1,10}$")
NUM = re.compile(r"^[1-9]\d{0,2}(?:\([a-z]{1,4}\))*$")

def main() -> None:
    settings = get_settings()
    store = ContentAddressedStore(settings.artifacts_dir)
    con = sqlite3.connect("file:.data/examdata.db?mode=ro", uri=True)
    cur = con.cursor()
    rows = cur.execute(
        """select d.id, a.storage_key from document d
        join document_revision r on r.id = d.current_revision_id
        join artifact a on a.id = r.artifact_id
        where d.doc_type='mark_scheme' and d.subject_id between 19 and 26
        order by d.id"""
    ).fetchall()
    suffix_counts = collections.Counter()
    suffix_examples = {}
    newx = collections.Counter()
    newx_examples = {}
    trailing_dot = collections.Counter()
    for doc_id, key in rows:
        path = store.path_for_key(key)
        if not path.exists():
            print(f"missing artifact doc={doc_id}")
            continue
        data = path.read_bytes()
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            for index, page in enumerate(pdf):
                if index == 0:
                    continue
                bounds = page.rect
                rot = page.rotation_matrix
                for word in page.get_text("words"):
                    rect = pymupdf.Rect(word[:4]) * rot
                    if not bounds.height * 0.04 < rect.y0 < bounds.height * 0.9:
                        continue
                    token = _MS_LEAD.sub("", word[4])
                    if not token:
                        continue
                    if token.endswith(".") and NUM.match(token[:-1]):
                        trailing_dot[token] += 1
                    m = OLD.fullmatch(token)
                    if m and not NEW.fullmatch(token):
                        letters = re.sub(r"^[1-9]\d{0,2}", "", token)
                        suffix_counts[letters] += 1
                        suffix_examples.setdefault(letters, (doc_id, index + 1, token))
                    if rect.x0 < bounds.width * 0.20 and NUM.match(token):
                        if not (rect.x0 < bounds.width * 0.16):
                            key2 = (token, round(rect.x0 / bounds.width, 3))
                            newx[key2] += 1
                            newx_examples.setdefault(key2, (doc_id, index + 1))
    print("== OLD-compact tokens NOT matching NEW class (suffix: count, example) ==")
    for suffix, count in suffix_counts.most_common():
        doc_id, page, token = suffix_examples[suffix]
        print(f"  {suffix!r}: {count}  e.g. {token!r} doc={doc_id} p{page}")
    print("\n== tokens with trailing dot normalized ==")
    for token, count in trailing_dot.most_common(30):
        print(f"  {token!r}: {count}")
    print("\n== NUM tokens newly inside x-limit [0.16,0.20) ==")
    for (token, xf), count in newx.most_common(60):
        doc_id, page = newx_examples[(token, xf)]
        print(f"  {token!r} x/width={xf}: {count}  e.g. doc={doc_id} p{page}")

if __name__ == "__main__":
    main()
