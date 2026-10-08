import pymupdf

doc = pymupdf.open(r'.data/specs/pdfs/ial-history-0.pdf')
for i in [29, 30, 31, 32]:
    print(f'===== PAGE {i} =====')
    d = doc[i].get_text('dict')
    for b in d['blocks']:
        if b.get('type') != 0:
            continue
        for l in b['lines']:
            for s in l['spans']:
                txt = s['text']
                if not txt.strip():
                    continue
                flags = s['flags']
                bf = 'B' if flags & 16 else ' '
                it = 'I' if flags & 2 else ' '
                print(f'[{bf}{it}] {txt}')
doc.close()
