import re, sys, json

def extract_literal(src, name, open_ch='{'):
    close_ch = '}' if open_ch == '{' else ']'
    pat = 'const' + r'\s+' + name + (r'\s*=\s*\{' if open_ch == '{' else r'\s*=\s*\[')
    m = re.search(pat, src)
    if not m:
        return None
    body_start = src.index(open_ch, m.start())
    depth = 0; i = body_start; in_str = None; esc = False
    while i < len(src):
        ch = src[i]
        if in_str:
            if esc: esc = False
            elif ch == '\\': esc = True
            elif ch == in_str: in_str = None
        else:
            if ch in ('"', "'", '`'): in_str = ch
            elif ch == open_ch: depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    i += 1
                    break
        i += 1
    return src[body_start:i]

def load_js(path):
    html = open(path, encoding='utf-8').read()
    scripts = re.findall(r'<script[^>]*>([\s\S]*?)</script>', html, re.I)
    return max(scripts, key=len)

BASE = 'C:/Users/weo/Desktop/api/tmp_audit_ielts/cam21/'

print('########## READING ##########')
for t in (1,2,3,4):
    js = load_js(BASE + f't{t}-reading.html')
    qlit = extract_literal(js, 'QUESTIONS', '[')
    alit = extract_literal(js, 'ANSWERS', '{')
    glit = extract_literal(js, 'GROUPS', '{')
    # count question objects and their ids/types
    ids = [int(m.group(1)) for m in re.finditer(r'\{id:(\d+),', qlit or '')]
    types = re.findall(r"type:'([a-z]+)'", qlit or '')
    import collections
    tc = collections.Counter(types)
    # multi groups
    multis = re.findall(r'\{id:(\d+),p:(\d+),g:(\'g\d+\'),type:\'multi\',from:(\d+),to:(\d+),pick:(\d+)', qlit or '')
    # answers keys
    akeys = re.findall(r'(\d+):', alit or '')
    arr_ans = re.findall(r'(\d+):\[', alit or '')
    print(f't{t}: q_objs={len(ids)} ids={ids[:5]}...{ids[-3:]} types={dict(tc)}')
    print(f'   multi_groups={multis} answer_keys={len(akeys)} array_answers={arr_ans}')
    print(f'   headings_empty={"const HEADINGS = [];" in js} groups_len={len(glit or "")}')

print()
print('########## LISTENING ##########')
for t in (1,2,3,4):
    js = load_js(BASE + f't{t}-listening.html')
    plit = extract_literal(js, 'PARTS', '{')
    tlit = extract_literal(js, 'TITLES', '{')
    trk = extract_literal(js, 'audioTracks', '{')
    calit = extract_literal(js, 'correctAnswers', '{')
    mlit = extract_literal(js, 'multiCorrect', '{')
    slit = extract_literal(js, 'TRANSCRIPTS', '{')
    print(f't{t}: PARTS len={len(plit or "")} TITLES len={len(tlit or "")} audioTracks len={len(trk or "")}')
    print(f'   correctAnswers len={len(calit or "")} multiCorrect len={len(mlit or "")} TRANSCRIPTS len={len(slit or "")}')
    if t == 1:
        open('t1l-parts.lit.txt','w',encoding='utf-8').write(plit or '')
        open('t1l-titles.lit.txt','w',encoding='utf-8').write(tlit or '')
        open('t1l-tracks.lit.txt','w',encoding='utf-8').write(trk or '')
        open('t1l-correct.lit.txt','w',encoding='utf-8').write(calit or '')
        open('t1l-multi.lit.txt','w',encoding='utf-8').write(mlit or '')
        open('t1l-transcripts-head.lit.txt','w',encoding='utf-8').write((slit or '')[:4000])
