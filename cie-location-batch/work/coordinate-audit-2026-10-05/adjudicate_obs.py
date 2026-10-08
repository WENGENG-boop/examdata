"""把 obs-<slice>.jsonl 中经父 agent 平议判为非缺陷的 issues 归零，并留痕到旁侧日志。

原则：
  - 只在有离线/原件证据证明"非缺陷"时归零；
  - 原 issues 文本一字不改地保存在 deliverables/obs-adjudications.json；
  - 平议理由追加进该行 checks.observed（原有观察文本保留）。

用法: python adjudicate_obs.py <slice> <seq:verdict[:reason]> [...]
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REVIEW = os.path.join(HERE, "review")
DELIV = os.path.join(HERE, "deliverables")


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    slice_id = sys.argv[1]
    specs = {}
    for a in sys.argv[2:]:
        parts = a.split(":", 2)
        seq = int(parts[0])
        verdict = parts[1]
        reason = parts[2] if len(parts) > 2 else ""
        specs[seq] = (verdict, reason)

    path = os.path.join(REVIEW, f"obs-{slice_id}.jsonl")
    lines = [l for l in open(path, encoding="utf-8").read().splitlines() if l.strip()]
    out, log = [], []
    for l in lines:
        r = json.loads(l)
        s = r.get("seq")
        if s in specs and r.get("issues"):
            verdict, reason = specs[s]
            if verdict == "benign":
                orig = r["issues"]
                note = f"【父 agent 平议·非缺陷】{reason}"
                ch = r.get("checks") or {}
                ch["observed"] = (ch.get("observed") or r.get("observed") or "") + " " + note
                r["checks"] = ch
                r["issues"] = []
                r["adjudication"] = {"by": "main-agent", "verdict": "benign",
                                     "reason": reason, "original_issues": orig}
                log.append({"slice": slice_id, "seq": s, "file": r.get("file"),
                            "question": r.get("question"), "role": r.get("role"),
                            "page": r.get("page"), "bbox": r.get("bbox"),
                            "original_issues": orig, "verdict": "benign",
                            "reason": reason, "adjudicated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
        out.append(json.dumps(r, ensure_ascii=False))

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")
    os.replace(tmp, path)

    lp = os.path.join(DELIV, "obs-adjudications.json")
    cur = json.load(open(lp, encoding="utf-8")) if os.path.exists(lp) else []
    cur.extend(log)
    json.dump(cur, open(lp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{slice_id}: 平议 {len(log)} 行 -> {path}")
    for e in log:
        print("  seq", e["seq"], e["question"], e["role"], "p", e["page"], "|", e["original_issues"])
    print("留痕 ->", lp.replace("\\", "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
