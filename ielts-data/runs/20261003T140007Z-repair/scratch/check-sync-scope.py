import json, io, os

with io.open(r"C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/changed-files.json", "r", encoding="utf-8") as f:
    d = json.load(f)
ch = {x["rel"] for x in d["changes"]}
root = r"C:/Users/weo/Desktop/api/ielts-api"
allf = []
for dp, dns, fns in os.walk(root):
    dns[:] = [x for x in dns if x not in (".tmp", "node_modules", "__pycache__")]
    for fn in fns:
        rel = os.path.relpath(os.path.join(dp, fn), root).replace("\\", "/")
        allf.append(rel)
allf = [x for x in allf if not x.startswith(".tmp/")]
print("main files (excl .tmp):", len(allf))
missing = [x for x in allf if x not in ch]
print("not in changes:", missing)
extra = [x for x in ch if x not in allf]
print("in changes but not on disk:", extra)
