"""Root review guard for agents' owned-paper evidence, without network/import.

Reject foreign/stale regions or images, and preserve genuine failed/incomplete
observations. The gate derives pass/fail from records rather than agent claims.
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import batchlib as B
import cleanup_paper as C
import import_index as I
import validate_index as V

def merge(key, source, origin='gpt-6-luna/max delegated parsing; root identity/hash/geometry guard'):
    path=I.index_path(key)
    data=B.read_json(path,{})
    subject,year,season,paper=key.split('/')
    assert data['identity']=={'subject':subject,'year':int(year),'season':season,'paper':paper}
    qp,ms=I.locate_pdf(key,'qp'),I.locate_pdf(key,'ms')
    report=V.validate(path,qp=qp,ms=ms)
    assert not report['errors'],report['errors']
    records=B.read_json(Path(source),None)
    assert isinstance(records,list) and records,'empty or non-array evidence'
    current=C.index_regions(key)
    index_sha=B.sha256_file(path)
    checked=[]
    for row in records:
        assert row.get('key')==key,'foreign key'
        assert C.record_key(row) in current,'stale or foreign region'
        assert row.get('index_sha256')==index_sha,'evidence belongs to another index'
        assert row.get('method')=='local_image_visual','not an actual image observation'
        assert isinstance(row.get('issues'),list),'missing issues'
        assert isinstance(row.get('checks',{}).get('observed'),str) and row['checks']['observed'].strip(),'missing observation'
        assert row.get('checked_at'),'missing timestamp'
        image=Path(row['image']).resolve()
        owner=B.BATCH_ROOT/'tmp'/subject/f'{year}-{season}-{paper}'
        assert C.unsafe_component(owner.resolve(),image) is None,'foreign or reparse image'
        assert image.is_file() and B.sha256_file(image)==row['image_sha256'],'missing or changed image'
        checked.append(row)
    covered={C.record_key(row) for row in checked}
    missing=set(current)-covered
    # Keep partial evidence; report the uncovered regions honestly.
    merge_path=B.WORK/f'{subject}-{year}-{season}-{paper}-agent-merge.json'
    previous=B.read_json(merge_path,{})
    if previous.get('index_sha256')==index_sha and previous.get('source_sha256')==B.sha256_file(Path(source)):
        print('Already merged unchanged evidence:',key)
        return
    for row in checked:
        B.append_jsonl(B.VERIFICATION,{**row,'review_origin':origin})
    problems,stats=C.verification_state(key,[q['question'] for q in data['questions']])
    out={'key':key,'at':B.now_iso(),'index_sha256':index_sha,'source_sha256':B.sha256_file(Path(source)),
         'validation':report,'records_merged':len(checked),'regions_without_agent_record':len(missing),
         'visual_problems':problems,'visual_stats':stats,'local_visual_verified':not problems,
         'service_conflict_retained':True,'originals_retained':True}
    B.atomic_write_json(merge_path,out)
    papers=B.read_json(B.PAPERS,{})
    papers[key].update(question_count=len(data['questions']),local_visual_verified=not problems,
      local_visual_verified_at=out['at'],local_visual_report=str(merge_path),
      local_visual_problems=problems)
    B.atomic_write_json(B.PAPERS,papers)
    B.append_jsonl(B.ERRORS,{'kind':'agent_visual_review_merged',**out})
    print(json.dumps({k:out[k] for k in ('key','records_merged','regions_without_agent_record','local_visual_verified','visual_problems')},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('key');parser.add_argument('source')
    parser.add_argument('--origin',default='gpt-6-luna/max delegated parsing; root identity/hash/geometry guard')
    args=parser.parse_args();merge(args.key,args.source,args.origin)
