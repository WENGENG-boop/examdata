# -*- coding: utf-8 -*-
"""0472/2024-Jun-11: 离线修正草稿区域与文字（propose.py 节说明归属缺陷）。

问题（work/logs/0472-region-precheck.txt 证实）：
- propose.py 把「上一题到下一题之间」的一切算给上一题：Q8/Q14/Q19/Q28/Q34
  的第 2 个区域实际是下一节的节前说明；这些说明文字也被并进了题 text。
- Q24 区域混入 [PAUSE] 与 "Part 2" 标题；Q11/Q31/Q35/Q36/Q37 等 text 尾部
  混入 [PAUSE]/[Total]/卷末说明。
- Q1 之前的 "Questions 1–8" 节说明被 propose.py 整体丢弃。

修正规则（离线推导，视觉核验是最终依据）：
- 节说明（"Questions X–Y" 块）并入该节首题：作为 qp[0]（ctx 区域），文字前置。
- [Total: N]、[PAUSE]、Part 标题不算题目内容：text 在第一个 " [Total:" 或
  " [PAUSE]" 处截断；区域 y1 收到最后一个印刷条目底部 + 4pt。
- 只改 17 题的 qp 区域与文字/notes；其余题不动。

用法：python work/fix_0472_regions.py [--apply]
"""
import hashlib
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(BASE, 'indexes', '0472', '2024-Jun-11', 'cie-index.json')
BACKUP = os.path.join(BASE, 'work', 'index-backups',
                      '0472-2024-Jun-11-before-fix.json')
DUMP = os.path.join(BASE, 'work', 'logs', '0472-qp-text-dump.txt')

# question -> (page, y0, y1, section_label)
CTX = {
    '1':  (3,  55.1, 135.8, '1–8'),
    '9':  (6,  55.1, 156.9, '9–14'),
    '15': (8,  55.1, 462.3, '15–19'),
    '20': (9,  55.1, 196.9, '20–28'),
    '25': (10, 338.5, 407.0, '25–28'),
    '29': (12, 55.1, 160.2, '29–34'),
    '35': (14, 55.1, 160.2, '35–37'),
}

# 期望的当前（草稿）区域：[(page, [x0,y0,x1,y1]), ...]
OLD = {
    '1':  [(3, [68.4, 140.7, 543.0, 347.6])],
    '8':  [(5, [68.4, 503.2, 543.0, 734.5]), (6, [68.4, 55.1, 542.8, 156.9])],
    '9':  [(6, [68.4, 160.9, 543.0, 341.2])],
    '11': [(6, [68.4, 546.4, 543.0, 750.2])],
    '14': [(7, [68.4, 454.3, 543.0, 661.2]), (8, [68.4, 55.1, 542.9, 462.3])],
    '15': [(8, [68.4, 467.2, 543.0, 486.7])],
    '19': [(8, [68.4, 613.9, 543.1, 657.9]), (9, [68.4, 55.1, 538.1, 196.9])],
    '20': [(9, [68.4, 201.8, 543.0, 320.3])],
    '24': [(10, [68.4, 190.7, 543.0, 407.0])],
    '25': [(10, [68.4, 411.9, 543.0, 530.4])],
    '28': [(11, [68.4, 190.7, 543.0, 333.6]), (12, [68.4, 55.1, 542.8, 160.2])],
    '29': [(12, [68.4, 165.1, 543.0, 313.4])],
    '31': [(12, [68.4, 495.9, 543.0, 668.6])],
    '34': [(13, [68.4, 385.9, 543.0, 558.6]), (14, [68.4, 55.1, 542.9, 160.2])],
    '35': [(14, [68.4, 165.1, 543.0, 340.5])],
    '36': [(14, [68.4, 345.4, 543.0, 520.8])],
    '37': [(14, [68.4, 525.7, 543.0, 741.1])],
}

# 修正后的区域（含 ctx 首区域）
NEW = {
    '1':  [(3, [68.4, 55.1, 543.0, 135.8]), (3, [68.4, 140.7, 543.0, 347.6])],
    '8':  [(5, [68.4, 503.2, 543.0, 710.1])],
    '9':  [(6, [68.4, 55.1, 543.0, 156.9]), (6, [68.4, 160.9, 543.0, 341.2])],
    '11': [(6, [68.4, 546.4, 543.0, 726.6])],
    '14': [(7, [68.4, 454.3, 543.0, 636.7])],
    '15': [(8, [68.4, 55.1, 543.0, 462.3]), (8, [68.4, 467.2, 543.0, 486.7])],
    '19': [(8, [68.4, 613.9, 543.1, 633.4])],
    '20': [(9, [68.4, 55.1, 543.0, 196.9]), (9, [68.4, 201.8, 543.0, 320.3])],
    '24': [(10, [68.4, 190.7, 543.0, 309.2])],
    '25': [(10, [68.4, 338.5, 543.0, 407.0]), (10, [68.4, 411.9, 543.0, 530.4])],
    '28': [(11, [68.4, 190.7, 543.0, 309.2])],
    '29': [(12, [68.4, 55.1, 543.0, 160.2]), (12, [68.4, 165.1, 543.0, 313.4])],
    '31': [(12, [68.4, 495.9, 543.0, 644.2])],
    '34': [(13, [68.4, 385.9, 543.0, 534.1])],
    '35': [(14, [68.4, 55.1, 543.0, 160.2]), (14, [68.4, 165.1, 543.0, 316.1])],
    '36': [(14, [68.4, 345.4, 543.0, 496.3])],
    '37': [(14, [68.4, 525.7, 543.0, 676.6])],
}

LINE_RE = re.compile(
    r'^\s*\[(-?[\d.]+), (-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\]\s?(.*)$')
PAGE_RE = re.compile(r'^--- page (\d+) ')


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load_dump():
    """返回 {page: [(x0,y0,x1,y1,text), ...]}，保持文件顺序。"""
    pages = {}
    cur = None
    with open(DUMP, encoding='utf-8') as f:
        for line in f:
            m = PAGE_RE.match(line)
            if m:
                cur = int(m.group(1))
                pages[cur] = []
                continue
            m = LINE_RE.match(line)
            if m and cur is not None:
                x0, y0, x1, y1 = (float(m.group(i)) for i in range(1, 5))
                pages[cur].append((x0, y0, x1, y1, m.group(5)))
    return pages


def ctx_text(pages, page_no, y0, y1):
    parts = []
    for x0, a, x1, b, text in pages.get(page_no, []):
        mid = (a + b) / 2.0
        if y0 <= mid <= y1:
            parts.append(text)
    return ' '.join(parts)


def truncate_text(text):
    for token in (' [Total:', ' [PAUSE]'):
        pos = text.find(token)
        if pos != -1:
            text = text[:pos]
    return text.strip()


def main():
    apply = '--apply' in sys.argv
    old_sha = sha256_file(INDEX)
    with open(INDEX, encoding='utf-8') as f:
        doc = json.load(f)

    if doc['identity'] != {'subject': '0472', 'year': 2024,
                           'season': 'Jun', 'paper': '11'}:
        print('ERROR: identity mismatch', doc['identity'])
        sys.exit(2)
    questions = doc['questions']
    if len(questions) != 37:
        print(f'ERROR: expected 37 questions, got {len(questions)}')
        sys.exit(2)
    by_q = {q['question']: q for q in questions}

    # 1) 校验草稿区域与预期一致
    for qno, exp in OLD.items():
        q = by_q[qno]
        got = [(r['page'], r['bbox']) for r in q['qp']]
        if got != exp:
            print(f'ERROR: {qno} 当前区域与预期不符')
            print(f'  expected: {exp}')
            print(f'  got     : {got}')
            sys.exit(2)

    # 2) 从文字层转储提取 ctx 文字
    pages = load_dump()
    ctx_texts = {}
    for qno, (pg, y0, y1, _sec) in CTX.items():
        text = ctx_text(pages, pg, y0, y1)
        if not text:
            print(f'ERROR: {qno} ctx 区域 p{pg} [{y0},{y1}] 未提取到文字')
            sys.exit(2)
        ctx_texts[qno] = text

    print(f'index sha256 (old): {old_sha}')
    print(f'questions: {len(questions)}  待改: {len(NEW)} 题 '
          f'(ctx {len(CTX)} + 截断 {len(NEW) - len(CTX)})')
    print()

    # 3) 应用区域 / 文字 / notes
    for qno in sorted(NEW, key=lambda s: int(s)):
        q = by_q[qno]
        old_regions = [(r['page'], list(r['bbox'])) for r in q['qp']]
        new_regions = [{'page': pg, 'bbox': list(bb)} for pg, bb in NEW[qno]]
        q['qp'] = new_regions

        old_text = q['text']
        new_text = truncate_text(old_text)
        if qno in ctx_texts:
            new_text = ctx_texts[qno] + ' ' + new_text
        q['text'] = new_text

        if qno in CTX:
            sec = CTX[qno][3]
            q['notes'] = (f'含本节（{sec}）共同说明区域（qp[0]）与说明文字；'
                          '区域/文字经离线修正（节说明归首题、剔除总分行/暂停行）；'
                          '待视觉核验后置 uncertain=false')
        else:
            q['notes'] = ('区域/文字经离线修正（节说明归首题、剔除总分行/暂停行）；'
                          '待视觉核验后置 uncertain=false')

        print(f'== Q{qno} ==')
        print(f'  regions: {len(old_regions)} -> {len(new_regions)}')
        for a in old_regions:
            mark = '' if a in [(r["page"], r["bbox"]) for r in new_regions] else '  <REMOVED/CHANGED>'
            print(f'    old {a}{mark}')
        for r in new_regions:
            print(f'    new ({r["page"]}, {r["bbox"]})')
        print(f'  text old: {old_text[:90]}...')
        print(f'  text new: {new_text[:90]}...')
        if len(new_text) > 90:
            print(f'       ...: ...{new_text[-70:]}')
        print()

    # 4) 统计
    n_regions = sum(len(q['qp']) for q in questions)
    n_ms = sum(len(q['ms']) for q in questions)
    print(f'total qp regions: {n_regions}  ms regions: {n_ms}')

    if not apply:
        print('\nDRY RUN（未写盘）。确认无误后加 --apply。')
        return

    if os.path.exists(BACKUP):
        print('BACKUP 已存在，拒绝覆盖：', BACKUP)
        sys.exit(2)
    os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
    with open(BACKUP, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')

    tmp = INDEX + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')
    os.replace(tmp, INDEX)
    new_sha = sha256_file(INDEX)
    print(f'\nAPPLIED. old sha: {old_sha}')
    print(f'         new sha: {new_sha}')
    print(f'backup: {BACKUP}')


if __name__ == '__main__':
    main()
