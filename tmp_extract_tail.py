import json

WIRE = "C:/Users/weo/.kimi-code/sessions/wd_api_8f9bde7994a5/session_d883c71d-510f-483d-9810-d178a60ee98c/agents/main/wire.jsonl"

out = []
with open(WIRE, encoding="utf-8") as f:
    for lineno, line in enumerate(f, 1):
        if lineno < 30900:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        t = rec.get("type")
        ev = rec.get("event") or {}
        if t == "context.append_loop_event":
            etype = ev.get("type")
            if etype == "content.part":
                part = ev.get("part") or {}
                if part.get("type") in ("text", "think"):
                    txt = part.get("text") or ""
                    out.append(f"\n===== L{lineno} [{part.get('type')}] len={len(txt)}\n{txt}")
            elif etype == "tool.call":
                name = ev.get("name") or ev.get("tool") or "?"
                out.append(f"\n----- L{lineno} TOOLCALL {name}: {json.dumps(ev.get('arguments') or ev.get('args') or {}, ensure_ascii=False)[:600]}")
            elif etype == "tool.result":
                out.append(f"\n----- L{lineno} TOOLRESULT: {json.dumps(ev.get('result') or {}, ensure_ascii=False)[:600]}")
        elif t == "context.append_message":
            msg = rec.get("message") or {}
            out.append(f"\n##### L{lineno} USERMSG: {json.dumps(msg, ensure_ascii=False)[:2000]}")

with open("examdata/tmp_wire_tail.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("chars:", sum(len(x) for x in out), "blocks:", len(out))
