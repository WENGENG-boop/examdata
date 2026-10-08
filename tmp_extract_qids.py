import json, re

WIRE = "C:/Users/weo/.kimi-code/sessions/wd_api_8f9bde7994a5/session_d883c71d-510f-483d-9810-d178a60ee98c/agents/main/wire.jsonl"

qids = [61416, 61516, 61770, 61771, 61790, 61319, 61322, 61328, 61329, 61423, 61608, 61617, 61389, 61392, 61250, 61240, 61252]

out = []
with open(WIRE, encoding="utf-8") as f:
    lines = f.readlines()

for q in qids:
    qs = str(q)
    wins = []
    for n, line in enumerate(lines, 1):
        if n < 29700 or qs not in line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        ev = r.get("event") or {}
        if ev.get("type") != "content.part":
            continue
        part = ev.get("part") or {}
        txt = part.get("text") or part.get("think") or ""
        if not txt:
            continue
        for m in re.finditer(re.escape(qs), txt):
            s = max(0, m.start() - 220)
            e = min(len(txt), m.end() + 220)
            seg = txt[s:e].replace("\n", " ")
            if re.search(r"WPS\d\d", seg) or "Section" in seg or "section" in seg:
                wins.append((n, seg))
    # dedupe by (line, rough seg)
    seen = set()
    uniq = []
    for n, seg in wins:
        key = (n, seg[:80])
        if key in seen:
            continue
        seen.add(key)
        uniq.append((n, seg))
    out.append(f"\n########## QID {q} — {len(uniq)} windows (last 7 shown) ##########")
    for n, seg in uniq[-7:]:
        out.append(f"  [L{n}] {seg}")

with open("examdata/tmp_wire_qids.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("chars:", sum(len(x) for x in out))
