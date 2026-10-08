import re, sys

def extract_literal(src, name, open_ch='{'):
    close_ch = '}' if open_ch == '{' else ']'
    # match: const NAME = {   (backslash-escaped open brace in regex)
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

def main():
    path = sys.argv[1]
    names = sys.argv[2:] if len(sys.argv) > 2 else ['GROUPS','HEADINGS','ENDINGS']
    html = open(path, encoding='utf-8').read()
    scripts = re.findall(r'<script[^>]*>([\s\S]*?)</script>', html, re.I)
    js = max(scripts, key=len)
    for spec in names:
        if ':' in spec:
            name, op = spec.split(':', 1)
        else:
            name, op = spec, '{'
        lit = extract_literal(js, name, op)
        print('='*25, name, 'len', len(lit) if lit else None)
        if lit:
            lim = int(__import__('os').environ.get('LIM', '2500'))
            print(lit[:lim])
        print()

if __name__ == '__main__':
    main()
