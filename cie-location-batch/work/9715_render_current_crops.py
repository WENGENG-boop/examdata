import json
from pathlib import Path
import fitz

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'indexes/9715/2023-Nov-21/cie-index.json'
TMP = ROOT / 'tmp/9715/2023-Nov-21'
OUT = ROOT / 'work/9715-current-crops'
OUT.mkdir(parents=True, exist_ok=True)
data = json.loads(INDEX.read_text(encoding='utf-8'))
docs = {'qp': fitz.open(TMP / '9715_w23_qp_21.pdf'), 'ms': fitz.open(TMP / '9715_w23_ms_21.pdf')}
by_page = {}
manifest = []
for q in data['questions']:
    for role in ('qp','ms'):
        for i, region in enumerate(q.get(role) or [], start=1):
            page_no = int(region['page'])
            page = docs[role][page_no-1]
            raw = fitz.Rect(region['bbox'])
            visual = raw * page.rotation_matrix
            pad = 2.0
            clip = fitz.Rect(max(0, visual.x0-pad), max(0, visual.y0-pad),
                             min(page.rect.width, visual.x1+pad), min(page.rect.height, visual.y1+pad))
            pix = page.get_pixmap(matrix=fitz.Matrix(1.65, 1.65), clip=clip, alpha=False)
            name = f'{role}-p{page_no:02}-{q["question"].replace("(", "-").replace(")", "")}-{i:02}.png'
            path = OUT / name
            pix.save(path)
            label = f'{q["question"]} {role.upper()} p{page_no} bbox={region["bbox"]}'
            by_page.setdefault((role,page_no), []).append((label,path,pix.width,pix.height))
            manifest.append({'question': q['question'], 'role': role, 'page': page_no,
                             'bbox': region['bbox'], 'crop': str(path.resolve()),
                             'visual_bbox': [round(x,2) for x in visual],
                             'size_px': [pix.width,pix.height]})
contact = fitz.open()
for (role,page_no), items in sorted(by_page.items()):
    width=max(900,max(w for _,_,w,_ in items)+24)
    heights=[24+h+8 for _,_,w,h in items]
    height=24+sum(heights)
    sheet=contact.new_page(width=width,height=height)
    y=18
    for label,path,w,h in items:
        sheet.insert_text((12,y),label,fontsize=10,fontname='helv',color=(0,0,0))
        y+=24
        sheet.insert_image(fitz.Rect(12,y,12+w,y+h),filename=str(path),keep_proportion=False)
        y+=h+8
    pix=sheet.get_pixmap(matrix=fitz.Matrix(1,1),alpha=False)
    target=ROOT/'work'/f'9715-current-crops-{role}-p{page_no:02}.png'
    pix.save(target)
    print(f'{target.resolve()}\tregions={len(items)}\tsize={pix.width}x{pix.height}')
(ROOT/'work'/'9715-current-crop-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('total regions',len(manifest),'unique visual clips',len({(m['role'],m['page'],tuple(m['visual_bbox'])) for m in manifest}))
