import os, json, datetime

BATCH = r"C:\Users\weo\Desktop\api\cie-location-batch"
CKPT = os.path.join(BATCH, "checkpoint.json")
ERRORS = os.path.join(BATCH, "errors.jsonl")

now = datetime.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")

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
    "source": "用户 2026-10-05 消息「继续」（08:29 停机后的第二次续跑授权）——执行顺序：1 探针 0472/2026/Jun/41 → 2 Phase B 43+1 卷重验 → 3 Phase C 13,734 卷主流程",
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
    "source": new_resume["source"],
    "previous_stop": prev_stop,
}
with open(ERRORS, "a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")

print(json.dumps({"checkpoint_updated": True, "needs_user_resume": False,
                  "stage": "resuming", "at": now}, ensure_ascii=False))
