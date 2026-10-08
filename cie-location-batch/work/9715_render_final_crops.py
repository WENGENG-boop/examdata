import hashlib, json
from pathlib import Path
import fitz

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'indexes/9715/2023-Nov-21/cie-index.json'
TMP = ROOT / 'tmp/9715/2023-Nov-21'
OUT = ROOT / 'work/9715-final-region-crops'
OUT.mkdir(parents=True, exist_ok=True)
data=json.loads(INDEX.read_text(encoding='utf-8'))
docs={'qp':fitz.open(TMP/'9715_w23_qp_21.pdf'),'ms':fitz.open(TMP/'9715_w23_ms_21.pdf')}
by_page={}
manifest=[]
for q in data['questions']:
    for role in ('qp','ms'):
        for rnum,r in enumerate(q[role],1):
            page_no=int(r['page'])
            page=docs[role][page_no-1]
            stored=fitz.Rect(r['bbox'])
            visible=stored*page.rotation_matrix
            pad=2.0
            clip=fitz.Rect(max(0,visible.x0-pad),max(0,visible.y0-pad),
                           min(page.rect.width,visible.x1+pad),min(page.rect.height,visible.y1+pad))
            pix=page.get_pixmap(matrix=fitz.Matrix(1.65,1.65),clip=clip,alpha=False)
            name=f'{role}-p{page_no:02}-r{len(manifest)+1:02}.png'
            path=OUT/name
            pix.save(path)
            label=f'{q["question"]} {role.upper()} p{page_no} bbox={r["bbox"]}'
            by_page.setdefault((role,page_no),[]).append((label,path,pix.width,pix.height))
            manifest.append({'question':q['question'],'role':role,'page':page_no,'bbox':r['bbox'],
                             'image':str(path.resolve()),'image_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                             'visible_bbox':[round(v,2) for v in visible],'size_px':[pix.width,pix.height]})
for (role,page_no),items in sorted(by_page.items()):
    width=max(900,max(w for _,_,w,_ in items)+24)
    height=24+sum(24+h+8 for _,_,_,h in items)
    sheet=fitz.open()
    page=sheet.new_page(width=width,height=height)
    y=18
    for label,path,w,h in items:
        page.insert_text((12,y),label,fontsize=10,fontname='helv',color=(0,0,0))
        y+=24
        page.insert_image(fitz.Rect(12,y,12+w,y+h),filename=str(path),keep_proportion=False)
        y+=h+8
    target=ROOT/'work'/f'9715-final-crops-{role}-p{page_no:02}.png'
    page.get_pixmap(matrix=fitz.Matrix(1,1),alpha=False).save(target)
    print(f'{target.resolve()}\tregions={len(items)}\tsize={width}x{height}')
(ROOT/'work'/'9715-final-crop-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('regions',len(manifest),'pages_with_regions',len(by_page))
