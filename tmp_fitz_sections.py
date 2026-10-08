import fitz, re, sys

BASE = 'examdata/.data/artifacts'

def find(path, keywords, ctx=700, maxhits=6):
    doc = fitz.open(path)
    print(f'===== {path.split("/")[-1][:20]} pages={len(doc)} =====')
    for kw in keywords:
        hits = 0
        for pno in range(len(doc)):
            text = doc[pno].get_text()
            for m in re.finditer(re.escape(kw), text, re.I):
                hits += 1
                if hits > maxhits:
                    break
                s = max(0, m.start() - ctx)
                e = min(len(text), m.end() + ctx)
                snippet = text[s:e].replace('\n', ' | ')
                print(f'--- [{kw}] page {pno+1} ---')
                print(snippet[:1500])
                print()
            if hits > maxhits:
                break
    doc.close()

# 1. Oct2016 U1 (paper 2092): 61328/61329 practical investigation 场景
find(f'{BASE}/85/2b/852b31951d4559c6fe99a9d11c158887ccb94b6c02c79d4d5fdfca0082834c6f.pdf',
     ['operationalised', 'conclusions you reached'])

# 2. Jun2016 U1 (paper 2095): 61423 p<0.05 场景
find(f'{BASE}/5c/e7/5ce72e2b0852dae582041dcba74c084a50a68aee3203430363e8500db3090365.pdf',
     ['p<0.05', 'p < 0.05'])

# 3. Jan2018 P2 (paper 2106): 61770/61771 分区
find(f'{BASE}/79/eb/79eb56b2b1b95d73c1d6fe4fcef37d4a23a1eba76ed8d77943fa34c6f643d30a.pdf',
     ['Interpret the data shown in Table 3', 'Compare ordinal data and interval data'])

# 4. Jan2018 U4 (paper 2107): 61790 分区
find(f'{BASE}/f4/f7/f4f732f07b819d65d22341b475ee587b0f09dae951cd087a95b9a6542e5730f3.pdf',
     ['conclusions that the researchers can make'])
