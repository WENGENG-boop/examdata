import json, fitz
root='C:/Users/weo/Desktop/api/cie-location-batch'
cur=json.load(open(root+'/indexes/9715/2023-Nov-21/cie-index.json',encoding='utf-8'))
prop=json.load(open(root+'/work/proposals/9715/2023-Nov-21.json',encoding='utf-8'))
doc=fitz.open(root+'/tmp/9715/2023-Nov-21/9715_w23_ms_21.pdf')
page=doc[5]  # p6
Z=1.5
pix=page.get_pixmap(matrix=fitz.Matrix(Z,Z))
out=root+'/tmp/9715/2023-Nov-21/probe/p6-clean.png'
pix.save(out)
print('saved',out,pix.width,pix.height)
# collect rects
curR=[]; propR=[]
for q in cur['questions']:
    for r in q['ms']:
        if r['page']==6: curR.append((q['question'],r['bbox']))
for c in prop['ms_candidates']:
    if c['page']==6: propR.append((c['label'],c['row_bbox']))
json.dump({'cur':curR,'prop':propR,'zoom':Z},open(root+'/work/p6-overlay-rects.json','w'),ensure_ascii=False,indent=1)
print('cur rects:',len(curR),'prop rects:',len(propR))
