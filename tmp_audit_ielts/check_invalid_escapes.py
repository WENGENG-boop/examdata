# -*- coding: utf-8 -*-
# 检查 \d \s \/ 等非 JSON 合法转义的位置（是否落在被解析的字面量内）
import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BS = chr(92)
for path in [r"C:/Users/weo/Desktop/api/tmp_audit_ielts/cam21_t1l.html"]:
    s = open(path, encoding='utf-8', errors='replace').read()
    print("=== file:", path.split("/")[-1], "size:", len(s))
    for pat in [BS + "d", BS + "s", BS + "/"]:
        for m in re.finditer(re.escape(pat), s):
            ctx = s[max(0, m.start()-80):m.end()+40].replace("\n", " ")
            print("  [" + pat + "] ...", ctx)
