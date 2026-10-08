import json, re

pte = json.load(open('pte21_listening_answers.json', encoding='utf-8'))

def parse_listening(path):
    html = open(path, encoding='utf-8').read()
    m = re.search(r'const correctAnswers = (\{.*?\});', html, re.S)
    ca = json.loads(m.group(1))
    m2 = re.search(r'const multiCorrect = (\{.*?\});', html, re.S)
    mc = json.loads(m2.group(1)) if m2 else {}
    return ca, mc

def norm(x):
    return str(x).strip().lower()

def variants(got):
    # pte 用 "A/ B/ C" 表示备选，用 "B, D" 表示多选组合
    parts = re.split(r'/', str(got))
    return [p.strip() for p in parts if p.strip()]

for t in ['1', '2', '3', '4']:
    ca, mc = parse_listening(f'cam21/t{t}-listening.html')
    ans = pte['t' + t]['answers']
    multi_inputs = set()
    for k, blk in mc.items():
        for i in blk['inputs']:
            multi_inputs.add(int(i))
    n_match = 0; n_tot = 0; diffs = []
    for q in range(1, 41):
        if q in multi_inputs:
            continue
        expected = ca.get(str(q))
        got = ans[q - 1] if ans and q - 1 < len(ans) else None
        if expected is None or got is None:
            continue
        exp_list = expected if isinstance(expected, list) else [expected]
        n_tot += 1
        if any(norm(v) in [norm(e) for e in exp_list] for v in variants(got)):
            n_match += 1
        else:
            diffs.append((q, expected, got))
    multi_ok = 0; multi_bad = []
    for k, blk in mc.items():
        got = [ans[int(i)-1] for i in blk['inputs']]
        gsets = []
        for g in got:
            gsets.append(set(x.strip().upper() for x in str(g).split(',')))
        expect = set(str(x).upper() for x in blk['accept'])
        if all(gs == expect for gs in gsets):
            multi_ok += 1
        else:
            multi_bad.append((k, blk['accept'], got))
    print(f'pteListening(21,{t}) [{pte["t"+t]["slug"]}] vs cam21 T{t}: single {n_match}/{n_tot}, multi {multi_ok}/{len(mc)}')
    for d in diffs[:8]:
        print('   Q%d cam21=%r pte=%r' % d)
    for d in multi_bad[:5]:
        print('   MULTI', d)
