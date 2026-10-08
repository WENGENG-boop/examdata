import fitz, re

BASE = 'examdata/.data/artifacts'

# 4. Jan2018 U4 (paper 2107) sections + page 9 context
P3340 = f'{BASE}/f4/f7/f4f732f07b819d65d22341b475ee587b0f09dae951cd087a95b9a6542e5730f3.pdf'
doc = fitz.open(P3340)
print('===== Jan2018 U4 (3340) sections =====')
for pno in range(len(doc)):
    text = doc[pno].get_text()
    for m in re.finditer(r'SECTION [AB]', text):
        s = max(0, m.start()-100); e = min(len(text), m.end()+260)
        print(f'  [page {pno+1}] ...{text[s:e].replace(chr(10)," | ")}...')
print()
print('----- page 9 -----')
print(doc[8].get_text()[:2600].replace('\n', ' | '))
doc.close()

# 1. Oct2016 U1 (paper 2092): 61319/61322 context
P3285 = f'{BASE}/85/2b/852b31951d4559c6fe99a9d11c158887ccb94b6c02c79d4d5fdfca0082834c6f.pdf'
doc = fitz.open(P3285)
print()
print('===== Oct2016 U1 (3285) hits =====')
for kw in ['conclusions that can be drawn', 'Draw an appropriate graph']:
    for pno in range(len(doc)):
        text = doc[pno].get_text()
        for m in re.finditer(re.escape(kw), text, re.I):
            s = max(0, m.start()-600); e = min(len(text), m.end()+250)
            print(f'--- [{kw}] page {pno+1} ---')
            print(text[s:e].replace('\n', ' | '))
            print()
print('===== Oct2016 U1 (3285) sections =====')
for pno in range(len(doc)):
    text = doc[pno].get_text()
    for m in re.finditer(r'SECTION [AB]', text):
        s = max(0, m.start()-80); e = min(len(text), m.end()+180)
        print(f'  [page {pno+1}] ...{text[s:e].replace(chr(10)," | ")}...')
doc.close()
