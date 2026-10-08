"""Read-only source audit; writes only its own dated evidence artifacts."""
import sys, json, hashlib, math, csv
from pathlib import Path
from collections import Counter
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import service_audit as A
import validate_index as V
import batchlib as B

out = Path(__file__).parent / 'coordinate-audit-2026-10-05'
out.mkdir(exist_ok=True)
sources = ['papers.json','subjects.json','catalogue-grid.json','checkpoint.json','summary.json','verification.jsonl']
before = {n: B.sha256_file(B.BATCH_ROOT/n) for n in sources}
papers = B.read_json(B.PAPERS)
manifest = A.build_manifest()
rows=[]
counts=Counter()
for r in manifest['entries']:
    p=Path(r['local_index']); d=B.read_json(p)
    validation=V.validate(p)
    errors,warnings=validation['errors'],validation.get('warnings',[])
    c=Counter(); issues=[]
    for q in d['questions']:
        c['questions']+=1
        c['uncertain']+=bool(q.get('uncertain',True))
        c['empty_text']+=not bool(q.get('text','').strip())
        for role in ('qp','ms'):
            regs=q.get(role,[])
            c['missing_'+role]+=not bool(regs)
            c[role+'_regions']+=len(regs)
            for reg in regs:
                box=reg.get('bbox',[])
                if len(box)!=4 or not all(isinstance(v,(float,int)) and math.isfinite(v) for v in box) or box[0]<0 or box[1]<0 or box[2]<=box[0] or box[3]<=box[1]:
                    issues.append({'question':q['question'],'role':role,'region':reg})
    counts.update(c)
    r.update(dict(c),schema_errors=errors,schema_warnings=warnings,basic_bbox_issues=issues)
    rows.append(r)
keys={r['key'] for r in rows}
missing=[{'key':k,'kind':v.get('kind'),'stage':v.get('stage'),'qp_files':'|'.join(v.get('qp',[])),'ms_files':'|'.join(v.get('ms',[]))} for k,v in papers.items() if k not in keys]
with (out/'papers-without-index.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['key','kind','stage','qp_files','ms_files']);w.writeheader();w.writerows(missing)
after={n:B.sha256_file(B.BATCH_ROOT/n) for n in sources}
result={'checked_at':datetime.now().astimezone().isoformat(),'source_hashes':before,'sources_unchanged':before==after,'papers_total':len(papers),'kind_counts':dict(Counter(v.get('kind') for v in papers.values())),'stage_counts':dict(Counter(v.get('stage') for v in papers.values())),'indexes':len(rows),'missing_indexes':len(missing),'unknown_index_keys':sorted(keys-set(papers)),'indexed_subjects':sorted({r['subject'] for r in rows}),'counts':dict(counts),'schema_invalid_indexes':sum(bool(r['schema_errors']) for r in rows),'basic_bbox_invalid_indexes':sum(bool(r['basic_bbox_issues']) for r in rows),'service':{k:v for k,v in manifest.items() if k!='entries'},'checkpoint':B.read_json(B.CHECKPOINT),'entries':rows}
(out/'evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('entries','checkpoint','source_hashes')},ensure_ascii=False,indent=2))
for r in rows:
    if r['verification_problems'] or r['missing_ms'] or r['schema_errors']:
        print(r['key'], 'missing_ms=',r['missing_ms'],'gate=',r['visual_gate_passed'],'problems=',str(r['verification_problems'])[:250])
