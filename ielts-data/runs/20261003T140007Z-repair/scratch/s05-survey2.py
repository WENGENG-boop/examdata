import re, json

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
    return s.replace('\\"', '"').replace('\\n', '\n').replace("\\'", "'")

for t in (2, 3, 4):
    html = open(BASE + f't{t}-listening.html', encoding='utf-8').read()
    scripts = re.findall(r'<script[^>]*>([\s\S]*?)</script>', html, re.I)
    js = max(scripts, key=len)
    parts = unesc(extract_literal(js, 'PARTS', '{') or '')
    open(f't{t}-parts.unesc.txt', 'w', encoding='utf-8').write(parts)
    ca = unesc(extract_literal(js, 'correctAnswers', '{') or '')
    mc = unesc(extract_literal(js, 'multiCorrect', '{') or '')
    print('=' * 30, 't' + str(t))
    print('q-labels:', re.findall(r'<p class="q-label"[^>]*>([^<]+)</p>', parts))
    print('mcq-question count:', len(re.findall(r'<span class="qnum">(\d+)</span>', parts)))
    print('mcq qnums:', re.findall(r'<span class="qnum">(\d+)</span>', parts))
    print('radio names:', sorted(set(re.findall(r'name="q(\d+)"', parts)), key=int))
    print('check-groups:', re.findall(r'<div class="check-group" data-questions="([^"]+)" data-max="(\d+)"', parts))
    print('data-q:', re.findall(r'data-q="(\d+)"', parts))
    print('correctAnswers:', ca[:700])
    print('multiCorrect:', mc[:400])
    print()
