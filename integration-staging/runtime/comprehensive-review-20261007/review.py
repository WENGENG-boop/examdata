"""Independent synthetic audit. Writes only below a new private evidence root."""
from pathlib import Path
import sys, os, json, hashlib, tempfile, subprocess
from unittest.mock import patch

WS = Path(__file__).resolve().parents[3]
RUN = WS / 'integration-staging/runtime/b07-reviewfix-20261007-774e4dad'
CAND = RUN / 'candidates/b07-operations-v2'
OUT = Path(tempfile.mkdtemp(prefix='evidence-', dir=Path(__file__).parent))
os.environ['EXAMDATA_INTEGRATION_ROOT'] = str(CAND)
sys.path.insert(0, str(CAND / 'src'))
from examdata.integration.operations import checkpoints as cp, jobs, published as pub
from examdata.integration.catalog.model import CatalogEntry
from examdata.integration.api.dataset import default_dataset
from examdata.integration.api.app import create_app
from examdata.integration.api.links import spec_for, PREFIX
from fastapi.testclient import TestClient

def tree(root, exclude):
    rows = [(p.relative_to(root).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(root.rglob('*')) if p.is_file() and p.name != exclude
            and not any(x in p.parts for x in ('__pycache__', '.pytest_cache'))]
    return {'files': len(rows), 'sha256': hashlib.sha256(''.join(a+'\0'+b+'\n' for a,b in rows).encode()).hexdigest()}

results = {'candidate_before': tree(CAND, 'B07R2_CANDIDATE_MANIFEST.json'), 'checks': {}}
checks = results['checks']

wide = OUT / 'wide'; wide.mkdir()
for i in range(40): (wide / f'{i:03}.txt').write_text('x')
real_scandir = cp.os.scandir
counts = {'n': 0}
class CountScan:
    def __init__(self, path): self.it = real_scandir(path)
    def __enter__(self): return self
    def __exit__(self, *args): self.it.close()
    def __iter__(self): return self
    def __next__(self):
        value = next(self.it); counts['n'] += 1; return value
with patch.object(cp.os, 'scandir', CountScan):
    walker = cp.iter_checkpoint_paths(wide, max_entries=1); list(walker)
checks['discovery_budget'] = {'budget': 1, 'actual_enumerated': counts['n'], 'reported_entries_seen': walker.entries_seen}

growth = OUT / 'growth'; growth.mkdir(); (growth / 'checkpoint.json').write_bytes(b'{}')
real_reader = jobs.read_checkpoint_bounded
def grow(path, **kwargs):
    Path(path).write_bytes(b'{}' + b' ' * 14)
    return real_reader(path, **kwargs)
with patch.object(jobs, 'read_checkpoint_bounded', grow):
    scan = jobs.scan_checkpoint_root(growth, max_bytes=32, max_read_bytes=8)
checks['cumulative_read_growth'] = {'budget': 8, 'actual_reported_bytes': scan.bytes_read, 'truncated': scan.truncated, 'exhausted': scan.exhausted}

secret = 'synthetic-audit-secret-only'
checks['generator_secrets'] = jobs.sanitize_tree({'fixed': secret, 'nested': [secret]}, secrets=iter([secret]))
checks['tuple_secrets_control'] = jobs.sanitize_tree({'fixed': secret, 'nested': [secret]}, secrets=(secret,))
checks['mapping_collisions_control'] = jobs.sanitize_tree({secret: 1, '<secret>': 2, '<secret>#2': 3}, secrets=(secret,))

def entry(pid='synthetic-q', **changes):
    values = dict(public_id=pid, system='cie', kind='question', identity_fields={'native_id': pid}, native_locator={'ref':pid},
                  quality_summary={'content':'complete','answer_presence':'present','answer_verification':'source_verified'},
                  evidence_labels=[])
    values.update(changes)
    return CatalogEntry(**values)
def view(entries, expected=1, **scope):
    return pub.build_published(entries, pub.ExpectedManifest(scopes=(pub.ExpectedScope(id='audit',system='cie',kind='question',expected=expected,**scope),),source_label='synthetic-audit')).to_dict()
checks['quality_claim_without_evidence'] = {'entry_validation':entry().validate(), 'coverage':view([entry()])}
checks['contradictory_answer_presence'] = view([entry(quality_summary={'content':'complete','answer_presence':'missing','answer_verification':'source_verified'})])
checks['absent_manifest_reference'] = view([entry()], partial=(pub.PartialExpectation('absent-q','required partial record'),))
checks['duplicate_public_ids'] = view([entry(),entry()], expected=2)
checks['empty_identity'] = view([entry(identity_fields={})])
checks['missing_denominator_control'] = view([entry()],expected=None)
checks['excess_count_control'] = view([entry(),entry('synthetic-q2')],expected=1)

# Static snapshot freshness through actual HTTP handlers, with a real private file change.
ops = OUT / 'operations'; ops.mkdir(); checkpoint = ops / 'checkpoint.json'
def write_checkpoint(stage, updated):
    checkpoint.write_text(json.dumps({'stage':stage,'loop_stage':'queued','current_subject':'synthetic-audit',
                                     'totals':{'done':1},'updated_at':updated}),encoding='utf8')
write_checkpoint('running','2026-10-07T01:00:00Z')
ds = default_dataset(operations_root=ops)
with TestClient(create_app(dataset=ds)) as client:
    before = client.get(PREFIX + spec_for('coverage.get').path).json()['data']['operations']
    write_checkpoint('stopped','2026-10-07T02:00:00Z')
    after = client.get(PREFIX + spec_for('coverage.get').path).json()['data']['operations']
checks['http_checkpoint_refresh'] = {'before':before, 'after':after, 'unchanged':before==after}

# Link test stays inside this new synthetic evidence root, including the target.
linkroot = OUT / 'links'; linkroot.mkdir(); target = OUT / 'synthetic-outside-configured-root.json'; target.write_text('{}')
link = linkroot / 'checkpoint.json'
try:
    link.symlink_to(target)
except OSError as exc:
    checks['checkpoint_symlink'] = {'status':'not_run','reason':type(exc).__name__, 'winerror':getattr(exc,'winerror',None)}
else:
    scan = jobs.scan_checkpoint_root(linkroot)
    checks['checkpoint_symlink'] = {'status':'executed','outside_configured_root_read':bool(scan.observations), 'observations':len(scan.observations), 'skipped':scan.skipped}

# Observe expected-manifest IO API use without supplying a huge payload.
manifest = ops / 'expected-manifest.json'
manifest.write_text(json.dumps({'schema':pub.SCHEMA,'scopes':[{'id':'audit','system':'cie','kind':'question','expected':1}]}))
original_read_text = Path.read_text; calls=[]
def track_read_text(path,*args,**kwargs):
    if path == manifest: calls.append({'method':'Path.read_text','bounded_read_argument':False})
    return original_read_text(path,*args,**kwargs)
with patch.object(Path,'read_text',track_read_text): pub.load_expected_manifest(ops)
checks['manifest_read'] = calls

env=os.environ.copy(); env['PYTHONPATH']=str(CAND/'src');env['PYTHONDONTWRITEBYTECODE']='1';env['B07R2_EXPECT_CANDIDATE_ROOT']=str(CAND);env.pop('EXAMDATA_INTEGRATION_STAGING_ROOT',None)
command=[sys.executable,'-B','-m','pytest','-c',str(RUN/'tests/pytest.ini'),str(RUN/'tests'),'-p','no:cacheprovider','--basetemp',str(OUT/'pytest-temp'),'-q']
run=subprocess.run(command,cwd=OUT,env=env,capture_output=True,text=True)
(OUT/'pytest.txt').write_text(run.stdout+run.stderr,encoding='utf8')
results['pytest']={'command':command,'cwd':str(OUT),'exit_code':run.returncode,'stdout':run.stdout}
results['module_origins']={name:str(Path(mod.__file__).resolve()) for name,mod in sys.modules.items() if name.startswith('examdata') and getattr(mod,'__file__',None)}
assert all(Path(p).is_relative_to(CAND) for p in results['module_origins'].values())
results['candidate_after']=tree(CAND,'B07R2_CANDIDATE_MANIFEST.json')
assert results['candidate_before']==results['candidate_after']
results['ledger_sha256']=hashlib.sha256((WS/'docs/integration/execution/execution-ledger.json').read_bytes()).hexdigest()
results['evidence_root']=str(OUT)
(OUT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'evidence_root':str(OUT),'candidate':results['candidate_after'],'checks':checks,'pytest_exit':run.returncode},ensure_ascii=False,indent=2))
