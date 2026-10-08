import json, glob, os, re, sys

ev = r'C:\Users\weo\Desktop\api\tmp_audit_ielts\completeness_20261003'
req = json.load(open(os.path.join(ev, 'requests.json'), encoding='utf-8'))

stats = {'files': 0, 'ol': 0, 'ol_start': 0, 'li_value': 0, 'img': 0, 'audio': 0,
         'input': 0, 'table': 0, 'figure': 0, 'ol_start_vals': [], 'img_samples': [],
         'input_samples': [], 'empty_li_files': 0, 'numbered_ans': 0}

for i in range(len(req)):
    p = os.path.join(ev, f'raw-{i}.txt')
    if not os.path.exists(p):
        continue
    body = open(p, encoding='utf-8').read()
    if 'practicepteonline' not in req[i]['url']:
        continue
    # only page content payloads
    if 'slug=' not in req[i]['url'] and 'pages/' not in req[i]['url']:
        continue
    try:
        d = json.loads(body)
    except Exception:
        continue
    if isinstance(d, list):
        if not d:
            continue
        page = d[0]
    else:
        page = d
    c = (page.get('content') or {}).get('rendered') or ''
    if not c:
        continue
    stats['files'] += 1
    if re.search(r'<ol[^>]*>', c):
        stats['ol'] += 1
        for m in re.finditer(r'<ol([^>]*)>', c):
            a = m.group(1)
            sm = re.search(r'start=["\']?(\d+)', a)
            if sm:
                stats['ol_start'] += 1
                stats['ol_start_vals'].append(sm.group(1))
    if re.search(r'<li[^>]*value=', c):
        stats['li_value'] += 1
    if re.search(r'<img\b', c):
        stats['img'] += 1
        if len(stats['img_samples']) < 12:
            m = re.search(r'<img[^>]*>', c)
            stats['img_samples'].append((i, page.get('slug'), m.group(0)[:220]))
    if re.search(r'<audio\b', c):
        stats['audio'] += 1
    if re.search(r'<input\b', c):
        stats['input'] += 1
        if len(stats['input_samples']) < 12:
            m = re.search(r'<input[^>]*>', c)
            stats['input_samples'].append((i, page.get('slug'), m.group(0)[:200]))
    if re.search(r'<table\b', c):
        stats['table'] += 1
    if re.search(r'<figure\b', c):
        stats['figure'] += 1
    if re.search(r'<li[^>]*>\s*</li>', c):
        stats['empty_li_files'] += 1
    if re.search(r'bg-showmore-hidden', c):
        # numbered paragraph form?
        m = re.search(r"bg-showmore-hidden-[^'\"]*['\"][^>]*>([\s\S]{0,2000})", c)
        if m and re.search(r'\d+\.\s', m.group(1)):
            stats['numbered_ans'] += 1

print(json.dumps(stats, ensure_ascii=False, indent=1))
