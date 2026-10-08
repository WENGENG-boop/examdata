import json, re

pte = json.load(open('pte21_reading_answers.json', encoding='utf-8'))

def parse_answers(path):
    html = open(path, encoding='utf-8').read()
    m = re.search(r'const ANSWERS = \{(.*?)\};', html, re.S)
    body = m.group(1)
    pairs = re.findall(r'(\d+):"([^"]*)"', body)
    return {int(k): v for k, v in pairs}

c1 = parse_answers('cam21/t1-reading.html')
c2 = parse_answers('cam21/t2-reading.html')
print('cam21 T1 parsed:', len(c1), '| cam21 T2 parsed:', len(c2))

def cmp(name, cam, pte_list):
    n_match = 0; n_tot = 0; diffs = []
    for i in range(1, 41):
        p = pte_list[i-1] if pte_list and i-1 < len(pte_list) else None
        c = cam.get(i)
        if p is None or c is None:
            continue
        n_tot += 1
        if str(p).strip().lower() == str(c).strip().lower():
            n_match += 1
        else:
            diffs.append((i, c, p))
    print(f'{name}: match {n_match}/{n_tot}')
    for d in diffs[:12]:
        print('   Q%d cam21=%r pte=%r' % d)

print()
print('=== pteReading(21,1) [slug 314] vs cam21 T1 ===')
cmp('314 vs T1', c1, pte['t1']['answers'])
print('=== pteReading(21,2) [slug 315] vs cam21 T2 ===')
cmp('315 vs T2', c2, pte['t2']['answers'])
print('=== pteReading(21,3) [slug 316] vs cam21 T1 ===')
cmp('316 vs T1', c1, pte['t3']['answers'])
print('=== pteReading(21,4) [slug 317] vs cam21 T2 ===')
cmp('317 vs T2', c2, pte['t4']['answers'])
