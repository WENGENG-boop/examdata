import pymupdf, sys
pdf=sys.argv[1]; a=int(sys.argv[2]); b=int(sys.argv[3])
doc=pymupdf.open(pdf)
print('pdf pages:',doc.page_count)
for i in range(a-1,min(b,doc.page_count)):
    pg=doc[i]
    t=pg.get_text('text') or ''
    lines=[l.strip() for l in t.splitlines() if l.strip()]
    head=' | '.join(lines[:6])[:150]
    tail=' | '.join(lines[-3:])[:60]
    print(f'--- file {i+1}: HEAD: {head}')
    print(f'    TAIL: {tail}')
