import json, re, subprocess, sys

# fetch fresh answers via node (independent from the json cached earlier)
node_code = """
const m = await import('file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs');
const out = {};
for (const t of [1,2,3,4]) {
  const r = await m.pteReading(21, t);
  out['t'+t] = { slug: r.slug, ok: r.ok, answers: r.answer_key, count: r.answer_count };
}
console.log(JSON.stringify(out));
"""
res = subprocess.run(['node', '--input-type=module', '-e', node_code], capture_output=True, text=True, encoding='utf-8', cwd=r'C:\Users\weo\Desktop\api\tmp_audit_ielts')
if res.returncode != 0:
    print('node failed:', res.stderr); sys.exit(1)
pte = json.loads(res.stdout.strip().splitlines()[-1])
json.dump(pte, open('pte21_reading_answers_v2.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

def parse_answers(path):
    html = open(path, encoding='utf-8').read()
    m = re.search(r'const ANSWERS = \{(.*?)\};', html, re.S)
    body = m.group(1)
    pairs = re.findall(r'(\d+):"([^"]*)"', body)
    return {int(k): v for k, v in pairs}

cam = {}
for t in [1,2,3,4]:
    cam[t] = parse_answers('cam21/t%d-reading.html' % t)
    print('cam21 T%d parsed: %d answers' % (t, len(cam[t])))

def cmp(name, cam_d, pte_list):
    n_match = 0; n_tot = 0; diffs = []
    for i in range(1, 41):
        p = pte_list[i-1] if pte_list and i-1 < len(pte_list) else None
        c = cam_d.get(i)
        if p is None or c is None:
            if c is not None and p is None: diffs.append((i, c, '<missing>'))
            continue
        n_tot += 1
        if str(p).strip().lower() == str(c).strip().lower():
            n_match += 1
        else:
            diffs.append((i, c, p))
    print('%-28s match %d/%d %s' % (name, n_match, n_tot, 'OK' if n_match==n_tot and not diffs else 'DIFFS'))
    for d in diffs[:15]:
        print('     Q%d cam21=%r pte=%r' % d)
    return n_match, n_tot, diffs

print()
for t in [1,2,3,4]:
    r = pte['t%d' % t]
    print('--- pteReading(21,%d) slug=%s answers=%d ---' % (t, r['slug'], r['count']))
    cmp('pte T%d vs cam21 T%d' % (t, t), cam[t], r['answers'])
    print()
