"""Combined dump: Q4/Q6 family entries for 2026 papers + verification failure records for all 4 vols."""
import json
import os
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
os.chdir(BR)

print("############ INDEX DUMPS ############")
for name in ["2026-Jun-21", "2026-Jun-22"]:
    f = BR / "indexes" / "0472" / name / "cie-index.json"
    data = json.loads(f.read_bytes().decode("utf-8"))
    print(f"\n===== {name} =====")
    for q in data.get("questions") or []:
        qid = str(q.get("question"))
        if qid == "4" or qid.startswith("4(") or qid == "6" or qid.startswith("6("):
            qp = q.get("qp") or []
            ms = q.get("ms") or []
            reg = "; ".join(f"p{r['page']}:{r['bbox']}" for r in qp[:3])
            msr = "; ".join(f"p{r['page']}:{r['bbox']}" for r in ms[:2])
            text = (q.get("text") or "").replace("\n", " ")[:58]
            print(f"  {qid!r} par={q.get('parent')!r} unc={q.get('uncertain')}")
            print(f"     qp={reg} | ms={msr}")
            print(f"     {text!r}")

print("\n############ VERIFICATION RECORDS ############")
VF = BR / "verification.jsonl"
records = []
for line in VF.read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if not line:
        continue
    try:
        records.append(json.loads(line))
    except json.JSONDecodeError:
        pass

for key in ["0472/2025/Jun/21", "0472/2025/Jun/22", "0472/2026/Jun/21", "0472/2026/Jun/22"]:
    sub = [r for r in records if r.get("key") == key
           and r.get("stage") != "verification_correction"
           and r.get("kind") != "verification_correction"]
    manual = [r for r in sub if r.get("method") == "browser_visual_snapshot"]
    # latest per (question, role, page, bbox)
    latest = {}
    for r in sub:
        rk = (str(r.get("question")), str(r.get("role")), r.get("page"),
              tuple(round(float(v), 2) for v in (r.get("bbox") or [])))
        prev = latest.get(rk)
        if prev is None or str(prev.get("checked_at") or "") <= str(r.get("checked_at") or ""):
            latest[rk] = r
    failed = [(k, v) for k, v in latest.items() if v.get("issues") != []]
    print(f"\n== {key}: records={len(sub)} manual={len(manual)} latest_regions={len(latest)} failed={len(failed)}")
    for (qid, role, page, bbox), r in sorted(failed):
        print(f"   FAIL {qid}/{role}/p{page} bbox={list(bbox)}")
        print(f"        issues={json.dumps(r.get('issues'), ensure_ascii=False)[:200]}")
        print(f"        method={r.get('method')} checked_at={r.get('checked_at')}")
    if manual:
        print(f"   manual records:")
        for r in manual[:10]:
            print(f"     {r.get('question')}/{r.get('role')}/p{r.get('page')} bbox={r.get('bbox')} issues={json.dumps(r.get('issues'), ensure_ascii=False)[:80]}")
