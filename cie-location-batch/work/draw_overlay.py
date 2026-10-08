import json
from PIL import Image, ImageDraw
root='C:/Users/weo/Desktop/api/cie-location-batch'
d=json.load(open(root+'/work/p6-overlay-rects.json',encoding='utf-8'))
Z=d['zoom']
img=Image.open(root+'/tmp/9715/2023-Nov-21/probe/p6-clean.png').convert('RGB')
W,H=img.size
def to_disp(bb):
    x0,y0,x1,y1=bb
    # display: x_d=792-y_u ; y_d=x_u
    return [ (792-y1)*Z, x0*Z, (792-y0)*Z, x1*Z ]
for name,rects,color,off in [('cur',d['cur'],(255,0,0),0),('prop',d['prop'],(0,80,255),6)]:
    im=img.copy(); dr=ImageDraw.Draw(im)
    for lbl,bb in rects:
        x0,y0,x1,y1=to_disp(bb)
        dr.rectangle([x0+off,y0+off,x1-off,y1-off],outline=color,width=4 if name=='cur' else 3)
    im.save(root+f'/tmp/9715/2023-Nov-21/probe/p6-{name}.png')
# both
im=img.copy(); dr=ImageDraw.Draw(im)
for lbl,bb in d['cur']:
    x0,y0,x1,y1=to_disp(bb); dr.rectangle([x0,y0,x1,y1],outline=(255,0,0),width=4)
for lbl,bb in d['prop']:
    x0,y0,x1,y1=to_disp(bb); dr.rectangle([x0+5,y0+5,x1-5,y1-5],outline=(0,80,255),width=3)
im.save(root+'/tmp/9715/2023-Nov-21/probe/p6-both.png')
print('ok',W,H)
