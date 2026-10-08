"""Refresh pending facts from current local manifest/checkpoint; no HTTP calls."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import batchlib as B
import service_audit as A

pending=B.read_json(B.BATCH_ROOT/'pending-work.json',{})
state=B.read_json(B.CHECKPOINT,{})
manifest=A.build_manifest()
B.atomic_write_json(B.BATCH_ROOT/'service-index-manifest.json',manifest)
pending['generated_at']=B.now_iso()
pending['plan']='../SESSION_CONTINUATION_PLAN.md'
pending['network_resume_required']=state.get('needs_user_resume',False)
pending['stop']={k:state.get(k) for k in ('current_paper','stop_reason','stopped_at','stop_detail')}
pending['service_conflicts']=[r for r in manifest['entries'] if r['comparison']=='different']
pending['needs_visual_reverification']=[r for r in manifest['entries'] if not r['visual_gate_passed']]
pending['local_visual_verified_service_pending']=[r['key'] for r in manifest['entries']
    if r['visual_gate_passed'] and r['comparison']!='identical']
pending['delegation']={'model':'gpt-6-luna','reasoning_effort':'max',
 'user_request':'解析派子agent，模型选择gpt-6luna-max',
 'current_papers':['0413/2026/Jun/11','0509/2026/Jun/11','9715/2023/Nov/21'],
 'rule':'agents write only owned local indexes/images/work records; root merges shared state; no upstream/import/delete'}
B.atomic_write_json(B.BATCH_ROOT/'pending-work.json',pending)
print(f"visual_pending={len(pending['needs_visual_reverification'])}; local_visual_done_service_pending={pending['local_visual_verified_service_pending']}; network_stopped={pending['network_resume_required']}")
