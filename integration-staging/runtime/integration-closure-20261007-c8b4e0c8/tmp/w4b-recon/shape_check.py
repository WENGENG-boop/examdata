import json

BASE = r"C:/Users/weo/Desktop/api/integration-staging/runtime/integration-closure-20261007-c8b4e0c8/tmp/w4b-recon"
dump = json.load(open(BASE + "/api_dump/api_dump.json", encoding="utf-8"))
run = dump["with_operations_root"]

want = [
    "/api/v2/exam-systems",
    "/api/v2/questions?system=toefl",
    "/api/v2/coverage?system=cie",
    "/api/v2/timetables?system=cie",
    "/api/v2/questions/q_lkfcr6zycmxmr4bdx2edj437sxpxkylo/audio",
    "/api/v2/info",
]
for e in run:
    if e["path"] in want:
        print("###", e["path"], "status", e["status"])
        print(json.dumps(e.get("json"), ensure_ascii=False, indent=1)[:2600])
        print()

second = json.load(open(BASE + "/api_dump2.json", encoding="utf-8"))
print("### api_dump2 top-level keys:", list(second.keys()) if isinstance(second, dict) else type(second))
