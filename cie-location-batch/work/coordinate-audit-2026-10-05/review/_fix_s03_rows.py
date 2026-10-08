import json, sys, io

path = 'obs-s03.jsonl'
rows = [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]
assert len(rows) == 36, len(rows)

new1 = ("区域左上完整包含印刷题号 \"1\"（左边界 70.4pt，题号墨迹 x≈72.4–81.0pt，未被切）；其后为题面 "
        "\"(a) The photographs show a goalkeeper in association football diving to make a save.\"；"
        "中部两幅黑白照片：A（门将站姿、双手抬起准备扑救）与 B（门将侧身鱼跃单手触球），照片下方标注 A / B；"
        "再下为 \"Complete the table for the movement from position A to position B.\" 及其表格，"
        "四列表头 joint / articulating bones / type of movement / main agonist，"
        "行标签 goalkeeper's left elbow（articulating bones 行 1/2/3）与 goalkeeper's right knee（行 1/2），"
        "表格右下角分值 [6]；表格下方为 \"(b) Suggest strategies that could be used to improve the response time of a goalkeeper.\" "
        "及其五条作答点线，末行右侧分值 [3]。四边检查：左边界 70.4pt 含题号 \"1\" 完整（题号与 (a) 同行）；"
        "上边界含题号 \"1\" 与 (a) 题面首行，未切；右边界含表格右边框与 [3]；"
        "下边界 709.6pt 含最后一条作答点线（实测该点线底 y≈708.3pt）与 [3]，未切。"
        "跨页：q1 为跨页题，本页 (b) 作答区止于页末，续见 p3（region q1 p3）。")

new2 = ("区域左上完整包含印刷题号 \"1\"（左边界 70.4pt，与 (a) 同行，未被切），其后 \"(a)\" 及题面 "
        "\"The photographs show a goalkeeper in association football diving to make a save.\"；"
        "两幅黑白照片 A（站姿准备扑救）与 B（鱼跃侧扑触球），下方标注 A / B；"
        "\"Complete the table for the movement from position A to position B.\" 及完整表格"
        "（joint / articulating bones / type of movement / main agonist；"
        "goalkeeper's left elbow 行 1/2/3，goalkeeper's right knee 行 1/2），表格右下角分值 [6]。"
        "四边检查：左边界 70.4pt 含题号 \"1\" 完整；上边界含题号 \"1\" 与 (a) 首行；"
        "右边界含表格右边框；下边界 549.2pt 止于表格下边框，[6] 完整可见，未切。"
        "本区域为 q1 的 (a) 部分，(b) 部分见同页下一区域（y≥549.2）。")

for r in rows:
    if r.get('seq') == 1:
        assert r['bbox'] == [92.4, 58.8, 540.4, 709.6], r['bbox']
        r['bbox'] = [70.4, 58.8, 540.4, 709.6]
        r['observed'] = new1
        r['checks'] = {"content_complete": True, "boundary_checked": True, "role_matches": True}
        r['issues'] = []
    elif r.get('seq') == 2:
        assert r['bbox'] == [92.4, 58.8, 540.4, 549.2], r['bbox']
        r['bbox'] = [70.4, 58.8, 540.4, 549.2]
        r['observed'] = new2
        r['checks'] = {"content_complete": True, "boundary_checked": True, "role_matches": True}
        r['issues'] = []

with open(path, 'w', encoding='utf-8') as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

# done file update
d = json.load(open('done-s03.json', encoding='utf-8'))
d['suspects'] = []
d['notes'] = (d['notes'].rstrip()
    + " 【主代理 2026-10-06 复核】seq1 报告的左边界切题号问题经独立确认属实（题号 \"1\" 墨迹 x≈72.4–95pt，"
      "旧 bbox 左边界 92.4pt 将其切出），已由主代理用 fix_bbox.py 将 8386/2026/Jun/12 与 8386/2026/Jun/13 的 "
      "q1/1(a) 两个区域左边界由 92.4pt 修为 70.4pt（与同卷 q2/q4/q5 一致）；索引 sha 分别更新为 "
      "f3ea5ed7f794aa4713307ea305bfa795b4dbd894d01efd5d1aaa2e82684b40b7（Jun12）与 "
      "8ebc9ee617b3b06be90d0ded7975b59160818a1de485cf7066661844d36dc4c7（Jun13）。"
      "渲染已重跑（regions_rendered 55/55），主代理亲自在浏览器目视复核了修复后的 "
      "qp-p2-q1-r0.png 与 qp-p2-q1a-r0.png 两张区域图，确认题号 \"1\" 已完整包含、四边无切；"
      "seq1/seq2 两行 observed 已按实见重写、issues 清空，其余 34 行原样保留。")
json.dump(d, open('done-s03.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print("ok, rows:", len(rows), "suspects:", d['suspects'])
