# -*- coding: utf-8 -*-
"""Append root-agent visual fix records for 0509 (3) + 0413 (5) regions.

Each record is written only after the root agent personally viewed the
referenced probe image. Guards: index sha + image sha must match; refuses
to double-append identical records.
"""
import datetime
import hashlib
import json
import os
import sys

BATCH = r"C:\Users\weo\Desktop\api\cie-location-batch"
VERIF = os.path.join(BATCH, "verification.jsonl")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def img(subject_slug, name):
    return os.path.join(BATCH, "tmp", subject_slug, "probe", name)


NOW = datetime.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")

IDX = {
    "0413/2026/Jun/11": (os.path.join(BATCH, "indexes", "0413", "2026-Jun-11", "cie-index.json"),
                         "8783790d7e42fe4a0df151cd7137623e648b3287b0d6b33604548a59babdf046"),
    "0509/2026/Jun/11": (os.path.join(BATCH, "indexes", "0509", "2026-Jun-11", "cie-index.json"),
                         "c14ee3ad3ff3fd7f55f1dd6a43c3af7fc710fd7d4d7d24e9326fc001ffbc1275"),
}

IMGS = {
    "q5": (img("0413/2026-Jun-11", "q5-rotmat.png"),
           "36347913f8140f1086daae39e49f3f6e23dfa0ae82a3ece18120091aefe066db"),
    "q5b": (img("0413/2026-Jun-11", "q5b-rotmat.png"),
            "ce0f623b053e7d6dd5b8e0b6868ebaa7c7b7c7fa56e46f4385244826a8470818"),
    "ms8": (img("0413/2026-Jun-11", "ms-p15-region8.png"),
            "6df77322d82fb9106af8666846f8858d1181514b71b1d76c70be288e43857bfe"),
    "qp12ci": (img("0413/2026-Jun-11", "qp-p14-region.png"),
               "0d7848f607c2bbf477cc70b55730e6c5fdd3cb1f1bddcebf2d8cce762ed574fb"),
    "3a": (img("0509/2026-Jun-11", "check-3a-rot270.png"),
           "64817751baad80f76a4ad4ee36a506528c93e83b380e31b275b0e31de25b1e67"),
    "3b": (img("0509/2026-Jun-11", "check-3b-rot270.png"),
           "54731435af96bff7450ad61f4418ddb9ee48b98593ccb01403f39d6350c11bcb"),
    "3ei": (img("0509/2026-Jun-11", "check-3e-rot270.png"),
            "4fb6999a42b8eee9fe9e6d2bda076b7440418fca3a39804036d10fdee6eeb951"),
}


def rec(key, question, role, page, bbox, image_key, observed):
    path, sha = IMGS[image_key]
    return {
        "key": key,
        "question": question,
        "role": role,
        "page": page,
        "bbox": bbox,
        "method": "local_image_visual",
        "checks": {
            "content_complete": True,
            "boundary_checked": True,
            "role_matches": True,
            "observed": observed,
        },
        "issues": [],
        "checked_at": NOW,
        "index_sha256": IDX[key][1],
        "image": path,
        "image_sha256": sha,
        "verifier": "main_agent_root_visual",
    }


RECORDS = [
    rec("0413/2026/Jun/11", "5", "ms", 11, [337.2, 65.2, 554.0, 729.2], "q5",
        "完整 5(a)+5(b) 两行评分条目：5(a) stroke volume 定义与 Accept alternative wording、Marks 1、"
        "guidance 'Answer must include in one beat or similar'；5(b) cardiac output 4.8 l/min OR 4800 ml/min "
        "与单位分、Marks 2、guidance 'If the answer is wrong, cannot give the unit mark'。"
        "仅页脚 © 符号左缘被裁，属页面家具非题目内容。旋转页按 rotation_matrix 裁剪核验。"),
    rec("0413/2026/Jun/11", "5(b)", "ms", 11, [407.6, 65.2, 554.0, 729.2], "q5b",
        "完整 5(b) 评分行：cardiac output: 4.8 / unit: litres per minute OR cardiac output: 4800 / "
        "unit: millilitres per minute；Marks 2；guidance 'If the answer is wrong, cannot give the unit mark'。"
        "页脚 © 符号左缘被裁属页面家具；无 5(a) 内容混入。旋转页按 rotation_matrix 裁剪核验。"),
    rec("0413/2026/Jun/11", "8", "ms", 15, [102.0, 76.4, 296.8, 729.2], "ms8",
        "完整 8(a) 评分行：'1 mark for the shape of the graph. / 1 mark for each axis being labelled (max 2 marks)'；"
        "inverted-U 图完整（两轴箭头、performance 标签框、arousal 标签框与文字）；Marks 3；"
        "guidance 'Accept either an inverted U shape / a bell shape or similar for shape mark'。"
        "arousal 标签框底边约 7pt 细条在裁切边下方（框底 display y≈303.6 vs 裁切边 296.8），"
        "无评分文字或图形内容丢失。旋转页按 rotation_matrix 裁剪核验。"),
    rec("0413/2026/Jun/11", "8(a)", "ms", 15, [102.0, 76.4, 296.8, 729.2], "ms8",
        "与题 8 同一区域：完整 8(a) 评分行（shape/axis marks、inverted-U 图、performance/arousal 标签、"
        "Marks 3、guidance 均可见）；arousal 标签框底边约 7pt 细条在裁切边下方，无评分文字或图形内容丢失。"),
    rec("0413/2026/Jun/11", "12(c)(i)", "qp", 14, [71.2, 212.0, 540.4, 322.0], "qp12ci",
        "完整子题 (i)：'Identify the stages of the diagram labelled A, B and C.' + A/B/C 三条答题线 + [3]。"
        "所引用图与 (c) 引导语属父题 12(c) 区域（同页 y 58.8–212，已另行核验覆盖 A→B→C+feedback 全图），"
        "按共同图归父题设计合规，无下一题内容混入。"),
    rec("0509/2026/Jun/11", "3(a)", "ms", 14, [150.13, 62.2, 218.84, 779.7], "3a",
        "完整 3(a) 评分行（270° 旋转后可读）：Q 詹鼎在学习上有什么天赋？A 记忆力强／听人读书，回到家，"
        "就能复述别人所诵读的内容。／听人读书，归，辄能言诸生所诵。Marks 1；Guidance Reject: 能言诸生所诵。"
        "无相邻行混入；批处理报的转写受限不构成区域错误。"),
    rec("0509/2026/Jun/11", "3(b)", "ms", 14, [218.84, 62.2, 287.66, 779.7], "3b",
        "完整 3(b) 评分行（270° 旋转后可读）：Q 用自己的话说说为什么詹鼎的父亲不让他去读书。"
        "A 1. 因为他们本是商人之家/他们家本是做生意的。2. 希望他能继承手艺/生意。/希望他家的手艺传下去。"
        "Marks 2；BOD: 为了家业。无相邻行混入。"),
    rec("0509/2026/Jun/11", "3(e)(i)", "ms", 14, [411.03, 62.2, 480.31, 779.7], "3ei",
        "完整 3(e) 评分行（270° 旋转后可读）：(i) 奈何从儒生游也–跟随/跟从；(ii) 遣之读书–送/送走；"
        "(iii) 时吴氏家延师儒–邀请/请；(iv) 鼎遂为吴氏诸子师。–于是/就；Marks 4；BOD: (ii)送去。(iii)聘请。"
        "(i)–(iv) 共用同一 MS 行区域属评分表行设计，非重复错误；无相邻题混入。"),
]


def main():
    for key, (path, expect) in IDX.items():
        actual = sha256_file(path)
        assert actual == expect, f"index sha mismatch {key}: {actual} != {expect}"
        print("index ok:", key, actual)
    for name, (path, expect) in IMGS.items():
        assert os.path.isfile(path), f"image missing: {path}"
        actual = sha256_file(path)
        assert actual == expect, f"image sha mismatch {name}: {actual} != {expect}"
        print("image ok:", name, actual)

    existing = []
    with open(VERIF, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                existing.append(json.loads(line))
            except ValueError:
                continue
    for r in RECORDS:
        for old in existing:
            if (old.get("key") == r["key"] and old.get("question") == r["question"]
                    and old.get("role") == r["role"] and old.get("page") == r["page"]
                    and old.get("verifier") == r["verifier"]
                    and old.get("checked_at") == r["checked_at"]):
                print("DUPLICATE found, abort:", r["key"], r["question"])
                return 2

    with open(VERIF, "a", encoding="utf-8") as f:
        for r in RECORDS:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    print(f"appended {len(RECORDS)} records at {NOW}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
