# -*- coding: utf-8 -*-
"""S07: 把 45 条答案裁决从历史证据 JSON 迁移为 ielts-api/adjudications.mjs。

输入（只读）：tmp_audit_ielts/repair-20261003-152644/answer_adjudications.json
输出：ielts-api/adjudications.mjs（含 DECISIONS 结构化副本 + 应用函数）

迁移规则：
- 每条 decision 保留完整 identity、from/to、PDF 哈希/页、理由、验证者类型/方法、时间；
- 原值守卫由 applyAdjudications 执行（from 不匹配 -> decision_stale，不强套）；
- 分类字段按 category 补充 book_value / equivalents / artifact_values / mapping / group。
"""
import json
import os
import sys

ROOT = r"C:/Users/weo/Desktop/api"
SRC = os.path.join(ROOT, "tmp_audit_ielts/repair-20261003-152644/answer_adjudications.json")
OUT = os.path.join(ROOT, "ielts-api/adjudications.mjs")

PDF_SHA = {
    4: "b254324578e8f7a5187810aa36f5e1bf3049537b49bd7cc2c34fc2c963185bed",
    5: "852607dd3c8aa7e0d7cd6d66cae312337696997635902629fcadbf65c12eef5a",
    6: "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573",
    7: "a219bf469ba75c39938a2a9d8bfd4bf15caf206e8c249d70d188ff4e36ad3b00",
    12: "f791300937f11d8380eba7b7997db1da751d66802a96aed996db704947e52407",
    17: "90ae888c4cd495761fe5639418ca894e63c9e7066382ed9ffad6bd74a409726a",
}

# order_semantics 组的显式集合（来自各裁决条目 basis 中的官方键列分析）
GROUP_SPECS = {
    (5, 2, 18): {"input_numbers": [18, 19, 20], "accepted_sets": [["C", "E", "F"]]},
    (5, 2, 19): {"input_numbers": [18, 19, 20], "accepted_sets": [["C", "E", "F"]]},
    (5, 2, 20): {"input_numbers": [18, 19, 20], "accepted_sets": [["C", "E", "F"]]},
    (5, 3, 11): {"input_numbers": [11, 12], "accepted_sets": [["C", "E"]]},
    (5, 3, 12): {"input_numbers": [11, 12], "accepted_sets": [["C", "E"]]},
    (6, 1, 38): {"input_numbers": [38, 39, 40], "accepted_sets": [["C", "E", "F"]]},
    (6, 1, 39): {"input_numbers": [38, 39, 40], "accepted_sets": [["C", "E", "F"]]},
    (6, 1, 40): {"input_numbers": [38, 39, 40], "accepted_sets": [["C", "E", "F"]]},
    (6, 2, 18): {"input_numbers": [18, 19, 20], "accepted_sets": [["C", "D", "G"]]},
    (6, 2, 19): {"input_numbers": [18, 19, 20], "accepted_sets": [["C", "D", "G"]]},
    (6, 2, 20): {"input_numbers": [18, 19, 20], "accepted_sets": [["C", "D", "G"]]},
    (6, 4, 28): {"input_numbers": [28, 29, 30], "accepted_sets": [["C", "E", "F"]]},
    (6, 4, 29): {"input_numbers": [28, 29, 30], "accepted_sets": [["C", "E", "F"]]},
    (6, 4, 30): {"input_numbers": [28, 29, 30], "accepted_sets": [["C", "E", "F"]]},
}
# 12-1 Q14 特殊：官方键 Q14='C'；同页 Q15&16 'IN EITHER ORDER' 组被提取器并入 Q14 行
SPECIAL_12_1 = {
    "input_numbers": [15, 16],
    "accepted_sets": [["A", "E"]],
    "note": "Q15&16 IN EITHER ORDER；提取器把该组并入 Q14 行（行 [031]-[036]）",
}

METHOD_BY_CATEGORY = {
    "option_mapping": "官方答案页选项表逐条映射核对（book4_p16/p17_options.txt）",
    "order_semantics": "官方答案键垂直堆叠列分析（dumpfull_*.txt 行/列坐标）",
    "extraction_artifact": "官方 PDF 渲染视觉核对（visual_batchA/B.png）",
    "representation": "官方 PDF 渲染视觉核对（visual_batchA/B.png）",
    "source_error": "官方答案页 + 官方原文行交叉核验（视觉批 + dumpfull + 原文）",
}


def enrich(i, it):
    b, t, q = it["book"], it["test"], it["question"]
    cat = it["category"]
    d = {
        "id": "adj-%02d" % (i + 1),
        "identity": {"book": b, "test": t, "skill": "listening", "question": q, "group_id": None},
        "category": cat,
        "action": it["action"],
        "status": it["status"],
        "origin": it["origin"],
        "official_extracted": it["official_extracted"],
        "source": it["source"],
        "source_value": it["source_value"],
        "page_raw_value": it["page_raw_value"],
        "basis": it["basis"],
        "pdf": {
            "file": "tmp_audit_ielts/downloads/book_%d.pdf" % b,
            "page": it["pdf_page"],
            "sha256": PDF_SHA.get(b),
        },
        "verifier": {
            "type": "independent_visual_review",
            "method": METHOD_BY_CATEGORY.get(cat, "独立复审"),
            "at": "2026-10-03T17:12:00+08:00",
        },
        "from": None,
        "to": None,
        "book_value": None,
        "equivalents": [],
        "artifact_values": [],
        "mapping": None,
        "group": None,
    }
    if cat == "source_error":
        d["from"] = it["source_value"]
        d["to"] = it["official_extracted"]
        d["book_value"] = it["official_extracted"]
    elif cat == "option_mapping":
        d["book_value"] = it["official_extracted"]
        d["equivalents"] = [it["source_value"]]
        d["mapping"] = {"letter": it["official_extracted"], "option_text": it["source_value"], "options_ref": it["page_raw_value"]}
    elif cat == "order_semantics":
        d["book_value"] = it["source_value"]
        d["equivalents"] = [it["source_value"]]
        d["artifact_values"] = [it["official_extracted"]]
    elif cat == "extraction_artifact":
        d["book_value"] = it["page_raw_value"]
        d["equivalents"] = [it["source_value"]]
        d["artifact_values"] = [it["official_extracted"]]
    elif cat == "representation":
        d["book_value"] = it["page_raw_value"]
        d["equivalents"] = [it["source_value"]]
        d["artifact_values"] = [it["official_extracted"]]
    # 组语义
    g = GROUP_SPECS.get((b, t, q))
    if g:
        gid = "g-%d-%d-%d-%d" % (b, t, g["input_numbers"][0], g["input_numbers"][-1])
        d["identity"]["group_id"] = gid
        d["group"] = {
            "group_id": gid,
            "input_numbers": g["input_numbers"],
            "accepted_sets": g["accepted_sets"],
            "required_count": len(g["input_numbers"]),
            "ordered": False,
            "allow_reuse": False,
            "scoring": "exact_set",
        }
    if (b, t, q) == (12, 1, 14):
        gid = "g-12-1-15-16"
        d["group"] = {
            "group_id": gid,
            "input_numbers": SPECIAL_12_1["input_numbers"],
            "accepted_sets": SPECIAL_12_1["accepted_sets"],
            "required_count": 2,
            "ordered": False,
            "allow_reuse": False,
            "scoring": "exact_set",
            "note": SPECIAL_12_1["note"],
        }
    return d


def main():
    with open(SRC, encoding="utf-8") as f:
        src = json.load(f)
    decisions = [enrich(i, it) for i, it in enumerate(src["items"])]
    meta = {
        "source_file": "tmp_audit_ielts/repair-20261003-152644/answer_adjudications.json",
        "source_generated_at": src["generated_at"],
        "source_generated_by": src["generated_by"],
        "purpose": src["purpose"],
        "summary": src["summary"],
        "sources": src["sources"],
        "pdf_sha256": {("book_%d.pdf" % k): v for k, v in sorted(PDF_SHA.items())},
        "migrated_at": "2026-10-04",
        "migrated_by": "S07 gen-adjudications.py（结构化副本，不修改历史证据）",
    }
    dec_json = json.dumps(decisions, ensure_ascii=False, indent=2)
    meta_json = json.dumps(meta, ensure_ascii=False, indent=2)

    header = '''/**
 * adjudications.mjs — S07: 答案裁决的结构化迁移（45 条裁决 = 43 条 diff + 2 条被比较器
 * 单字母子串 bug 掩盖的独立补验项；其中 7 条窄修正 action=correct）。
 *
 * 源（只读历史证据，不修改）：
 *   tmp_audit_ielts/repair-20261003-152644/answer_adjudications.json（2026-10-03T17:12+08:00 生成）
 * 语义：对 practicepteonline 来源值与官方 PDF 答案键（视觉核验）逐条裁决。
 *
 * 迁移规则（S07 算法第 8 条）：
 *  - 每条 decision 含完整 identity（book/test/skill/question[/group]）、from/to、PDF sha256/页、
 *    理由（basis）、验证者类型与方法、时间；
 *  - 应用时以完整 identity + 原值守卫（当前值 === from）为准；上游值变动 -> decision_stale，
 *    保留旧记录、不强套修正；
 *  - book_value 为该题核验后的书内值（选项字母/集合/印刷值）；equivalents 为裁决明确允许的
 *    等价来源形式；artifact_values 为提取器字形伪影（不得当作官方值）；mapping 为字母↔选项文本。
 *  - 本模块不修改来源解析器；由 ielts-api.mjs 与 answer-matcher.mjs 在展示/比较层消费。
 */

export const ADJUDICATIONS_META = '''
    footer = ''';

/** 45 条裁决的结构化副本（顺序与源文件 items 一致） */
export const DECISIONS = ''' + dec_json + ''';

/** 按完整 identity 过滤（book/test 必填；skill 默认 listening） */
export function decisionsFor(book, test, opts = {}) {
  const skill = opts.skill || "listening";
  return DECISIONS.filter(
    (d) => d.identity.book === Number(book) && d.identity.test === Number(test) && (!d.identity.skill || d.identity.skill === skill)
  );
}

/** 单题裁决（无则 null） */
export function decisionForQuestion(book, test, question, opts = {}) {
  return decisionsFor(book, test, opts).find((d) => d.identity.question === Number(question)) || null;
}

/** 按裁决条目 id 取（测试用） */
export function decisionById(id) {
  return DECISIONS.find((d) => d.id === id) || null;
}

/** 组裁决：group_id -> group spec（仅含 group 的裁决条目） */
export function groupDecisionsFor(book, test, opts = {}) {
  const out = new Map();
  for (const d of decisionsFor(book, test, opts)) {
    if (d.group) out.set(d.group.group_id, { ...d.group, decision_id: d.id, question: d.identity.question });
  }
  return out;
}

/** number -> {from,to,basis,decision_id}（仅 action=correct 的窄修正） */
export function correctionsFor(book, test, opts = {}) {
  const out = new Map();
  for (const d of decisionsFor(book, test, opts)) {
    if (d.action === "correct" && d.from != null) {
      out.set(d.identity.question, { from: d.from, to: d.to, basis: d.basis, decision_id: d.id });
    }
  }
  return out;
}

/**
 * 应用裁决窄修正到 pte 结果形状（{ok, answer_key, questions[]}）。
 * 非破坏性：仅当当前值 === from 时替换；from 不匹配 -> adjudication_stale（保留旧值，不强套）。
 * 返回带 answer_corrections / adjudication_stale 的新对象（无变化时原样返回）。
 */
export function applyAdjudications(book, test, r) {
  const corrections = correctionsFor(book, test);
  if (!corrections.size || !r || !r.ok || !Array.isArray(r.answer_key)) return r;
  const applied = [];
  const stale = [];
  const answer_key = r.answer_key.map((v, i) => {
    const c = corrections.get(i + 1);
    if (!c) return v;
    if (v === c.from) {
      applied.push({ question: i + 1, from: c.from, to: c.to, basis: c.basis, decision_id: c.decision_id });
      return c.to;
    }
    stale.push({ question: i + 1, decision_id: c.decision_id, expected_from: c.from, actual: v, reason: "upstream_value_changed" });
    return v;
  });
  const questions = Array.isArray(r.questions)
    ? r.questions.map((q) => {
        const c = corrections.get(q.number);
        if (c && q.answer === c.from) return { ...q, answer: c.to, answer_decision_id: c.decision_id };
        return q;
      })
    : r.questions;
  if (!applied.length && !stale.length) return r;
  const out = { ...r, answer_key, questions };
  if (applied.length) out.answer_corrections = applied;
  if (stale.length) out.adjudication_stale = stale;
  return out;
}
'''
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(header + meta_json + footer)
    print("wrote", OUT, "decisions:", len(decisions))


if __name__ == "__main__":
    main()
