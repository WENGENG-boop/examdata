import pymupdf, sys
pdf=sys.argv[1]; term=sys.argv[2]
doc=pymupdf.open(pdf)
for i in range(doc.page_count):
    t=doc[i].get_text('text') or ''
    if term.lower() in t.lower():
        lines=[l.strip() for l in t.splitlines() if l.strip()]
        print(f'file {i+1}: {len(lines)} lines')
        for l in lines:
            if term.lower() in l.lower():
                print('   ',l[:110])
