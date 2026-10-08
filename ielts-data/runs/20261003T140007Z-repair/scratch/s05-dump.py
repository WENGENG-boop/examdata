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

def main():
    path = sys.argv[1]
    name = sys.argv[2]
    op = sys.argv[3] if len(sys.argv) > 3 else ('[' if name in ('QUESTIONS',) else '{')
    html = open(path, encoding='utf-8').read()
    scripts = re.findall(r'<script[^>]*>([\s\S]*?)</script>', html, re.I)
    js = max(scripts, key=len)
    lit = extract_literal(js, name, op)
    out = sys.stdout
    out.write(lit if lit else 'NONE')
    out.write('\n')

if __name__ == '__main__':
    main()
