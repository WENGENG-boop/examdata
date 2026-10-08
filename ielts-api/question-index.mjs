/**
 * question-index.mjs — S08 统一题目索引
 *
 * 把 PTE raw 页面（parsePtePage 产物）与 cam21 HTML 页面（parseReadingHtml/parseListeningHtml 产物）
 * 统一为同一题目索引：每题一条记录（内容状态 / 答案状态 / 分类），另存答案表（key=题目 id）
 * 与多选答案组表（cam21 multi 的 inputs/accepted sets）。
 *
 * 规则（计划 S08）：
 * - 题号身份完整：id=cambridge:{book}:{variant}:{skill}:{test}:{part}:Q{n}（组 :G{ordinal}，篇目 :P{n}）。
 * - 内容状态按优先级判定：missing_content > missing_prompt > missing_options > missing_asset
 *   > missing_passage > partial > complete；PDF/来源页图可作视觉回落但记 partial（presentation）。
 * - 空答案/缺答案不移位：answer 表保留原始值，区分 empty（有槽无值）与 missing（无槽）。
 * - unknown/conflict 分类、丢选项、失效资产、缺正文不进入 fully_complete。
 * - 组共享 instruction/constraints 保留在 groups 表；题目引用 group_id/shared_prompt_ref，不复制正文。
 * - 官方核验覆盖（applyGroupVerifications）：分类/字数限制/答案表示按官方 PDF 核验覆盖（from 守卫 +
 *   原值保留 + answers[qid].official 记录官方值）；冲突条目入 cross_source_conflicts。
 */
import {
  classifyGroup,
  deriveStructure,
  resolveTypeName,
  resolveSkillName,
  resolveVariantName,
  typeFamily,
  QUESTION_TYPES,
  SKILLS,
  VARIANTS,
  TYPE_FAMILIES,
} from "./taxonomy.mjs";
import { expectedFor } from "./pte.mjs";

export const INDEX_SCHEMA = "ielts-question-index/1";

export const CONTENT_STATUS = Object.freeze([
  "complete",
  "partial",
  "missing_prompt",
  "missing_options",
  "missing_asset",
  "missing_passage",
  "missing_content",
]);

export const ANSWER_STATUS = Object.freeze(["attached", "empty", "missing", "open_response", "not_applicable"]);

export const ANSWER_MODES = Object.freeze(["standard", "open_response"]);

export const CLASSIFICATION_STATUS = Object.freeze(["classified", "inferred", "unknown", "conflict"]);

const FAMILY_LABELS = Object.freeze({
  choice: "选择",
  judgement: "判断",
  matching: "匹配",
  completion: "填空",
  visual: "图表",
  short_answer: "简答",
  open: "开放",
  unknown: "未知",
});

const FAMILY_LOOKUP = (() => {
  const map = new Map();
  const add = (k, v) => {
    const key = normNameLocal(k);
    if (key && !map.has(key)) map.set(key, v);
  };
  for (const family of Object.values(TYPE_FAMILIES)) add(family, family);
  for (const [family, zh] of Object.entries(FAMILY_LABELS)) add(zh, family);
  return map;
})();

function normNameLocal(value) {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/[（(]/g, " ")
    .replace(/[）)]/g, " ")
    .replace(/[\/／、，,;；:：|]+/g, " ")
    .replace(/[-_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** 题型族解析（canonical 题型名 → 族；族名/中文族名 → 族） */
export function resolveFamilyName(value) {
  if (value == null) return null;
  const type = resolveTypeName(value);
  if (type) return typeFamily(type);
  return FAMILY_LOOKUP.get(normNameLocal(value)) ?? null;
}

/** test 归一为字符串："1".."4" / "gta" / "gtb" */
export function normTest(test) {
  return test == null ? null : String(test);
}

/** 来源技能 → {skill, variant} 归一 */
export function skillVariantOf(sourceSkill) {
  switch (sourceSkill) {
    case "academic_reading":
      return { skill: "reading", variant: "academic" };
    case "general_reading":
      return { skill: "reading", variant: "general" };
    case "reading":
      return { skill: "reading", variant: "academic" }; // cam21 阅读（学术）
    case "listening":
      return { skill: "listening", variant: "shared" };
    case "academic_writing":
      return { skill: "writing", variant: "academic" };
    case "general_writing":
      return { skill: "writing", variant: "general" };
    case "writing":
      return { skill: "writing", variant: "academic" };
    case "speaking":
      return { skill: "speaking", variant: "shared" };
    default:
      return { skill: sourceSkill ?? null, variant: null };
  }
}

const WORD_NUM = Object.freeze({ one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10 });

/** 字数限制解析：{raw, max_words, allows_number}；无限制信息返回 null */
export function parseWordLimit(text) {
  const s = String(text ?? "");
  if (!s.trim()) return null;
  const t = s.toLowerCase();
  const pick = (m) => (/^\d+$/.test(m[1]) ? parseInt(m[1], 10) : WORD_NUM[m[1]]);
  let max_words = null;
  let raw = null;
  let m = /no more than (one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+words?/.exec(t);
  if (m) {
    max_words = pick(m);
    raw = m[0];
  } else {
    m = /(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+words?\s+and\/or\s+a\s+number/.exec(t);
    if (m) {
      max_words = pick(m);
      raw = m[0];
    } else {
      m = /(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+words?\s+only/.exec(t);
      if (m) {
        max_words = pick(m);
        raw = m[0];
      }
    }
  }
  const allows_number = /number/.test(t);
  if (max_words == null && !allows_number) return null;
  return { raw, max_words, allows_number };
}

/** 期望 Part 归属：按 expected.parts ranges 命中 */
export function partOfNumber(number, parts) {
  if (!Array.isArray(parts)) return null;
  for (const p of parts) {
    for (const range of (p && p.ranges) || []) {
      if (Array.isArray(range) && number >= range[0] && number <= range[1]) return p.part;
    }
  }
  return null;
}

function passageForGroup(passages, groupIndex) {
  if (groupIndex == null || !Array.isArray(passages)) return null;
  for (const p of passages) if (Array.isArray(p.question_groups) && p.question_groups.includes(groupIndex)) return p;
  return null;
}

function passageForNumber(number, passages) {
  if (!Array.isArray(passages)) return null;
  for (const p of passages) {
    if (Array.isArray(p.range) && number >= p.range[0] && number <= p.range[1]) return p;
  }
  return null;
}

export function passageTextOf(passage) {
  if (!passage) return "";
  if (typeof passage.text === "string") return passage.text;
  if (Array.isArray(passage.paragraphs)) return passage.paragraphs.map((x) => String((x && x.text) || "")).join("\n\n");
  return "";
}

function questionIdOf({ book, variant, skill, test, part, number }) {
  return `cambridge:${book}:${variant}:${skill}:${test}:${part}:Q${number}`;
}

function groupIdOf({ book, variant, skill, test, part, ordinal }) {
  return `cambridge:${book}:${variant}:${skill}:${test}:${part}:G${ordinal}`;
}

function passageIdOf({ book, variant, skill, test, part }) {
  return `cambridge:${book}:${variant}:${skill}:${test}:${part}`;
}

/**
 * 内容状态判定（按计划优先级）。
 * @returns {{status:string, presentation:string|null, notes:string[]}}
 */
export function contentStatusOf(ctx = {}) {
  const {
    prompt,
    shared,
    options,
    pools,
    type,
    assets,
    passageText,
    skill,
    letterOptions = false,
    groupContext = true,
  } = ctx;
  const family = type ? typeFamily(type) : null;
  const hasPrompt = !!String(prompt ?? "").trim();
  const hasShared = !!String(shared ?? "").trim();
  const hasOptions = Array.isArray(options) && options.length > 0;
  const hasPools = Array.isArray(pools) && pools.length > 0;
  const hasAssets = Array.isArray(assets) && assets.length > 0;
  const hasPassage = !!String(passageText ?? "").trim();
  const notes = [];
  let presentation = "structured";

  const choiceMissing = family === "choice" && !hasOptions && !hasPools;
  const matchingMissing = family === "matching" && !hasOptions && !hasPools && !letterOptions;
  const visualMissing = (family === "visual" || type === "table_completion" || type === "flow_chart_completion") && !hasAssets;

  if (!hasPrompt && !hasShared) {
    if (!hasOptions && !hasPools && !hasAssets) return { status: "missing_content", presentation: null, notes };
    return { status: "missing_prompt", presentation: null, notes };
  }
  if (choiceMissing || matchingMissing) {
    if (hasAssets) {
      notes.push(choiceMissing ? "choice_options_missing_image_fallback" : "matching_options_missing_image_fallback");
      presentation = "source_image";
    } else {
      return { status: "missing_options", presentation: null, notes };
    }
  }
  if (visualMissing) return { status: "missing_asset", presentation: null, notes };
  if (skill === "reading" && !hasPassage) return { status: "missing_passage", presentation: null, notes };
  if (!groupContext) {
    notes.push("group_context_missing");
    return { status: "partial", presentation, notes };
  }
  if (presentation === "source_image") return { status: "partial", presentation, notes };
  return { status: "complete", presentation, notes };
}

function normalizeAssets(assets) {
  if (!Array.isArray(assets)) return [];
  return assets
    .map((a) => ({
      kind: String((a && a.kind) || "unknown"),
      source_ref: (a && a.source_ref) ?? null,
      local_path: (a && a.local_path) ?? null,
    }))
    .filter((a) => a.source_ref || a.local_path);
}

function answerStatusOf(entry) {
  if (!entry) return "missing";
  if (entry.raw == null || String(entry.raw).trim() === "") return "empty";
  return "attached";
}

function openModeFor(skill) {
  return skill === "writing" || skill === "speaking" ? "open_response" : "standard";
}

function fullyCompleteOf(q) {
  const classificationOk = q.classification_status === "classified" || q.classification_status === "inferred";
  const answerOk = q.answer_status === "attached" || q.answer_mode === "open_response";
  return q.content_status === "complete" && classificationOk && answerOk;
}

/** PTE 页面 → {questions, groups, answers, answer_groups, gaps, page} */
export function buildFromPtePage(parsed, meta = {}) {
  const book = Number(meta.book);
  const test = normTest(meta.test);
  const sourceSkill = meta.skill;
  const { skill, variant } = skillVariantOf(sourceSkill);
  const expected = meta.expected || expectedFor(book, test, sourceSkill) || null;
  const parts = (expected && expected.parts) || [];
  const passages = parsed.passages || [];
  const groupsIn = parsed.question_groups || [];
  const questionsIn = parsed.questions || [];
  const metaRefs = Array.isArray(meta.source_refs) ? meta.source_refs.slice() : [];
  const pageRef = meta.page_key || `pte:${book}:${test}:${sourceSkill}`;
  const gaps = [];
  const groupRecords = [];
  const questions = [];
  const answers = {};
  const byIndex = new Map();

  // 1) 组分类（同 Part 内前一组已分类题型作保守延续依据）
  let prevType = null;
  for (const g of groupsIn) {
    const structure = deriveStructure(g);
    const cls = classifyGroup({
      source_type: null,
      instruction: g.instruction,
      shared_prompt: g.shared_prompt,
      heading_text: g.heading_text,
      skill,
      neighbor_type: prevType,
      structure,
    });
    if (cls.status === "classified" || cls.status === "inferred") prevType = cls.type;
    const numbers = Array.isArray(g.numbers) ? g.numbers.slice() : [];
    const first = numbers.length ? Math.min(...numbers) : null;
    byIndex.set(g.index, { g, cls, structure, numbers, first, part: null, ordinal: null, id: null });
  }

  // 2) 组 Part 归属与序数（Part 内按首题号 0 起编）
  const ordered = [...byIndex.values()].sort((a, b) => (a.first ?? Number.MAX_SAFE_INTEGER) - (b.first ?? Number.MAX_SAFE_INTEGER));
  const ordCount = new Map();
  for (const rec of ordered) {
    const first = rec.first;
    let part = first != null ? partOfNumber(first, parts) : null;
    let psgPart = null;
    if (skill === "reading") {
      const psg = passageForGroup(passages, rec.g.index) || (first != null ? passageForNumber(first, passages) : null);
      if (psg) psgPart = `P${psg.index + 1}`;
    }
    if (!part) part = psgPart;
    rec.part = part || "P?";
    const key = rec.part;
    const ord = ordCount.get(key) || 0;
    ordCount.set(key, ord + 1);
    rec.ordinal = ord;
    rec.id = groupIdOf({ book, variant, skill, test, part: rec.part, ordinal: ord });
  }

  // 3) 组记录（空组排除并记缺口）
  for (const rec of ordered) {
    const { g, cls, numbers } = rec;
    const isEmptyGroup = (g.slots || []).length === 0 && !(g.pools || []).length && !(g.assets || []).length;
    if (isEmptyGroup && numbers.length) {
      gaps.push({
        kind: "empty_group_excluded",
        book,
        variant,
        skill,
        test,
        part: rec.part,
        range: g.range || null,
        numbers,
        note: "组无槽位/选项/资产；题目按 missing_content 保留，组不进入索引",
      });
      rec.excluded = true;
      continue;
    }
    const wordLimitSource = [g.word_limit, g.instruction, g.shared_prompt, g.heading_text].filter((x) => x && String(x).trim()).join("\n");
    const constraints = parseWordLimit(g.word_limit || wordLimitSource);
    groupRecords.push({
      id: rec.id,
      page_ref: pageRef,
      identity: { book, variant, skill, test, part: rec.part, range: g.range || null },
      range: g.range || null,
      numbers,
      instruction: g.instruction || null,
      shared_prompt: g.shared_prompt || null,
      heading_text: g.heading_text || null,
      word_limit: g.word_limit || null,
      constraints,
      options: (g.pools || []).map((p) => ({
        kind: String((p && p.kind) || "unknown"),
        source_ref: (p && p.source_ref) ?? null,
        options: ((p && p.options) || []).map((o) => ({ label: (o && o.label) ?? null, text: (o && o.text) ?? null })),
      })),
      slots: (g.slots || []).map((s) => ({ number: s.number, kind: s.kind || "unknown" })),
      assets: normalizeAssets(g.assets),
      type: cls.type,
      classification_status: cls.status,
      classification_reason: cls.reason,
      type_candidates: cls.candidates || null,
      source_ref: g.source_ref || null,
      heading_source_ref: g.heading_source_ref || null,
    });
  }

  // 3b) 多选答案组（inputs/accepted sets；镜像 cam21 语义）
  const answerGroups = [];
  for (const ag of parsed.answer_groups || []) {
    const slotQ = questionsIn.find((q) => (ag.slots || []).includes(q.number));
    const key = ag.key ?? ag.group ?? null;
    let rec = null;
    if (slotQ && slotQ.group != null) rec = byIndex.get(slotQ.group) || null;
    if (!rec && key != null) rec = byIndex.get(key) || null;
    answerGroups.push({
      id: rec && !rec.excluded ? rec.id : `pte:${book}:${test}:${skill}:answer_group:${key ?? "unknown"}`,
      page_ref: pageRef,
      numbers: ag.slots || [],
      inputs_raw: ag.inputs_raw || ag.slots || [],
      accept: ag.accept || [],
      required_count: ag.required_count ?? null,
      section: ag.section ?? null,
      source: ag.source || meta.source || "pte-raw",
    });
  }

  // 4) 答案表（保留原始值；empty 与 missing 分开）
  const answerSlots = new Map();
  for (const s of parsed.answer_slots || []) {
    if (!answerSlots.has(s.number)) answerSlots.set(s.number, s);
  }
  const answersMissingDetail = new Map();
  for (const d of parsed.answer_missing_detail || []) answersMissingDetail.set(d.number, d.reason);

  // 5) 题目记录
  for (const q of questionsIn) {
    const rec = q.group != null ? byIndex.get(q.group) : null;
    const group = rec ? rec.g : null;
    const cls = rec ? rec.cls : null;
    const psg = skill === "reading" ? passageForGroup(passages, q.group) || passageForNumber(q.number, passages) : null;
    const expectedPart = partOfNumber(q.number, parts);
    const psgPart = psg ? `P${psg.index + 1}` : null;
    const part = expectedPart || psgPart || (rec && rec.part) || "P?";
    const notes = [];
    if (Array.isArray(q.notes)) notes.push(...q.notes);
    if (expectedPart && psgPart && expectedPart !== psgPart) notes.push(`part_passage_mismatch:${expectedPart}vs${psgPart}`);
    const letterOptions =
      cls && cls.type === "matching_information"
        ? /(?:[A-Z]\s*[–—-]\s*[A-Z])/.test(String((group && group.instruction) || "")) ||
          ((psg && Array.isArray(psg.paragraphs) ? psg.paragraphs.filter((p) => p && p.letter).length : 0) >= 2)
        : false;
    const groupContext = group ? !!(String(group.instruction || "").trim() || String(group.shared_prompt || "").trim() || String(group.heading_text || "").trim()) : true;
    const content = contentStatusOf({
      prompt: q.prompt,
      shared: group ? group.shared_prompt : null,
      options: q.options,
      pools: group ? group.pools : null,
      type: cls ? cls.type : "unknown",
      assets: group ? group.assets : null,
      passageText: skill === "reading" ? passageTextOf(psg) : "",
      skill,
      letterOptions,
      groupContext,
    });
    const answerEntry = answerSlots.get(q.number) || null;
    const answer = answerEntry
      ? { raw: answerEntry.raw ?? null, form: answerEntry.form ?? null, status: answerStatusOf(answerEntry), source: meta.source || "pte-raw", ref: answerEntry.source_ref ?? null }
      : { raw: null, form: null, status: "missing", source: meta.source || "pte-raw", ref: null, note: answersMissingDetail.get(q.number) === "empty" ? "empty_slot_no_entry" : "absent" };
    if (answerEntry && answerEntry.official != null) answer.official = answerEntry.official;
    if (answerEntry && answerEntry.note != null) answer.note = answerEntry.note;
    const id = questionIdOf({ book, variant, skill, test, part, number: q.number });
    answers[id] = answer;
    const sourceRefs = [];
    for (const r of [q.source_ref, group ? group.source_ref : null, ...metaRefs]) if (r && !sourceRefs.includes(r)) sourceRefs.push(r);
    const record = {
      id,
      identity: { book, variant, skill, test, part, number: q.number },
      book,
      variant,
      skill,
      test,
      part,
      passage: psg ? psg.index + 1 : null,
      number: q.number,
      group_id: rec && !rec.excluded ? rec.id : null,
      prompt: q.prompt || null,
      shared_prompt_ref: group && String(group.shared_prompt || "").trim() ? (rec && rec.id) : null,
      instruction: group ? group.instruction || null : null,
      constraints: group ? parseWordLimit(group.word_limit || [group.instruction, group.shared_prompt, group.heading_text].filter((x) => x && String(x).trim()).join("\n")) : null,
      options: Array.isArray(q.options) ? q.options.map((o) => ({ label: (o && o.label) ?? null, text: (o && o.text) ?? null })) : [],
      assets: group ? normalizeAssets(group.assets) : [],
      answer_ref: id,
      audio_alignment_ref: null,
      source_refs: sourceRefs,
      content_status: content.status,
      content_presentation: content.presentation,
      content_notes: [...notes, ...content.notes],
      answer_status: answer.status,
      answer_mode: openModeFor(skill),
      classification_status: cls ? cls.status : "unknown",
      classification_reason: cls ? cls.reason : "no_group",
      type: cls ? cls.type : "unknown",
      page_ref: pageRef,
    };
    record.fully_complete = fullyCompleteOf(record);
    questions.push(record);
  }

  const page = {
    page_ref: pageRef,
    kind: meta.page_kind || "pte-raw",
    book,
    test,
    skill,
    variant,
    source_skill: sourceSkill,
    source: meta.source || null,
    slug: meta.slug || null,
    url: meta.url || null,
    source_page_id: meta.source_page_id ?? null,
    raw_index: meta.raw_index ?? null,
    raw_file: meta.raw_file || null,
    counts: {
      questions: questions.length,
      groups: groupRecords.length,
      groups_excluded: gaps.filter((g) => g.kind === "empty_group_excluded").length,
      answers_attached: questions.filter((q) => q.answer_status === "attached").length,
      passages: passages.length,
    },
    warnings: (parsed.warnings || []).map((w) => ({ kind: (w && w.kind) || "unknown", numbers: (w && w.numbers) || undefined })),
  };

  return { page, groups: groupRecords, questions, answers, answer_groups: answerGroups, gaps };
}

/** cam21 资产规范化：保留表格/流程图/图片的结构化内容（kind/source_ref/title/headers/rows/steps/numbers/alt） */
function cam21AssetOf(a) {
  if (!a || typeof a !== "object") return null;
  const out = { kind: String(a.kind || "unknown") };
  if (a.source_ref != null) out.source_ref = a.source_ref;
  if (a.title != null) out.title = a.title;
  if (Array.isArray(a.headers) && a.headers.length) out.headers = a.headers;
  if (Array.isArray(a.rows) && a.rows.length) out.rows = a.rows;
  if (Array.isArray(a.steps) && a.steps.length) out.steps = a.steps;
  if (Array.isArray(a.numbers) && a.numbers.length) out.numbers = a.numbers;
  if (a.alt != null) out.alt = a.alt;
  return out;
}

/** 组资产 → 共享文本（表格 title+表头+行；流程图 title+步骤；图片 title/alt），用于 shared_prompt 与证据回读 */
function cam21SharedTextOf(assets) {
  if (!Array.isArray(assets) || !assets.length) return null;
  const parts = [];
  for (const a of assets) {
    if (a.kind === "table") {
      const lines = [];
      if (a.title) lines.push(a.title);
      if (Array.isArray(a.headers) && a.headers.length) lines.push(a.headers.join(" | "));
      for (const row of a.rows || []) if (Array.isArray(row) && row.length) lines.push(row.join(" | "));
      parts.push(lines.join("\n"));
    } else if (a.kind === "flowchart") {
      parts.push([a.title, ...(a.steps || [])].filter((x) => x && String(x).trim()).join("\n"));
    } else if (a.kind === "figure") {
      parts.push([a.title, a.alt].filter((x) => x && String(x).trim()).join(" — "));
    }
  }
  const s = parts.filter((x) => x && String(x).trim()).join("\n\n");
  return s.trim() ? s : null;
}

/** 组内题选项并集：仅当所有题选项集完全一致时返回该集（多选/匹配共享字母集），否则空（mcq 逐题选项留在题目记录） */
function sharedOptionsOf(qs) {
  const list = qs.map((q) => JSON.stringify((q.options || []).map((o) => ({ label: (o && o.label) ?? null, text: (o && o.text) ?? null }))));
  if (!list.length || !(qs[0].options || []).length) return [];
  if (!list.every((x) => x === list[0])) return [];
  return (qs[0].options || []).map((o) => ({ label: (o && o.label) ?? null, text: (o && o.text) ?? null }));
}

function stripHtmlToText(html) {
  return String(html ?? "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

/**
 * cam21 阅读页的表格/流程图为扁平文本（源页无结构化资产标记，题面文本已含单元格/步骤内容）：
 * 按题面文本派生资产（derived=flattened_question_text 标注来源），使表格/流程图组内容可被回读且状态判定有据。
 */
function derivedReadingAssetOf(rec) {
  const clsType = rec.cls ? rec.cls.type : null;
  if (clsType !== "table_completion" && clsType !== "flow_chart_completion") return null;
  const qs = (rec.qs || []).slice().sort((a, b) => a.number - b.number);
  const texts = qs.map((q) => String(q.prompt || "").trim()).filter(Boolean);
  if (!texts.length) return null;
  const instr = stripHtmlToText(rec.g ? rec.g.instruction : "");
  const tm = /^complete the (?:table|flow-?chart)\s*[—–-]\s*(.*?)(?:\.\s*(?:choose|write)|\.?$)/i.exec(instr);
  const title = tm && tm[1] ? tm[1].replace(/\s+([.,;:])/g, "$1").replace(/[.\s]+$/, "").trim() : null;
  const numbers = qs.map((q) => q.number);
  if (clsType === "table_completion") {
    const rows = texts.map((t) => {
      const idx = t.indexOf(":");
      return idx > 0 && idx < 60 ? [t.slice(0, idx).trim(), t.slice(idx + 1).trim()] : [t];
    });
    return { kind: "table", source_ref: `cam21:reading:${rec.key}`, title, rows, numbers, derived: "flattened_question_text" };
  }
  return { kind: "flowchart", source_ref: `cam21:reading:${rec.key}`, title, steps: texts, numbers, derived: "flattened_question_text" };
}

/** cam21 页面 → {questions, groups, answers, answer_groups, gaps, page} */
export function buildFromCam21Page(parsed, meta = {}) {
  const book = Number(meta.book ?? 21);
  const test = normTest(meta.test);
  const sourceSkill = meta.skill === "listening" ? "listening" : "reading";
  const { skill, variant } = skillVariantOf(sourceSkill);
  const expected = meta.expected || expectedFor(book, test, sourceSkill === "reading" ? "academic_reading" : "listening") || null;
  const parts = (expected && expected.parts) || [];
  const metaRefs = Array.isArray(meta.source_refs) ? meta.source_refs.slice() : [];
  const pageRef = meta.page_key || `cam21:${book}:${test}:${sourceSkill}`;
  const gaps = [];
  const groupRecords = [];
  const questions = [];
  const answers = {};
  const answerGroups = [];

  const groupsIn = parsed.groups || [];
  const questionsIn = parsed.questions || [];
  const answerKey = new Map();
  for (const e of parsed.answer_key || []) if (!answerKey.has(e.number)) answerKey.set(e.number, e);
  const passagesIn = parsed.passages || [];

  const qByGroup = new Map();
  for (const q of questionsIn) {
    const key = q.group != null ? q.group : null;
    if (!qByGroup.has(key)) qByGroup.set(key, []);
    qByGroup.get(key).push(q);
  }

  const sectionOf = (q) => (skill === "listening" ? q.section : q.passage);
  const partOfQuestion = (q) => {
    const sec = sectionOf(q);
    return sec != null ? `P${sec}` : null;
  };

  // 组记录（分类同 verify-cam21 口径）
  const recs = [];
  for (const g of groupsIn) {
    const key = skill === "listening" ? g.index : g.id;
    const qs = qByGroup.get(key) || [];
    const numbers = qs.map((q) => q.number).sort((a, b) => a - b);
    const first = numbers.length ? numbers[0] : null;
    const sec = qs.length ? sectionOf(qs[0]) : skill === "listening" ? g.section : null;
    const part = sec != null ? `P${sec}` : first != null ? partOfNumber(first, parts) : null;
    const slots = qs.map((q) => ({
      kind: skill === "listening" ? (q.type === "multi" ? "multi_select" : q.type || "unknown") : q.slot_kind || "single",
      prompt: q.prompt || "",
      options: q.options || [],
    }));
    const cls = classifyGroup({ source_type: g.type || null, instruction: g.instruction, skill, slots, pools: [] });
    recs.push({ g, key, qs, numbers, first, part, cls });
  }
  const ordCount = new Map();
  const ordered = recs.slice().sort((a, b) => (a.first ?? Number.MAX_SAFE_INTEGER) - (b.first ?? Number.MAX_SAFE_INTEGER));
  for (const rec of ordered) {
    const part = rec.part || "P?";
    const ord = ordCount.get(part) || 0;
    ordCount.set(part, ord + 1);
    rec.id = groupIdOf({ book, variant, skill, test, part, ordinal: ord });
    rec.part = part;
  }
  const recByKey = new Map(ordered.map((r) => [r.key, r]));

  for (const rec of ordered) {
    const g = rec.g;
    const wordLimitText = [g.word_limit, g.instruction, g.sublabel].filter((x) => x && String(x).trim()).join("\n");
    let gAssets = (g.assets || []).map(cam21AssetOf).filter(Boolean);
    if (!gAssets.length && skill === "reading") {
      const derived = derivedReadingAssetOf(rec);
      if (derived) gAssets = [derived];
    }
    rec.groupAssets = gAssets;
    groupRecords.push({
      id: rec.id,
      page_ref: pageRef,
      identity: { book, variant, skill, test, part: rec.part, range: rec.numbers.length ? [rec.numbers[0], rec.numbers[rec.numbers.length - 1]] : null },
      range: rec.numbers.length ? [rec.numbers[0], rec.numbers[rec.numbers.length - 1]] : null,
      numbers: rec.numbers,
      instruction: g.instruction || null,
      shared_prompt: cam21SharedTextOf(gAssets),
      heading_text: g.label || g.sublabel || null,
      word_limit: g.word_limit || null,
      constraints: parseWordLimit(g.word_limit || wordLimitText),
      options: sharedOptionsOf(rec.qs),
      slots: rec.qs.map((q) => ({ number: q.number, kind: skill === "listening" ? (q.type === "multi" ? "multi_select" : q.type || "unknown") : q.slot_kind || "single" })),
      assets: gAssets,
      type: rec.cls.type,
      classification_status: rec.cls.status,
      classification_reason: rec.cls.reason,
      type_candidates: rec.cls.candidates || null,
      source_ref: g.id || g.label || null,
      heading_source_ref: null,
    });
  }

  // 多选答案组（inputs/accepted sets）
  for (const ag of parsed.answer_groups || []) {
    // 听力: {key, inputs_raw, slots, accept, required_count, section} — key=multiCorrect 原始键，不等于组索引
    // 阅读: {group, slots, accept, required_count, source} — key=group id, inputs=slots
    // 统一按槽位题目的 group 字段解析组记录；回退用 key/group
    const slotQ = questionsIn.find((q) => (ag.slots || []).includes(q.number));
    const key = ag.key ?? ag.group ?? null;
    let rec = null;
    if (slotQ && slotQ.group != null) rec = recByKey.get(slotQ.group) || null;
    if (!rec && key != null) rec = recByKey.get(key) || null;
    answerGroups.push({
      id: rec ? rec.id : `cam21:${book}:${test}:${skill}:answer_group:${key ?? "unknown"}`,
      page_ref: pageRef,
      numbers: ag.slots || [],
      inputs_raw: ag.inputs_raw || ag.slots || [],
      accept: ag.accept || [],
      required_count: ag.required_count ?? null,
      section: ag.section ?? null,
      source: ag.source || meta.source || "cam21-html",
    });
  }
  const answerGroupBySlot = new Map();
  for (const ag of answerGroups) for (const n of ag.numbers) answerGroupBySlot.set(n, ag);

  for (const q of questionsIn) {
    const rec = q.group != null ? recByKey.get(q.group) : null;
    const cls = rec ? rec.cls : null;
    const part = partOfQuestion(q) || (rec && rec.part) || (partOfNumber(q.number, parts) || "P?");
    const psg = skill === "reading" ? passagesIn.find((p) => p.passage === q.passage) || null : null;
    const notes = [];
    const gAssets = (rec && rec.groupAssets) || [];
    const letterOptions = cls && cls.type === "matching_information" ? Array.isArray(q.options) && q.options.length > 0 : false;
    const content = contentStatusOf({
      prompt: q.prompt,
      shared: null,
      options: q.options,
      pools: null,
      type: cls ? cls.type : "unknown",
      assets: gAssets,
      passageText: skill === "reading" ? passageTextOf(psg) : "",
      skill,
      letterOptions,
      groupContext: true,
    });
    const entry = answerKey.get(q.number) || null;
    const ag = answerGroupBySlot.get(q.number) || null;
    let answer;
    if (q.type === "multi" || (entry && entry.kind === "multi_member")) {
      const accept = (entry && entry.accept) || q.accept || (ag && ag.accept) || [];
      answer = {
        raw: null,
        accept,
        form: "group_set",
        status: accept.length ? "attached" : "missing",
        source: meta.source || "cam21-html",
        group_ref: ag ? ag.id : null,
        note: "multi_select 组答案（accepted set）；单槽分配未定义",
      };
    } else if (entry) {
      answer = { raw: entry.answer ?? null, form: entry.kind || "single", status: answerStatusOf({ raw: entry.answer }), source: meta.source || "cam21-html" };
    } else {
      answer = { raw: null, form: null, status: "missing", source: meta.source || "cam21-html", note: "no_answer_key_entry" };
    }
    const id = questionIdOf({ book, variant, skill, test, part, number: q.number });
    answers[id] = answer;
    const sourceRefs = [];
    for (const r of [meta.file || null, ...metaRefs]) if (r && !sourceRefs.includes(r)) sourceRefs.push(r);
    const record = {
      id,
      identity: { book, variant, skill, test, part, number: q.number },
      book,
      variant,
      skill,
      test,
      part,
      passage: skill === "reading" ? q.passage ?? null : null,
      number: q.number,
      group_id: rec ? rec.id : null,
      prompt: q.prompt || null,
      shared_prompt_ref: null,
      instruction: q.instruction || (rec ? rec.g.instruction : null) || null,
      constraints: rec ? parseWordLimit(rec.g.word_limit || [rec.g.instruction, rec.g.sublabel].filter((x) => x && String(x).trim()).join("\n")) : null,
      options: Array.isArray(q.options) ? q.options.map((o) => ({ label: (o && o.label) ?? null, text: (o && o.text) ?? null })) : [],
      assets: gAssets,
      answer_ref: id,
      audio_alignment_ref: null,
      source_refs: sourceRefs,
      content_status: content.status,
      content_presentation: content.presentation,
      content_notes: [...notes, ...content.notes],
      answer_status: answer.status,
      answer_mode: openModeFor(skill),
      classification_status: cls ? cls.status : "unknown",
      classification_reason: cls ? cls.reason : "no_group",
      type: cls ? cls.type : "unknown",
      page_ref: pageRef,
    };
    record.fully_complete = fullyCompleteOf(record);
    questions.push(record);
  }

  const page = {
    page_ref: pageRef,
    kind: "cam21-html",
    book,
    test,
    skill,
    variant,
    source_skill: sourceSkill,
    slug: null,
    url: null,
    source_page_id: null,
    raw_index: null,
    raw_file: meta.file || null,
    counts: {
      questions: questions.length,
      groups: groupRecords.length,
      groups_excluded: 0,
      answers_attached: questions.filter((q) => q.answer_status === "attached").length,
      passages: passagesIn.length,
    },
    warnings: (parsed.warnings || []).map((w) => ({ kind: (w && w.kind) || "unknown", numbers: (w && w.numbers) || undefined })),
  };

  return { page, groups: groupRecords, questions, answers, answer_groups: answerGroups, gaps };
}

function mergeGap(gaps, gap) {
  const key = `${gap.kind}|${gap.book}|${gap.variant}|${gap.skill}|${gap.test}|${gap.part ?? ""}`;
  const found = gaps.find((g) => g.__key === key);
  if (!found) {
    const entry = { ...gap, __key: key };
    if (Array.isArray(gap.numbers)) entry.numbers = gap.numbers.slice();
    gaps.push(entry);
    return entry;
  }
  if (Array.isArray(gap.numbers)) {
    const set = new Set([...(found.numbers || []), ...gap.numbers]);
    found.numbers = [...set].sort((a, b) => a - b);
  }
  return found;
}

/** manifest 覆盖检查：逐 item 逐 expected_number 对照索引 */
export function manifestGaps(index, manifest) {
  const gaps = [];
  if (!manifest || !Array.isArray(manifest.books)) return gaps;
  const byKey = new Map();
  const byTest = new Map();
  for (const q of index.questions) {
    byKey.set(`${q.book}|${q.variant}|${q.skill}|${q.test}|${q.number}`, q);
    const tkey = `${q.book}|${q.variant}|${q.skill}|${q.test}`;
    byTest.set(tkey, (byTest.get(tkey) || 0) + 1);
  }
  for (const b of manifest.books) {
    for (const item of b.items || []) {
      const tkey = `${b.book}|${item.variant}|${item.skill}|${item.test}`;
      const hasContent = (byTest.get(tkey) || 0) > 0;
      const nums = Array.isArray(item.expected_numbers) ? item.expected_numbers : [];
      if (!hasContent) {
        mergeGap(gaps, {
          kind: "content_not_indexed",
          book: b.book,
          variant: item.variant,
          skill: item.skill,
          test: item.test,
          part: null,
          expected_total: nums.length,
          manifest_status: item.status || null,
          note: item.skill === "writing" || item.skill === "speaking" ? "writing/speaking 抽取未实施" : "该套无索引内容（源未抓取或未解析）",
        });
        continue;
      }
      const missing = [];
      const partMismatch = [];
      for (const n of nums) {
        const q = byKey.get(`${b.book}|${item.variant}|${item.skill}|${item.test}|${n}`);
        if (!q) missing.push(n);
        else if (q.part !== item.part) partMismatch.push({ number: n, got: q.part, want: item.part });
      }
      if (missing.length) {
        mergeGap(gaps, {
          kind: "missing_questions",
          book: b.book,
          variant: item.variant,
          skill: item.skill,
          test: item.test,
          part: item.part,
          numbers: missing,
          expected_total: nums.length,
          manifest_status: item.status || null,
        });
      }
      if (partMismatch.length) {
        mergeGap(gaps, {
          kind: "part_mismatch",
          book: b.book,
          variant: item.variant,
          skill: item.skill,
          test: item.test,
          part: item.part,
          detail: partMismatch,
        });
      }
    }
  }
  return gaps;
}

/**
 * 构建索引。
 * @param {object} input
 * @param {Array<{parsed:object,meta:object}>} input.pages PTE 页面
 * @param {Array<{parsed:object,meta:object}>} input.cam21Pages cam21 页面
 * @param {object|null} input.manifest expected-manifest
 * @param {Array<object>} [input.alternate_sources] 备用来源记录（如剑21 PTE raw）
 * @param {object} [input.options] {run_id, generated_at_utc}
 */
export function buildIndex({ pages = [], cam21Pages = [], manifest = null, alternate_sources = [], options = {} } = {}) {
  const index = {
    schema: INDEX_SCHEMA,
    run_id: options.run_id ?? null,
    generated_at_utc: options.generated_at_utc || new Date().toISOString(),
    pages: [],
    groups: [],
    questions: [],
    answers: {},
    answer_groups: [],
    gaps: [],
    alternate_sources: alternate_sources.slice(),
  };
  for (const { parsed, meta } of pages) {
    const built = buildFromPtePage(parsed, meta);
    index.pages.push(built.page);
    index.groups.push(...built.groups);
    index.questions.push(...built.questions);
    Object.assign(index.answers, built.answers);
    index.answer_groups.push(...built.answer_groups);
    for (const g of built.gaps) mergeGap(index.gaps, g);
  }
  for (const { parsed, meta } of cam21Pages) {
    const built = buildFromCam21Page(parsed, meta);
    index.pages.push(built.page);
    index.groups.push(...built.groups);
    index.questions.push(...built.questions);
    Object.assign(index.answers, built.answers);
    index.answer_groups.push(...built.answer_groups);
    for (const g of built.gaps) mergeGap(index.gaps, g);
  }
  if (manifest) {
    for (const g of manifestGaps(index, manifest)) mergeGap(index.gaps, g);
  }
  index.gaps = index.gaps.map((g) => {
    const { __key, ...rest } = g;
    return rest;
  });
  // 陈旧空组缺口后置过滤：缺口题号若已被最终题目完整覆盖（内容组 + 非 missing_content），
  // 则该结构性空组缺口作废，移入 empty_group_resolved（S12）
  const questionByScope = new Map();
  for (const q of index.questions) {
    const k = `${q.book}:${q.variant}:${q.skill}:${q.test}:${q.number}`;
    if (!questionByScope.has(k)) questionByScope.set(k, q);
  }
  const emptyGroupResolved = [];
  index.gaps = index.gaps.filter((g) => {
    if (g.kind !== "empty_group_excluded" || !Array.isArray(g.numbers) || !g.numbers.length) return true;
    const covered = g.numbers.every((n) => {
      const q = questionByScope.get(`${g.book}:${g.variant}:${g.skill}:${g.test}:${n}`);
      return !!(q && q.group_id && q.content_status !== "missing_content");
    });
    if (!covered) return true;
    emptyGroupResolved.push({
      kind: "empty_group_resolved",
      book: g.book,
      variant: g.variant,
      skill: g.skill,
      test: g.test,
      part: g.part ?? null,
      numbers: g.numbers,
      note: "题号已由同套内容组覆盖；结构性空组缺口作废（S12）",
    });
    return false;
  });
  index.empty_group_resolved = emptyGroupResolved;
  index.stats = summarize(index);
  return index;
}

/** 核验条目压缩摘要（用于 cross_source_conflicts / official_verifications 自包含记录） */
function verificationEvidenceSummary(evidence) {
  if (!evidence) return null;
  const out = {};
  if (evidence.official_pdf) out.official_pdf = { file: evidence.official_pdf.file ?? null, sha256: evidence.official_pdf.sha256 ?? null };
  if (evidence.instruction) out.instruction = { file_page: evidence.instruction.file_page ?? null, printed_page: evidence.instruction.printed_page ?? null };
  if (evidence.answer_key) out.answer_key = { file_page: evidence.answer_key.file_page ?? null, printed_page: evidence.answer_key.printed_page ?? null };
  return out;
}

function mergeVerification(cur, v, from) {
  const decisions = Array.isArray(cur && cur.decisions) ? cur.decisions.slice() : [];
  if (!decisions.includes(v.id)) decisions.push(v.id);
  return {
    decision_id: v.id,
    decisions,
    from: { ...((cur && cur.from) || {}), ...from },
    evidence: v.evidence || null,
    verifier: v.verifier || null,
  };
}

function mergeQuestionVerification(cur, v, from) {
  const decisions = Array.isArray(cur && cur.decisions) ? cur.decisions.slice() : [];
  if (!decisions.includes(v.id)) decisions.push(v.id);
  return { decisions, from: { ...((cur && cur.from) || {}), ...from } };
}

/**
 * 应用官方 PDF 组级核验覆盖（S08；模式同 S07 裁决：identity + from 原值守卫）。
 *  - 守卫：group_id 未命中 -> verification_issues 记 group_not_found；from 值不匹配 ->
 *    decision_stale（保留原值，不强套）；
 *  - 分类覆盖（to.type）：组与组内题目 type + classification_reason=official_pdf_override，
 *    原值保留于 verification.from；
 *  - 答案表示（answer_representation）：answers[qid].official = {value, form, decision_id,
 *    mapped_from_raw, raw_form_consistent}；raw 原值不动；
 *  - 字数限制（to.word_limit）：组与组内题目 word_limit/constraints 更新为官方值；
 *  - 冲突条目（kind=classification_conflict / word_limit_conflict，含 from/to/裁决来源）追加到
 *    index.cross_source_conflicts。
 * 原地修改 index；返回 {applied, issues}。
 */
export function applyGroupVerifications(index, verifications = []) {
  const applied = [];
  const issues = [];
  const conflictEntries = [];
  const groupById = new Map((index.groups || []).map((g) => [g.id, g]));
  for (const v of verifications) {
    const gid = v.identity && v.identity.group_id;
    const g = gid ? groupById.get(gid) : null;
    if (!g) {
      issues.push({ decision_id: v.id, kind: "group_not_found", group_id: gid ?? null });
      continue;
    }
    const from = {};
    let stale = null;
    if (v.from && v.from.type != null && g.type !== v.from.type) stale = { field: "type", expected: v.from.type, actual: g.type };
    if (!stale && v.from && v.from.word_limit != null && g.word_limit !== v.from.word_limit) stale = { field: "word_limit", expected: v.from.word_limit, actual: g.word_limit };
    if (stale) {
      issues.push({ decision_id: v.id, kind: "decision_stale", group_id: g.id, ...stale });
      continue;
    }
    const qsInGroup = (index.questions || []).filter((q) => q.group_id === g.id);
    if (v.to && v.to.type) {
      from.type = g.type;
      from.classification_reason = g.classification_reason;
      g.type = v.to.type;
      g.classification_reason = "official_pdf_override";
      g.verification = mergeVerification(g.verification, v, from);
      for (const q of qsInGroup) {
        q.type = v.to.type;
        q.classification_reason = "official_pdf_override";
        q.verification = mergeQuestionVerification(q.verification, v, from);
        q.fully_complete = fullyCompleteOf(q);
      }
      if (v.answer_representation) {
        const rep = v.answer_representation;
        for (const n of rep.numbers || []) {
          const qid = questionIdOf({
            book: v.identity.book,
            variant: v.identity.variant,
            skill: v.identity.skill,
            test: normTest(v.identity.test),
            part: v.identity.part,
            number: n,
          });
          const entry = index.answers ? index.answers[qid] : null;
          if (!entry) {
            issues.push({ decision_id: v.id, kind: "answer_not_found", question_id: qid });
            continue;
          }
          const rawNorm = String(entry.raw ?? "").trim().toLowerCase();
          const mapped = rep.map ? rep.map[rawNorm] ?? null : null;
          const officialValue = rep.official_values ? rep.official_values[String(n)] ?? null : null;
          entry.official = {
            value: officialValue,
            form: rep.form || null,
            decision_id: v.id,
            mapped_from_raw: mapped,
            raw_form_consistent: officialValue != null && mapped != null ? mapped === officialValue : null,
          };
          if (entry.official.raw_form_consistent === false) {
            issues.push({ decision_id: v.id, kind: "answer_form_mismatch", question_id: qid, raw: entry.raw, mapped, official: officialValue });
          }
        }
      }
      conflictEntries.push({
        kind: v.kind,
        book: v.identity.book,
        variant: v.identity.variant,
        skill: v.identity.skill,
        test: normTest(v.identity.test),
        part: v.identity.part,
        group_id: g.id,
        range: v.identity.range || null,
        from: { type: from.type, classification_reason: from.classification_reason, source_pool: v.from.source_pool || null },
        to: v.to,
        decision_id: v.id,
        ruling: "官方 PDF 核验覆盖；原值保留于 from，裁决来源 decision_id",
        evidence_summary: verificationEvidenceSummary(v.evidence),
      });
    }
    if (v.to && v.to.word_limit) {
      from.word_limit = g.word_limit;
      g.word_limit = v.to.word_limit;
      g.constraints = parseWordLimit(v.to.word_limit);
      g.verification = mergeVerification(g.verification, v, from);
      for (const q of qsInGroup) {
        q.constraints = parseWordLimit(v.to.word_limit);
        q.verification = mergeQuestionVerification(q.verification, v, from);
        q.fully_complete = fullyCompleteOf(q);
      }
      conflictEntries.push({
        kind: v.kind,
        book: v.identity.book,
        variant: v.identity.variant,
        skill: v.identity.skill,
        test: normTest(v.identity.test),
        part: v.identity.part,
        group_id: g.id,
        range: v.identity.range || null,
        from: { word_limit: from.word_limit },
        to: v.to,
        decision_id: v.id,
        ruling: "官方 PDF 核验覆盖；原值保留于 from，裁决来源 decision_id",
        evidence_summary: verificationEvidenceSummary(v.evidence),
      });
    }
    applied.push({
      decision_id: v.id,
      kind: v.kind,
      group_id: g.id,
      range: v.identity.range || null,
      from,
      to: v.to || null,
      evidence_summary: verificationEvidenceSummary(v.evidence),
    });
  }
  index.cross_source_conflicts = (index.cross_source_conflicts || []).concat(conflictEntries);
  return { applied, issues };
}

/** 分类索引查询：过滤 + 分页（先过滤后分页，不扫描后错误分页） */
export function queryIndex(index, filters = {}) {
  const { skill, variant, type, book, test, part, passage, number, status, text, page = 1, pageSize = 50 } = filters;
  let skillWanted = null;
  let variantWanted = null;
  let typeWanted = null;
  let familyWanted = null;
  if (skill != null) {
    skillWanted = resolveSkillName(skill);
    if (!skillWanted) throw new Error(`queryIndex: 未知 skill: ${skill}`);
  }
  if (variant != null) {
    variantWanted = resolveVariantName(variant);
    if (!variantWanted) throw new Error(`queryIndex: 未知 variant: ${variant}`);
  }
  if (type != null) {
    typeWanted = resolveTypeName(type);
    if (!typeWanted) {
      familyWanted = FAMILY_LOOKUP.get(normNameLocal(type)) ?? null;
      if (!familyWanted) throw new Error(`queryIndex: 未知 type/family: ${type}`);
    }
  }
  let statusWanted = null;
  let statusKind = null;
  if (status != null) {
    const s = String(status);
    if (CONTENT_STATUS.includes(s)) {
      statusWanted = s;
      statusKind = "content";
    } else if (ANSWER_STATUS.includes(s)) {
      statusWanted = s;
      statusKind = "answer";
    } else if (CLASSIFICATION_STATUS.includes(s)) {
      statusWanted = s;
      statusKind = "classification";
    } else if (s === "fully_complete" || s === "gap") {
      statusWanted = s;
      statusKind = "complete";
    } else {
      throw new Error(`queryIndex: 未知 status: ${status}`);
    }
  }
  let bookWanted = null;
  if (book != null) {
    bookWanted = Number(book);
    if (!Number.isFinite(bookWanted)) throw new Error(`queryIndex: book 非数字: ${book}`);
  }
  const testWanted = test != null ? normTest(test) : null;
  const partWanted = part != null ? String(part).replace(/^p(\d+)$/i, (m, d) => `P${d}`) : null;
  const passageWanted = passage != null ? Number(passage) : null;
  const numberWanted = number != null ? Number(number) : null;
  const textWanted = text != null ? String(text).toLowerCase() : null;

  let groupById = null;
  if (textWanted) {
    groupById = new Map(index.groups.map((g) => [g.id, g]));
  }

  const matched = [];
  for (const q of index.questions) {
    if (skillWanted && q.skill !== skillWanted) continue;
    if (variantWanted && q.variant !== variantWanted) continue;
    if (typeWanted && q.type !== typeWanted) continue;
    if (familyWanted && typeFamily(q.type) !== familyWanted) continue;
    if (bookWanted != null && q.book !== bookWanted) continue;
    if (testWanted != null && q.test !== testWanted) continue;
    if (partWanted != null && q.part !== partWanted) continue;
    if (passageWanted != null && q.passage !== passageWanted) continue;
    if (numberWanted != null && q.number !== numberWanted) continue;
    if (statusWanted != null) {
      if (statusKind === "content" && q.content_status !== statusWanted) continue;
      if (statusKind === "answer" && q.answer_status !== statusWanted) continue;
      if (statusKind === "classification" && q.classification_status !== statusWanted) continue;
      if (statusKind === "complete") {
        if (statusWanted === "fully_complete" && !q.fully_complete) continue;
        if (statusWanted === "gap" && q.fully_complete) continue;
      }
    }
    if (textWanted) {
      const g = q.group_id ? groupById.get(q.group_id) : null;
      const hay = [q.prompt, q.instruction, g ? g.shared_prompt : null, g ? g.heading_text : null, q.id]
        .filter(Boolean)
        .join("\n")
        .toLowerCase();
      if (!hay.includes(textWanted)) continue;
    }
    matched.push(q);
  }
  const total = matched.length;
  const size = Math.max(1, Math.min(500, Number(pageSize) || 50));
  const pageNum = Math.max(1, Number(page) || 1);
  const pageCount = total === 0 ? 0 : Math.ceil(total / size);
  const start = (pageNum - 1) * size;
  return { total, page: pageNum, pageSize: size, pageCount, items: matched.slice(start, start + size) };
}

/** 汇总统计 */
export function summarize(index) {
  const inc = (obj, key) => {
    const k = key ?? "null";
    obj[k] = (obj[k] || 0) + 1;
  };
  const bySkill = {};
  const byVariant = {};
  const byContent = {};
  const byAnswer = {};
  const byClassification = {};
  const byType = {};
  const byBook = {};
  let fully = 0;
  for (const q of index.questions) {
    inc(bySkill, q.skill);
    inc(byVariant, q.variant);
    inc(byContent, q.content_status);
    inc(byAnswer, q.answer_status);
    inc(byClassification, q.classification_status);
    inc(byType, q.type);
    const b = byBook[q.book] || (byBook[q.book] = { questions: 0, fully_complete: 0, content_complete: 0, answers_attached: 0, classified: 0, gaps: 0 });
    b.questions++;
    if (q.fully_complete) {
      b.fully_complete++;
      fully++;
    } else {
      b.gaps++;
    }
    if (q.content_status === "complete") b.content_complete++;
    if (q.answer_status === "attached") b.answers_attached++;
    if (q.classification_status === "classified" || q.classification_status === "inferred") b.classified++;
  }
  const gapsByKind = {};
  for (const g of index.gaps || []) inc(gapsByKind, g.kind);
  return {
    pages: index.pages.length,
    groups: index.groups.length,
    questions: index.questions.length,
    answers: Object.keys(index.answers || {}).length,
    answer_groups: index.answer_groups.length,
    fully_complete: fully,
    gaps_total: (index.gaps || []).length,
    gaps_by_kind: gapsByKind,
    by_skill: bySkill,
    by_variant: byVariant,
    by_content_status: byContent,
    by_answer_status: byAnswer,
    by_classification_status: byClassification,
    by_type: byType,
    by_book: byBook,
  };
}

export const __internals = {
  normNameLocal,
  FAMILY_LOOKUP,
  questionIdOf,
  groupIdOf,
  passageIdOf,
  passageForGroup,
  passageForNumber,
  answerStatusOf,
  fullyCompleteOf,
  normalizeAssets,
  mergeGap,
};
