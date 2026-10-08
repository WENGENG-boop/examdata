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

for t in ['1', '2']:
    ca, mc = parse_listening(f'cam21/t{t}-listening.html')
    ans = pte['t' + t]['answers']  # list of 40, index 0 = Q1
    n_match = 0; n_tot = 0; diffs = []
    for q in range(1, 41):
        expected = ca.get(str(q))
        got = ans[q - 1] if ans and q - 1 < len(ans) else None
        if expected is None or got is None:
            continue
        exp_list = expected if isinstance(expected, list) else [expected]
        n_tot += 1
        if norm(got) in [norm(e) for e in exp_list]:
            n_match += 1
        else:
            diffs.append((q, expected, got))
    print(f'pteListening(21,{t}) [slug {pte["t"+t]["slug"]}] vs cam21 T{t}: match {n_match}/{n_tot}')
    for d in diffs[:10]:
        print('   Q%d cam21=%r pte=%r' % d)
    # multi blocks
    for k, blk in mc.items():
        print('   multi', k, 'inputs', blk['inputs'], 'accept', blk['accept'], 'pte:', [ans[int(i)-1] for i in blk['inputs']])
