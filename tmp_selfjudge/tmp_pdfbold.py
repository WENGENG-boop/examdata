import pymupdf, sys, re

doc = pymupdf.open(r'.data/specs/pdfs/ial-history-0.pdf')
print('pages:', doc.page_count)
# find pages mentioning India option
hits = []
for i in range(doc.page_count):
    t = doc[i].get_text()
    if 'India, 1857' in t or 'WHI02' in t:
        hits.append(i)
print('hit pages:', hits)

out = []
for i in hits:
    page = doc[i]
    d = page.get_text('dict')
    for b in d['blocks']:
        if b.get('type') != 0:
            continue
        for l in b['lines']:
            for s in l['spans']:
                txt = s['text']
                if not txt.strip():
                    continue
                flags = s['flags']
                b_flag = bool(flags & 16)
                i_flag = bool(flags & 2)
                if b_flag or i_flag:
                    mark = ('B' if b_flag else '') + ('I' if i_flag else '')
                    out.append(f'p{i} [{mark}] {txt}')
if not out:
    print('NO BOLD/ITALIC SPANS FOUND — dumping plain text of hit pages')
    for i in hits:
        print(f'----- page {i} -----')
        print(doc[i].get_text())
else:
    print('\n'.join(out))
doc.close()
