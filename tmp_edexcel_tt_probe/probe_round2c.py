import sys, json
sys.path.insert(0, "../examdata/src")
from examdata.timetable.edexcel_parser import parse_pdf

r = parse_pdf("downloads/edexcel/gcse/2016-06.pdf", "gcse", 2016, 6)
print("### gcse/2016-06 全部 unparsed 行")
for u in r["unparsed_rows"]:
    print(json.dumps(u, ensure_ascii=False))
print("### 2016-06-08 事件")
for e in r["events"]:
    if e["date"] == "2016-06-08":
        print("   ", e["date"], e["session"], e["subject_code"], e["paper_code"], e["subject_title"][:60], e["duration_raw"])

r2 = parse_pdf("downloads/edexcel/ial/2018-06.pdf", "ial", 2018, 6)
print("### ial/2018-06 全部 unparsed 行")
for u in r2["unparsed_rows"]:
    print(json.dumps(u, ensure_ascii=False))
print("### ial/2018-06 WBI06 事件")
for e in r2["events"]:
    if e["subject_code"] == "WBI06":
        print("   ", e["date"], e["session"], e["subject_code"], e["duration_raw"])
