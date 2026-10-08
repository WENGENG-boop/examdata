"""Current local PDF identity evidence plus explicitly historical download logs."""
import hashlib,json,re,time
from pathlib import Path
import fitz
root=Path(__file__).resolve().parent
ptrs={r['book']:r for r in json.loads((root/'lfs_pointers.json').read_text(encoding='utf-8'))}
history={}
for name in ('download_log.tsv','download_log_full.tsv'):
    for line in (root/'downloads'/name).read_text(encoding='utf-8').splitlines():
        match=re.search(r'book=(\d+)',line)
        if match:history[int(match[1])]=line
t0=time.perf_counter();rows=[]
for book in range(1,21):
    path=root/'downloads'/f'book_{book}.pdf'
    sha=hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
    with fitz.open(path) as doc:pages=len(doc)
    rows.append({'book':book,'path':str(path),'bytes':path.stat().st_size,'magic':path.open('rb').read(5).decode('ascii'),
      'sha256':sha,'historical_lfs_oid':ptrs[book]['oid'],'historical_pointer_bytes':ptrs[book]['ptrBytes'],
      'sha_matches_historical_oid':sha==ptrs[book]['oid'],'pages':pages,
      'scope':'Test1分册' if book==20 else '文件内容尚未逐页证明整本完整',
      'historical_download_log':history.get(book),'content_length':None})
out={'kind':'offline_current_files_vs_historical_lfs_pointers','fresh_download':False,'http_requests':0,
 'elapsed_local_seconds':round(time.perf_counter()-t0,3),'total_bytes':sum(r['bytes'] for r in rows),
 'all_sha_match':all(r['sha_matches_historical_oid'] for r in rows),'files':rows}
(root/'continuation_pdf_evidence.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k!='files'},ensure_ascii=False))
