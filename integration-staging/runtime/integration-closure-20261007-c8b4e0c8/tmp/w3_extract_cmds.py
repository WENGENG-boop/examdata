import json, sys

WIRE = r"C:/Users/weo/.kimi-code/sessions/wd_api_8f9bde7994a5/session_6b1562f5-c2e7-428a-bf9a-72619f246c2b/agents/agent-958/wire.jsonl"
NEEDLES = ("w3_reproduce.py", "pin_recheck", "w3-ev-", "operations_ttl")
out = []
with open(WIRE, encoding="utf-8") as fh:
    for lineno, line in enumerate(fh, 1):
        if not any(n in line for n in NEEDLES):
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("type") != "context.append_loop_event":
            continue
        ev = rec.get("event", {})
        if ev.get("type") != "tool.call":
            continue
        args = ev.get("args") or {}
        cmd = args.get("command")
        if not cmd:
            continue
        out.append(f"##### line {lineno} :: {ev.get('name')}\n{cmd}\n")

with open(sys.argv[1], "w", encoding="utf-8") as fh:
    fh.write(f"total {len(out)} records\n\n")
    fh.write("\n".join(out))
print(f"records={len(out)}")
