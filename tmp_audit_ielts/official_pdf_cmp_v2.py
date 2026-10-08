# -*- coding: utf-8 -*-
"""
official_pdf_cmp_v2.py — 官方 PDF 听力答案提取器 v2（列感知 + OCR 容错）

背景: 旧版 official_pdf_cmp.py 对剑3 有效，对剑4 提取 0 条。原因:
  1. 剑4 答案页为双栏交错 + 号码/值分行渲染 + 值行可能渲染在号码上方 3-6px
  2. OCR 噪声: "7"→"1", "10"→"I 0", "1"→"I", "10th"→"1Oth", "11-20"→"11..:..20"
  3. 组合号 "2 & 3" / "8 & 9" / "25 & 26" / "39 & 40"
  4. 剑4 T4 标题为 ". TESTA ."（不是 "TEST 4"）
  5. 值内分隔符是字面 "I"（如 "coal I firewood"）

算法:
  - 按 x 间隙分栏（>20px 间隙，位于页宽 20%-80% 区间）
  - 词级行分组 (y 容差 3px) + 前向合并（无号码行紧随有号码行且 y 差 ≤6.5px → 值行归下一个号码）
  - 号码 token: x ≤ 栏起点+26 且匹配 [0-9IlOo]{1,2} 或 &；OCR 归一化; "N & M" 组合
  - 序列修复: 重复号且下一期望号缺失 → 视为期望号（"1"→7）
  - 值行保留行结构（供 either-order 拆分）

用法:
  python official_pdf_cmp_v2.py [books...]     默认: 3 4
  python official_pdf_cmp_v2.py 4 --dump       只提取并打印剑4
"""
import json, re, subprocess, sys
import pymupdf

BASE = 'C:/Users/weo/Desktop/api/tmp_audit_ielts'
IELTS = 'C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api'

NUM_RE = re.compile(r'^([0-9IlOo]{1,2}|&)$')
NUM_FIX = str.maketrans('IlOo', '1100')
# 页定位: "TEST N"（或 "TESTA"）后紧跟 "LISTENING"，且页面含答案页特征
TEST_RE = re.compile(r'TEST\s*([1-4A])\b[^\n]{0,6}\n+\s*LISTENING')
KEY_HINT = re.compile(r'answer\s*key|each\s+question\s+correctly\s+answered', re.I)


# ---------- 1. 页面级提取 ----------
def extract_page(page):
    """返回 entries: list of (nums, value_lines)；按列顺序（左→右）"""
    W = page.rect.width
    words = [(w[0], w[1], w[4]) for w in page.get_text('words')]
    xs = sorted(set(round(w[0]) for w in words))
    best_gap, split_x = 0, None
    for a, b in zip(xs, xs[1:]):
        if 0.2 * W <= a and b <= 0.8 * W and b - a > best_gap:
            best_gap, split_x = b - a, (a + b) / 2
    if best_gap >= 20:
        cols = [[w for w in words if w[0] < split_x],
                [w for w in words if w[0] >= split_x]]
    else:
        cols = [words]

    entries = []
    for col in cols:
        if not col:
            continue
        colx0 = min(w[0] for w in col)
        zone = colx0 + 26

        def numtoks(row):
            return [w for w in row if w[0] <= zone and NUM_RE.match(w[2])]

        ws = sorted(col, key=lambda w: (w[1], w[0]))
        rows = []
        for w in ws:
            if rows and w[1] - rows[-1][0][1] <= 3:
                rows[-1].append(w)
            else:
                rows.append([w])

        # 前向合并: 无号码行 + 下一行有号码 + y 差 ≤ 6.5 → 合并（值归下一个号码）
        blocks = []
        i = 0
        while i < len(rows):
            r = rows[i]
            if not numtoks(r) and i + 1 < len(rows) and numtoks(rows[i + 1]) and \
                    (rows[i + 1][0][1] - r[0][1]) <= 6.5:
                blocks.append(r + rows[i + 1])
                i += 2
            else:
                blocks.append(r)
                i += 1

        cur = None
        for row in blocks:
            nt = numtoks(row)
            if nt:
                joined = ''.join(w[2].translate(NUM_FIX) for w in nt)
                nums, consumed = None, set()
                m = re.match(r'^(\d{1,2})&(\d{1,2})$', joined)
                if m and 1 <= int(m.group(1)) <= 40 and 1 <= int(m.group(2)) <= 40:
                    nums = [int(m.group(1)), int(m.group(2))]
                    consumed = set(id(w) for w in nt)
                else:
                    m2 = re.match(r'^(\d{1,2})$', joined)
                    if m2 and 1 <= int(m2.group(1)) <= 40:
                        nums = [int(m2.group(1))]
                        consumed = set(id(w) for w in nt)
                    else:
                        t0 = nt[0][2].translate(NUM_FIX)
                        if re.match(r'^\d{1,2}$', t0) and 1 <= int(t0) <= 40:
                            nums = [int(t0)]
                            consumed = {id(nt[0])}
                if nums:
                    vt = sorted([w for w in row if id(w) not in consumed],
                                key=lambda w: (w[1], w[0]))
                    line = ' '.join(w[2] for w in vt).strip()
                    cur = [nums, [line] if line else []]
                    entries.append(cur)
                    continue
            if cur is not None:
                line = ' '.join(w[2] for w in sorted(row, key=lambda w: (w[1], w[0]))).strip()
                if line:
                    cur[1].append(line)
    return entries


def extract_book(book):
    """扫描整本 PDF, 返回 {test: {qnum: [value_lines]}}"""
    doc = pymupdf.open(f'{BASE}/downloads/book_{book}.pdf')
    per_test = {}
    for i in range(doc.page_count):
        page = doc[i]
        t = page.get_text()
        m = TEST_RE.search(t)
        if not m or not KEY_HINT.search(t):
            continue
        test = 4 if m.group(1) == 'A' else int(m.group(1))
        if test in per_test:
            continue
        raw = extract_page(page)
        out, expected, seen = {}, 1, set()
        for nums, vlines in raw:
            fixed = []
            for n in nums:
                if n in seen and expected not in seen:
                    n = expected  # OCR 重复号修复
                fixed.append(n)
                seen.add(n)
            expected = max(seen) + 1
            for n in fixed:
                out[n] = vlines
        per_test[test] = {'page': i + 1, 'answers': out}
    doc.close()
    return per_test


# ---------- 2. 规范化与匹配 ----------
def norm(s):
    s = str(s).lower()
    s = s.replace('\u2019', "'").replace('\u2018', "'").replace('\u201c', '"').replace('\u201d', '"')
    s = re.sub(r'[^a-z0-9/ ]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def variants(raw):
    out = set()
    for p in re.split(r'//|/| accept |\bor\b| I | \| ', raw, flags=re.I):
        p = p.strip()
        if not p:
            continue
        out.add(norm(p))
        out.add(norm(re.sub(r'\([^)]*\)', ' ', p)))
        out.add(norm(re.sub(r'[()]', '', p)))
    out.add(norm(raw))
    return {v for v in out if v}


def match_one(pte_ans, official_raw):
    if pte_ans is None:
        return None
    p = norm(pte_ans)
    if not p:
        return False
    for v in variants(official_raw):
        if p == v or (len(p) >= 2 and p in v) or (len(v) >= 2 and v in p):
            return True
    pt = set(p.split())
    if len(pt) > 1:
        for v in variants(official_raw):
            vt = set(v.split())
            if pt and pt <= vt:
                return True
    return False


INSTR_RE = re.compile(r'either\s*order|both\s*required|for\s+one\s+mark|inanyorder', re.I)


def compare_one(official_lines, pte_ans):
    """official_lines: list[str]; pte_ans: str 或 list[str]（组合号）"""
    if pte_ans is None:
        return None
    official = ' '.join(official_lines)
    if 'either order' in official.lower() or 'inanyorder' in official.lower():
        cands = []
        for ln in official_lines:
            if INSTR_RE.search(ln):
                continue
            for part in re.split(r'\s*//\s*|\s+I\s+|\s*\|\s*', ln):
                if part.strip():
                    cands.append(part.strip())
        parts = pte_ans if isinstance(pte_ans, list) else re.split(r'\s+and\s+|\s*&\s*', str(pte_ans))
        parts = [p for p in parts if p and p.strip()]
        if not parts or not cands:
            return False
        return all(any(match_one(p, c) for c in cands) for p in parts)
    return match_one(pte_ans, official)


# ---------- 3. 取抓取答案（node 实时拉取） ----------
def fetch_answers(books):
    node_code = """
const ielts = await import('file:///%s/ielts-api.mjs');
const iprog = await import('file:///%s/iprog.mjs');
const books = %s;
const out = { pte: {}, iprog: {} };
for (const b of books) for (const t of [1,2,3,4]) {
  const r = await ielts.pteListening(b, t);
  out.pte[`${b}-${t}`] = { ok: r.ok, slug: r.slug || null, answers: r.answer_key || null, count: r.answer_count, err: r.error || null };
  if (b === 3) {
    const r2 = await iprog.listeningAnswers(3, t);
    out.iprog[`3-${t}`] = { ok: r2.ok, answers: r2.answer_key || null, count: r2.answer_count, url: r2.url, err: r2.error || null };
  }
}
console.log(JSON.stringify(out));
""" % (IELTS, IELTS, json.dumps(books))
    res = subprocess.run(['node', '--input-type=module', '-e', node_code],
                         capture_output=True, text=True, encoding='utf-8', cwd=BASE)
    if res.returncode != 0:
        print('NODE FAIL:', res.stderr[-2000:])
        sys.exit(1)
    return json.loads(res.stdout.strip().splitlines()[-1])


# ---------- 4. 主流程 ----------
def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dump_only = '--dump' in sys.argv
    books = [int(a) for a in args] if args else [3, 4]

    extraction = {}
    for b in books:
        per_test = extract_book(b)
        extraction[b] = per_test
        for t in [1, 2, 3, 4]:
            if t not in per_test:
                print(f'[book {b} T{t}] 未找到答案页!')
                continue
            ans = per_test[t]['answers']
            missing = [q for q in range(1, 41) if q not in ans]
            print(f'[book {b} T{t}] page {per_test[t]["page"]}: {len(ans)} 条'
                  + (f', 缺失 {missing}' if missing else ''))
    json.dump({str(b): {str(t): {'page': v['page'], 'answers': {str(k): vv for k, vv in v['answers'].items()}}
                        for t, v in per_test.items()} for b, per_test in extraction.items()},
              open(f'{BASE}/official_v2_extracted.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'提取结果已存: {BASE}/official_v2_extracted.json')

    if dump_only:
        return

    fetched = fetch_answers(books)
    json.dump(fetched, open(f'{BASE}/official_cmp_fetched_v2.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    for b in books:
        print(f'\n===== 剑{b} =====')
        for t in [1, 2, 3, 4]:
            if t not in extraction[b]:
                continue
            off = extraction[b][t]['answers']
            pte = fetched['pte'].get(f'{b}-{t}')
            pte_ans = pte['answers'] if pte and pte['ok'] else None
            if not pte or not pte['ok']:
                print(f'-- T{t}: pte 拉取失败: {pte}')
                continue
            # 组合号: 将两个号的 pte 答案合为 list
            combined = {}
            for q, lines in off.items():
                pass
            # 找出组合号（提取阶段两个号共享同一 value_lines 对象）
            groups = {}
            for q, lines in off.items():
                key = id(lines)
                groups.setdefault(key, []).append(q)
            match = tot = 0
            diffs = []
            for q in range(1, 41):
                lines = off.get(q)
                if lines is None:
                    continue
                g = groups[id(lines)]
                if len(g) > 1:
                    pa = [pte_ans[x - 1] for x in sorted(g) if x - 1 < len(pte_ans)]
                else:
                    pa = pte_ans[q - 1] if q - 1 < len(pte_ans) else None
                r = compare_one(lines, pa)
                if r is None:
                    continue
                tot += 1
                if r:
                    match += 1
                else:
                    diffs.append((q, ' '.join(lines), pa))
            print(f'-- 剑{b} T{t} (slug {pte["slug"]}): {match}/{tot} 匹配')
            for q, o, p in diffs:
                print(f'    Q{q} PDF={o!r}  pte={p!r}')


if __name__ == '__main__':
    main()
