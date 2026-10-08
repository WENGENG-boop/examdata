import json, sys

WIRE = r"C:/Users/weo/.kimi-code/sessions/wd_api_8f9bde7994a5/session_08decdcf-1f0e-4c8c-b664-4c2eebc98d1c/agents/main/wire.jsonl"
lo, hi = int(sys.argv[1]), int(sys.argv[2])

with open(WIRE, encoding="utf-8") as fh:
    for i, line in enumerate(fh, 1):
        if i < lo or i > hi:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        t = rec.get("type")
        ev = rec.get("event", {}) if isinstance(rec.get("event"), dict) else {}
        et = ev.get("type", "")
        if t == "context.append_loop_event" and et == "tool.call":
            args = ev.get("args") or {}
            op = args.get("operation", "") if isinstance(args, dict) else ""
            extra = ""
            if op == "tab.navigate":
                extra = str(args.get("url", ""))[-70:]
            elif op == "page.visual.scroll":
                extra = "dy={}".format(args.get("deltaY"))
            elif op == "tab.set_device_mode":
                extra = json.dumps(args.get("device", {}), ensure_ascii=False)
            print(i, "CALL", ev.get("name", "")[-30:], op, extra)
        elif t == "context.append_loop_event" and et == "tool.result":
            out = ""
            r = ev.get("result", {})
            if isinstance(r, dict):
                out = str(r.get("output", r))[:400]
            else:
                out = str(r)[:400]
            print(i, "RESULT", out.replace("\n", " ")[:380])
        elif t == "context.append_loop_event" and et == "content.part":
            part = ev.get("part", {})
            if part.get("type") == "text":
                print(i, "TEXT", str(part.get("text", ""))[:200].replace("\n", " "))
