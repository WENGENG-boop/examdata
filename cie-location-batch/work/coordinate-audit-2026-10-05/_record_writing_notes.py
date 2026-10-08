import json, glob, os
out = {"generated_at": "2026-10-06", "note": "补建 ms 区域前后 notes/uncertain 对照（保留历史记录）", "papers": []}
for k in ["8238-2025-Jun-32","8238-2025-Nov-31","8238-2025-Nov-32","8238-2025-Nov-33","8238-2026-Jun-32"]:
    key = k.replace("-", "/", 1).replace("-", "/", 1).replace("-", "/", 1)
    b = sorted(glob.glob(f"index-backups/{k}-before-writing-ms-*.json"))[-1]
    idxp = f"../../../cie-location-batch/indexes/8238/{k.split('-',1)[1]}/cie-index.json"
    old = json.load(open(b, encoding="utf-8")); new = json.load(open(idxp, encoding="utf-8"))
    rec = {"key": key, "backup": b.replace("\\","/"), "questions": []}
    for qo, qn in zip(old["questions"], new["questions"]):
        rec["questions"].append({
            "question": qo["question"],
            "uncertain_before": qo.get("uncertain"), "uncertain_after": qn.get("uncertain"),
            "ms_before": qo.get("ms"), "ms_after": qn.get("ms"),
            "notes_before": qo.get("notes"), "notes_after": qn.get("notes")})
    out["papers"].append(rec)
p = "deliverables/writing-ms-notes-before-after.json"
json.dump(out, open(p, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
print("wrote", p)
for rec in out["papers"]:
    q = rec["questions"][0]
    print(rec["key"], "uncertain", q["uncertain_before"], "->", q["uncertain_after"], "| ms", len(q["ms_before"]), "->", len(q["ms_after"]))
