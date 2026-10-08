#!/usr/bin/env bash
# 统一接口 E2E 实测（服务：http://127.0.0.1:8763，数据目录 .pytest_cache/callable-api）
# 运行：bash e2e_run.sh
set -u
B=http://127.0.0.1:8763/api/v1
OUT=/tmp/e2e; mkdir -p "$OUT"; cd "$OUT"
PY=/c/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe
export PYTHONIOENCODING=utf-8

echo '== 0 openapi 路由清单'
curl -s -o openapi.json -w 'HTTP %{http_code}\n' http://127.0.0.1:8763/openapi.json
$PY -c "import json;d=json.load(open('openapi.json',encoding='utf-8'));print(chr(10).join(sorted(d['paths'])))"

echo; echo '== 1 materials 列表'
curl -s -o list.json -w 'HTTP %{http_code} size=%{size_download}\n' "$B/materials"
$PY -c "
import json
d=json.load(open('list.json',encoding='utf-8'))
print('count=',d['count'],'schema=',d['schema_version'])
for it in d['items']: print(' -',it['id'],'|',it.get('board'),'|',it.get('kind'))
print('dynamic_endpoints=',d.get('dynamic_endpoints'))
"

echo; echo '== 2 MF19 content（静态快照对照 c075388e...）'
curl -s -D h_mf19.txt -o mf19.pdf -w 'HTTP %{http_code} size=%{size_download}\n' "$B/materials/cie-mf19-formulae-and-statistical-tables/content"
sha256sum mf19.pdf
grep -i '^x-material\|^content-disposition\|^content-length' h_mf19.txt

echo; echo '== 3 周期表 content（预期 422 + dynamic_endpoint）'
curl -s -o pt.json -w 'HTTP %{http_code}\n' "$B/materials/cie-periodic-table/content"
cat pt.json; echo

echo; echo '== 4 in-paper 清单：0500 2024 Jun role=in'
curl -s -o inp_list.json -w 'HTTP %{http_code}\n' "$B/materials/cie/in-paper?subject=0500&year=2024&season=Jun&role=in"
$PY -c "
import json;d=json.load(open('inp_list.json',encoding='utf-8'))
print('documents=',d['counts']['documents'])
for doc in d['documents']: print(' -',doc['name'],'| paper=',doc.get('paper'))
print('source=',d.get('source'))
"

echo; echo '== 5 in-paper 下载 0500/11（对照 7d49097c...）'
curl -s -D h_0500.txt -o in0500.pdf -w 'HTTP %{http_code} size=%{size_download}\n' "$B/materials/cie/in-paper?subject=0500&year=2024&season=Jun&paper=11&role=in&download=true"
sha256sum in0500.pdf
grep -i '^x-material\|^content-disposition' h_0500.txt

echo; echo '== 6 edexcel 化学数据册 content（对照 a372a93d...）'
curl -s -D h_edx.txt -o edx.pdf -w 'HTTP %{http_code} size=%{size_download}\n' "$B/materials/edexcel-ial-chemistry-data-booklet/content"
sha256sum edx.pdf
grep -i '^x-material' h_edx.txt

echo; echo '== 7 timetable/seasons'
curl -s -o seasons.json -w 'HTTP %{http_code}\n' "$B/timetable/seasons"
$PY -c "
import json;d=json.load(open('seasons.json',encoding='utf-8'))
print('totals=',d.get('totals'))
ks=[s['key'] for s in d['seasons']]; print('seasons n=',len(ks),'range',ks[0],'...',ks[-1])
print('unobtainable n=',len(d['unobtainable']),[u['key'] for u in d['unobtainable']])
"

echo; echo '== 8 timetable 2026 Nov subject=9709'
curl -s -o tt.json -w 'HTTP %{http_code}\n' "$B/timetable?year=2026&season=Nov&subject=9709"
$PY -c "
import json;d=json.load(open('tt.json',encoding='utf-8'))
print('key=',d['key'],'total=',d['total'],'count=',d['count'])
e=d['events'][0] if d['events'] else None
print('first=',json.dumps(e,ensure_ascii=False) if e else None)
print('source=',{k:d['source'].get(k) for k in ('file','sha256','pages')})
"

echo; echo '== 9 windows 2026 Nov'
curl -s -o win.json -w 'HTTP %{http_code}\n' "$B/timetable/windows?year=2026&season=Nov"
$PY -c "
import json;d=json.load(open('win.json',encoding='utf-8'));print('count=',d['count'])
w=d['date_windows'][0] if d['date_windows'] else None;print('first=',json.dumps(w,ensure_ascii=False) if w else None)
"

echo; echo '== 10 不可得考季 404 证据 / 未收录 422'
read -r UY US < <($PY -c "import json;d=json.load(open('seasons.json',encoding='utf-8'));u=d['unobtainable'][0];print(u['year'],u['season'])")
curl -s -o un.json -w "timetable $UY $US HTTP %{http_code}\n" "$B/timetable?year=$UY&season=$US"
head -c 400 un.json; echo
curl -s -o bad.json -w 'timetable 2001 Jun HTTP %{http_code}\n' "$B/timetable?year=2001&season=Jun"
head -c 200 bad.json; echo

echo; echo '== 11 旧端点抽查'
curl -s -o boards.json -w 'boards HTTP %{http_code} size=%{size_download}\n' "$B/boards"
head -c 200 boards.json; echo
echo 'DONE'
