"""Categorize the 71 LocationError docs. Read-only. Output: tmp_r8_locerr_survey.json/.out"""
from __future__ import annotations
import sqlite3, sys, json, re
from pathlib import Path
import pymupdf
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from examdata.paperqa import locator as L
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT/".data/examdata.db"); con.row_factory=sqlite3.Row; cur = con.cursor()
d=json.load(open('tmp_r8_scan_split.json'))
errs=[e for e in d['errors'] if e.get('error','').startswith('LocationError')]
out=[]
for e in errs:
    doc_id=e['doc']
    row = cur.execute("""SELECT a.storage_key, d.title FROM document d
        JOIN document_revision r ON r.id=d.current_revision_id
        JOIN artifact a ON a.id=r.artifact_id WHERE d.id=?""",(doc_id,)).fetchone()
    p = ROOT/".data/artifacts"/row["storage_key"]
    rec={"doc":doc_id,"title":row["title"],"error":e["error"]}
    try:
        doc = pymupdf.open(p)
    except Exception as ex:
        rec["category"]="open_fail"; rec["detail"]=str(ex)[:100]; out.append(rec); continue
    rec["pages"]=len(doc)
    rec["ciphered"]=L.is_ciphered(doc)
    # text stats over first 8 pages
    total=0; nonws=0; imgs=0
    for i in range(min(8,len(doc))):
        t=doc[i].get_text(); total+=len(t); nonws+=sum(1 for c in t if not c.isspace())
        imgs+=len(doc[i].get_images(full=True))
    rec["chars_first8"]=total; rec["nonws_first8"]=nonws; rec["images_first8"]=imgs
    # left-column numeric candidates over first 8 pages (with cipher decode if needed)
    cip=rec["ciphered"]
    n_cand=0; samples=[]
    for i in range(1,min(8,len(doc))):
        page=doc[i]; b=L._page_bounds(page)
        words=sorted(L._page_words(page,cip), key=lambda w:(round(w[1]/3),w[0]))
        for w in words:
            if w[0] < b.width*.125 and re.fullmatch(r"[1-9]\d{0,2}\.{0,2}", w[4].lstrip("*")):
                n_cand+=1
                if len(samples)<5: samples.append((i+1, round(w[0],1), w[4]))
    rec["left_cands"]=n_cand; rec["cand_samples"]=samples
    # first text of page 2 for eyeballing
    if len(doc)>1:
        t2=doc[1].get_text()[:200].replace("\n"," | ")
        rec["p2_head"]=t2
    # category heuristic
    if rec["nonws_first8"] < 200: cat="scanned_or_empty"
    elif n_cand==0 and rec["nonws_first8"]<3000: cat="no_question_numbers"
    elif n_cand==0: cat="layout_mismatch"
    else: cat="other"
    rec["category"]=cat
    out.append(rec)
    doc.close()
json.dump(out, open("tmp_r8_locerr_survey.json","w"), ensure_ascii=False, indent=1)
from collections import Counter
c=Counter(r["category"] for r in out)
print("categories:", dict(c))
for r in out:
    print(f"{r['doc']:6d} {r['category']:20s} pages={r.get('pages')} cip={r.get('ciphered')} nonws8={r.get('nonws_first8')} cands={r.get('left_cands')} imgs={r.get('images_first8')} {r['title'][:60]}")
