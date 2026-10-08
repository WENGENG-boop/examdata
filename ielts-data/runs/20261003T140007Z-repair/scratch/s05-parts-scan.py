import re, collections

BASE = 'C:/Users/weo/Desktop/api/tmp_audit_ielts/cam21/'

def extract_literal(js, name, open_ch='{'):
    close_ch = '}' if open_ch == '{' else ']'
    pat = 'const' + r'\s+' + name + (r'\s*=\s*\{' if open_ch == '{' else r'\s*=\s*\[')
    m = re.search(pat, js)
    if not m:
        return None
    bs = js.index(open_ch, m.start())
    depth = 0; i = bs; in_str = None; esc = False
    while i < len(js):
        ch = js[i]
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
    return js[bs:i]

def unesc(s):
    return s.replace('\\"', '"').replace("\\'", "'").replace('\\\\', '\\').replace('\\n', '\n')

for t in (1, 2, 3, 4):
    html = open(BASE + f't{t}-listening.html', encoding='utf-8').read()
    scripts = re.findall(r'<script[^>]*>([\s\S]*?)</script>', html, re.I)
    js = max(scripts, key=len)
    parts = unesc(extract_literal(js, 'PARTS', '{') or '')
    print(f'== t{t}')
    print('   input types:', dict(collections.Counter(re.findall(r'<input[^>]*?type="([a-z]+)"', parts))))
    print('   data-q total:', len(re.findall(r'data-q="(\d+)"', parts)))
    print('   elements with data-q:', dict(collections.Counter(re.findall(r'<([a-z0-9]+)[^>]*data-q="', parts))))
    print('   inputs with name=:', dict(collections.Counter(re.findall(r'<input[^>]*name="([^"]+)"', parts))))
    print('   inputs with value=:', dict(collections.Counter(re.findall(r'<input[^>]*type="radio"[^>]*value="([^"]+)"', parts))))
    print('   checkboxes:', len(re.findall(r'type="checkbox"', parts)), ' radios:', len(re.findall(r'type="radio"', parts)))
    # data-q="N" where N is a range like "21-22"?
    rng = re.findall(r'data-q="([^"]*)"', parts)
    odd = [x for x in rng if not x.isdigit()]
    print('   non-numeric data-q:', odd[:10])
    # q-label lines
    print('   q-labels:', re.findall(r'<p class="q-label">([^<]+)</p>', parts))
    # checkbox inputs sample
    cbs = re.findall(r'<input[^>]*type="checkbox"[^>]*>', parts)
    if cbs: print('   checkbox sample:', cbs[:6])
    radios = re.findall(r'<input[^>]*type="radio"[^>]*>', parts)
    if radios: print('   radio sample:', radios[:4])
