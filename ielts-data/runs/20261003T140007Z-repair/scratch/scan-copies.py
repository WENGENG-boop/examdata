import hashlib, json
from pathlib import Path

MAIN = Path(r"C:\Users\weo\Desktop\api\ielts-api")
OTHER = Path(r"C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api")
EXCLUDE_SEGS = {"node_modules", ".git", "__pycache__", ".pytest_cache", ".tmp"}

def scan(root: Path):
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        rel_parts = p.relative_to(root).parts
        if any(seg in EXCLUDE_SEGS for seg in rel_parts):
            continue
        rel = p.relative_to(root).as_posix()
        try:
            data = p.read_bytes()
            out[rel] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        except Exception as e:
            out[rel] = {"error": str(e)}
    return out

main = scan(MAIN)
other = scan(OTHER)
out_dir = Path(r"C:\Users\weo\Desktop\api\ielts-data\runs\20261003T140007Z-repair\scratch")
out_dir.mkdir(parents=True, exist_ok=True)
json.dump({"dir": str(MAIN), "count": len(main), "files": main},
          open(out_dir / "main-files.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({"dir": str(OTHER), "count": len(other), "files": other},
          open(out_dir / "other-files.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

mk, ok = set(main), set(other)
print("main files:", len(main))
print("other files:", len(other))
only_main = sorted(mk - ok)
only_other = sorted(ok - mk)
print("only in main:", len(only_main))
print("only in other:", len(only_other))
for k in only_other:
    print("   O", k)
diff = [k for k in sorted(mk & ok) if main[k].get("sha256") != other[k].get("sha256")]
print("both differ:", len(diff))
for k in diff[:80]:
    print("   D", k, main[k].get("size"), other[k].get("size"))
