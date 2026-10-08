import json
import sys

path = sys.argv[1]
rec = json.loads(sys.stdin.read().strip())
with open(path, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
print("appended frame", rec.get("frame"), "regions:", len(rec.get("regions", [])))
