import json, fitz
from collections import defaultdict
root='C:/Users/weo/Desktop/api/cie-location-batch'
cur=json.load(open(root+'/indexes/9715/2023-Nov-21/cie-index.json',encoding='utf-8'))
prop=json.load(open(root+'/work/proposals/9715/2023-Nov-21.json',encoding='utf-8'))
doc=fitz.open(root+'/tmp/9715/2023-Nov-21/9715_w23_ms_21.pdf')

cur_bands=defaultdict(list)
for q in cur['questions']:
    for r in q['ms']:
        cur_bands[r['page']].append((r['bbox'][0],r['bbox'][2],q['question']))
prop_bands=defaultdict(list)
for c in prop['ms_candidates']:
    prop_bands[c['page']].append((c['row'][0],c['row'][1],c['label']))

Y0,Y1=57.2,735.6
for pno in range(6,19):
    page=doc[pno-1]
    words=[w for w in page.get_text('words') if w[4].strip()]
    words=[w for w in words if w[1]>=Y0-1 and w[3]<=Y1+1]
    print(f'=== page {pno} rot={page.rotation} words={len(words)}')
    for name,bands in [('cur',cur_bands[pno]),('prop',prop_bands[pno])]:
        edges=sorted(set([round(b[0],1) for b in bands]+[round(b[1],1) for b in bands]))
        cut=[]
        for w in words:
            x0,x1,t=w[0],w[2],w[4]
            for e in edges:
                if x0<e-0.5 and x1>e+0.5:
                    cut.append((t,round(x0,1),round(x1,1),e))
        uncov=[]
        for w in words:
            x0,x1,t=w[0],w[2],w[4]
            cov=any(b[0]-0.6<=x0 and x1<=b[1]+0.6 for b in bands)
            if not cov: uncov.append((t,round(x0,1),round(x1,1)))
        print(f'  [{name}] edges={edges}')
        print(f'    cut={cut}')
        print(f'    uncov={uncov}')
