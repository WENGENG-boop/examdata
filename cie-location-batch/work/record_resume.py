"""记录用户续跑授权：checkpoint（原子）+ errors.jsonl（追加）。

用法: python record_resume.py "<source 描述文本>"
"""
import os, sys, json, datetime

BATCH = r"C:\Users\weo\Desktop\api\cie-location-batch"
CKPT = os.path.join(BATCH, "checkpoint.json")
ERRORS = os.path.join(BATCH, "errors.jsonl")

now = datetime.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
source = sys.argv[1] if len(sys.argv) > 1 else ""

with open(CKPT, "r", encoding="utf-8") as f:
    ck = json.load(f)

prev_stop = {
    "current_paper": ck.get("current_paper"),
    "stage": ck.get("stage"),
    "stop_reason": ck.get("stop_reason"),
    "stopped_at": ck.get("stopped_at"),
    "stop_detail": ck.get("stop_detail"),
}
old_resume = ck.get("network_resume")
new_resume = {
    "kind": "user_authorized_network_resume",
    "at": now,
    "source": source,
    "previous_stop": prev_stop,
}

ck["network_resume_previous"] = old_resume
ck["network_resume"] = new_resume
ck["needs_user_resume"] = False
ck["stage"] = "resuming"
ck["updated_at"] = now

tmp = CKPT + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(ck, f, ensure_ascii=False, indent=2)
    f.write("\n")
os.replace(tmp, CKPT)

rec = {
    "kind": "user_authorized_network_resume",
    "at": now,
    "source": source,
    "previous_stop": prev_stop,
}
with open(ERRORS, "a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")

print(json.dumps({"ok": True, "at": now, "needs_user_resume": False,
                  "stage": "resuming"}, ensure_ascii=False))
