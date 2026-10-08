import json
root='C:/Users/weo/Desktop/api/cie-location-batch'
cur=json.load(open(root+'/indexes/9715/2023-Nov-21/cie-index.json',encoding='utf-8'))
prop=json.load(open(root+'/work/proposals/9715/2023-Nov-21.json',encoding='utf-8'))
curb={}
for q in cur['questions']:
    if q['parent'] is not None:
        curb[q['question']]=[(r['page'],r['bbox']) for r in q['ms']]
# for each prop candidate: label_bbox must be inside cur band of same page
bad=[]; ok=0; missing=[]
for c in prop['ms_candidates']:
    lab=c['label']; pg=c['page']; lb=c['label_bbox']
    cand=[bb for (p,bb) in curb.get(lab,[]) if p==pg]
    if not cand: missing.append((lab,pg)); continue
    bb=cand[0]
    if lb[0]>=bb[0]-1 and lb[2]<=bb[2]+1: ok+=1
    else: bad.append((lab,pg,lb,bb))
print('label-in-cur-band ok:',ok,'bad:',len(bad),'missing:',len(missing))
for b in bad: print('  BAD',b)
for m in missing: print('  MISSING',m)
# check: does a cur child band contain the next label?
labels=sorted([(c['page'],c['row'][0],c['label'],c['label_bbox']) for c in prop['ms_candidates']])
import collections
byp=collections.defaultdict(list)
for pg,r0,lab,lb in labels: byp[pg].append((r0,lab,lb))
for pg,items in sorted(byp.items()):
    items.sort()
    for i,(r0,lab,lb) in enumerate(items):
        if i+1<len(items):
            nxt=items[i+1]
            cand=[bb for (p,bb) in curb.get(lab,[]) if p==pg]
            if cand and nxt[2][0] <= cand[0][2]+0.5:
                print('  OVERLAP-NEXT',pg,lab,'band',cand[0],'next-label-x0',nxt[2][0],nxt[1])
print('done')
