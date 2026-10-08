import json, io

P = "review/obs-s04.jsonl"
objs = [json.loads(l) for l in io.open(P, encoding="utf-8").read().split("\n") if l.strip()]
by = {o["seq"]: o for o in objs}

# 1) page_pair lines: swap "checks" -> "missing_questions" (prompt-s04 schema), preserve key order
for o in objs:
    if o["kind"] == "page_pair":
        o.pop("checks", None)
        o["missing_questions"] = []

# 2) seq4/5/12/13: index lists a question-level "1" on these pages BY DESIGN (p8: "1,1(c)"; p11:"1,1(h)"),
#    so question-level region == the single part region. Not an anomaly -> clear issues, explain in observed.
ADD = {
 4: " 依索引页码分布，p8 的题号集为 \"1, 1(c)\"，其中 question 级 \"1\" 是 1(c) 的归并条目，故其区域与 1(c) 区域必然同框，属设计使然、非异常。",
 5: " 索引中 p8 的 \"1\" 为 1(c) 的归并条目，故与 1(c) 同框，非异常。",
 12:" 依索引页码分布，p11 的题号集为 \"1, 1(h)\"，question 级 \"1\" 为 1(h) 的归并条目，故与 1(h) 同框，非异常。",
 13:" 索引中 p11 的 \"1\" 为 1(h) 的归并条目，故与 1(h) 同框，非异常。",
}
for s, txt in ADD.items():
    by[s]["observed"] = by[s]["observed"] + txt
    by[s]["issues"] = []

# 3) seq6/8/17/20/25: page-pair evidence proves the last row is complete -> not a defect -> clear issues
for s in (6, 8, 17, 20, 25):
    by[s]["issues"] = []

out = "\n".join(json.dumps(o, ensure_ascii=False) for o in objs) + "\n"
with io.open(P, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(out)

# summary
import collections
print("records", len(objs))
print("page_pair keys", list(by[28].keys()))
print("region keys", list(by[1].keys()))
print("non-empty issues:", [(o["seq"], len(o["issues"])) for o in objs if o["issues"]])
