import json, fitz
from PIL import Image, ImageDraw
root='C:/Users/weo/Desktop/api/cie-location-batch'
cur=json.load(open(root+'/indexes/9715/2023-Nov-21/cie-index.json',encoding='utf-8'))
doc=fitz.open(root+'/tmp/9715/2023-Nov-21/9715_w23_ms_21.pdf')
page=doc[7]  # p8
Z=1.5
pix=page.get_pixmap(matrix=fitz.Matrix(Z,Z))
out=root+'/tmp/9715/2023-Nov-21/probe/p8-clean.png'
pix.save(out)
img=Image.open(out).convert('RGB')
dr=ImageDraw.Draw(img)
def to_disp(bb):
    x0,y0,x1,y1=bb
    return [ (792-y1)*Z, x0*Z, (792-y0)*Z, x1*Z ]
rects=[]
for q in cur['questions']:
    for r in q['ms']:
        if r['page']==8: rects.append((q['question'],q['parent'],r['bbox']))
print('rects:',rects)
for lbl,par,bb in rects:
    x0,y0,x1,y1=to_disp(bb)
    color=(255,0,0) if par is None else (0,170,0)
    dr.rectangle([x0,y0,x1,y1],outline=color,width=4)
img.save(root+'/tmp/9715/2023-Nov-21/probe/p8-overlay.png')
print('saved p8-overlay.png',img.size)
