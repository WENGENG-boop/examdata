import re

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

html = open(BASE + 't1-listening.html', encoding='utf-8').read()
scripts = re.findall(r'<script[^>]*>([\s\S]*?)</script>', html, re.I)
js = max(scripts, key=len)
parts = extract_literal(js, 'PARTS', '{')
# it's a JS object literal with keys "1": "...", ...; unescape and split by part
# Simple approach: replace \" with " and write whole thing
raw = parts.replace('\\"', '"').replace('\\n', '\n')
open('t1-parts.unesc.txt', 'w', encoding='utf-8').write(raw)
print('written', len(raw))
