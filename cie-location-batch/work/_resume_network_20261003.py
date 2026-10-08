"""落盘 2026-10-03 用户授权联网续跑记录（先于 0472 恢复探针）。

- errors.jsonl 追加 user_authorized_network_resume
- checkpoint：network_resume 更新、旧记录移入 network_resume_previous、needs_user_resume=False
- 不改写历史日志；不动 stage（fetch_paper 会自行推进）
"""
import sys

sys.path.insert(0, 'tools')
import batchlib as B

now = B.now_iso()
ck = B.read_json(B.CHECKPOINT, {}) or {}

prev_stop = {
    "current_paper": ck.get("current_paper"),
    "stage": ck.get("stage"),
    "stop_reason": ck.get("stop_reason"),
    "stopped_at": ck.get("stopped_at"),
    "stop_detail": ck.get("stop_detail"),
}

source = ("用户 2026-10-03 消息「3」——对上一条列出的续跑执行顺序的确认"
          "（1 重试 0472 探针、2 54 卷重验、3 主流程）；"
          "先恢复 0472/2024/Jun/11 一组 QP/MS 作为上游恢复探针")

B.append_jsonl(B.ERRORS, {
    "kind": "user_authorized_network_resume",
    "at": now,
    "source": source,
    "previous_stop": prev_stop,
})

fields = {
    "network_resume": {
        "kind": "user_authorized_network_resume",
        "at": now,
        "source": source,
        "previous_stop": prev_stop,
    },
    "needs_user_resume": False,
}
old = ck.get("network_resume")
if old:
    fields["network_resume_previous"] = old
B.set_checkpoint(**fields)

print("resume recorded:", now)
print("needs_user_resume:", False)
