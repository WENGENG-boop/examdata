# -*- coding: utf-8 -*-
"""Rebuild the 0472 viewer with current sheets (cache-busted).

Frames: 4 qp-pages + 1 ms-pages + 18 qp-region stacks + 3 msreg stacks = 26.
"""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SHEETS = BASE / 'work' / 'sheets'
NAME = '0472-2024-Jun-11'
V = '4'

entries = []  # (url, label)
for i in range(1, 5):
    entries.append((f'/work/sheets/{NAME}-qp-pages-{i}.html?v={V}',
                    f'qp-pages | p{(i-1)*4+1}-{i*4}'))
entries.append((f'/work/sheets/{NAME}-ms-pages-1.html?v={V}',
                'ms-pages | p1-p3'))

def stack_entries(pattern, prefix, count):
    for i in range(1, count + 1):
        html = (SHEETS / f'{NAME}-{prefix}-stack-{i}.html').read_text(encoding='utf-8')
        labels = [lab.split('  [')[0].strip()
                  for lab in re.findall(r'<div class=cap>(.*?)</div>', html)]
        entries.append((f'/work/sheets/{NAME}-{prefix}-stack-{i}.html?v={V}',
                        f'{pattern} | ' + ','.join(labels)))

stack_entries('qp-regions', 'qp-regions', 18)
stack_entries('ms-regions', 'msreg', 3)

parts = ["<!doctype html><html><head><meta charset='utf-8'><title>VIEWER 0472</title><style>",
         "html,body{margin:0;padding:0;background:#222;height:100vh;overflow:hidden}",
         "#bar{font:16px monospace;background:#ff0;color:#000;padding:4px 8px;position:fixed;top:0;left:0;right:0;z-index:99}",
         "iframe{position:absolute;top:36px;left:0;width:1020px;height:656px;border:0;display:none;background:#fff}",
         "iframe.on{display:block}",
         "</style></head><body><div id='bar'></div>"]
for i, (url, lab) in enumerate(entries):
    parts.append(f"<iframe id='f{i}' src='{url}'></iframe>")
parts.append("<script>")
parts.append("const L = " + json.dumps([e[1] for e in entries], ensure_ascii=False) + ";")
parts.append("""let cur = 0;
{ const m = location.hash.match(/^#(\\d+)$/); if (m) { cur = Math.min(Math.max(parseInt(m[1],10)-1,0), L.length-1); } }
function show(){ for(let i=0;i<L.length;i++){document.getElementById('f'+i).className=(i===cur?'on':'');} document.getElementById('bar').textContent=(cur+1)+'/'+L.length+'  '+L[cur]; }
document.addEventListener('keydown',e=>{ if(e.key==='ArrowRight'||e.key==='PageDown'||e.key===' '){cur=Math.min(cur+1,L.length-1);show();} else if(e.key==='ArrowLeft'||e.key==='PageUp'){cur=Math.max(cur-1,0);show();} e.preventDefault();});
show();
</script></body></html>""")
out = SHEETS / f'{NAME}-viewer.html'
out.write_text('\n'.join(parts), encoding='utf-8')
print('viewer written:', out, '| frames:', len(entries))
for i, (u, l) in enumerate(entries):
    print(f'  {i+1}/{len(entries)}  {l}')
