"""扫描：全季中 _split_entries 会丢弃「单元格开头的无代码行」的所有位置。"""
import sys
sys.path.insert(0, "../examdata/src")
import examdata.timetable.edexcel_parser as ep

original = ep._split_entries
dropped: list[list[str]] = []

def instrumented(cell):
    entries = []
    for line in str(cell or "").split("\n"):
        cleaned = ep._clean(line)
        if not cleaned:
            continue
        if ep._entry_code(cleaned):
            entries.append(cleaned)
        elif entries:
            entries[-1] = f"{entries[-1]} {cleaned}"
        else:
            dropped.append([cleaned])
    return entries

ep._split_entries = instrumented
total = 0
for path, family, year, month, r_paper in ep.iter_seasons("downloads/edexcel"):
    dropped.clear()
    ep.parse_pdf(path, family, year, month, r_paper=r_paper)
    if dropped:
        total += len(dropped)
        name = f"{family}/{year:04d}-{month:02d}" + ("-r" if r_paper else "")
        print(f"{name}: {len(dropped)} 处")
        for item in dropped[:6]:
            print("    ", item[0][:130])
print("合计受影响单元格:", total)
