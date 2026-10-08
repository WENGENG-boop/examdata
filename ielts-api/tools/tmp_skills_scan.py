import re, sys, json
import pymupdf

books = [int(x) for x in sys.argv[1].split(',')] if len(sys.argv) > 1 else list(range(1, 21))
out = {}
for bk in books:
    path = 'tmp_audit_ielts/downloads/book_%d.pdf' % bk
    try:
        d = pymupdf.open(path)
    except Exception as e:
        out[str(bk)] = {'error': str(e)}
        continue
    marks = []
    for i in range(len(d)):
        t = d[i].get_text()
        if not t.strip():
            continue
        tl = t.lower()
        found = []
        if 'speaking' in tl:
            # capture context word
            found.append('speaking')
        if re.search(r'writing\s+task\s*1', tl):
            found.append('writing_task1')
        if re.search(r'writing\s+task\s*2', tl):
            found.append('writing_task2')
        if 'general training' in tl:
            found.append('gt')
        if found:
            marks.append((i + 1, found))
    out[str(bk)] = {'pages': len(d), 'marks': marks}
    d.close()

print(json.dumps(out, ensure_ascii=False, indent=1))
