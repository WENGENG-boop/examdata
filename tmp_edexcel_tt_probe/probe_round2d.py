import sys, json
sys.path.insert(0, "../examdata/src")
from examdata.timetable.edexcel_parser import parse_pdf

r = parse_pdf("downloads/edexcel/gcse/2016-06.pdf", "gcse", 2016, 6)
print("### unparsed 行")
for u in r["unparsed_rows"]:
    print(json.dumps(u, ensure_ascii=False)[:250])
print("### 2016-06-08 事件")
for e in r["events"]:
    if e["date"] == "2016-06-08":
        print("   ", e["session"], e["subject_code"], e["paper_code"], e["subject_title"][:55], "|", e["duration_raw"])
