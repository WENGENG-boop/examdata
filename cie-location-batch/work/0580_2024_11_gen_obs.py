# -*- coding: utf-8 -*-
"""生成 0580/2024/Jun/11 的 76 条区域目视读数 obs_final.jsonl。

读数来源：work/0580_2024_11_browser_notes.md（浏览器 page.visual.snapshot 目视）。
M14/M22 采用修复后重看的加长区域读数。
"""
import json
import pathlib

WORK = pathlib.Path(__file__).resolve().parent

QP = {
    "1": "题号1及(a)(b)(c)三小问完整（Write 0.8 as a fraction / Write 28% as a decimal / Write 4876 correct to the nearest hundred），各含[1]；下缘止于(c)的[1]，未混入Q2。",
    "1(a)": "(a) Write 0.8 as a fraction. … [1] 完整；上缘含题号1，未混入(b)。",
    "1(b)": "(b) Write 28% as a decimal. … [1] 完整；未混入(c)。",
    "1(c)": "(c) Write 4876 correct to the nearest hundred. … [1] 完整；下缘未混入Q2。",
    "2": "题号2；线段AB图完整（A、B两端点可见）；Measure the length of line AB in millimetres.；答题虚线+mm [1]；下缘止于[1]行，未混入Q3。",
    "3": "题号3；The travel graph shows the journey of a bus.；行程图完整（Distance(km) 0–14、Time 1400–1600 坐标轴全）；(a)(b) 各含 km [1]/min [1]；下缘未混入Q4。",
    "3(a)": "(a) Find the distance the bus travels in the first 50 minutes. … km [1] 完整。",
    "3(b)": "(b) Find how long, in minutes, the bus is stationary. … min [1] 完整。",
    "4": "题号4；Write down the order of rotational symmetry of a rhombus. + 答案线 + [1]；题干完整，区域内无其他题。",
    "5": "题号5；The diagram shows a shape on a 1 cm² grid. + 网格图完整（图形轮廓与网格可见，未截断）+ Find the area of this shape. + …… cm² + [1]。",
    "6": "题号6；共同题干(a) Work out.可见；父区含子题(a)(b)（允许）；(a) 28 − 16 ÷ 2；(b) Find the reciprocal of 4/5（由MS 6(b)=1.25=5/4确认分母为4/5）；无Q7混入。",
    "6(a)": "(a) Work out. 28 − 16 ÷ 2 + 答案线 [1]，与MS 6(a)=20对应。",
    "6(b)": "(b) Find the reciprocal of 4/5. + 答案线 [1]；分数经MS侧确认（MS=1.25 or 1¼ ⇒ 题面为4/5）。",
    "7": "题号7；7 The temperature on Monday is −27 °C. The temperature on Tuesday is 15 °C higher than on Monday. Work out the temperature on Tuesday. + 答案线 + °C [1]。完整。",
    "8": "题号8；十字（plus）轮廓图完整（上下左右臂全可见）+ Draw all the lines of symmetry on this shape. + [2]。图形完整未截断。",
    "9": "题号9；坐标系图完整（x: −8..5，y: −1..8；A(−7,5)、B(−1,1)、C(3,3) 标注与 A–B、B–C 两线段均可见，坐标轴刻度完整）+ The diagram shows two sides of a parallelogram ABCD. + Find the coordinates of point D. + ( …… , …… ) [2]。区域完整含图；无下一题混入。",
    "10": "题号10；长方体立体图完整（h cm / 6 cm / 15 cm 三标注齐全，虚线隐藏棱可见）+ NOT TO SCALE + The total surface area of this cuboid is 369 cm². + Work out the value of h. + h = …………… [4]；单题无子问；无下一题混入。",
    "11": "题号11；共同题干完整（Geetha has a box of toys…probability 0.6）+ (a) Work out the probability that she does not pick a wooden toy. [1] + (b) 表格（Type of toy: Wooden/Plastic/Metal；Number of toys: 空/14/14；Probability: 0.6/空/空）+ Complete the table. [2]；父区含子题（允许），无Q12混入。",
    "11(a)": "(a) Work out the probability that she does not pick a wooden toy. + 答案线 + [1]；边界正确（从(a)缩进处起，不含父题干）。",
    "11(b)": "(b) The box contains three types of toys, wooden, plastic or metal. + 表格 + Complete the table. + [2]；边界从(b)起，正确。",
    "12": "题号12；The table shows some information about two sequences. + 表格（nth term/5th term；Sequence A: 60 − 4n；Sequence B: n² − 300；5th term 两格空）+ Complete the table. + [2]；单题无子问，结构确认。",
    "13": "题号13；13 Find the coordinates of the point where the line y = 3x − 5 crosses the y-axis. + ( …… , …… ) [1]。完整。",
    "14": "题号14；14 By writing each number in the calculation correct to 1 significant figure, find an estimate for the value of + 分数式 (28.2 − 5.6) / (4.2 × 1.68) + You must show all your working. + 答案线 [2]；单题无子问，完整。",
    "15": "题号15；15 Factorise completely. + 36x² + 40x + 答案线 [2]。完整。",
    "16": "题号16；矩形图完整（左边标注 x + 7，下边标注 3x − 12，图形四边闭合）+ NOT TO SCALE + The diagram shows a rectangle with length 3x − 12 and width x + 7. + Find an expression for the perimeter of the rectangle. Give your answer in its simplest form. + 答案线 [3]。完整。",
    "17": "题号17；17 The diagram shows a circle, centre O. P lies on the circle. + 圆图完整（O 圆心、P 在圆上、线段 OP 可见）+ (a) Write down the mathematical name of the line OP. [1] + (b) Draw a tangent to the circle at P. [1]；父区含子题（允许）。",
    "17(a)": "(a) Write down the mathematical name of the line OP. + 答案线 + [1]；边界正确。",
    "17(b)": "(b) Draw a tangent to the circle at P. + [1]；绘图所依圆图在父区（子题继承，notes 说明）。",
    "18": "题号18；18 Find the greatest odd number that is a factor of 140 and a factor of 210. + 答案线 [2]。完整。",
    "19": "题号19；19 Calculate. + (a) ∛343 − √40.96 + 答案线 [1] + (b) (192 + 4 × 16)^1.25 + 答案线 [1]；父区含子题（允许）；（b）运算符+由MS 19(b)=1024确认。",
    "19(a)": "(a) ∛343 − √40.96 + 答案线 [1]；边界正确（∛343=7，√40.96=6.4 ⇒ 0.6，与MS 19(a)=0.6一致）。",
    "19(b)": "(b) (192 + 4 × 16)^1.25 + 答案线 [1]；运算符+经MS侧确认（(192+4×16)=256，256^1.25=1024=MS值）。",
    "20": "题号20；20 (a) Find the value of 137⁰. + 答案线 [1] + (b) 7¹² ÷ 7ᵖ = 7¹⁷ + Find the value of p. + p = ………… [1]；父区含子题（允许）。",
    "20(a)": "(a) Find the value of 137⁰. + 答案线 [1]；与MS 20(a)=1一致。",
    "20(b)": "(b) 7¹² ÷ 7ᵖ = 7¹⁷ + Find the value of p. + p = ………… [1]；与MS 20(b)=−5一致。",
    "21": "题号21；21 Calculate 1.827 × 10⁶ ÷ 9000 + Give your answer in standard form. + 答案线 [2]；指数6经MS侧确认（203=2.03×10²）。",
    "22": "题号22；22 Solve the simultaneous equations. You must show all your working. + 6x + 2y = 29 + 3x − 4y = 17 + x = ………… + y = ………… [3]；完整，单题无子问。",
    "23": "题号23；23 Change 9.6 km/h into m/s. + 答案线 + m/s [2]。完整。",
    "24": "题号24；24 These are the first five terms of a sequence. + 11 18 25 32 39 + Find an expression for the nth term of the sequence. + 答案线 [2]。完整。",
    "25": "题号25；图形完整（J/K/L 三顶点标注、JL 虚线、J 处直角标记、两处 12.8 cm 标注、半圆弧与三角形边完整）+ NOT TO SCALE + The diagram shows a shape made from a triangle JKL and a semicircle with diameter JL. + JKL is an isosceles right-angled triangle with JK = JL = 12.8 cm. + (a) Calculate the area of this shape. cm² [3] + (b) Calculate the perimeter of this shape. cm [4]；父区含子题（允许）。",
    "25(a)": "(a) Calculate the area of this shape. + ……… cm² [3]；边界正确（从(a)起，不含父题干）。",
    "25(b)": "(b) Calculate the perimeter of this shape. + ……… cm [4]；边界正确。",
}

MS = {
    "1(a)": "1(a) = 8/10 oe fraction｜1；确实对应本题评分内容。",
    "1(b)": "1(b) = 0.28｜1；确实对应本题评分内容。",
    "1(c)": "1(c) = 4900 cao｜1；确实对应本题评分内容。",
    "2": "2 = 107｜1；确实对应本题评分内容。",
    "3(a)": "3(a) = 10｜1；确实对应本题评分内容。",
    "3(b)": "3(b) = 40｜1；确实对应本题评分内容。",
    "4": "4 = 2｜1；确实对应本题评分内容。",
    "5": "5 = 12｜1；确实对应本题评分内容。",
    "6(a)": "6(a) = 20｜1；确实对应本题评分内容。",
    "6(b)": "6(b) = 1.25 or 1¼ oe｜1；确实对应本题评分内容。",
    "7": "7 = −12｜1；确实对应本题评分内容。",
    "8": "8 = 2 correct lines of symmetry｜2；B1：一条正确且无多余，或两条正确且多一条；确实对应本题评分内容。",
    "9": "9 = (−3, 7)｜2；B1 正确图 或 their D 坐标正确 或 (−3,k)/(k,7)；确实对应本题评分内容。",
    "10": "10 = 4.5｜4；M3: 2(6h+15h)=369−2(6×15) or better；M2: 2(6×15+6h+15h) oe；M1: 2×6×15 或 2×6h 或 2×15h；确实对应本题评分内容。",
    "11(a)": "11(a) = 0.4 oe｜1；确实对应本题评分内容。",
    "11(b)": "11(b) = 42 及 0.2 0.2｜2；B1 for 42；B1 for 0.2 and 0.2；若 B0，SC1 their 两概率各为 their(a) 的一半；确实对应本题评分内容。",
    "12": "12 = 40 / −275｜2；B1 each；确实对应本题评分内容。",
    "13": "13 = (0, −5)｜1；确实对应本题评分内容。",
    "14": "14 = (30−6)/(4×2)｜M1；含 A1 行「3 nfww」及 SC1 附注（If 0 scored, SC1 for 3 correct roundings or all correct but with trailing zeros）；加长后两行完整；确实对应本题评分内容。",
    "15": "15 = 4x(9x+10) final answer｜2；B1: x(36x+40) 或 4(9x²+10x) 或 2x(18x+20) 或 4x(9x+10) seen then spoilt；确实对应本题评分内容。",
    "16": "16 = 8x−10 或 2(4x−5) final answer｜3；B2 8x−10 seen and spoilt；M2 2(x+7)+2(3x−12) oe；M1 x+7+3x−12 oe；B1 8x 或 −10 in final answer；确实对应本题评分内容。",
    "17(a)": "17(a) = radius｜1；确实对应本题评分内容。",
    "17(b)": "17(b) = Ruled line drawn through P perpendicular to OP｜1；确实对应本题评分内容。",
    "18": "18 = 35｜2；B1 answer 5/7/70；M1 2×2×5×7 and 2×3×5×7 或两个正确因子树/表 或 5×7×k seen；确实对应本题评分内容。",
    "19(a)": "19(a) = 0.6 or 3/5｜1；确实对应本题评分内容。",
    "19(b)": "19(b) = 1024｜1；确实对应本题评分内容。",
    "20(a)": "20(a) = 1｜1；确实对应本题评分内容。",
    "20(b)": "20(b) = −5｜1；确实对应本题评分内容。",
    "21": "21 = 2.03×10² cao｜2；B1 for 203 oe；若 0 分，SC1 their ordinary number 正确写成标准形式；确实对应本题评分内容。",
    "22": "22 = Correctly eliminating one variable（M1）+ [x=]5（A1）+ [y=]−0.5（A1；若 M0 得 SC1 for 2 values satisfying one of the original equations）；加长后三行完整；确实对应本题评分内容。",
    "23": "23 = 2⅔ or 2.67 or 2.666 to 2.667｜2；M1: 9.6×1000/(60×60) oe；确实对应本题评分内容。",
    "24": "24 = 7n+4 oe final answer｜2；B1: 7n+j 或 kn+4 k≠0 或 7n+4 seen then spoilt；确实对应本题评分内容。",
    "25(a)": "25(a) = 146 或 146.2 to 146.3｜3；M1 ½×12.8×12.8；M1 [½]×π×(12.8/2)²；确实对应本题评分内容。",
    "25(b)": "25(b) = 51[.0] 或 51.00 to 51.01…｜4；M1: ½×π×12.8；M2: √(12.8²+12.8²) 或 12.8/Sin45 oe；或 M1: 12.8²+12.8² oe；或 sin45 = 12.8/KL oe；确实对应本题评分内容。",
}

EXPECTED_QP = [
    "1", "1(a)", "1(b)", "1(c)", "2", "3", "3(a)", "3(b)", "4", "5",
    "6", "6(a)", "6(b)", "7", "8", "9", "10", "11", "11(a)", "11(b)",
    "12", "13", "14", "15", "16", "17", "17(a)", "17(b)", "18", "19",
    "19(a)", "19(b)", "20", "20(a)", "20(b)", "21", "22", "23", "24", "25",
    "25(a)", "25(b)",
]
EXPECTED_MS = [
    "1(a)", "1(b)", "1(c)", "2", "3(a)", "3(b)", "4", "5", "6(a)", "6(b)",
    "7", "8", "9", "10", "11(a)", "11(b)", "12", "13", "14", "15",
    "16", "17(a)", "17(b)", "18", "19(a)", "19(b)", "20(a)", "20(b)", "21", "22",
    "23", "24", "25(a)", "25(b)",
]

assert list(QP.keys()) == EXPECTED_QP, "QP key order mismatch"
assert list(MS.keys()) == EXPECTED_MS, "MS key order mismatch"
assert len(QP) == 42 and len(MS) == 34

out = WORK / "0580_2024_11_obs_final.jsonl"
lines = []
for q in EXPECTED_QP:
    lines.append(json.dumps({"question": q, "role": "qp", "obs": QP[q]}, ensure_ascii=False))
for q in EXPECTED_MS:
    lines.append(json.dumps({"question": q, "role": "ms", "obs": MS[q]}, ensure_ascii=False))
out.write_text("\n".join(lines) + "\n", encoding="utf-8")

# 自检：逐行 json 可解析，计数正确
n_qp = n_ms = 0
for ln in out.read_text(encoding="utf-8").splitlines():
    obj = json.loads(ln)
    if obj["role"] == "qp":
        n_qp += 1
    else:
        n_ms += 1
print("written:", out)
print("qp lines:", n_qp, "ms lines:", n_ms, "total:", n_qp + n_ms)
