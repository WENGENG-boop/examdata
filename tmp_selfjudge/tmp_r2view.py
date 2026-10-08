import sys, json, re

ev2_path, appl_path = sys.argv[1], sys.argv[2]
out = []

qids = []
cur = {}
hdr = {}
qtxt = {}
ms = {}
fam = {}
curq = None
for line in open(ev2_path, encoding='utf-8'):
    line = line.rstrip('\n')
    m = re.match(r'\[(\d+)\] p=', line)
    if m:
        curq = int(m.group(1)); qids.append(curq); hdr[curq] = line
        qtxt[curq] = ''; ms[curq] = ''; fam[curq] = ''
        continue
    if curq is None: continue
    if line.startswith('Q: '): qtxt[curq] = line[3:]
    elif line.startswith('MS['): ms[curq] = (ms[curq] + ' ' + line).strip()
    elif line.startswith('FAM('): fam[curq] = line

recs = {}
seen = set(qids)
for line in open(appl_path, encoding='utf-8'):
    line = line.strip()
    if not line: continue
    try: d = json.loads(line)
    except: continue
    if d.get('question_id') in seen: recs[d['question_id']] = d

rows = []
for q in qids:
    d = recs.get(q, {})
    r = d.get('reason') or ''
    mc = re.search(r'置信度 ([0-9.]+)', r)
    mo = re.search(r'与原标签（([^）]*)）', r)
    conf = float(mc.group(1)) if mc else 9.0
    rows.append((conf, q, d.get('code', '?'), (mo.group(1) if mo else '?')))

rows.sort()
print('=== sorted by confidence, low first ===')
for conf, q, code, orig in rows:
    h = hdr.get(q, '')
    m2 = re.search(r'cur=(\S+)', h)
    curcode = m2.group(1) if m2 else '?'
    if conf < 0.6:
        print('---', q, 'cur=', curcode, 'conf=', conf, 'orig:', orig)
        print('  Q:', qtxt.get(q, '')[:300])
        if ms.get(q): print('  MS:', ms[q][:260])
        if fam.get(q): print('  ', fam[q][:160])
    else:
        print(q, curcode, 'c=', conf, '|', qtxt.get(q, '')[:110])
