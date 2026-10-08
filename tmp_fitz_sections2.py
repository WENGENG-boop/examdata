import fitz, re

BASE = 'examdata/.data/artifacts'

def sections(path, name):
    doc = fitz.open(path)
    print(f'===== {name} pages={len(doc)} =====')
    for pno in range(len(doc)):
        text = doc[pno].get_text()
        for m in re.finditer(r'SECTION [AB]', text):
            s = max(0, m.start()-120); e = min(len(text), m.end()+220)
            print(f'  [page {pno+1}] ...{text[s:e].replace(chr(10)," | ")}...')
    doc.close()

def show(path, name, page_range, full=False):
    doc = fitz.open(path)
    print(f'===== {name} pages {page_range} =====')
    for pno in page_range:
        text = doc[pno-1].get_text()
        print(f'----- page {pno} -----')
        print(text[:2600].replace('\n', ' | '))
        print()
    doc.close()

# 2. Jun2016 U1 (paper 2095) — 61423 p<0.05 场景 + 分区
P3290 = f'{BASE}/5c/e7/5ce72e2b0852dae582041dcba74c084a50a68aee3203430363e8500db3090365.pdf'
sections(P3290, 'Jun2016 U1 (3290)')
show(P3290, 'Jun2016 U1 (3290)', [12, 13])

# 3. Jan2018 P2 (paper 2106) — 61770/61771 分区
P3339 = f'{BASE}/79/eb/79eb56b2b1b95d73c1d6fe4fcef37d4a23a1eba76ed8d77943fa34c6f643d30a.pdf'
sections(P3339, 'Jan2018 P2 (3339)')
show(P3339, 'Jan2018 P2 (3339)', [16, 17, 18])

# 4. Jan2018 U4 (paper 2107) — 61790 分区
P3340 = f'{BASE}/f4/f7/f4f732f07b819d65d22341b475ee587b0f09dae951cd087a95b9a6542e5730f3.pdf'
doc = fitz.open(P3340)
print('===== Jan2018 U4 (3340) conclusion hits =====')
for pno in range(len(doc)):
    text = doc[pno].get_text()
    for m in re.finditer(r'conclusion', text, re.I):
        s = max(0, m.start()-250); e = min(len(text), m.end()+250)
        print(f'  [page {pno+1}] ...{text[s:e].replace(chr(10)," | ")}...')
doc.close()
