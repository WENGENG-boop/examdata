"""S16 逐文件同步：主副本 ielts-api -> 另一副本（备份 + 冲突保护 + 校验）。

用法：
  python sync-other-copy.py --dry      # 只生成计划（changed-files.json）
  python sync-other-copy.py --execute  # 执行 add/overwrite 并逐文件校验
"""
import hashlib, json, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

MAIN = Path(r"C:\Users\weo\Desktop\api\ielts-api")
OTHER = Path(r"C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api")
RUN = Path(r"C:\Users\weo\Desktop\api\ielts-data\runs\20261003T140007Z-repair")
BACKUP = RUN / "backup" / "other-copy-2026-10-05"
OUT = RUN / "changed-files.json"
SCRATCH = RUN / "scratch"

mode = "--execute" if "--execute" in sys.argv else "--dry"

main_files = json.load(open(SCRATCH / "main-files.json", encoding="utf-8"))["files"]
other_files = json.load(open(SCRATCH / "other-files.json", encoding="utf-8"))["files"]
baseline = json.load(open(RUN / "baseline.json", encoding="utf-8"))
src_map = baseline["shared_files_sha256"]["src_map"]  # 另一副本 S01 基线
dst_map = baseline["shared_files_sha256"]["dst_map"]  # 主副本 S01 基线

def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

changes = []
for rel in sorted(main_files):
    m = main_files[rel]
    o = other_files.get(rel)
    action, status, other_before = None, None, None
    if o is None:
        action, status = "add", "planned"
    elif o.get("sha256") == m.get("sha256"):
        continue  # 已一致，不记录
    else:
        other_before = o.get("sha256")
        base_other = src_map.get(rel)
        if base_other is not None and other_before == base_other:
            action, status = "overwrite", "planned"
        elif base_other is None and dst_map.get(rel) == m.get("sha256"):
            action, status = "conflict", "main_unchanged_since_baseline_but_other_differs"
        elif base_other is None:
            action, status = "conflict", "no_baseline_record"
        else:
            action, status = "conflict", "other_changed_since_baseline"
    changes.append({
        "rel": rel, "action": action, "status": status,
        "main_sha256": m.get("sha256"), "main_bytes": m.get("size"),
        "other_before": other_before, "other_after": None,
        "baseline_other": src_map.get(rel), "baseline_main": dst_map.get(rel),
    })

executed = {"add": 0, "overwrite": 0, "conflict": 0, "failed": 0}
if mode == "--execute":
    for c in changes:
        if c["action"] not in ("add", "overwrite"):
            continue
        rel = c["rel"]
        src = MAIN / rel
        dst = OTHER / rel
        try:
            if c["action"] == "overwrite":
                bk = BACKUP / rel
                bk.parent.mkdir(parents=True, exist_ok=True)
                if not bk.exists():
                    shutil.copy2(dst, bk)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            after = sha256_file(dst)
            c["other_after"] = after
            if after == c["main_sha256"]:
                c["status"] = "done"
                executed[c["action"]] += 1
            else:
                c["status"] = "verify_failed"
                executed["failed"] += 1
        except Exception as e:
            c["status"] = "error: " + str(e)
            executed["failed"] += 1

other_only = sorted(set(other_files) - set(main_files))
doc = {
    "run_id": "20261003T140007Z-repair",
    "stage": "S16",
    "mode": mode,
    "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "main_dir": str(MAIN),
    "other_dir": str(OTHER),
    "backup_dir": str(BACKUP) if mode == "--execute" else None,
    "counts": {
        "main_files": len(main_files), "other_files": len(other_files),
        "to_add": sum(1 for c in changes if c["action"] == "add"),
        "to_overwrite": sum(1 for c in changes if c["action"] == "overwrite"),
        "conflicts": sum(1 for c in changes if c["action"] == "conflict"),
        "executed": executed,
    },
    "other_only_untouched": other_only,
    "changes": changes,
}
OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
print("mode:", mode)
print("planned:", doc["counts"])
for c in changes:
    if c["action"] == "conflict" or str(c.get("status", "")).startswith(("error", "verify")):
        print("  !!", c["rel"], c["status"], c.get("other_before"), c.get("main_sha256"))
