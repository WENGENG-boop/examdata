import importlib.util, json, sys
from pathlib import Path
spec=importlib.util.spec_from_file_location("pav","ielts-api/tools/pdf-answer-values.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
import pymupdf, re
book=sys.argv[1]; pno=int(sys.argv[2]); ocrfile=sys.argv[3]
ocr=json.loads(Path(ocrfile).read_text(encoding='utf-8'))
pg_ocr={int(p['file_page']):p['words'] for p in ocr['pages']}
doc=pymupdf.open(f'tmp_audit_ielts/downloads/book_{book}.pdf')
pg=doc[pno-1]
ocr_words=pg_ocr[pno]
rawt=m.raw_tokens(pg)
ocr_segs=m.build_segments(ocr_words)
raw_segs=m.build_segments(rawt)
headers=[]
for h in m.detect_headers(ocr_segs,"ocr") + m.detect_headers(raw_segs,"raw"):
    dup=False
    for e in headers:
        if abs(e["y0"]-h["y0"])<=6 and abs(e["x0"]-h["x0"])<=15 and e["range"]==h["range"]:
            dup=True
            if h["source"]=="ocr" and e["source"]!="ocr": e.update(h)
            break
    if not dup: headers.append(h)
print("HEADERS:")
for h in headers: print("  ",h)
col_xs=[h["x0"] for h in headers]
cols=m.cluster_columns(col_xs)
print("COLS:",cols)
for h in headers: h["col"]=m.col_of(h["x0"],cols)
for c in cols:
    band=(c+10,c+200)
    o_items=[w for w in ocr_words if band[0]<=w["x0"]<=band[1]]
    r_items=[t for t in rawt if band[0]<=t["x0"]<=band[1]]
    orows=m.build_rows(o_items,5.0)
    rrows=m.build_rows(r_items,4.0)
    rrows=[r for r in rrows if re.search(r"[A-Za-z0-9]",m.join_raw_row(r["items"])) and max(x["size"] for x in r["items"])<=20]
    print(f"--- col {c} band {band}: orows={len(orows)} rrows={len(rrows)}")
    for r in orows: print(f"    OR y={r['y']:7.1f} text={' '.join((w.get('text') or '').strip() for w in r['items'])[:60]!r}")
    for r in rrows: print(f"    RR y={r['y']:7.1f} text={m.join_raw_row(r['items'])[:60]!r}")
# anchors
for c in cols:
    band=(c-10,c+16)
    anch=[]
    for w in ocr_words:
        t=(w.get("text") or "").strip()
        mm=m.NUM_RE.match(t)
        if mm and band[0]<=w["x0"]<=band[1]:
            n=int(mm.group(1))
            if 1<=n<=45: anch.append({"num":n,"y":w["y0"],"x0":w["x0"],"src":"ocr","text":t[:30]})
    raw_anch=[]
    for t in rawt:
        mm=m.NUM_RE.match((t.get("text") or "").strip())
        if mm and band[0]<=t["x0"]<=band[1]:
            n=int(mm.group(1))
            if 1<=n<=45: raw_anch.append({"num":n,"y":t["y0"],"x0":t["x0"],"src":"raw","text":(t.get("text") or "")[:30]})
    raw_seq=[a["num"] for a in sorted(raw_anch,key=lambda a:a["y"])]
    raw_ok=bool(raw_seq) and all(b>a for a,b in zip(raw_seq,raw_seq[1:]))
    print(f"=== col {c}: OCR anchors={[(a['num'],round(a['y'],1),a['text']) for a in anch]}")
    print(f"    RAW anchors={[(a['num'],round(a['y'],1),a['text']) for a in raw_anch]} raw_ok={raw_ok} seq={raw_seq}")
