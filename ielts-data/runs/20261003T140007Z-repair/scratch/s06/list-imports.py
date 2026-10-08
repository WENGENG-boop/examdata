# list-imports.py — 列出 pdf store 全部导入记录
import glob, json, os

for f in sorted(glob.glob("ielts-data/derived/pdf/*/*/provenance-*.json")):
    m = json.load(open(f, encoding="utf-8"))
    rel = f.replace("ielts-data/derived/pdf/", "").replace("\\", "/")
    print(f"{rel} | book={m.get('book')} | pages={m.get('returned_pages')} | imported={str(m.get('imported_at',''))[:19]} | assets={len(m.get('assets',[]))} | missing={m.get('missing_pages')}/{m.get('missing_assets')}")
