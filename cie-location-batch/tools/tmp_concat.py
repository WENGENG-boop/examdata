import re, sys, os

d = os.path.join(os.path.dirname(__file__), "..", "work", "sheets")
files = [os.path.join(d, f"9608-2021-Nov-11-v2-grid-{i}.html") for i in range(1, 6)]

parts = []
for idx, f in enumerate(files, 1):
    html = open(f, encoding="utf-8").read()
    body = re.search(r"<body>(.*)</body>", html, re.S).group(1)
    marker = (f'<div class=cap style="background:#c00;color:#fff;padding:0;'
              f'height:18px;line-height:18px">=== SHEET {idx} (start) ===</div>')
    parts.append(marker + body)

parts.append('<div class=cap style="background:#c00;color:#fff;padding:0;'
             'height:18px;line-height:18px">=== END OF ALL SHEETS ===</div>')

style = ("html,body{margin:0;padding:0;background:#fff}"
         ".r{display:flex;align-items:flex-start}"
         ".c{width:33.333%}"
         ".cap{font:11px/15px monospace;background:#ff0;color:#000;padding:1px 3px;"
         "white-space:nowrap;overflow:hidden}"
         "img{display:block;border-bottom:1px solid #888;width:100%!important;height:auto!important}")

overlay = ('<div id=ov style="position:fixed;top:0;right:0;background:#00f;color:#fff;'
           'font:bold 26px/34px monospace;padding:2px 10px;z-index:99">WINDOW ?/?</div>')

script = """
<script>
var ov=document.getElementById('ov');
function H(){return Math.max(document.documentElement.scrollHeight, document.body.scrollHeight);}
function N(){return Math.ceil(H()/window.innerHeight);}
function show(){
  var y=window.scrollY, h=window.innerHeight, n=N();
  var k=Math.round(y/h);
  var total=Math.round(H());
  ov.textContent='W '+k+'/'+(n-1)+' y='+Math.round(y)+' h='+h+' H='+total;
}
window.addEventListener('scroll',show);
window.addEventListener('resize',show);
window.addEventListener('load',show);
show();
</script>
"""

out = ("<!doctype html><html><head><meta charset='utf-8'><style>" + style +
       "</style></head><body>" + overlay + "".join(parts) + script + "</body></html>")
p = os.path.join(d, "9608-2021-Nov-11-v2-static.html")
open(p, "w", encoding="utf-8").write(out)
print("wrote", p)
print("http://127.0.0.1:8792/work/sheets/9608-2021-Nov-11-v2-static.html")
