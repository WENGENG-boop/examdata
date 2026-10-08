/**
 * taxonomy.mjs — 雅思题型统一分类（S08）
 *
 * 固定 23 种题型枚举；分类优先依据「来源明确 type + 组指令文本」，
 * 指令缺失/未命中时按组结构（slots/pools/选项）保守回退，判断题以 pool 标签为准。
 * 冲突不靠答案格式猜：来源语义类型与指令判定不一致 → conflict（type=unknown 带候选）；
 * 无法自动判定的 → unknown 并带原因进入 review。topic 标签可选，不作为题型完整性依据。
 */

export const SCHEMA = "ielts-taxonomy/1";

/** 固定题型枚举（顺序稳定，勿随意增删） */
export const QUESTION_TYPES = Object.freeze([
  "multiple_choice_single",
  "multiple_choice_multiple",
  "true_false_not_given",
  "yes_no_not_given",
  "matching_headings",
  "matching_information",
  "matching_features",
  "matching_sentence_endings",
  "form_completion",
  "note_completion",
  "table_completion",
  "flow_chart_completion",
  "summary_completion",
  "sentence_completion",
  "diagram_labeling",
  "map_plan_labeling",
  "short_answer",
  "writing_task1",
  "writing_task2",
  "speaking_part1",
  "speaking_part2",
  "speaking_part3",
  "unknown",
]);

/** 题型族（用于呈现校验与冲突提示，不改变枚举） */
export const TYPE_FAMILIES = Object.freeze({
  multiple_choice_single: "choice",
  multiple_choice_multiple: "choice",
  true_false_not_given: "judgement",
  yes_no_not_given: "judgement",
  matching_headings: "matching",
  matching_information: "matching",
  matching_features: "matching",
  matching_sentence_endings: "matching",
  form_completion: "completion",
  note_completion: "completion",
  table_completion: "completion",
  flow_chart_completion: "completion",
  summary_completion: "completion",
  sentence_completion: "completion",
  diagram_labeling: "visual",
  map_plan_labeling: "visual",
  short_answer: "short_answer",
  writing_task1: "open",
  writing_task2: "open",
  speaking_part1: "open",
  speaking_part2: "open",
  speaking_part3: "open",
  unknown: "unknown",
});

export function typeFamily(type) {
  return TYPE_FAMILIES[type] || null;
}

/** 类型标签：canonical / 英文 / 中文 / 别名（精确匹配，无模糊） */
export const TYPE_LABELS = Object.freeze({
  multiple_choice_single: { en: "Multiple choice (single answer)", zh: "单项选择", aliases: ["multiple choice", "mcq", "single choice", "mcq single", "单选"] },
  multiple_choice_multiple: { en: "Multiple choice (multiple answers)", zh: "多项选择", aliases: ["mcq multiple", "multiple answers", "multi select", "choose two letters", "多选"] },
  true_false_not_given: { en: "True / False / Not Given", zh: "判断正误", aliases: ["tfng", "true false", "true/false/not given", "true false not given", "判断"] },
  yes_no_not_given: { en: "Yes / No / Not Given", zh: "观点判断", aliases: ["ynng", "yes no", "yes/no/not given", "yes no not given"] },
  matching_headings: { en: "Matching headings", zh: "标题匹配", aliases: ["headings", "list of headings", "heading matching"] },
  matching_information: { en: "Matching information", zh: "信息匹配", aliases: ["which paragraph contains", "which section contains", "information matching"] },
  matching_features: { en: "Matching features", zh: "特征匹配", aliases: ["matching people", "matching experts", "people matching", "feature matching"] },
  matching_sentence_endings: { en: "Matching sentence endings", zh: "句尾匹配", aliases: ["sentence endings", "matching endings"] },
  form_completion: { en: "Form completion", zh: "表单填空", aliases: ["form", "fact sheet completion", "form filling", "表单"] },
  note_completion: { en: "Note completion", zh: "笔记填空", aliases: ["notes completion", "note", "notes", "lecture notes", "笔记"] },
  table_completion: { en: "Table completion", zh: "表格填空", aliases: ["table", "表格"] },
  flow_chart_completion: { en: "Flow-chart completion", zh: "流程图填空", aliases: ["flowchart", "flow chart", "flow-chart", "流程图"] },
  summary_completion: { en: "Summary completion", zh: "摘要填空", aliases: ["summary", "摘要"] },
  sentence_completion: { en: "Sentence completion", zh: "句子填空", aliases: ["sentences", "sentence", "句子"] },
  diagram_labeling: { en: "Diagram labeling", zh: "图表标注", aliases: ["diagram", "label the diagram"] },
  map_plan_labeling: { en: "Map/plan labeling", zh: "地图/平面图标注", aliases: ["map labeling", "plan labeling", "map", "plan", "label the map"] },
  short_answer: { en: "Short answer", zh: "简答题", aliases: ["short answers", "answer questions", "简答"] },
  writing_task1: { en: "Writing Task 1", zh: "写作任务一", aliases: ["task 1", "writing task one", "wt1", "task1"] },
  writing_task2: { en: "Writing Task 2", zh: "写作任务二", aliases: ["task 2", "writing task two", "wt2", "task2"] },
  speaking_part1: { en: "Speaking Part 1", zh: "口语第一部分", aliases: ["speaking part one", "part 1", "sp1", "part1"] },
  speaking_part2: { en: "Speaking Part 2", zh: "口语第二部分", aliases: ["speaking part two", "cue card", "part 2", "sp2", "part2"] },
  speaking_part3: { en: "Speaking Part 3", zh: "口语第三部分", aliases: ["speaking part three", "part 3", "sp3", "part3"] },
  unknown: { en: "Unknown", zh: "未分类", aliases: [] },
});

export const SKILLS = Object.freeze(["listening", "reading", "writing", "speaking"]);

export const SKILL_LABELS = Object.freeze({
  listening: { en: "Listening", zh: "听力", aliases: ["listen", "l"] },
  reading: { en: "Reading", zh: "阅读", aliases: ["read", "r"] },
  writing: { en: "Writing", zh: "写作", aliases: ["write", "w"] },
  speaking: { en: "Speaking", zh: "口语", aliases: ["speak", "s"] },
});

export const VARIANTS = Object.freeze(["academic", "general", "shared"]);

export const VARIANT_LABELS = Object.freeze({
  academic: { en: "Academic", zh: "学术类", aliases: ["acad", "a", "学术"] },
  general: { en: "General Training", zh: "培训类", aliases: ["gt", "g", "general training", "培训", "移民类"] },
  shared: { en: "Shared", zh: "通用", aliases: ["common", "both", "通用"] },
});

function normName(value) {
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

function buildLookup(labels, canonicalList) {
  const map = new Map();
  const add = (key, canonical) => {
    const k = normName(key);
    if (k && !map.has(k)) map.set(k, canonical);
  };
  for (const canonical of canonicalList) {
    add(canonical, canonical);
    const meta = labels[canonical];
    if (!meta) continue;
    add(meta.en, canonical);
    add(meta.zh, canonical);
    for (const alias of meta.aliases || []) add(alias, canonical);
  }
  return map;
}

const TYPE_LOOKUP = buildLookup(TYPE_LABELS, QUESTION_TYPES);
const SKILL_LOOKUP = buildLookup(SKILL_LABELS, SKILLS);
const VARIANT_LOOKUP = buildLookup(VARIANT_LABELS, VARIANTS);

/** 题型名解析（canonical/英文/中文/别名；精确匹配，无模糊）→ canonical | null */
export function resolveTypeName(value) {
  return TYPE_LOOKUP.get(normName(value)) ?? null;
}

export function resolveSkillName(value) {
  return SKILL_LOOKUP.get(normName(value)) ?? null;
}

export function resolveVariantName(value) {
  return VARIANT_LOOKUP.get(normName(value)) ?? null;
}

export function typeLabel(type, lang = "en") {
  const meta = TYPE_LABELS[type];
  if (!meta) return null;
  return lang === "zh" ? meta.zh : meta.en;
}

/**
 * 来源语义类型映射（cam21 阅读组的明确类型）。
 * 通用结构 kind（gap/line/input/…）不算权威，见 GENERIC_SOURCE_HINTS。
 */
export const SOURCE_TYPE_MAP = Object.freeze({
  "note completion": "note_completion",
  "true false not given": "true_false_not_given",
  "matching information": "matching_information",
  "summary completion": "summary_completion",
  "matching people": "matching_features",
  "multiple choice": "multiple_choice_single",
  "yes no not given": "yes_no_not_given",
  "table completion": "table_completion",
  "matching sentence endings": "matching_sentence_endings",
  "flow chart completion": "flow_chart_completion",
  "form completion": "form_completion",
  "sentence completion": "sentence_completion",
  "diagram labeling": "diagram_labeling",
  "map plan labeling": "map_plan_labeling",
  "short answer": "short_answer",
});

/** 通用来源 kind → 题型族提示（弱证据，仅用于校验与兜底推断，不单独定性） */
export const GENERIC_SOURCE_HINTS = Object.freeze({
  gap: "completion",
  input: "completion",
  "cell gap": "completion",
  "multi select": "choice_multiple",
  multi: "choice_multiple",
  mcq: "choice_single",
  "letter match": "matching",
  tfng: "judgement",
  "true false": "judgement",
  headings: "matching",
  letters: "matching",
});

const HINT_FAMILY_TYPES = Object.freeze({
  completion: ["form_completion", "note_completion", "table_completion", "flow_chart_completion", "summary_completion", "sentence_completion"],
  choice_single: ["multiple_choice_single"],
  choice_multiple: ["multiple_choice_multiple"],
  matching: ["matching_headings", "matching_information", "matching_features", "matching_sentence_endings"],
  judgement: ["true_false_not_given", "yes_no_not_given"],
});

function hintFamilyMatches(family, type) {
  const list = HINT_FAMILY_TYPES[family];
  return Array.isArray(list) && list.includes(type);
}

/** 来源明确类型解析：canonical / 语义映射 / "Multiple Choice (choose TWO)" 形态 → canonical | null */
export function sourceTypeToCanonical(sourceType) {
  if (sourceType == null) return null;
  const direct = resolveTypeName(sourceType);
  if (direct) return direct;
  const norm = normName(sourceType);
  if (SOURCE_TYPE_MAP[norm]) return SOURCE_TYPE_MAP[norm];
  const mcqMulti = /^multiple choice choose (two|three|four|five|\d)$/.exec(norm);
  if (mcqMulti) return "multiple_choice_multiple";
  const mcqSingle = /^multiple choice( \(?choose (one|a)\)?)?$/.exec(norm);
  if (mcqSingle) return "multiple_choice_single";
  return null;
}

/**
 * 组指令匹配规则（按顺序，首个命中生效）。
 * 顺序原则：专属短语（句尾/标题/信息/图表）→ 填空细分 → 判断 → 特征匹配 → 选择 → 开放题。
 * 只匹配指令性文本；词表由全量真实语料回归校准（ielts-data 各 run 下 scratch/s08 回归）。
 */
const INSTRUCTION_RULES = [
  {
    type: "matching_sentence_endings",
    patterns: [
      /complete\s+each\s+sentence\s+with\s+the\s+correct\s+ending/i,
      /matching\s+sentence\s+endings/i,
      /complete\s+each\s+key\s+point/i,
      /ch[o]?se\s+one\s+phrase/i,
      /complete\s+each\s+of\s+the\s+following\s+statements[^.]{0,80}\bending\b/i,
      /match\s+each\s+sentence\s+with\s+the\s+(correct\s+)?ending/i,
    ],
  },
  {
    type: "matching_headings",
    patterns: [
      /(choose|select)\s+the\s+(most\s+suitable\s+|correct\s+)?headings?\b/i,
      /correct\s+heading\s+for\s+(each\s+)?(paragraph|section)/i,
      /list\s+of\s+headings/i,
    ],
  },
  {
    type: "matching_information",
    patterns: [
      /which\s+(paragraph|section)\s+contains/i,
      /which\s+(paragraph|section)\b[^.?]{0,80}\bcontains?\b/i,
      /state\s+which\s+(paragraph|section)/i,
      /which\s+paragraphs?\s+(concentrate|state|discuss|mention|refer)/i,
      /in\s+which\s+(?:(?:two|three|four|five|six|\d)\s+)?(?:paragraphs?|sections?)\b/i,
    ],
  },
  {
    type: "diagram_labeling",
    patterns: [
      /label\s+the\s+diagram/i,
      /complete\s+the\s+diagram/i,
      /complete\s+the\s+labels?\s+on\s+(the\s+)?diagram/i,
      /complete\s+the\s+(vertical\s+)?axis/i,
      /label\s+the\s+chart/i,
      /label\s+the\s+[^.]{0,40}\bon\s+the\s+diagram/i,
      /the\s+diagram\s+below\s+illustrates/i,
    ],
  },
  {
    type: "map_plan_labeling",
    patterns: [
      /label\s+the\s+(map|plan)\b/i,
      /label\s+the\s+[^.]{0,40}\bon\s+the\s+(map|plan)\b/i,
      /complete\s+the\s+plan\b/i,
    ],
  },
  {
    type: "flow_chart_completion",
    patterns: [
      /complete\s+the\s+flow[\s-]?chart/i,
      /complete\s+the\s+steps/i,
    ],
  },
  {
    type: "form_completion",
    patterns: [
      /complete\s+(in\s+)?(the\s+)?(following\s+)?(form|application\s+form|fact\s?sheet|registration|booking|questionnaire|invoice|order\s+form)\b/i,
    ],
  },
  {
    type: "note_completion",
    patterns: [
      /complete\s+(the\s+)?(following\s+)?(notes?|lecture\s+notes?)\b/i,
      /complete\s+the\s+(notice|explanation)\b/i,
      /complete\s+[^\s.]{1,30}['’]s\s+notes/i,
    ],
  },
  {
    type: "table_completion",
    patterns: [
      /complete\s+(the\s+)?(following\s+)?table/i,
      /choose\s+the\s+table\s+below/i,
    ],
  },
  {
    type: "summary_completion",
    patterns: [
      /complete\s+(the\s+)?(following\s+)?summary/i,
    ],
  },
  {
    type: "sentence_completion",
    patterns: [
      /complete\s+(the\s+)?(following\s+)?sentences?\b/i,
      /complete\s+each\s+of\s+the\s+following\s+statements?[^.]{0,80}words\s+taken\s+from/i,
      /complete\s+each\s+of\s+the\s+following\s+sentences/i,
    ],
  },
  {
    type: "yes_no_not_given",
    patterns: [
      /agree\s+with\s+the\s+(views?|claims?|opinions?)/i,
      /reflect\s+the\s+(claims|views|opinions|situation)/i,
      /write\s+yes\s+if/i,
      /yes\s+if\s+the\s+statement\s+agrees/i,
    ],
  },
  {
    type: "true_false_not_given",
    patterns: [
      /agree\s+with\s+the\s+(following\s+)?(given\s+)?information/i,
      /write\s+true\s+if/i,
      /true\s+if\s+the\s+statement\s+agrees/i,
    ],
  },
  {
    type: "matching_features",
    patterns: [
      /match\s+each\b[^.]{0,100}?\bwith\b/i,
      /match\s+each\b[^.]{0,100}?\bto\s+the\b/i,
      /match\s+the\s+[a-z]+\s+with\s+the\b/i,
      /match\s+the\s+(list|people|pairs|cities|groups|descriptions|statements|processes|names|items|options|words|phrases|findings|nationalities|systems|companies|experts|scientists|researchers|writers|speakers|hotels|countries|places)\b[^.]{0,140}?\b(with|to)\b/i,
      /list\s+of\s+(people|experts|scientists|researchers|writers|speakers|companies|descriptions|findings|statements|nationalities|phrases|systems|pairs|processes|options|items|topics|ways|methods|reasons|courses|activities|jobs|inventions|inventors|dates|numbers|places|countries|hotels|vehicles|equipment|destinations|exhibits|paintings|styles|modules)/i,
      /matching\s+(people|features|experts)/i,
      /classify\s+the\b/i,
      /state\s+whether/i,
      /which\s+of\s+the\s+list\b/i,
      /choose\s+your\s+answers?\s+from\s+the\s+(box|list|options|table)/i,
      /choose\s+(six|seven|eight|five|four|three|two|\d)\s+answers?\s+from\s+the\s+(box|list|options|table)/i,
      /write\s+the\s+correct\s+letter\s*,?\s*A\s*[-–—]\s*[A-Za-z]\b/i,
      /write\s+the\s+correct\s+letters?\s*,?\s*A\s*[,;]\s*B\b/i,
      /write\s+the\s+appropriate\s+letters?\s+A[-–—]?C/i,
      /next\s+to\s+questions?\b/i,
      /next\s+to\s+each\s+name\b/i,
      /look\s+at\s+figures?/i,
      /look\s+at\s+the\s+drawings/i,
      /decide\s+which/i,
      /tick\s+column/i,
      /some\s+of\s+the\s+exhibits/i,
      /indicate\s+who\s+first/i,
      /(?:^|[.?!]\s*)the\s+following\s+are\b/i,
      /\b(which|who|what)\b(?!\s+(?:two|three|four|five|six|seven|eight|\d)\b)[^.?]{0,140}\beach\b/i,
      /\b(which|who|what)\b(?!\s+(?:two|three|four|five|six|seven|eight|\d)\b)[^.?]{0,140}\bfollowing\s+(items|things|features|ways)\b/i,
    ],
  },
  {
    type: "multiple_choice_multiple",
    patterns: [
      /choose\s+(two|three|four|five|six|seven|eight|\d)\s+letters?/i,
      /circle\s+(the\s+)?(two|three|four|five|\d)\s+(other\s+)?(letters?|items?|options?|answers?|things?|features?|reasons?)/i,
      /choose\s+(two|three|four|five|\d)\s+(correct\s+)?(options?|answers?|features?|reasons?)/i,
      /which\s+(two|three|four|five|\d)\s+of\s+the\s+following/i,
      /(circle|select)\s+the\s+(two|three|four|five|\d)\s+correct\s+(options?|answers?)/i,
    ],
  },
  {
    type: "multiple_choice_single",
    patterns: [
      /choose\s+the\s+(correct|appropriate)\s+letters?\b/i,
      /circle\s+the\s+(correct|appropriate)\s+letters?\b/i,
      /choose\s+the\s+correct\s+(answer|option)/i,
      /choose\s+the\s+best\s+answer/i,
      /circle\s+the\s+correct\s+(answer|option)/i,
      /choose\s+[abc]\s*,\s*[abc]\s+or\s+[abc]\b/i,
      /choose\s+the\s+most\s+suitable\s+title/i,
    ],
  },
  {
    type: "short_answer",
    patterns: [
      /answer\s+the\s+(following\s+)?questions?/i,
      /answer\s+questions?\s+\d/i,
      /write\s+short\s+answers?/i,
      /\blist\s+the\s+(two|three|four|five|six|seven|eight|\d)\b/i,
    ],
  },
  { type: "writing_task1", skills: ["writing"], patterns: [/task\s*1\b/i] },
  { type: "writing_task2", skills: ["writing"], patterns: [/task\s*2\b/i] },
  { type: "speaking_part1", skills: ["speaking"], patterns: [/part\s*1\b/i] },
  { type: "speaking_part2", skills: ["speaking"], patterns: [/part\s*2\b/i] },
  { type: "speaking_part3", skills: ["speaking"], patterns: [/part\s*3\b/i] },
];

/** 指令文本 → {type, pattern} | null */
export function matchInstruction(text, skill = null) {
  const src = String(text ?? "");
  if (!src.trim()) return null;
  for (const rule of INSTRUCTION_RULES) {
    if (rule.skills && (!skill || !rule.skills.includes(skill))) continue;
    for (const pattern of rule.patterns) {
      if (pattern.test(src)) return { type: rule.type, pattern: String(pattern) };
    }
  }
  return null;
}

const WORD_LIMIT_ONLY = /^\s*(write|use)\b[^.]{0,80}?\b(words?|number)\b[^.]{0,20}\.?\s*$/i;

const SUMMARY_LIKE_KINDS = Object.freeze(["gap", "line", "line_plain", "line_paren", "line_ellipsis", "cell_gap"]);
const SENTENCE_LIKE_KINDS = Object.freeze(["gap", "line", "line_plain", "line_paren", "line_ellipsis"]);

function isJudgementType(type) {
  return type === "true_false_not_given" || type === "yes_no_not_given";
}

/**
 * 组结构派生（slots/pools/assets → 结构特征）。
 * 供分类回退、索引与回归共用；不修改传入对象。
 */
export function deriveStructure(group = {}) {
  const slots = Array.isArray(group.slots) ? group.slots : [];
  const pools = Array.isArray(group.pools) ? group.pools : [];
  const slot_kinds = [...new Set(slots.map((s) => String((s && s.kind) || "unknown")))];
  const has_slot_options = slots.some((s) => Array.isArray(s && s.options) && s.options.length > 0);
  const pool_summaries = pools.map((p) => ({
    kind: String((p && p.kind) || "unknown"),
    labels: (p && Array.isArray(p.options) ? p.options : []).map((o) => String((o && o.label) ?? "")),
  }));
  const pool_kinds = [...new Set(pool_summaries.map((p) => p.kind))];
  const pool_labels = pool_summaries.flatMap((p) => p.labels);
  const question_like_slots = slots.filter((s) => /\?\s*$/.test(String((s && s.prompt) || ""))).length;
  const prompts = slots.map((s) => String((s && s.prompt) || "").trim()).filter(Boolean);
  const same_prompt_slots = prompts.length >= 2 && prompts.every((p) => p === prompts[0]);
  const asset_count = Array.isArray(group.assets) ? group.assets.length : 0;
  return {
    slot_count: slots.length,
    slot_kinds,
    has_slot_options,
    pool_kinds,
    pool_labels,
    pools: pool_summaries,
    question_like_slots,
    same_prompt_slots,
    asset_count,
    has_pool: pools.length > 0,
  };
}

/**
 * 判断题 pool 标签判定：pool 明确给出 TRUE/FALSE 或 YES/NO 选项时返回对应题型。
 * 仅认判断题标签，避免误伤普通选项池；TFNG/YNNG 混写时以 pool 为准。
 */
export function judgementFromPools(structure) {
  if (!structure || !structure.has_pool) return null;
  const set = new Set((structure.pool_labels || []).map((l) => String(l ?? "").trim().toUpperCase()));
  if (!set.size) return null;
  if (set.has("TRUE") && set.has("FALSE")) return "true_false_not_given";
  if (set.has("YES") && set.has("NO")) return "yes_no_not_given";
  return null;
}

/**
 * 组分类。
 * @param {object} input
 * @param {string|null} input.source_type 来源类型（cam21 组 type / 通用 kind）
 * @param {string} input.instruction 组指令
 * @param {string} input.shared_prompt 组共享内容（可能含指令）
 * @param {string} input.heading_text 组标题（不参与指令判定，仅作补充文本）
 * @param {string} input.skill listening|reading|writing|speaking
 * @param {string|null} input.neighbor_type 同 Part 前一组的已分类题型（用于保守延续推断）
 * @param {object} [input.structure] deriveStructure(group) 结果；缺省时按空结构处理
 * @returns {{type:string,status:"classified"|"unknown"|"conflict"|"inferred",reason:string,candidates?:string[],notes?:string[]}}
 */
export function classifyGroup(input = {}) {
  const { source_type, instruction, shared_prompt, heading_text, skill, neighbor_type } = input;
  const text = [instruction, shared_prompt, heading_text]
    .filter((s) => typeof s === "string" && s.trim())
    .join("\n");
  const structure = input.structure || deriveStructure(input.group || { slots: input.slots, pools: input.pools, assets: input.assets });
  const srcRaw = source_type == null ? null : String(source_type);
  const srcNorm = srcRaw ? normName(srcRaw) : null;
  const srcCanonical = srcRaw ? sourceTypeToCanonical(srcRaw) : null;
  const srcHint = srcNorm && Object.prototype.hasOwnProperty.call(GENERIC_SOURCE_HINTS, srcNorm)
    ? { raw: srcRaw, family: GENERIC_SOURCE_HINTS[srcNorm] }
    : null;
  const instr = matchInstruction(instruction, skill || null) || matchInstruction(text, skill || null);
  const poolJudgement = judgementFromPools(structure);
  const base = {
    source_type: srcRaw,
    instruction_type: instr ? instr.type : null,
    instruction_pattern: instr ? instr.pattern : null,
  };

  if (srcCanonical) {
    if (instr && instr.type !== srcCanonical) {
      return {
        type: "unknown",
        status: "conflict",
        reason: `source_type=${srcRaw} 与指令判定 ${instr.type} 冲突`,
        candidates: [srcCanonical, instr.type],
        ...base,
      };
    }
    return {
      type: srcCanonical,
      status: "classified",
      reason: instr ? "source_type+instruction" : "source_type",
      ...base,
    };
  }

  if (instr) {
    const notes = [];
    if (srcHint && srcHint.family && !hintFamilyMatches(srcHint.family, instr.type)) {
      notes.push(`source_hint_mismatch:${srcHint.raw}`);
    }
    if (isJudgementType(instr.type) && poolJudgement && poolJudgement !== instr.type) {
      notes.push(`pool_overrides_instruction:${instr.type}`);
      return { type: poolJudgement, status: "classified", reason: "pool_overrides_instruction", notes, ...base };
    }
    return { type: instr.type, status: "classified", reason: "instruction", notes, ...base };
  }

  // 结构回退链（指令缺失/未命中时按组结构保守判定）
  if (structure.slot_count === 0 && !structure.has_pool) {
    return { type: "unknown", status: "unknown", reason: "empty_group_no_content", ...base };
  }
  if (poolJudgement) {
    return { type: poolJudgement, status: "classified", reason: "pool_labels", ...base };
  }
  if (structure.slot_kinds.includes("multi_select")) {
    return { type: "multiple_choice_multiple", status: "classified", reason: "slot_multi_select", ...base };
  }
  if (structure.has_slot_options) {
    return { type: "multiple_choice_single", status: "classified", reason: "slot_options", ...base };
  }
  if (structure.slot_count > 0 && structure.slot_kinds.every((k) => k === "cell_gap")) {
    return { type: "table_completion", status: "classified", reason: "cell_gap_table", ...base };
  }
  if (structure.slot_count > 0 && structure.question_like_slots === structure.slot_count && /words?|number/i.test(text)) {
    return { type: "short_answer", status: "classified", reason: "question_like_slots", ...base };
  }
  const sharedText = String(shared_prompt || "");
  if (
    structure.slot_count > 0 &&
    !structure.has_pool &&
    !structure.has_slot_options &&
    /\b(what|which|who|whom|whose|where|when|why|how)\b[^?\n]{0,120}\?/i.test(sharedText) &&
    /words?|number/i.test(text)
  ) {
    return { type: "short_answer", status: "classified", reason: "shared_question_prompt", ...base };
  }
  const kindsSubset = (allowed) => structure.slot_kinds.length > 0 && structure.slot_kinds.every((k) => allowed.includes(k));
  if (structure.slot_count >= 2 && structure.same_prompt_slots && kindsSubset(SUMMARY_LIKE_KINDS)) {
    return { type: "summary_completion", status: "classified", reason: "shared_prompt_block", ...base };
  }
  if (structure.slot_count >= 2 && kindsSubset(SENTENCE_LIKE_KINDS)) {
    return { type: "sentence_completion", status: "classified", reason: "independent_sentence_slots", ...base };
  }
  if (
    structure.slot_count === 1 &&
    !structure.has_pool &&
    !structure.has_slot_options &&
    kindsSubset(["gap", "line", "input", "line_plain", "line_paren", "line_ellipsis"]) &&
    /words?|number/i.test(text)
  ) {
    return { type: "sentence_completion", status: "classified", reason: "single_slot_completion", ...base };
  }

  const limitOnly = WORD_LIMIT_ONLY.test(text);
  if (neighbor_type && typeFamily(neighbor_type) === "completion" && (srcHint == null || srcHint.family === "completion") && limitOnly) {
    return {
      type: neighbor_type,
      status: "inferred",
      reason: `neighbor_continuation:${neighbor_type}`,
      ...base,
    };
  }

  return {
    type: "unknown",
    status: "unknown",
    reason: srcHint ? "instruction_missing_with_hint" : text.trim() ? "no_instruction_match" : "instruction_missing",
    ...base,
  };
}

export const __internals = { normName, INSTRUCTION_RULES, HINT_FAMILY_TYPES, WORD_LIMIT_ONLY, SUMMARY_LIKE_KINDS, SENTENCE_LIKE_KINDS, judgementFromPools, isJudgementType };
