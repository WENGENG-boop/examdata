"""S16: 重算 CIE/Edexcel 受保护文件与生产数据库 hash，对照 S01 基线。"""
import hashlib, json, subprocess, sys
from pathlib import Path

WS = Path(r"C:\Users\weo\Desktop\api")
RUN = WS / "ielts-data" / "runs" / "20261003T140007Z-repair"
EVID = RUN / "evidence" / "S16-protected-recheck.txt"

base = json.load(open(RUN / "protected-files-baseline.json", encoding="utf-8"))
out = []
def log(s=""):
    out.append(s)
    print(s)

def sha256_stream(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

log("S16 protected recheck")
log("baseline generated_at_utc: " + base["generated_at_utc"])
log("note: baseline 仅登记清单/SHA256/大小/mtime；数据库可能被运行中服务写入，hash 变化不能直接归咎本任务")
log()

for g in base["protected_dirs"]:
    d = WS / g["dir"]
    base_files = {f["rel"]: f for f in g["files"]}
    current = {}
    if d.exists():
        for p in sorted(d.rglob("*")):
            if p.is_file():
                rel = p.relative_to(WS).as_posix()
                current[rel] = p
    changed, missing = [], []
    for rel, f in base_files.items():
        if rel not in current:
            missing.append(rel)
            continue
        h = sha256_stream(current[rel])
        if h != f["sha256"]:
            changed.append((rel, f["sha256"][:12], h[:12]))
    added = [rel for rel in current if rel not in base_files]
    log(f"[dir] {g['dir']}: baseline={len(base_files)} current={len(current)} changed={len(changed)} missing={len(missing)} added={len(added)}")
    for c in changed:
        log(f"   CHANGED {c[0]} {c[1]} -> {c[2]}")
    for m in missing:
        log(f"   MISSING {m}")
    for a in added:
        log(f"   ADDED {a}")
log()

for f in base["protected_db_files"]:
    p = WS / f["rel"]
    if not p.exists():
        log(f"[db] {f['rel']} MISSING (baseline exists={f['exists']})")
        continue
    st = p.stat()
    h = sha256_stream(p)
    log(f"[db] {f['rel']} bytes={st.st_size} (baseline {f['bytes']}) sha256={h[:16]}... baseline={f['sha256'][:16]}... same={h == f['sha256']}")
    log(f"     mtime_now={st.st_mtime:.0f} baseline_mtime={f['mtime_iso']}")
log()

r = subprocess.run(["git", "-C", str(WS / "examdata"), "rev-parse", "--short", "HEAD"],
                   capture_output=True, text=True)
r2 = subprocess.run(["git", "-C", str(WS / "examdata"), "status", "--porcelain"],
                    capture_output=True, text=True)
dirty = len([l for l in r2.stdout.splitlines() if l.strip()])
log(f"[git] head={r.stdout.strip()} (baseline {base['examdata_git']['head']}) dirty={dirty} (baseline {base['examdata_git']['dirty_count']})")
log("说明：dirty 计数包含本任务对 IELTS 模块/测试/文档的修改（允许范围），不代表 CIE/Edexcel 业务文件被改动；以逐文件 hash 对照为准。")

EVID.write_text("\n".join(out) + "\n", encoding="utf-8")
print("written:", EVID)
