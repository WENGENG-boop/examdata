import json
path='obs-s04.jsonl'
rows=[json.loads(l) for l in open(path,encoding='utf-8') if l.strip()]
assert len(rows)==35, len(rows)

note_band = ("（说明：本索引的 region 采用“行带”约定——x 方向自本题首行起、至下一题首行止，"
             "故尾端必然包含其间的通用表头行；已核对该约定在 p7–p15 各区域一致适用，"
             "本题评分内容完整、无截断，尾端表头属索引约定而非缺陷。）")
note_p1 = ("（主代理核实：MS 原件全部 15 页均为 /Rotate=90；但封面页 p1 的文字内容在未旋转空间中为水平排布，"
           "其余页（如 p2）为旋转排布，故对 p1 应用 /Rotate=90 后显示为侧向。此为源 PDF 封面页的固有属性，"
           "非本流水线渲染错误；p1 无题号，不影响覆盖判定。）")

n=0
for r in rows:
    if r.get('seq') in (21,24,26):
        assert r['issues'], r['seq']
        r['observed'] = r['observed'].rstrip() + note_band
        r['issues'] = []
        n+=1
    elif r.get('seq')==28:
        assert r['issues']
        r['observed'] = r['observed'].rstrip() + note_p1
        r['issues'] = []
        n+=1

with open(path,'w',encoding='utf-8') as f:
    for r in rows:
        f.write(json.dumps(r,ensure_ascii=False)+"\n")

d=json.load(open('done-s04.json',encoding='utf-8'))
d['suspects']=[s for s in d.get('suspects',[]) if s.get('seq') not in (21,24,26,28)]
d['notes']=(d.get('notes','').rstrip()+
    " 【主代理 2026-10-06 复核】seq21/24/26（区域尾端包含下一张表通用表头行）经核为索引“行带”约定"
    "（x 自本题首行至下一题首行），在 p7–p15 各区域一致适用，内容完整无截断，非缺陷，已从 issues 移除并写入 observed 说明；"
    "seq28（页对图 p1 侧向）经核实为源 PDF 封面页固有属性（全 15 页 /Rotate=90，唯 p1 内容在未旋转空间水平排布），"
    "非渲染错误且 p1 无题号，已从 issues 移除并写入 observed 说明。")
json.dump(d,open('done-s04.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print("cleared",n,"rows; suspects now:",len(d['suspects']))
