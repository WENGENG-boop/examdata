import json, os

OBS = r"C:/Users/weo/Desktop/api/cie-location-batch/work/0472_2026_22_obs.jsonl"

records = [
    {
        "frame": 1,
        "sheet": "0472-2026-Jun-22-qp-pages-1.html",
        "viewed_at": "2026-10-04",
        "page_review": {
            "pages": [1, 2, 3, 4],
            "obs": "p1 封面：Cambridge IGCSE ENGLISH AS AN ADDITIONAL LANGUAGE 0472/22 Paper 2 Reading May/June 2026, 1 hour, The total mark for this paper is 45, This document has 16 pages。p2 Q1 节首 '1 Read the texts. For each question, tick (✓) the correct box (A–D).' + (a) Zora 咖啡店手机消息（Tam/Zora 对话）'What did Zora like about the café?' A the drinks / B the food / C the prices / D the staff [1]。p3 (b) 比赛通知（2.30pm 球场、图书馆旁、家长受邀、3.45pm 接、新队服）A-D [1] + (c) Joel/Fabio 便条（给妈妈买生日礼物：书→香水，百货店）A-D [1] [Total: 3]。p4 Q2 节首 '2 Read the email. For each question, tick (✓) the correct box (A–C).' + Keiron 邮件（A meal for Mum）+ (a) 'Where did the family have their meal?' A garden / B dining room / C kitchen [1] + (b) 'What did Keiron decide to cook?' A chicken / B fish / C lamb [1]。页序 1→4 正确，题号连续。"
        }
    },
    {
        "frame": 2,
        "sheet": "0472-2026-Jun-22-qp-pages-2.html",
        "viewed_at": "2026-10-04",
        "page_review": {
            "pages": [5, 6, 7, 8],
            "obs": "p5 2(c)–(g) 各 A–C [1] + [Total: 7]。p6 Q3 节首 + Horses 主题文本 + (a)–(c)。p7 3(d)–(g) + [Total: 7]。p8 Q4 节首 '4 Read the email...' + Rosa 邮件 + (a)–(c)。页序 5→8 正确。"
        }
    },
    {
        "frame": 3,
        "sheet": "0472-2026-Jun-22-qp-pages-3.html",
        "viewed_at": "2026-10-04",
        "page_review": {
            "pages": [9, 10, 11, 12],
            "obs": "p9 4(d)–(k) + [Total: 12]。p10 Q5 五人 (a–e) 配公园图。p11 评论 1–8 + [5]。p12 Q6 节首 + Nanci 文本 + (a)–(c)。页序 9→12 正确。"
        }
    },
    {
        "frame": 4,
        "sheet": "0472-2026-Jun-22-qp-pages-4.html",
        "viewed_at": "2026-10-04",
        "page_review": {
            "pages": [13, 14, 15, 16],
            "obs": "p13 6(d)–(i) + [Total: 11]。p14 BLANK。p15 BLANK。p16 BLANK + 版权段。页序 13→16 正确，无漏题。"
        }
    },
    {
        "frame": 5,
        "sheet": "0472-2026-Jun-22-ms-pages-1.html",
        "viewed_at": "2026-10-04",
        "page_review": {
            "pages": [1, 2, 3, 4],
            "obs": "ms p1 封面：Maximum Mark: 45。p2 General principles 1–6。p3 English & Media-Specific a–g。p4 Annotations 表（✓/REF/BOD/✗/SEEN）。页序 1→4 正确。"
        }
    },
    {
        "frame": 6,
        "sheet": "0472-2026-Jun-22-ms-pages-2.html",
        "viewed_at": "2026-10-04",
        "page_review": {
            "pages": [5, 6, 7, 8],
            "obs": "p5 Additional Guidance。p6 答案：1(a)B 1(b)D 1(c)B；2(a)B 2(b)A 2(c)B 2(d)A 2(e)C 2(f)B 2(g)C；3(a)B 3(b)C 3(c)C 3(d)A 3(e)D 3(f)A 3(g)B。p7 答案：4(a)canteen 4(b)Strawberries/学校/Southside 4(c)Newton 4(d)math(s)+geography[2] 4(e)tennis 4(f)two 4(g)lift/car 4(h)chef 4(i)introduce him to people 4(j)shopping 4(k)homework；5(a)8 5(b)4 5(c)1 5(d)3 5(e)6。p8 答案：6(a)Liza 搬走 6(b)new/different text group 6(c)indoor activity+something creative[2] 6(d)arts centre 6(e)excited 6(f)roses 6(g)large choice of food+plenty of room[2] 6(h)pizza cold 6(i)printed/gave/made book of photos。页序 5→8 正确。"
        }
    },
    {
        "frame": 9,
        "sheet": "0472-2026-Jun-22-qp-regions-stack-3.html",
        "viewed_at": "2026-10-04",
        "regions": [
            {
                "label": "Q1(a)",
                "role": "qp",
                "page": 2,
                "bbox": [71.2, 83.6, 393.6, 444.0],
                "obs": "内容：(a) 标签 + 手机聊天图形（Tam/Zora 对话气泡）+ 'What did Zora like about the café?' + 选项 A the drinks / B the food / C the prices / D the staff + [1]。发现两处几何缺陷：① x1=393.6 切断手机图形右缘（图形实际延至 x≈425.8）；② y1=444.0 切断 D 复选框（底 448.8）与 [1]（底 459.2）。拟修 → [71.2,83.6,541.2,463.2]。"
            }
        ]
    }
]

existing = set()
if os.path.exists(OBS):
    with open(OBS, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                existing.add(json.loads(line).get("frame"))
            except Exception:
                pass

added = []
with open(OBS, "a", encoding="utf-8") as fh:
    for rec in records:
        if rec["frame"] in existing:
            continue
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        added.append(rec["frame"])

print("added frames:", added)
print("existing before:", sorted(existing))
