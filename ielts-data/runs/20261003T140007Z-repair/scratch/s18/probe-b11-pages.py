import sys
try:
    from pypdf import PdfReader
except Exception:
    from PyPDF2 import PdfReader
r = PdfReader(r'tmp_audit_ielts/downloads/book_11.pdf')
print('pages:', len(r.pages))
for p in range(113, 127):  # 1-based 114..127
    try:
        t = r.pages[p-1].extract_text() or ''
    except Exception as e:
        t = f'<ERR {e}>'
    lines = [l.strip() for l in t.splitlines() if l.strip()]
    head = ' | '.join(lines[:6])
    print(f'--- page {p} ({len(lines)} lines): {head[:300]}')
