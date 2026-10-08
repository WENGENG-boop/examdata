/**
 * answer-matcher.mjs — S07: 题目—答案连接、规范化比较与冲突裁决算法
 *
 * 固定接口：matchAnswers({questions, groups, answerCandidates, identity, expected, decisions})
 * 返回：每题/组答案、状态、rule_id、候选、source_refs、conflicts、coverage。
 *
 * 算法顺序（S07 计划固定）：
 *  1. identity gate：edition/book/variant/skill/test 完全一致 + 题号在 expected 及其 group；
 *     不一致候选拒绝并保留 rejection 原因；源标签缺版次 -> unverified，不跨版本自动串联。
 *  2. 显式 number / group.inputs 关联；顺序答案仅当容器顺序已验证、start/value 正确、空位保留、
 *     长度符合 manifest 时挂接；否则 order_unverified，不靠下一个非空值补位。
 *  3. 保存 raw；规范化只做 NFKC/trim/重复空白/弯引号/可配置大小写；可选词、单复数、数字/单位、
 *     日期变体必须来自答案键明确允许形式或可追溯规则（本模块：括号可选词与斜杠备选总是展开；
 *     数字/单词、日期变体为显式 opt-in，默认关闭）。
 *  4. 选择题字母仅与题组 options 标签严格比较；文本映射字母需与选项全文规范化相等且唯一；
 *     禁止单字母子串与 token 子集判正确。
 *  5. TFNG 与 YNNG 分别标准化枚举；Roman heading 标签单独处理（单字符比较不加宽）。
 *  6. 多选/无序配对保存 group_id/input_numbers/accepted_sets/required_count/ordered/allow_reuse/scoring；
 *     无序按集合/多重集合比较（不排序后硬分配唯一题号）；组计一次但 covered_numbers 按各 slot 算。
 *  7. 来源优先级：视觉核验原书键/裁决 > 已核验版次结构化来源 > 未核验；OCR 候选不因名叫 official
 *     就覆盖；冲突未裁决前 status=conflict；多镜像同一上游不算独立双源。
 *  8. 45 条裁决按完整 identity + 原值守卫应用；上游值变动 -> decision_stale，保留旧记录不强套。
 *
 * 状态语义（区分）：
 *  - identity_linked：题号连接成功（不等于答案正确）
 *  - source_verified：来源结构与身份检查通过
 *  - official_verified：独立原书（视觉）核验或已裁决
 *  - conflict / order_unverified / unverified / missing / decision_stale
 */

import { decisionsFor } from "./adjudications.mjs";

export const ANSWER_STATUS = [
  "identity_linked", "source_verified", "official_verified",
  "conflict", "order_unverified", "unverified", "missing", "decision_stale",
];

export const RULES = {
  IDENTITY_GATE: "identity_gate",
  EXPLICIT_NUMBER: "explicit_number",
  SEQUENTIAL_VERIFIED: "sequential_verified",
  ORDER_UNVERIFIED: "order_unverified",
  DECISION_CORRECTION: "decision_correction",
  DECISION_CONFIRMED: "decision_confirmed",
  DECISION_STALE: "decision_stale",
  MCQ_LETTER_MAP: "mcq_letter_map",
  GROUP_ACCEPTED_SET: "group_accepted_set",
  CONFLICT: "conflict_unresolved",
  MISSING: "missing_no_candidate",
  UNVERIFIED: "source_unverified",
};

/* ============================ 规范化与比较 ============================ */

/** 规范化：NFKC、弯引号/破折号归一、trim、重复空白折叠、可配置大小写（默认不区分大小写）。 */
export function normalizeAnswer(value, opts = {}) {
  if (value == null) return "";
  let s = String(value);
  s = s.normalize("NFKC");
  s = s.replace(/[\u2018\u2019\u201A\u201B]/g, "'").replace(/[\u201C\u201D\u201E\u201F]/g, '"');
  s = s.replace(/[\u2013\u2014]/g, "-");
  s = s.replace(/\s+/g, " ").trim();
  if (opts.caseInsensitive !== false) s = s.toLowerCase();
  return s;
}

/**
 * 展开答案键的显式允许形式：
 *  - 括号内可选词（"(a) dentist" -> "a dentist" / "dentist"）；括号内斜杠为备选（"(out/the)"）；
 *  - 括号外 " / "（两侧带空格）为备选（"beach / beaches"），不拆日期数字（无空格斜杠不拆）。
 * 返回去重后的候选字符串数组（含原值）。不做模糊纠错。
 */
export function expandVariants(value) {
  const s = String(value ?? "");
  const out = new Set();
  const walk = (str) => {
    const m = /\(([^()]*)\)/.exec(str);
    if (m) {
      const before = str.slice(0, m.index);
      const after = str.slice(m.index + m[0].length);
      const alts = m[1].split("/").map((x) => x.trim()).filter(Boolean);
      if (alts.length === 0) { walk(before + after); return; }
      for (const alt of alts) walk(before + alt + after);
      walk((before + after).replace(/\s+/g, " "));
      return;
    }
    const parts = str.split(" / ");
    if (parts.length > 1) { for (const p of parts) out.add(p.trim()); return; }
    out.add(str.replace(/\s+/g, " ").trim());
  };
  walk(s);
  out.add(s);
  return [...out].filter((x) => x !== "");
}

const NUMBER_WORDS = {
  zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9,
  ten: 10, eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16,
  seventeen: 17, eighteen: 18, nineteen: 19, twenty: 20, thirty: 30, forty: 40, fifty: 50,
  sixty: 60, seventy: 70, eighty: 80, ninety: 90, hundred: 100, thousand: 1000,
};

/** 数字/单词的规范化形式（仅当显式启用 numberWord 时使用）："6" 与 "six" -> "6"。 */
export function numberWordForm(value) {
  const s = normalizeAnswer(value);
  if (/^\d{1,3}(,\d{3})+$/.test(s)) return s.replace(/,/g, "");
  if (/^\d+$/.test(s)) return String(Number(s));
  if (Object.prototype.hasOwnProperty.call(NUMBER_WORDS, s)) return String(NUMBER_WORDS[s]);
  return null;
}

/** 日期规范化形式（仅当显式启用 dateVariants 时使用）：dd.mm.yyyy / dd-mm-yyyy -> yyyy-mm-dd。 */
export function dateForm(value) {
  const s = normalizeAnswer(value);
  const m = /^(\d{1,4})[.\-/](\d{1,2})[.\-/](\d{1,4})$/.exec(s);
  if (!m) return null;
  const a = Number(m[1]), b = Number(m[2]), c = Number(m[3]);
  let y, mo, d;
  if (m[1].length === 4) { y = a; mo = b; d = c; }
  else { d = a; mo = b; y = c; }
  if (mo < 1 || mo > 12 || d < 1 || d > 31) return null;
  return `${String(y).padStart(4, "0")}-${String(mo).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

/** TFNG / YNNG 家族内标准化（不互相混同；Roman heading 不在此处理）。 */
export function normalizeChoice(value, family) {
  const s = normalizeAnswer(value);
  if (family === "tfng") {
    if (s === "t" || s === "true") return "true";
    if (s === "f" || s === "false") return "false";
    if (s === "ng" || s === "not given" || s === "notgiven") return "not given";
    return s;
  }
  if (family === "ynng") {
    if (s === "y" || s === "yes") return "yes";
    if (s === "n" || s === "no") return "no";
    if (s === "ng" || s === "not given" || s === "notgiven") return "not given";
    return s;
  }
  return s;
}

/** 从题组指令/类型推断 TFNG/YNNG 家族（未知 -> null，按普通文本比较）。 */
export function choiceFamilyOf(text) {
  const s = String(text || "").toUpperCase();
  if (/\bTRUE\b/.test(s) || /\bFALSE\b/.test(s)) return "tfng";
  if (/\bYES\b/.test(s) || /\bNO\b/.test(s)) return "ynng";
  return null;
}

/**
 * 严格比较两个答案（规范化 + 显式允许形式 + 可选变体族）。
 * 禁止：单字母子串、token 子集、任意删词/单位/数字、模糊纠错。
 * opts:
 *  - caseInsensitive（默认 true）
 *  - allowedVariantsA / allowedVariantsB：该答案键明确允许的等价形式
 *  - numberWord（默认 false）：数字与英文单词等价（可追溯规则表）
 *  - dateVariants（默认 false）：日期分隔符/补零等价
 *  - family：'tfng' | 'ynng'（由题组决定）
 */
export function compareAnswers(a, b, opts = {}) {
  const na0 = normalizeAnswer(a, opts);
  const nb0 = normalizeAnswer(b, opts);
  const fam = opts.family || null;
  const na = fam ? normalizeChoice(a, fam) : na0;
  const nb = fam ? normalizeChoice(b, fam) : nb0;
  if (!na || !nb) return { equal: false, reason: "empty", a: na, b: nb };
  if (na === nb) return { equal: true, reason: "exact", a: na, b: nb };
  // 单字母保护：单字符不得与多字符判等（防 "E" vs "read research methods" 类假匹配）
  const singleA = /^[a-z]$/i.test(na);
  const singleB = /^[a-z]$/i.test(nb);
  if (singleA !== singleB) return { equal: false, reason: "single_letter_mismatch", a: na, b: nb };
  // 答案键显式允许形式（括号可选词 / 斜杠备选）
  const setA = new Set(expandVariants(String(a ?? "")).map((v) => normalizeAnswer(v, opts)));
  const setB = new Set(expandVariants(String(b ?? "")).map((v) => normalizeAnswer(v, opts)));
  for (const x of setA) if (setB.has(x)) return { equal: true, reason: "variant", a: x, b: x };
  // 明确声明的 allowed_variants（来自答案键或裁决等价形式）
  const avA = (opts.allowedVariantsA || []).map((v) => normalizeAnswer(v, opts));
  const avB = (opts.allowedVariantsB || []).map((v) => normalizeAnswer(v, opts));
  if (avA.includes(nb) || avB.includes(na)) return { equal: true, reason: "allowed_variant", a: na, b: nb };
  // 可选变体族（默认关闭；显式 opt-in 才启用）
  if (opts.numberWord) {
    const fa = numberWordForm(na), fb = numberWordForm(nb);
    if (fa && fb && fa === fb) return { equal: true, reason: "number_word", a: fa, b: fb };
  }
  if (opts.dateVariants) {
    const da = dateForm(na), db = dateForm(nb);
    if (da && db && da === db) return { equal: true, reason: "date_variant", a: da, b: db };
  }
  return { equal: false, reason: "mismatch", a: na, b: nb };
}

/* ============================ 组比较 ============================ */

/**
 * 组答案比较（无序按集合/多重集合；有序逐位置）。
 * spec: {required_count, ordered, allow_reuse, scoring}
 *  - ordered=true：逐位置比较（数量必须一致）
 *  - ordered=false：数量必须等于 required_count；allow_reuse=false 时按集合（拒绝重复），
 *    allow_reuse=true 时按多重集合
 *  - scoring='any_of'：提交中任意一个命中 accepted 集合即通过（任选，非 both required）
 */
export function compareGroupAnswer(submitted, acceptedSets, spec = {}) {
  const required = spec.required_count != null ? spec.required_count : null;
  const ordered = spec.ordered === true;
  const allowReuse = spec.allow_reuse === true;
  const scoring = spec.scoring || (ordered ? "per_slot" : "exact_set");
  const normList = (arr) => (Array.isArray(arr) ? arr : [arr]).map((v) => normalizeAnswer(v));
  const sets = (acceptedSets || []).map(normList);
  const sub = normList(submitted);
  if (scoring === "any_of") {
    const hit = sets.some((s) => sub.some((x) => s.includes(x)));
    return { pass: hit, reason: hit ? "any_of_hit" : "any_of_miss", submitted: sub, accepted_sets: sets };
  }
  if (required != null && sub.length !== required) {
    return { pass: false, reason: "count_mismatch", submitted: sub, required_count: required, accepted_sets: sets };
  }
  const matchAgainst = (s) => {
    if (ordered) {
      if (sub.length !== s.length) return false;
      return sub.every((x, i) => x === s[i]);
    }
    if (allowReuse) {
      const a = [...sub].sort(), b = [...s].sort();
      return a.length === b.length && a.every((x, i) => x === b[i]);
    }
    const sa = new Set(sub), sb = new Set(s);
    if (sa.size !== sub.length) return false; // 重复且不允许复用 -> 拒绝
    return sa.size === sb.size && [...sa].every((x) => sb.has(x));
  };
  const pass = sets.some(matchAgainst);
  return { pass, reason: pass ? (ordered ? "ordered_match" : "set_match") : "set_mismatch", submitted: sub, accepted_sets: sets };
}

/* ============================ matchAnswers 主体 ============================ */

const asArray = (x) => (Array.isArray(x) ? x : x == null ? [] : [x]);

function normIdentity(id) {
  if (!id || typeof id !== "object") return null;
  const out = {};
  for (const k of ["book", "test", "skill", "variant", "edition"]) {
    if (id[k] != null && id[k] !== "") out[k] = k === "book" || k === "test" ? Number(id[k]) : String(id[k]);
  }
  return out;
}

/** identity gate：完整一致性检查，返回 {ok, reason, editionUnverified} */
function gateIdentity(callId, candId) {
  if (!candId) return { ok: false, reason: "identity_missing" };
  for (const k of ["book", "test", "skill"]) {
    if (candId[k] == null) return { ok: false, reason: "identity_incomplete", field: k };
    if (callId[k] != null && String(candId[k]) !== String(callId[k])) {
      return { ok: false, reason: `identity_${k}_mismatch`, expected: callId[k], actual: candId[k] };
    }
  }
  for (const k of ["variant", "edition"]) {
    if (candId[k] != null && callId[k] != null && String(candId[k]) !== String(callId[k])) {
      return { ok: false, reason: `identity_${k}_mismatch`, expected: callId[k], actual: candId[k] };
    }
  }
  const editionUnverified = callId.edition != null && candId.edition == null;
  return { ok: true, editionUnverified };
}

function priorityOf(c) {
  const cls = c.source_class || "structured_source";
  if (cls === "adjudication") return 1;
  if (c.visual_verified === true && (cls === "official_pdf" || cls === "official" || cls === "official_visual")) return 1;
  if (c.ocr === true && c.visual_verified !== true) return Math.max(3, c.verified ? 3 : 3);
  if (c.verified === true) return 2;
  return 3;
}

function statusFromCandidate(cand) {
  if (cand.priority === 1) return "official_verified";
  if (cand.decision_applied || cand.decision_confirmed) return "official_verified";
  if (cand.editionUnverified) return "unverified";
  if (cand.priority === 2) return "source_verified";
  return cand.verified ? "source_verified" : "identity_linked";
}

/**
 * 主入口。
 * @param {object} input
 *  - questions: [{number, group?, kind?, options?, prompt?}]
 *  - groups: 解析出的题组 [{group_id?|index?, numbers|range, options?, instruction?, kind?}]
 *  - answerCandidates: 候选来源数组：
 *      {source, source_class?, upstream?, identity?, verified?, visual_verified?, ocr?, source_ref?,
 *       kind:'numbered', entries:[{number, value, raw?, source_ref?}]}
 *      {kind:'answer_key_array', values:[...], start?, range?, order_verified?}
 *      {kind:'group', group_id, input_numbers, accepted_sets, required_count?, ordered?, allow_reuse?, scoring?}
 *  - identity: {book, test, skill, variant?, edition?}
 *  - expected: {numbers:[...], groups?:[{group_id?, input_numbers, accepted_sets?, required_count?, ordered?, allow_reuse?, scoring?}], source?}
 *    或直接数字数组
 *  - decisions: 覆盖默认（默认按 identity 从 adjudications.mjs 取）
 */
export function matchAnswers({ questions, groups, answerCandidates, identity, expected, decisions } = {}) {
  const callId = normIdentity(identity);
  if (!callId || callId.book == null || callId.test == null || callId.skill == null) {
    return { ok: false, error: "identity requires book/test/skill", identity: callId };
  }
  const expObj = Array.isArray(expected) ? { numbers: expected.slice() } : expected && typeof expected === "object" ? expected : null;
  const expectedNumbers = expObj && Array.isArray(expObj.numbers) ? expObj.numbers.map(Number) : null;
  const expectedSet = expectedNumbers ? new Set(expectedNumbers) : null;
  const parsedQuestions = asArray(questions);
  const parsedGroups = asArray(groups).map((g, i) => {
    const numbers = asArray(g.numbers || (g.range ? rangeOf(g.range) : [])).map(Number);
    return {
      group_id: g.group_id != null ? String(g.group_id) : `g${g.index != null ? g.index : i}`,
      numbers,
      options: asArray(g.options),
      instruction: g.instruction || "",
      kind: g.kind || g.type || null,
      ordered: g.ordered,
      raw: g,
    };
  });
  const questionSlot = new Map();
  for (const q of parsedQuestions) if (q && q.number != null) questionSlot.set(Number(q.number), q);
  const questionGroupOf = new Map();
  for (const g of parsedGroups) for (const n of g.numbers) if (!questionGroupOf.has(n)) questionGroupOf.set(n, g);

  const decisionsList = Array.isArray(decisions)
    ? decisions
    : decisionsFor(callId.book, callId.test, { skill: callId.skill });

  const notes = [];
  const rejections = [];
  const perNumber = new Map(); // n -> [candidate]
  const groupResults = new Map(); // group_id -> result

  const pushCand = (n, cand) => {
    if (!perNumber.has(n)) perNumber.set(n, []);
    perNumber.get(n).push(cand);
  };

  for (const raw of asArray(answerCandidates)) {
    if (!raw || typeof raw !== "object") continue;
    const candId = normIdentity(raw.identity);
    const gate = gateIdentity(callId, candId);
    if (!gate.ok) {
      rejections.push({ source: raw.source || null, reason: gate.reason, field: gate.field, expected: gate.expected, actual: gate.actual, source_ref: raw.source_ref || null });
      continue;
    }
    const base = {
      source: raw.source || "unknown",
      source_class: raw.source_class || "structured_source",
      upstream: raw.upstream || raw.source || "unknown",
      priority: priorityOf(raw),
      verified: raw.verified === true,
      visual_verified: raw.visual_verified === true,
      ocr: raw.ocr === true,
      editionUnverified: gate.editionUnverified,
      source_ref: raw.source_ref || null,
      allowed_variants: asArray(raw.allowed_variants).map(String),
      raw_candidate: raw,
    };
    if (raw.kind === "group") {
      const spec = {
        group_id: raw.group_id != null ? String(raw.group_id) : null,
        input_numbers: asArray(raw.input_numbers).map(Number),
        accepted_sets: asArray(raw.accepted_sets).map((s) => asArray(s)),
        required_count: raw.required_count != null ? Number(raw.required_count) : null,
        ordered: raw.ordered === true,
        allow_reuse: raw.allow_reuse === true,
        scoring: raw.scoring || (raw.ordered === true ? "per_slot" : "exact_set"),
      };
      if (!spec.group_id || !spec.input_numbers.length || !spec.accepted_sets.length) {
        rejections.push({ source: base.source, reason: "group_spec_incomplete", source_ref: base.source_ref });
        continue;
      }
      const missing = expectedSet ? spec.input_numbers.filter((n) => !expectedSet.has(n)) : [];
      if (missing.length) {
        rejections.push({ source: base.source, reason: "group_numbers_not_expected", numbers: missing, source_ref: base.source_ref });
        continue;
      }
      // 组语义校验：所有 input 属于同一个已解析题组（若有解析题组）
      if (parsedGroups.length) {
        const gids = new Set(spec.input_numbers.map((n) => (questionGroupOf.get(n) || {}).group_id).filter(Boolean));
        if (gids.size === 0) {
          spec.group_unverified = true;
          notes.push({ kind: "group_not_in_parsed_groups", group_id: spec.group_id, source: base.source });
        } else if (gids.size > 1) {
          rejections.push({ source: base.source, reason: "group_numbers_split_across_groups", groups: [...gids], source_ref: base.source_ref });
          continue;
        }
      }
      const result = {
        group_id: spec.group_id,
        input_numbers: spec.input_numbers,
        accepted_sets: spec.accepted_sets,
        required_count: spec.required_count != null ? spec.required_count : spec.input_numbers.length,
        ordered: spec.ordered,
        allow_reuse: spec.allow_reuse,
        scoring: spec.scoring,
        status: spec.group_unverified || base.editionUnverified ? "unverified" : base.priority === 1 ? "official_verified" : base.priority === 2 ? "source_verified" : "identity_linked",
        rule_id: RULES.GROUP_ACCEPTED_SET,
        covered_numbers: spec.input_numbers.slice(),
        sources: [{ source: base.source, priority: base.priority, source_ref: base.source_ref }],
        conflicts: [],
      };
      const prev = groupResults.get(spec.group_id);
      if (!prev) groupResults.set(spec.group_id, result);
      else {
        // 同组多候选：accepted_sets 不一致且来源独立 -> conflict
        const same = JSON.stringify(prev.accepted_sets) === JSON.stringify(result.accepted_sets)
          && prev.required_count === result.required_count && prev.ordered === result.ordered;
        const independent = prev.sources.every((s) => s.source !== base.source);
        if (!same && independent) {
          prev.status = "conflict";
          prev.conflicts.push({ source: base.source, accepted_sets: result.accepted_sets, required_count: result.required_count, ordered: result.ordered, source_ref: base.source_ref });
        } else if (same) {
          prev.sources.push({ source: base.source, priority: base.priority, source_ref: base.source_ref });
          if (base.priority === 1) prev.status = "official_verified";
        }
      }
      continue;
    }
    if (raw.kind === "answer_key_array" || raw.kind === "sequential" || Array.isArray(raw.values)) {
      const values = asArray(raw.values);
      const nums = expectedNumbers;
      let orderOk = raw.order_verified === true;
      let orderReason = orderOk ? null : "container_order_unverified";
      if (orderOk && nums) {
        if (raw.range) {
          const [a, b] = raw.range;
          orderOk = a === nums[0] && b === nums[nums.length - 1] && values.length === nums.length;
        } else {
          orderOk = values.length === nums.length && (raw.start == null || Number(raw.start) === nums[0]);
        }
        if (!orderOk) orderReason = "length_or_start_mismatch";
      }
      if (!nums) { orderOk = false; orderReason = "expected_missing"; }
      if (!orderOk) {
        notes.push({ kind: "order_unverified", source: base.source, reason: orderReason, count: values.length, source_ref: base.source_ref });
        // 槽位范围已知时（range 或 start）如实标记这些槽为 order_unverified（不补位、不猜测）
        let covered = [];
        if (Array.isArray(raw.range)) covered = rangeOf(raw.range);
        else if (raw.start != null) { const st = Number(raw.start); covered = values.map((_, i) => st + i); }
        for (const n of covered) {
          if (expectedSet && !expectedSet.has(n)) continue;
          pushCand(n, { ...base, number: n, value: "", raw: "", empty: true, order_unverified: true, rule_id: RULES.ORDER_UNVERIFIED, entry_source_ref: base.source_ref });
        }
        continue;
      }
      values.forEach((v, i) => {
        const n = nums[i];
        const rawV = v == null ? "" : String(v);
        pushCand(n, {
          ...base, number: n, value: rawV, raw: rawV, empty: rawV === "",
          link: "sequential", rule_id: RULES.SEQUENTIAL_VERIFIED, entry_source_ref: base.source_ref,
          allowed_variants: base.allowed_variants,
        });
      });
      continue;
    }
    // kind 'numbered'（默认）
    for (const e of asArray(raw.entries)) {
      const n = Number(e.number);
      if (!Number.isInteger(n)) continue;
      if (expectedSet && !expectedSet.has(n)) {
        rejections.push({ source: base.source, reason: "number_not_expected", number: n, source_ref: e.source_ref || base.source_ref });
        continue;
      }
      if (raw.group_id != null) {
        const pg = questionGroupOf.get(n);
        if (pg && String(raw.group_id) !== pg.group_id) {
          rejections.push({ source: base.source, reason: "group_membership_mismatch", number: n, expected_group: pg.group_id, actual_group: raw.group_id });
          continue;
        }
      }
      const rawV = e.raw != null ? String(e.raw) : e.value == null ? "" : String(e.value);
      const entryAv = asArray(e.allowed_variants).map(String);
      pushCand(n, {
        ...base, number: n, value: rawV, raw: rawV, empty: rawV === "",
        link: "explicit", rule_id: RULES.EXPLICIT_NUMBER, entry_source_ref: e.source_ref || base.source_ref,
        allowed_variants: entryAv.length ? entryAv : base.allowed_variants,
      });
    }
  }

  // ------- 组裁决合并（第 8 条）：视觉核验的组集合优先，状态升为 official_verified -------
  for (const dec of decisionsList) {
    if (!dec.group) continue;
    const spec = dec.group;
    let target = groupResults.get(spec.group_id) || null;
    if (!target) {
      for (const g of groupResults.values()) {
        if (JSON.stringify(g.input_numbers) === JSON.stringify(spec.input_numbers)) { target = g; break; }
      }
    }
    if (!target) {
      groupResults.set(spec.group_id, {
        group_id: spec.group_id,
        input_numbers: spec.input_numbers.slice(),
        accepted_sets: spec.accepted_sets.map((s) => s.slice()),
        required_count: spec.required_count != null ? spec.required_count : spec.input_numbers.length,
        ordered: spec.ordered === true,
        allow_reuse: spec.allow_reuse === true,
        scoring: spec.scoring || "exact_set",
        status: "official_verified",
        rule_id: RULES.GROUP_ACCEPTED_SET,
        covered_numbers: spec.input_numbers.slice(),
        sources: [{ source: "adjudication", priority: 1, decision_id: dec.id }],
        conflicts: [],
        decision_id: dec.id,
      });
      continue;
    }
    const same = JSON.stringify(target.accepted_sets) === JSON.stringify(spec.accepted_sets)
      && target.required_count === spec.required_count
      && target.ordered === (spec.ordered === true);
    if (!same) {
      target.conflicts.push({ source: "adjudication", decision_id: dec.id, accepted_sets: spec.accepted_sets, required_count: spec.required_count, ordered: spec.ordered === true, note: "裁决集合与来源集合不同；显示采用裁决值" });
    }
    target.accepted_sets = spec.accepted_sets.map((s) => s.slice());
    target.required_count = spec.required_count != null ? spec.required_count : target.required_count;
    target.ordered = spec.ordered === true;
    target.status = "official_verified";
    target.decision_id = dec.id;
    target.sources.push({ source: "adjudication", priority: 1, decision_id: dec.id });
  }

  // ------- 逐题解析 -------
  const numbers = expectedNumbers || [...perNumber.keys()].sort((a, b) => a - b);
  const outQuestions = [];
  for (const n of numbers) {
    const slot = questionSlot.get(n) || null;
    const group = questionGroupOf.get(n) || null;
    const cands = perNumber.get(n) || [];
    const dec = decisionsList.find((d) => d.identity.question === n) || null;
    const family = group ? choiceFamilyOf(`${group.instruction} ${group.kind || ""}`) : slot ? choiceFamilyOf(slot.kind || "") : null;
    const options = (group && group.options.length ? group.options : slot && Array.isArray(slot.options) ? slot.options : []).filter((o) => o && o.label != null);

    // 决策应用（第 8 条）：原值守卫 + 等价形式 + 伪影值
    const conflicts = [];
    const sourceRefs = [];
    let decisionState = null;
    const applied = cands.map((c) => {
      const cc = { ...c };
      if (dec) {
        if (dec.action === "correct") {
          if (c.raw === dec.from) {
            cc.value = dec.to; cc.decision_applied = true; cc.rule_id = RULES.DECISION_CORRECTION;
            cc.source_refs = [{ type: "decision", id: dec.id, pdf: dec.pdf, basis: dec.basis }];
            decisionState = "applied";
          } else {
            decisionState = decisionState || "stale";
          }
        } else {
          const eq = [dec.book_value, ...(dec.equivalents || [])].filter((x) => x != null);
          const hitBook = dec.book_value != null && compareAnswers(dec.book_value, c.value, { numberWord: true, dateVariants: true }).equal;
          const hitEq = (dec.equivalents || []).some((e) => compareAnswers(e, c.value, { numberWord: true, dateVariants: true }).equal);
          if (hitBook || hitEq) {
            cc.decision_confirmed = true; cc.rule_id = RULES.DECISION_CONFIRMED;
            cc.source_refs = [{ type: "decision", id: dec.id, pdf: dec.pdf, basis: dec.basis }];
            decisionState = decisionState || "confirmed";
          }
        }
        const artifacts = dec.artifact_values || [];
        if (artifacts.some((a) => a != null && compareAnswers(a, c.raw).equal)) {
          cc.artifact = true; cc.artifact_of = dec.id;
        }
      }
      return cc;
    });

    // MCQ 字母映射（第 4 条）：文本与选项全文规范化相等且唯一时才映射
    if (options.length) {
      const labelSet = new Set(options.map((o) => normalizeAnswer(o.label)));
      for (const c of applied) {
        const nv = normalizeAnswer(c.value);
        if (!nv) continue;
        if (labelSet.has(nv)) { c.mapped_label = normalizeAnswer(c.value); continue; }
        const hits = options.filter((o) => compareAnswers(o.text, c.value).equal);
        if (hits.length === 1) {
          c.mapped_label = normalizeAnswer(hits[0].label);
          c.mapping_rule = RULES.MCQ_LETTER_MAP;
        }
      }
    }

    // 每题显式允许形式（expected / question slot / 裁决等价形式）并入候选
    const qAllowed = [
      ...(expObj && expObj.allowed_variants ? asArray(expObj.allowed_variants[n]) : []),
      ...(slot && Array.isArray(slot.allowed_variants) ? slot.allowed_variants : []),
      ...(dec ? [dec.book_value, ...(dec.equivalents || [])].filter((x) => x != null) : []),
    ].map(String);
    if (qAllowed.length) {
      for (const c of applied) {
        c.allowed_variants = [...new Set([...(c.allowed_variants || []), ...qAllowed])];
      }
    }

    // 有效值键（映射后；TFNG/YNNG 家族内标准化）：用于冲突检测。
    // 分组用严格比较器做 union 合并：显式 allowed_variants 或同选项标签才归并为同键；
    // 单字母保护、禁止 token 子集等规则在此同样生效。
    const keyOf = (c) => {
      if (c.empty) return null;
      if (c.mapped_label != null) return `label:${c.mapped_label}`;
      const nv = family ? normalizeChoice(c.value, family) : normalizeAnswer(c.value);
      return `text:${nv}`;
    };
    const nonEmpty = applied.filter((c) => !c.empty);
    const artifactsOnly = nonEmpty.length > 0 && nonEmpty.every((c) => c.artifact);

    // 独立来源冲突检测（多镜像同一上游不算独立双源）
    const keyRecs = []; // {key, sources:Set, cands:[], best}
    for (const c of nonEmpty) {
      if (c.artifact && artifactsOnly) continue;
      const k = keyOf(c);
      if (k == null) continue;
      let rec = null;
      for (const r of keyRecs) {
        const rep = r.cands[0];
        const sameLabel = rep.mapped_label != null && c.mapped_label != null && rep.mapped_label === c.mapped_label;
        const eq = sameLabel || compareAnswers(rep.value, c.value, {
          family,
          allowedVariantsA: rep.allowed_variants || [],
          allowedVariantsB: c.allowed_variants || [],
          numberWord: !!(expObj && expObj.numberWord),
          dateVariants: !!(expObj && expObj.dateVariants),
        }).equal;
        if (eq) { rec = r; break; }
      }
      if (!rec) { rec = { key: k, sources: new Set(), cands: [], best: 99 }; keyRecs.push(rec); }
      rec.sources.add(c.upstream);
      rec.cands.push(c);
      rec.best = Math.min(rec.best, c.priority);
    }
    let status, answer = null, rule_id = RULES.MISSING, display = null;

    if (applied.some((c) => c.decision_applied)) {
      const c = applied.find((x) => x.decision_applied);
      status = "official_verified"; rule_id = RULES.DECISION_CORRECTION; answer = c.value;
      const isLabel = options.some((o) => normalizeAnswer(o.label) === normalizeAnswer(c.value));
      display = { value: c.value, kind: isLabel ? "letter" : "text", label: isLabel ? normalizeAnswer(c.value) : null, source: c.source };
    } else if (applied.some((c) => c.decision_confirmed) && dec && dec.book_value != null) {
      status = "official_verified"; rule_id = RULES.DECISION_CONFIRMED; answer = dec.book_value;
      const isLabel = options.some((o) => normalizeAnswer(o.label) === normalizeAnswer(dec.book_value));
      display = { value: dec.book_value, kind: isLabel ? "letter" : "text", label: isLabel ? normalizeAnswer(dec.book_value) : null, source: "adjudication", decision_id: dec.id };
    } else if (nonEmpty.length === 0) {
      if (applied.some((c) => c.order_unverified)) { status = "order_unverified"; rule_id = RULES.ORDER_UNVERIFIED; }
      else if (dec && dec.action === "correct") { status = "decision_stale"; rule_id = RULES.DECISION_STALE; }
      else { status = "missing"; rule_id = RULES.MISSING; }
    } else if (keyRecs.length > 1) {
      status = "conflict"; rule_id = RULES.CONFLICT;
      const bestRec = [...keyRecs].sort((a, b) => a.best - b.best)[0];
      const bestCand = bestRec.cands.sort((a, b) => a.priority - b.priority)[0];
      answer = bestCand.value;
      display = { value: bestCand.value, kind: bestCand.mapped_label != null ? "letter" : "text", label: bestCand.mapped_label || null, source: bestCand.source, conflict: true };
      for (const rec of keyRecs) {
        conflicts.push({ value: rec.key.replace(/^\w+:/, ""), key: rec.key, sources: [...rec.sources], best_priority: rec.best });
      }
    } else {
      const rec = keyRecs[0];
      const c = rec.cands.sort((a, b) => a.priority - b.priority)[0];
      status = statusFromCandidate(c);
      rule_id = c.rule_id || (c.link === "sequential" ? RULES.SEQUENTIAL_VERIFIED : RULES.EXPLICIT_NUMBER);
      answer = c.value;
      display = { value: c.value, kind: c.mapped_label != null ? "letter" : "text", label: c.mapped_label || null, source: c.source };
    }

    // decision_stale 提示（有候选但未命中 from）
    if (dec && dec.action === "correct" && decisionState === "stale" && status !== "decision_stale" && status !== "conflict") {
      notes.push({ kind: "decision_stale", number: n, decision_id: dec.id, expected_from: dec.from, candidates: nonEmpty.map((c) => c.raw) });
    }

    for (const c of applied) {
      sourceRefs.push({
        source: c.source, source_class: c.source_class, priority: c.priority,
        value: c.raw, normalized: normalizeAnswer(c.raw), empty: !!c.empty,
        source_ref: c.entry_source_ref || c.source_ref,
        decision_applied: !!c.decision_applied, decision_confirmed: !!c.decision_confirmed,
        artifact: !!c.artifact, mapped_label: c.mapped_label || null,
        mapping_rule: c.mapping_rule || null,
        rejected: false,
      });
    }

    // 组内槽位：无直接候选时由组答案覆盖（按 input_numbers 覆盖，不依赖解析组 id 一致）
    let groupRef = null;
    for (const g of groupResults.values()) {
      if (!g.input_numbers.includes(n)) continue;
      const rank = (s) => (s === "official_verified" ? 4 : s === "source_verified" ? 3 : s === "identity_linked" ? 2 : s === "conflict" ? 1 : 0);
      if (!groupRef || rank(g.status) > rank(groupRef.status)) {
        groupRef = { group_id: g.group_id, status: g.status, accepted_sets: g.accepted_sets, required_count: g.required_count, ordered: g.ordered };
      }
    }
    if (groupRef && status === "missing") {
      status = groupRef.status === "conflict" ? "conflict" : groupRef.status;
      rule_id = RULES.GROUP_ACCEPTED_SET;
      display = { value: null, kind: "set", accepted_sets: groupRef.accepted_sets };
    }

    outQuestions.push({
      number: n,
      group_id: groupRef ? groupRef.group_id : group ? group.group_id : dec && dec.identity.group_id ? dec.identity.group_id : null,
      status,
      rule_id,
      answer,
      display,
      raw_values: applied.map((c) => ({ source: c.source, raw: c.raw, empty: !!c.empty })),
      candidates: sourceRefs,
      conflicts,
      group_ref: groupRef,
      decision: dec ? { id: dec.id, action: dec.action, category: dec.category, pdf: dec.pdf, basis: dec.basis } : null,
      family,
      options_count: options.length,
      word_limit: slot && slot.word_limit != null ? slot.word_limit
        : group && group.raw && group.raw.word_limit != null ? group.raw.word_limit : null,
      allowed_variants: [...new Set(applied.flatMap((c) => c.allowed_variants || []))],
    });
  }

  // ------- coverage -------
  const statusCounts = {};
  for (const q of outQuestions) statusCounts[q.status] = (statusCounts[q.status] || 0) + 1;
  const missing = outQuestions.filter((q) => q.status === "missing").map((q) => q.number);
  const conflictNums = outQuestions.filter((q) => q.status === "conflict").map((q) => q.number);
  const unverifiedNums = outQuestions.filter((q) => q.status === "unverified" || q.status === "order_unverified").map((q) => q.number);
  const coverage = {
    expected_total: expectedNumbers ? expectedNumbers.length : null,
    processed: outQuestions.length,
    answered: outQuestions.filter((q) => q.status !== "missing").length,
    status_counts: statusCounts,
    missing,
    conflict: conflictNums,
    unverified: unverifiedNums,
    groups: groupResults.size,
    group_covered_numbers: [...groupResults.values()].reduce((s, g) => s + g.covered_numbers.length, 0),
    rejections: rejections.length,
  };

  return {
    ok: true,
    identity: callId,
    questions: outQuestions,
    groups: [...groupResults.values()],
    coverage,
    rejections,
    notes,
  };
}

function rangeOf(range) {
  if (!Array.isArray(range) || range.length < 2) return [];
  const out = [];
  for (let n = Number(range[0]); n <= Number(range[1]); n++) out.push(n);
  return out;
}

export const __internals = { gateIdentity, priorityOf, statusFromCandidate, rangeOf };
