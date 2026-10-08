import importlib.util, json, sys
from pathlib import Path
spec=importlib.util.spec_from_file_location("pav","ielts-api/tools/pdf-answer-values.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
import pymupdf
book=sys.argv[1]; pno=int(sys.argv[2]); ocrfile=sys.argv[3]
ocr=json.loads(Path(ocrfile).read_text(encoding='utf-8'))
pg_ocr={int(p['file_page']):p['words'] for p in ocr['pages']}
doc=pymupdf.open(f'tmp_audit_ielts/downloads/book_{book}.pdf')
pg=doc[pno-1]
ocr_words=pg_ocr[pno]
rawt=m.raw_tokens(pg)
ocr_segs=m.build_segments(ocr_words)
raw_segs=m.build_segments(rawt)
print("=== OCR SEGMENTS ===")
for s in sorted(ocr_segs,key=lambda s:(round(s['y0'],0),s['x0'])):
    print(f"y={s['y0']:7.1f} x={s['x0']:6.1f} | {s['text'][:90]!r}")
print()
print("=== RAW SEGMENTS ===")
for s in sorted(raw_segs,key=lambda s:(round(s['y0'],0),s['x0'])):
    print(f"y={s['y0']:7.1f} x={s['x0']:6.1f} | {s['text'][:90]!r}")
