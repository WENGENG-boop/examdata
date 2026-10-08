"""汇总 63 卷在 papers.json / work/state.json 里的流程状态（只读）。"""
import json
import os

B = r"C:/Users/weo/Desktop/api/cie-location-batch"
keys = [l.strip() for l in open(os.path.join(B, "work/coordinate-audit-2026-10-05/_all_keys.txt"),
                                encoding="utf-8") if l.strip()]
pj = json.load(open(os.path.join(B, "papers.json"), encoding="utf-8"))
st = json.load(open(os.path.join(B, "work/state.json"), encoding="utf-8"))

print(f"{'key':24} {'stage(pj)':18} {'stage(st)':18} imp rb conflict")
for k in keys:
    a = pj.get(k, {})
    b = st.get(k, {})
    print(f"{k:24} {str(a.get('stage')):18} {str(b.get('stage')):18} "
          f"{str(a.get('import_succeeded')):5} {str(a.get('readback_verified')):5} "
          f"{str(a.get('conflict'))[:30]}")
