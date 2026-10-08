"""Extract ToUnicode CMap of doc 1719 page 1 fonts. Read-only."""
from __future__ import annotations
import sqlite3, sys, re
from pathlib import Path
import pymupdf
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT/".data/examdata.db"); cur = con.cursor()
doc_id = int(sys.argv[1]) if len(sys.argv)>1 else 1719
row = cur.execute("""SELECT a.storage_key FROM document d
    JOIN document_revision r ON r.id=d.current_revision_id
    JOIN artifact a ON a.id=r.artifact_id WHERE d.id=?""",(doc_id,)).fetchone()
doc = pymupdf.open(ROOT/".data/artifacts"/row[0])
for pno in (0,2):
    print(f"===== page {pno+1} fonts =====")
    for f in doc[pno].get_fonts(full=True):
        xref, ext, ftype, basefont, name, encoding = f[:6]
        print(f"  xref={xref} ext={ext} type={ftype} base={basefont!r} name={name!r} enc={encoding!r}")
        obj = doc.xref_object(xref, compressed=True)
        print("    obj:", obj[:300])
        tu = doc.xref_get_key(xref, "ToUnicode")
        print("    ToUnicode:", tu)
        if tu[0] == 'xref':
            tux = int(tu[1].split()[0])
            stream = doc.xref_stream(tux)
            txt = stream.decode('latin-1')
            print("    cmap head:", repr(txt[:400]))
            # parse bfchar/bfrange mappings
            pairs = re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", txt)
            print("    pairs sample:", pairs[:12], "n=", len(pairs))
            # check whether mapping is a pure shift
            shifts = {}
            for a, b in pairs:
                ca, cb = int(a,16), int(b,16)
                shifts.setdefault(cb-ca, 0)
                shifts[cb-ca] += 1
            print("    shift histogram:", sorted(shifts.items(), key=lambda kv:-kv[1])[:10])
