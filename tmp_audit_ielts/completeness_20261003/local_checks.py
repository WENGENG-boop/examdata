import json, hashlib, pathlib, urllib.request, time, runpy
import pymupdf
base=pathlib.Path(__file__).resolve().parent
root=base.parent.parent
result={'pdfs':[],'gateway':[]}
for book in range(1,21):
 p=root/'tmp_audit_ielts'/'downloads'/f'book_{book}.pdf'
 if p.exists():
  d=pymupdf.open(p)
  result['pdfs'].append({'book':book,'path':str(p),'pages':len(d),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
m=runpy.run_path(str(root/'tmp_audit_ielts'/'official_pdf_cmp_v3.py'),run_name='audit_only')
result['comparator']={text:m['match_one'](text,'E') for text in ['read research methods','xyz qqq']}
for endpoint in ['info','listening/1/1','listening-audio/21/1','pdf/20','reading/19/1?passage=3']:
 start=time.time()
 try:
  with urllib.request.urlopen('http://127.0.0.1:8000/api/v1/ielts/'+endpoint,timeout=25) as response:
   payload=json.load(response)
   filename='gateway-'+endpoint.split('?')[0].replace('/','-')+'.json'
   (base/filename).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
   result['gateway'].append({'endpoint':endpoint,'status':response.status,'seconds':round(time.time()-start,2),'ok':payload.get('ok'),'error':payload.get('error'),'evidence':filename})
 except Exception as exc:
  result['gateway'].append({'endpoint':endpoint,'error':str(exc),'seconds':round(time.time()-start,2)})
(base/'local-checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'pdf_count':len(result['pdfs']),'comparator':result['comparator'],'gateway':result['gateway']},ensure_ascii=False,indent=2))
