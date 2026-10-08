import re, sys

raw = open('C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003/raw-332.txt', encoding='utf-8').read()
# find area around Oliver Stanton
i = raw.find('Oliver Stanton')
print('--- around Oliver Stanton (idx', i, ') ---')
seg = raw[max(0, i-2500):i+2500]
# unescape \n and \" for readability
seg = seg.replace('\\n', '\n').replace('\\"', '"')
print(seg)
