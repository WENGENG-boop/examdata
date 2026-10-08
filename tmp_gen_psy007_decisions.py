# -*- coding: utf-8 -*-
"""Generate batch-007 decisions JSONL for ial-psychology from the locked decision table.

Reads tmp_jev_psy007.jsonl (Jev round-2 results) for confidences, writes
.data/tagging/review-export/ial-psychology/decisions/batch-007.jsonl
"""

import json

JEV = 'C:/Users/weo/Desktop/api/examdata/tmp_jev_psy007.jsonl'
OUT = ('C:/Users/weo/Desktop/api/examdata/.data/tagging/review-export/'
       'ial-psychology/decisions/batch-007.jsonl')

jev = {r['question_id']: r for r in map(json.loads, open(JEV, encoding='utf-8'))}
assert len(jev) == 43, len(jev)


def c(qid):
    return f"{jev[qid]['confidence']:.2f}"


# (qid, decision, code or None, reason)
TABLE = [
    (65939, 'change', 'WPS02-4.1.2',
     f"初级强化物识别属操作性条件作用强化类型；Jev 判定 4.1.2（置信度 {c(65939)}）。"),
    (65977, 'keep', None,
     "WPS02 无抽样知识点，现标签为最近可用点；先例 65277 同标签已复核，保留。"),
    (65998, 'change', 'WPS01-1.2.6',
     f"量化数据分析（计算）；Jev 判定 1.2.6（置信度 {c(65998)}）。"),
    (65999, 'change', 'WPS01-1.2.6',
     f"量化数据分析（计算）；Jev 判定 1.2.6（置信度 {c(65999)}）。"),
    (66006, 'change', 'WPS01-2.2.11',
     "认知记忆场景数据题（Condition A 均值）；Jev 误归 1.2.6，按已复核先例 64940/64941/65854/64865 归 2.2.11。"),
    (66030, 'change', 'WPS04-9.1.2',
     f"随机抽样方法属抽样技术（9.1.2）；Jev 判定 9.1.2（置信度 {c(66030)}），丢弃错误 8.4.1。"),
    (66036, 'change', 'WPS04-9.1.11',
     f"数据表解读属描述统计（9.1.11）；Jev 判定 9.1.11（置信度 {c(66036)}），丢弃 9.1.7。"),
    (66040, 'change', 'WPS04-9.1.13',
     f"效度改进属方法论问题（9.1.13）；Jev 判定 9.1.13（置信度 {c(66040)} 低置信），与已复核先例 65094 一致，采纳。"),
    (66042, 'keep', None,
     f"20 分论文题；Jev 判定 9.3.4（置信度 {c(66042)} 低置信）与现标签一致，保留。"),
    (66057, 'change', 'WPS03-6.3.1',
     f"志愿者抽样实施属犯罪心理学研究方法运用（6.3.1）；Jev 判定 6.3.1（置信度 {c(66057)}）。"),
    (66058, 'change', 'WPS03-6.3.3',
     "量化数据优点属数据决策与解读（6.3.3）；Jev 误归 7.3.1，参照先例 64778 归数据决策族。"),
    (66059, 'change', 'WPS03-6.3.3',
     "质性数据优点属数据决策与解读（6.3.3）；Jev 误归 6.3.4，参照先例 64778 归数据决策族。"),
    (66067, 'change', 'WPS03-7.3.1',
     f"志愿者抽样实施属健康心理学研究方法运用（7.3.1）；Jev 判定 7.3.1（置信度 {c(66067)}）。"),
    (66068, 'change', 'WPS03-7.3.3',
     "量化数据优点属数据决策与解读（7.3.3）；Jev 误归 7.3.1，参照先例 64778 归数据决策族。"),
    (66069, 'change', 'WPS03-7.3.3',
     "质性数据优点属数据决策与解读（7.3.3）；Jev 误归 7.3.1，参照先例 64778 归数据决策族。"),
    (66103, 'change', 'WPS03-5.3.1',
     f"问卷开放题设计属研究方法运用（5.3.1）；Jev 判定 5.3.1（置信度 {c(66103)}）。"),
    (66104, 'change', 'WPS03-5.3.1',
     f"机会抽样实施属研究方法运用（5.3.1）；Jev 判定 5.3.1（置信度 {c(66104)}）。"),
    (66106, 'change', 'WPS03-5.3.1',
     f"问卷改进属研究方法运用（5.3.1）；Jev 判定 5.3.1（置信度 {c(66106)}）。"),
    (66111, 'change', 'WPS03-6.3.1',
     f"实验设计描述属犯罪心理学研究方法运用（6.3.1）；Jev 判定 6.3.1（置信度 {c(66111)}）。"),
    (66112, 'change', 'WPS03-6.3.3',
     f"均值计算属数据决策与解读（6.3.3）；Jev 判定 6.3.3（置信度 {c(66112)}）。"),
    (66113, 'change', 'WPS03-6.3.3',
     f"百分比计算属数据决策与解读（6.3.3）；Jev 判定 6.3.3（置信度 {c(66113)}）。"),
    (66114, 'change', 'WPS03-6.3.3',
     f"卡方检验选择属数据决策与解读（6.3.3）；Jev 判定 6.3.3（置信度 {c(66114)}）。"),
    (66115, 'change', 'WPS03-6.3.3',
     f"显著性判断属数据决策与解读（6.3.3）；Jev 判定 6.3.3（置信度 {c(66115)}）。"),
    (66122, 'change', 'WPS03-7.3.1',
     f"实验设计描述属健康心理学研究方法运用（7.3.1）；Jev 判定 7.3.1（置信度 {c(66122)}）。"),
    (66123, 'change', 'WPS03-7.3.3',
     f"均值计算属数据决策与解读（7.3.3）；Jev 判定 7.3.3（置信度 {c(66123)}）。"),
    (66126, 'change', 'WPS03-7.3.3',
     f"显著性判断属数据决策与解读（7.3.3）；Jev 判定 7.3.3（置信度 {c(66126)}）。"),
    (66150, 'change', 'WPS04-9.1.11',
     f"分布类型识别属描述统计（9.1.11）；Jev 判定 9.1.11（置信度 {c(66150)}）。"),
    (66154, 'change', 'WPS04-8.3.4',
     "从数据/结果得出结论属数据决策与解读（8.3.4）；Jev 9.1.11 不采纳，先例 61268/64361。"),
    (66170, 'change', 'WPS02-3.3.3',
     f"自选当代研究结果描述；本题 rubric 列 McDermott(3.3.3) 与 Hoefelmann(3.3.4) 二选一，单码取 3.3.3；Jev 判定 3.3.3（置信度 {c(66170)}）。"),
    (66180, 'change', 'WPS02-4.1.4',
     f"弗洛伊德性心理阶段属精神动力学取向（4.1.4）；Jev 判定 4.1.4（置信度 {c(66180)}），丢弃错误 4.2.4。"),
    (66196, 'keep', None,
     "WPS02 无 IV/DV 实验设计节点，现标签为最近可用点；先例 64643/64952，保留。"),
    (66203, 'change', 'WPS02-3.1.5',
     f"疗法弱点属节律障碍疗法（3.1.5）；Jev 判定 3.1.5（置信度 {c(66203)}）。"),
    (66209, 'keep', None,
     f"Jev 判定 4.1.2（置信度 {c(66209)}）与现标签一致，保留。"),
    (66214, 'change', 'WPS02-4.2.1',
     f"频次表用于观察数据收集（4.2.1）；Jev 判定 4.2.1（置信度 {c(66214)}）。"),
    (66241, 'keep', None,
     f"Jev 判定 9.1.11（置信度 {c(66241)}）与现标签一致，保留。"),
    (66257, 'change', 'WPS03-5.3.1',
     f"随机抽样实施属发展心理学研究方法运用（5.3.1）；Jev 判定 5.3.1（置信度 {c(66257)}）。"),
    (66258, 'change', 'WPS03-5.3.1',
     f"随机抽样弱点属研究方法运用（5.3.1）；Jev 判定 5.3.1（置信度 {c(66258)}）。"),
    (66259, 'change', 'WPS03-5.3.4',
     f"威尔科克森检验选择属数据决策与解读（5.3.4）；Jev 判定 5.3.4（置信度 {c(66259)}），丢弃 6.3.1。"),
    (66262, 'change', 'WPS03-5.4.1',
     f"依恋研究伦理属研究伦理（5.4.1）；Jev 判定 5.4.1（置信度 {c(66262)}），丢弃 5.1.2。"),
    (66268, 'change', 'WPS03-6.3.3',
     f"极差计算属数据决策与解读（6.3.3）；Jev 判定 6.3.3（置信度 {c(66268)}）。"),
    (66270, 'change', 'WPS03-6.3.4',
     f"研究改进评价属犯罪心理学研究评估（6.3.4）；Jev 判定 6.3.4（置信度 {c(66270)}）。"),
    (66281, 'change', 'WPS03-7.3.3',
     f"极差计算属数据决策与解读（7.3.3）；Jev 判定 7.3.3（置信度 {c(66281)}）。"),
    (66283, 'change', 'WPS03-7.3.4',
     f"研究改进评价属健康心理学研究评估（7.3.4）；Jev 判定 7.3.4（置信度 {c(66283)}）。"),
]

assert len(TABLE) == 43
assert len({q for q, _, _, _ in TABLE}) == 43

follows, overrides = [], []
for qid, dec, code, reason in TABLE:
    assert qid in jev, qid
    if dec == 'change':
        assert code and code.startswith(jev[qid]['unit'] + '-'), (qid, code)
        if jev[qid]['choice'] == code:
            follows.append(qid)
        else:
            overrides.append(qid)
    else:
        assert dec == 'keep' and code is None

print(f"follows {len(follows)} / overrides {len(overrides)} {overrides} / keeps "
      f"{len([1 for _, d, _, _ in TABLE if d == 'keep'])}")

lines = []
for qid, dec, code, reason in sorted(TABLE, key=lambda r: r[0]):
    row = {'question_id': qid, 'decision': dec}
    if code:
        row['code'] = code
    row['reason'] = reason
    lines.append(json.dumps(row, ensure_ascii=False, separators=(',', ':')))

with open(OUT, 'w', encoding='utf-8') as handle:
    handle.write('\n'.join(lines) + '\n')
print('wrote', OUT, len(lines), 'rows')
