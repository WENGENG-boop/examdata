# -*- coding: utf-8 -*-
# 简化版：统计 cam21 源数据里的反斜杠序列及其上下文
import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BS = chr(92)
path = r"C:/Users/weo/Desktop/api/tmp_audit_ielts/cam21_t1l.html"
s = open(path, encoding='utf-8', errors='replace').read()

seqs = re.findall(re.escape(BS) + r".", s)
print("total backslash sequences:", len(seqs))
from collections import Counter
print("distribution:", Counter(seqs).most_common(15))

print("\n-- contexts (first 30) --")
for i, m in enumerate(re.finditer(re.escape(BS) + r".", s)):
    if i >= 30:
        break
    ctx = s[max(0, m.start()-50):m.end()+30].replace("\n", " ")
    print("  ...", ctx)

# 判断这些反斜杠是否位于单引号字符串内：看其前面最近的引号类型
print("\n-- quote context of each backslash (sample 20) --")
for i, m in enumerate(re.finditer(re.escape(BS) + r".", s)):
    if i >= 20:
        break
    before = s[:m.start()]
    # 从后往前找最近的引号（' " `）
    j = len(before) - 1
    while j >= 0 and before[j] not in ("'", '"', chr(96)):
        j -= 1
    q = before[j] if j >= 0 else "?"
    print("  seq:", repr(s[m.start():m.end()]), "| nearest quote before:", repr(q), "| at", m.start())
