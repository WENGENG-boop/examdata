import re, sys, json
import pymupdf

books = [int(x) for x in sys.argv[1].split(',')]
out = {}
for bk in books:
    path = 'tmp_audit_ielts/downloads/book_%d.pdf' % bk
    try:
        d = pymupdf.open(path)
    except Exception as e:
        out[str(bk)] = {'error': str(e)}
        continue
    pages = []
    for i in range(len(d)):
        t = d[i].get_text()
        if not t.strip():
            continue
        if re.search(r'examiner', t, re.I):
            # find a context line
            ctx = ''
            for line in t.splitlines():
                if re.search(r'examiner', line, re.I):
                    ctx = line.strip()[:80]
                    break
            pages.append([i + 1, ctx])
    out[str(bk)] = {'pages': len(d), 'examiner_pages': pages}
    d.close()

print(json.dumps(out, ensure_ascii=False, indent=0))
