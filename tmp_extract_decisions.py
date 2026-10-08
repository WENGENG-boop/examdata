import json, re, sys

WIRE = "C:/Users/weo/.kimi-code/sessions/wd_api_8f9bde7994a5/session_d883c71d-510f-483d-9810-d178a60ee98c/agents/main/wire.jsonl"

# The 55 QIDs of batch-001
qids = list(range(61225, 61811))  # placeholder, will filter

# Load batch file to get actual QIDs
batch = []
with open("examdata/.data/tagging/review-export/ial-psychology/batches/batch-001.jsonl", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            batch.append(json.loads(line))
qid_set = {str(b["question_id"]) for b in batch}
print("batch qids:", len(qid_set), min(qid_set), max(qid_set))

out = []
with open(WIRE, encoding="utf-8") as f:
    for lineno, line in enumerate(f, 1):
        if lineno < 29700:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        ev = rec.get("event") or {}
        if ev.get("type") != "content.part":
            continue
        part = ev.get("part") or {}
        if part.get("type") not in ("text", "think"):
            continue
        txt = part.get("text") or ""
        if not txt:
            continue
        # find QID mentions
        hits = []
        for q in qid_set:
            for m in re.finditer(re.escape(q), txt):
                hits.append((m.start(), q))
        if not hits:
            continue
        hits.sort()
        # merge windows
        merged = []
        for pos, q in hits:
            s, e = max(0, pos-350), min(len(txt), pos+350)
            if merged and s <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e), merged[-1][2] + "|" + q)
            else:
                merged.append((s, e, q))
        for s, e, q in merged:
            seg = txt[s:e].replace("\n", " ")
            if re.search(r"WPS\d\d", seg) or "keep" in seg.lower() or "change" in seg.lower():
                out.append(f"=== L{lineno} [{part.get('type')}] q={q}\n{seg}\n")

with open("examdata/tmp_psy001_wire_extract.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("segments:", len(out))
