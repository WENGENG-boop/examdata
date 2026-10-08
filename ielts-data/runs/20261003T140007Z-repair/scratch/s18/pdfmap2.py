import pymupdf, sys
pdf=sys.argv[1]
doc=pymupdf.open(pdf)
for i in range(doc.page_count):
    t=doc[i].get_text('text') or ''
    lines=[l.strip() for l in t.splitlines() if l.strip()]
    head=' / '.join(lines[:2])[:95] if lines else '(empty)'
    tail=lines[-1][:20] if lines else ''
    print(f'{i+1:3d}: {head}   ... [{tail}]')
