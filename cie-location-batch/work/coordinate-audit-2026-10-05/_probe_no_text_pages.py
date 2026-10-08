import pymupdf, glob, hashlib, os, json, sys
BATCH=r"C:/Users/weo/Desktop/api/cie-location-batch"
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda:f.read(1<<20),b''): h.update(c)
    return h.hexdigest()
for key in ["8238/2025/Jun/32","8238/2026/Jun/32","8238/2025/Nov/31"]:
    s,y,se,p = key.split('/')
    idx=json.load(open(os.path.join(BATCH,'indexes',s,f"{y}-{se}-{p}",'cie-index.json'),encoding='utf-8'))
    for role in ('ms','qp'):
        want=next((d['sha256'] for d in idx['documents'] if d['role']==role),None)
        tmpdir=os.path.join(BATCH,'tmp',s,f"{y}-{se}-{p}")
        path=None
        for f in glob.glob(os.path.join(tmpdir,'*.pdf')):
            if sha(f)==want: path=f
        if not path: print(key,role,"missing"); continue
        doc=pymupdf.open(path)
        print(f"== {key} {role} pages={doc.page_count}")
        for i,page in enumerate(doc):
            t=page.get_text().strip()
            if t: continue
            imgs=page.get_images(full=True)
            info=[]
            for im in imgs:
                xref=im[0]
                d=doc.extract_image(xref)
                info.append(f"xref{xref} {d['width']}x{d['height']} {d['ext']} {len(d['image'])}B")
            print(f"   p{i+1} NO-TEXT images={len(imgs)} {info}")
        doc.close()
