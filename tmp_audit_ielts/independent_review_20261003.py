import json, time, hashlib, urllib.request, urllib.error
from pathlib import Path

root = Path('C:/Users/weo/Desktop/api')
out = root / 'tmp_audit_ielts/independent_review_20261003'
out.mkdir(exist_ok=True)
results = []
paths = ['/api/v1/boards', '/api/v1/search?board=cie&limit=2', '/api/v1/ielts/info', '/api/v1/paper?board=edexcel&subject=Economics&year=2024&season=June&paper=wec11-01', '/api/v1/ielts/reading/19/1', '/api/v1/ielts/aggregate/21/1']
for i, path in enumerate(paths):
    start = time.monotonic()
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000' + path, timeout=180) as r:
            status, body = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read()
    except Exception as e:
        results.append({'path': path, 'error': str(e)})
        print(results[-1], flush=True)
        break
    (out / f'endpoint_{i}.json').write_bytes(body)
    try:
        data = json.loads(body)
    except ValueError:
        data = {'non_json_body': body.decode('utf-8', errors='replace')[:500]}
    item = {'path': path, 'status': status, 'seconds': round(time.monotonic()-start, 2), 'bytes': len(body), 'ok': data.get('ok'), 'total': data.get('total'), 'score': data.get('score'), 'counts': data.get('counts'), 'question_count': data.get('question_count'), 'warnings': data.get('warnings')}
    results.append(item)
    if 'non_json_body' in data:
        item['non_json_body'] = data['non_json_body']
    print(json.dumps(item, ensure_ascii=False), flush=True)
    if status in (403,404,409,502):
        break
(out / 'endpoints_summary.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
src = Path('C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api')
dst = root / 'ielts-api'
comparison = {'src_exists': src.exists(), 'different': [], 'src_only': [], 'dst_only': []}
if src.exists():
    a = {p.relative_to(src).as_posix(): p for p in src.rglob('*') if p.is_file() and '.git' not in p.parts}
    b = {p.relative_to(dst).as_posix(): p for p in dst.rglob('*') if p.is_file() and '.git' not in p.parts}
    comparison['src_only'] = sorted(a.keys()-b.keys())
    comparison['dst_only'] = sorted(b.keys()-a.keys())
    comparison['different'] = sorted(k for k in a.keys() & b.keys() if hashlib.sha256(a[k].read_bytes()).digest() != hashlib.sha256(b[k].read_bytes()).digest())
print(json.dumps(comparison, ensure_ascii=False), flush=True)
(out / 'directory_comparison.json').write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding='utf-8')
pointers = json.loads((root/'tmp_audit_ielts/lfs_pointers.json').read_text(encoding='utf-8'))
checks = []
for p in pointers:
    f = root / f"tmp_audit_ielts/downloads/book_{p['book']}.pdf"
    body = f.read_bytes()
    checks.append({'book': p['book'], 'bytes': len(body), 'pass': len(body)==p['size'] and hashlib.sha256(body).hexdigest()==p['oid'] and body.startswith(b'%PDF-')})
print('LOCAL_PDF', len(checks), sum(c['pass'] for c in checks), sum(c['bytes'] for c in checks), flush=True)
(out / 'local_pdf_hashes.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
