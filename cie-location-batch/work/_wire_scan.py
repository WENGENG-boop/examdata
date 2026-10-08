import json, sys

WIRE = r"C:/Users/weo/.kimi-code/sessions/wd_api_8f9bde7994a5/session_08decdcf-1f0e-4c8c-b664-4c2eebc98d1c/agents/main/wire.jsonl"

calls = []
with open(WIRE, encoding="utf-8") as fh:
    for i, line in enumerate(fh, 1):
        if '"tool.call"' not in line or "desktop_browser" not in line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        ev = rec.get("event", {})
        if ev.get("type") != "tool.call":
            continue
        name = ev.get("name", "")
        if "desktop_browser" not in name:
            continue
        args = ev.get("args") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        op = args.get("operation", "")
        if not op:
            op = "RAW:" + json.dumps(args, ensure_ascii=False)[:60]
        info = ""
        if op == "tab.navigate":
            info = args.get("url", "")
        elif op == "page.visual.scroll":
            info = "dx={} dy={} x={} y={}".format(args.get("deltaX"), args.get("deltaY"), args.get("x"), args.get("y"))
        elif op in ("browser.activate_tab", "browser.switch_tab"):
            info = str(args.get("tabId"))
        elif op == "page.visual.snapshot":
            info = "snap"
        calls.append((i, op, info))

# print last 120
for i, op, info in calls[-120:]:
    print(i, op, info[:110])
print("TOTAL browser calls:", len(calls))
