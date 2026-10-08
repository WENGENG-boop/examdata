const TICK = String.fromCharCode(96);
/**
 * cam21.mjs — 剑桥21 官方题库适配器（maqsudjon-cell/cambridge-21）
 *
 * 站点把结构化数据直接内嵌在 HTML 的 <script> 里：
 *   阅读页: PASSAGES / GROUPS / HEADINGS / ENDINGS / QUESTIONS / ANSWERS
 *   听力页: PARTS / TITLES / audioTracks / correctAnswers / multiCorrect / TRANSCRIPTS
 *
 * 实测（4 套 Test，2026-10 S05 复核）：
 *   阅读：每套 40 题槽（t2 的多选组 Q20/Q21 展开为两个槽；t4 Q9 为 accept 数组），
 *         每套 40 个答案键；GROUPS 全量解析（9 组/套，含词库指令）；HEADINGS/ENDINGS 为空数组。
 *   听力：每套 40 题槽（gap / mcq / multi / letter_match 四类，逐套组成已核对）；
 *         答案原始键 147（= 38+35+36+38，单题键 + multiCorrect 组键），
 *         按槽展开后每套 40、合计 160（multiCorrect 的 inputs/accepted set 原样保留）。
 *   逐句原文 738 行（含时间戳；t1 有说话人，t2–t4 源侧 sp 为空 → speaker=null，不得声称官方完整）。
 *
 * 安全解析：禁 eval；字面量扫描处理字符串/转义/注释/尾逗号/括号嵌套；
 * 对模板表达式/函数表达式/箭头函数/正则等非数据表达式报 unsupported_literal 并保留 raw 原文；
 * 解析结果重建为 null-prototype 对象（Object.defineProperty），__proto__ 键不污染原型。
 */
const OWNER = "maqsudjon-cell";
const REPO = "cambridge-21";
const BRANCH = "main";
const RAW = "https://raw.githubusercontent.com/" + OWNER + "/" + REPO + "/" + BRANCH + "/";
const CDN = "https://cdn.jsdelivr.net/gh/" + OWNER + "/" + REPO + "@" + BRANCH + "/";
export const BASE = RAW;
export const SOURCE = "maqsudjon-cell/cambridge-21";
export const TESTS = [1, 2, 3, 4];
export const SECTIONS = [1, 2, 3, 4];

/** 带重试与 CDN 回落的抓取（S05 测试不调用：测试全部走本地 HTML） */
async function get(path, { retries = 3 } = {}) {
  let lastErr = "";
  for (let i = 0; i < retries; i++) {
    for (const base of [RAW, CDN]) {
      try {
        const r = await fetch(base + path, {
          headers: { "user-agent": "Mozilla/5.0", accept: "text/html,*/*" },
          signal: AbortSignal.timeout(30000),
        });
        if (r.ok) return { ok: true, body: await r.text(), via: base === RAW ? "raw" : "cdn" };
        lastErr = "HTTP " + r.status;
      } catch (e) { lastErr = String((e && e.message) || e); }
    }
    if (i < retries - 1) await new Promise((r) => setTimeout(r, 1200 * (i + 1)));
  }
  return { ok: false, error: lastErr };
}

/** 取出页面里最大的那个 <script>（数据块） */
function dataScript(html) {
  const all = [...String(html || "").matchAll(/<script[^>]*>([\s\S]*?)<\/script>/gi)].map((m) => m[1]);
  return all.sort((a, b) => b.length - a.length)[0] || "";
}

/**
 * 从 `const NAME = {`/`[` 起，按括号配平截取完整字面量。
 * 逐字符扫描：字符串（" ' `）与转义、行注释/块注释均跳过；不执行任何代码。
 */
function literalAuto(src, name) {
  const re = new RegExp("(?:const|let|var)\\s+" + name + "\\s*=\\s*");
  const m = re.exec(src);
  if (!m) return null;
  const start = m.index + m[0].length;
  const open = src[start];
  if (open !== "{" && open !== "[") return null;
  const close = open === "{" ? "}" : "]";
  let depth = 0, i = start, inStr = null, esc = false, inLine = false, inBlock = false;
  for (; i < src.length; i++) {
    const ch = src[i];
    if (inLine) { if (ch === "\n") inLine = false; continue; }
    if (inBlock) { if (ch === "*" && src[i + 1] === "/") { inBlock = false; i++; } continue; }
    if (inStr) {
      if (esc) { esc = false; continue; }
      if (ch === "\\") { esc = true; continue; }
      if (ch === inStr) inStr = null;
      continue;
    }
    if (ch === '"' || ch === "'" || ch === TICK) { inStr = ch; continue; }
    if (ch === "/" && src[i + 1] === "/") { inLine = true; i++; continue; }
    if (ch === "/" && src[i + 1] === "*") { inBlock = true; i++; continue; }
    if (ch === open) depth++;
    else if (ch === close) { depth--; if (!depth) { i++; break; } }
  }
  return src.slice(start, i);
}

/**
 * 扫描字面量中的非数据表达式（不执行任何代码）。
 * 返回问题种类数组（去重）：template_expression / function_expression / arrow_function / regex_or_division。
 * 字符串与注释内的内容一律跳过，避免误报。
 */
function scanUnsupported(lit) {
  const problems = [];
  const src = String(lit || "");
  const add = (k) => { if (!problems.includes(k)) problems.push(k); };
  let inStr = null, esc = false, inLine = false, inBlock = false;
  for (let i = 0; i < src.length; i++) {
    const ch = src[i];
    if (inLine) { if (ch === "\n") inLine = false; continue; }
    if (inBlock) { if (ch === "*" && src[i + 1] === "/") { inBlock = false; i++; } continue; }
    if (inStr) {
      if (esc) { esc = false; continue; }
      if (ch === "\\") { esc = true; continue; }
      if (inStr === TICK && ch === "$" && src[i + 1] === "{") { add("template_expression"); continue; }
      if (ch === inStr) inStr = null;
      continue;
    }
    if (ch === '"' || ch === "'" || ch === TICK) { inStr = ch; continue; }
    if (ch === "/" && src[i + 1] === "/") { inLine = true; i++; continue; }
    if (ch === "/" && src[i + 1] === "*") { inBlock = true; i++; continue; }
    if (ch === "/") { add("regex_or_division"); continue; }
    if (ch === "=" && src[i + 1] === ">") { add("arrow_function"); i++; continue; }
    if (ch === "f" && src.startsWith("function", i)) {
      const before = src[i - 1] || "";
      const after = src[i + 8] || "";
      if (!/[A-Za-z0-9_$]/.test(before) && !/[A-Za-z0-9_$]/.test(after)) {
        let j = i + 8;
        while (j < src.length && /\s/.test(src[j])) j++;
        if (src[j] !== ":") add("function_expression");
      }
    }
  }
  return problems;
}

/**
 * 把 JS 对象/数组字面量转成标准 JSON。
 * 用逐字符扫描而非正则：正则无法区分「字符串内的撇号」与「单引号字符串的边界」
 * （例如 double-quoted 里的 grandfather's，和 single-quoted 的 'gap'）。
 */
function jsToJson(src) {
  /** 解码 JS 字符串转义（与浏览器解析一致）：\n \r \t \b \f \v \0 \xHH \uHHHH \u{...} \\ \' \" \`，未知转义取字符本身 */
  function decodeEscapes(raw) {
    let buf = "";
    let i = 0;
    const n = raw.length;
    while (i < n) {
      const c = raw[i];
      if (c !== "\\") { buf += c; i++; continue; }
      const e = raw[i + 1];
      if (e === undefined) { buf += "\\"; i++; continue; }
      i += 2;
      switch (e) {
        case "n": buf += "\n"; break;
        case "r": buf += "\r"; break;
        case "t": buf += "\t"; break;
        case "b": buf += "\b"; break;
        case "f": buf += "\f"; break;
        case "v": buf += "\v"; break;
        case "0": buf += /[0-9]/.test(raw[i] || "") ? "0" : "\0"; break;
        case "x": {
          const h = raw.slice(i, i + 2);
          if (/^[0-9a-fA-F]{2}$/.test(h)) { buf += String.fromCharCode(parseInt(h, 16)); i += 2; }
          else buf += "x";
          break;
        }
        case "u": {
          if (raw[i] === "{") {
            const close = raw.indexOf("}", i + 1);
            const h = close > i ? raw.slice(i + 1, close) : "";
            if (/^[0-9a-fA-F]{1,6}$/.test(h)) { buf += String.fromCodePoint(parseInt(h, 16)); i = close + 1; }
            else buf += "u";
          } else {
            const h = raw.slice(i, i + 4);
            if (/^[0-9a-fA-F]{4}$/.test(h)) { buf += String.fromCharCode(parseInt(h, 16)); i += 4; }
            else buf += "u";
          }
          break;
        }
        case "\r": if (raw[i] === "\n") i++; break;
        case "\n": break;
        default: buf += e; break;
      }
    }
    return buf;
  }
  /** 读取一个字符串字面量的原始内容（不含首尾引号） */
  function readString(quote) {
    let raw = "";
    i++;
    while (i < n) {
      const c = src[i];
      if (c === "\\") { raw += c + (src[i + 1] ?? ""); i += 2; continue; }
      if (c === quote) { i++; break; }
      raw += c; i++;
    }
    return raw;
  }
  let out = "";
  let i = 0;
  const n = src.length;
  while (i < n) {
    const ch = src[i];
    // 字符串字面量（" ' `）：按 JS 语义解码转义后，用 JSON.stringify 重新编码
    if (ch === '"' || ch === "'" || ch === TICK) { out += JSON.stringify(decodeEscapes(readString(ch))); continue; }
    // 注释：跳过
    if (ch === "/" && src[i + 1] === "/") { while (i < n && src[i] !== "\n") i++; continue; }
    if (ch === "/" && src[i + 1] === "*") { i += 2; while (i < n && !(src[i] === "*" && src[i + 1] === "/")) i++; i += 2; continue; }
    // 尾逗号：`,` 后（跳过空白与注释）若是 } 或 ]，丢弃该逗号（只作用于结构，不碰字符串内容）
    if (ch === ",") {
      let k = i + 1;
      for (;;) {
        while (k < n && /\s/.test(src[k])) k++;
        if (src[k] === "/" && src[k + 1] === "/") { while (k < n && src[k] !== "\n") k++; continue; }
        if (src[k] === "/" && src[k + 1] === "*") { k += 2; while (k < n && !(src[k] === "*" && src[k + 1] === "/")) k++; k += 2; continue; }
        break;
      }
      if (src[k] === "}" || src[k] === "]") { i++; continue; }
      out += ch; i++; continue;
    }
    // 裸 key（标识符或纯数字）后紧跟冒号 -> 加引号
    if (/[A-Za-z_$\d]/.test(ch)) {
      let j = i;
      while (j < n && /[A-Za-z0-9_$]/.test(src[j])) j++;
      const word = src.slice(i, j);
      let k = j;
      while (k < n && /\s/.test(src[k])) k++;
      if (src[k] === ":") { out += JSON.stringify(word); i = j; continue; }
      out += word; i = j; continue;
    }
    out += ch; i++;
  }
  return out;
}

/**
 * 防原型污染：递归重建为 null-prototype 对象。
 * 键一律用 Object.defineProperty 落为普通数据属性（不触发 __proto__ setter）；
 * null-prototype 对象上 "__proto__" 只是一个普通键。
 */
function sanitize(value) {
  if (Array.isArray(value)) return value.map(sanitize);
  if (value && typeof value === "object") {
    const clean = Object.create(null);
    for (const key of Object.keys(value)) {
      Object.defineProperty(clean, key, { value: sanitize(value[key]), enumerable: true, writable: true, configurable: true });
    }
    return clean;
  }
  return value;
}

/** 安全解析：jsToJson + JSON.parse + sanitize；失败返回 null（不抛） */
function safeParse(lit) {
  if (!lit) return null;
  try { return sanitize(JSON.parse(jsToJson(lit))); } catch { return null; }
}

/**
 * 受限字面量解析入口：literalAuto 截取 → scanUnsupported 检查 → safeParse。
 * 命中非数据表达式时不解析，向 warnings 追加 {kind:"unsupported_literal", name, problems, raw} 并返回 null。
 */
function parseLiteral(src, name, warnings) {
  const lit = literalAuto(src, name);
  if (!lit) return null;
  const problems = scanUnsupported(lit);
  if (problems.length) {
    if (Array.isArray(warnings)) warnings.push({ kind: "unsupported_literal", name, problems, raw: lit });
    return null;
  }
  return safeParse(lit);
}

/** 剥标签 */
function toText(h) {
  return String(h || "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|li|tr|h\d)>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&ndash;/g, "–")
    .replace(/&mdash;/g, "—").replace(/&rsquo;|&#8217;/g, "'").replace(/&ldquo;|&rdquo;/g, '"')
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&#(\d+);/g, (_, d) => String.fromCharCode(+d))
    .replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim();
}

/** 空白归一（单行） */
function normalizeWs(s) {
  return String(s || "").replace(/\s+/g, " ").trim();
}

/* -------------------------------- 阅读 -------------------------------- */

const RE_WORD_LIMIT = /(NO MORE THAN (?:ONE|TWO|THREE|FOUR|FIVE) WORDS?(?: AND\/OR A NUMBER)?|ONE WORD ONLY|TWO WORDS(?: AND\/OR A NUMBER)?|ONE WORD AND\/OR A NUMBER|A NUMBER)/i;

/** 选项归一：["A) text", "B) ..."] / ["A","B"] / ["A. text"] -> [{label,text}] */
function parseOptions(opts) {
  if (!Array.isArray(opts)) return [];
  return opts.map((raw) => {
    const s = String(raw);
    let m = /^([A-Z])\)\s*([\s\S]*)$/.exec(s);
    if (m) return { label: m[1], text: m[2].trim() };
    m = /^([A-Z])[.:]\s+([\s\S]*)$/.exec(s);
    if (m) return { label: m[1], text: m[2].trim() };
    if (/^[A-Z]$/.test(s)) return { label: s, text: null };
    return { label: null, text: s };
  });
}

/**
 * 解析阅读页（t{n}-reading.html）：
 * PASSAGES / GROUPS / HEADINGS / ENDINGS / QUESTIONS / ANSWERS。
 * 多选组（type:"multi" 且 from/to）展开为独立题槽，每槽带 group_slots/pick 与共享选项；
 * 答案 accept 数组原样保留（单题多写法 vs 多选组共享字母集不做 join、不做猜测）。
 */
export function parseReadingHtml(html, meta = {}) {
  const js = dataScript(html);
  const warnings = [];
  const passagesRaw = parseLiteral(js, "PASSAGES", warnings) || {};
  const groupsRaw = parseLiteral(js, "GROUPS", warnings) || {};
  const headingsRaw = parseLiteral(js, "HEADINGS", warnings);
  const endingsRaw = parseLiteral(js, "ENDINGS", warnings);
  const questionsRaw = parseLiteral(js, "QUESTIONS", warnings) || [];
  const answersRaw = parseLiteral(js, "ANSWERS", warnings) || {};

  const passages = Object.keys(passagesRaw).sort((a, b) => a - b).map((k) => {
    const p = passagesRaw[k];
    const body = toText(p.html || p.text || "");
    return {
      passage: Number(k),
      title: p.title || null,
      range: p.qr || null,
      text: body,
      paragraphs: body.split(/\n{2,}/).filter((x) => x.length > 40),
    };
  });

  const groups = Object.keys(groupsRaw).map((id) => {
    const g = groupsRaw[id] || {};
    const instrHtml = String(g.instr || "");
    const instruction = toText(instrHtml);
    const wm = RE_WORD_LIMIT.exec(instruction);
    return { id, type: g.type || null, instruction, instruction_html: instrHtml, word_limit: wm ? wm[1] : null };
  });
  const groupById = Object.create(null);
  for (const g of groups) groupById[g.id] = g;

  const questions = [];
  const multiGroups = [];
  const seen = new Map();
  const duplicate_slots = [];
  const pushQuestion = (q) => {
    if (seen.has(q.number)) { duplicate_slots.push(q.number); return; }
    seen.set(q.number, q);
    questions.push(q);
  };
  for (const raw of questionsRaw) {
    const q = raw || {};
    const g = q.g != null ? groupById[q.g] || null : null;
    const base = {
      passage: q.p ?? null,
      group: q.g ?? null,
      group_type: g ? g.type : null,
      instruction: g ? g.instruction : null,
      options: parseOptions(q.opts),
    };
    const from = Number(q.from), to = Number(q.to);
    if (q.type === "multi" && Number.isFinite(from) && Number.isFinite(to) && to > from) {
      const slots = [];
      for (let n = from; n <= to; n++) {
        pushQuestion({ ...base, number: n, type: "multi", slot_kind: "multi_member", prompt: normalizeWs(q.prompt || q.text || ""), group_slots: [from, to], pick: q.pick ?? (to - from + 1) });
        slots.push(n);
      }
      multiGroups.push({ group: q.g ?? null, slots, accept: [], required_count: q.pick ?? (to - from + 1), source: "questions.multi" });
    } else if (Number.isFinite(Number(q.id))) {
      pushQuestion({ ...base, number: Number(q.id), type: q.type || "unknown", slot_kind: "single", prompt: normalizeWs(q.prompt || q.text || "") });
    }
  }
  questions.sort((a, b) => a.number - b.number);

  const answer_key = [];
  const missing_answers = [];
  for (const q of questions) {
    const v = answersRaw[q.number] ?? answersRaw[String(q.number)];
    if (v === undefined) { missing_answers.push(q.number); continue; }
    const accept = Array.isArray(v) ? v.map(String) : [String(v)];
    const entry = { number: q.number, kind: q.slot_kind, answer: q.slot_kind === "multi_member" ? null : accept[0], accept };
    if (q.slot_kind === "multi_member") {
      entry.group_slots = q.group_slots;
      entry.required_count = q.pick ?? null;
    }
    answer_key.push(entry);
  }
  for (const mg of multiGroups) {
    const first = answer_key.find((e) => e.kind === "multi_member" && e.number === mg.slots[0]);
    if (first) mg.accept = first.accept.slice();
  }

  return {
    ok: true,
    ...meta,
    warnings,
    passages,
    groups,
    headings: Array.isArray(headingsRaw) ? headingsRaw : [],
    endings: Array.isArray(endingsRaw) ? endingsRaw : [],
    questions,
    answer_key,
    answer_groups: multiGroups,
    counts: {
      passages: passages.length,
      groups: groups.length,
      questions: questions.length,
      answer_keys_raw: Object.keys(answersRaw).length,
      answers: answer_key.length,
      missing_answers,
      duplicate_slots,
    },
  };
}

/* -------------------------------- 听力 -------------------------------- */

const RE_QLABEL = /<p class="q-label"[^>]*>([\s\S]*?)<\/p>/g;
const RE_INSTRUCTION = /<p class="instruction">([\s\S]*?)<\/p>/g;
const RE_MCQ_OPEN = /<div class="mcq-group"[^>]*>/g;
const RE_CHECK_OPEN = /<div class="check-group"[^>]*>/g;
const RE_BANK_OPEN = /<div class="letter-bank"[^>]*>/g;
const RE_INPUT = /data-q="(\d+)"/g;
const RE_TABLE_OPEN = /<div class="data-table-wrap"[^>]*>/g;
const RE_MAP_OPEN = /<div class="map-wrap"[^>]*>/g;
const RE_FLOWCHART_OPEN = /<div class="flowchart"[^>]*>/g;

/** 从某个 <div ...> 开标签位置起，按 div 配平截取整块 */
function divSpan(html, startIdx) {
  const re = /<div\b[^>]*>|<\/div>/g;
  re.lastIndex = startIdx;
  let depth = 0, m;
  while ((m = re.exec(html))) {
    if (m[0] === "</div>") { depth--; if (depth === 0) return html.slice(startIdx, m.index + m[0].length); }
    else depth++;
  }
  return html.slice(startIdx);
}

/** "Questions 1–6" / "Questions 21 and 22" / "Questions 5, 6" -> {from,to}；非范围（如 "Duties"）返回 null */
function parseRangeLabel(text) {
  const t = normalizeWs(text);
  const m = /^questions?\s+(\d{1,3})(?:\s*[-\u2013\u2014]\s*(\d{1,3})|\s+and\s+(\d{1,3})|\s*&\s*(\d{1,3})|\s*,\s*(\d{1,3}))?\s*$/i.exec(t);
  if (!m) return null;
  const a = Number(m[1]);
  const b = m[2] ? Number(m[2]) : m[3] ? Number(m[3]) : m[4] ? Number(m[4]) : m[5] ? Number(m[5]) : a;
  if (!(a >= 1) || !(b >= a)) return null;
  return { from: a, to: b, text: t };
}

/** 字母库（letter-bank）：行内 <strong>X</strong> 文本；无字母的行（如表头 "Opinions"）不计为选项 */
function parseBank(block) {
  const options = [];
  for (const m of block.matchAll(/<div class="row"[^>]*>/g)) {
    const row = divSpan(block, m.index);
    const lm = /<strong[^>]*>([A-Z])<\/strong>([\s\S]*)$/.exec(row)
      || /<span class="opt-letter">([A-Z])<\/span>([\s\S]*)$/.exec(row);
    if (lm) options.push({ label: lm[1], text: normalizeWs(toText(lm[2])) });
  }
  return options;
}

/** check-group 内的选项（复选框组） */
function parseCheckOptions(block) {
  const options = [];
  for (const m of block.matchAll(/<label class="check-option"[^>]*>([\s\S]*?)<\/label>/g)) {
    const inner = m[1];
    const lm = /<span class="opt-letter">([A-Z])<\/span>([\s\S]*)$/.exec(inner);
    if (lm) options.push({ label: lm[1], text: normalizeWs(toText(lm[2])) });
    else options.push({ label: null, text: normalizeWs(toText(inner)) });
  }
  return options;
}

/** 单元格/步骤文本：题号徽标去除、输入框→" ___ "、列表项以 " / " 连接 */
function cellText(html) {
  let seg = String(html);
  seg = seg.replace(/<span class="qnum-prefix">\d+<\/span>/g, " ");
  seg = seg.replace(/<input[^>]*data-q="\d+"[^>]*>/g, " ___ ");
  seg = seg.replace(/<\/li>\s*<li[^>]*>/g, " / ");
  return normalizeWs(toText(seg));
}

/** data-table-wrap → {kind:"table", title, headers, rows, numbers}（保留表格结构与题号归属） */
function parseTableAsset(block) {
  const tm = /<table[^>]*>([\s\S]*?)<\/table>/.exec(block);
  if (!tm) return null;
  const titleM = /<div class="data-table-title"[^>]*>([\s\S]*?)<\/div>/.exec(block);
  const headers = [];
  const theadM = /<thead[^>]*>([\s\S]*?)<\/thead>/.exec(tm[1]);
  if (theadM) for (const c of theadM[1].matchAll(/<th[^>]*>([\s\S]*?)<\/th>/g)) headers.push(cellText(c[1]));
  const rows = [];
  const tbodyM = /<tbody[^>]*>([\s\S]*?)<\/tbody>/.exec(tm[1]);
  for (const rm of (tbodyM ? tbodyM[1] : tm[1]).matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)) {
    const cells = [];
    for (const cm of rm[1].matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/g)) cells.push(cellText(cm[1]));
    if (cells.length) rows.push(cells);
  }
  const numbers = [...block.matchAll(/data-q="(\d+)"/g)].map((x) => Number(x[1]));
  return { kind: "table", source_ref: "cam21:data-table-wrap", title: titleM ? normalizeWs(toText(titleM[1])) : null, headers, rows, numbers };
}

/** map-wrap → {kind:"figure", source_ref:img src, title, alt} */
function parseMapAsset(block) {
  const im = /<img[^>]*src="([^"]+)"[^>]*>/.exec(block);
  if (!im) return null;
  const titleM = /<div class="map-title"[^>]*>([\s\S]*?)<\/div>/.exec(block);
  const altM = /<img[^>]*alt="([^"]*)"/.exec(block);
  return { kind: "figure", source_ref: im[1], title: titleM ? normalizeWs(toText(titleM[1])) : null, alt: altM ? altM[1] : null };
}

/** flowchart → {kind:"flowchart", steps, numbers}；标题取紧邻的居中标题 div（若存在） */
function parseFlowchartAsset(block, html, at) {
  const steps = [];
  for (const m of block.matchAll(/<div class="flow-step"[^>]*>([\s\S]*?)<\/div>/g)) steps.push(cellText(m[1]));
  if (!steps.length) return null;
  const before = html.slice(Math.max(0, at - 600), at);
  const tm = /<div style="text-align:center[^"]*"[^>]*>([\s\S]*?)<\/div>\s*$/.exec(before);
  const numbers = [...block.matchAll(/data-q="(\d+)"/g)].map((x) => Number(x[1]));
  return { kind: "flowchart", source_ref: "cam21:flowchart", title: tm ? normalizeWs(toText(tm[1])) : null, steps, numbers };
}

/** 单个 mcq-group：题干 + 单选选项 */
function parseMcqBlock(block) {
  const qm = /<div class="mcq-question"><span class="qnum">(\d+)<\/span>([\s\S]*?)<\/div>/.exec(block);
  if (!qm) return null;
  const options = [];
  for (const m of block.matchAll(/<label class="mcq-option"[^>]*>([\s\S]*?)<\/label>/g)) {
    const inner = m[1];
    const lm = /<span class="opt-letter">([A-Z])<\/span>([\s\S]*)$/.exec(inner);
    if (lm) options.push({ label: lm[1], text: normalizeWs(toText(lm[2])) });
    else options.push({ label: null, text: normalizeWs(toText(inner)) });
  }
  return { number: Number(qm[1]), prompt: normalizeWs(toText(qm[2])), options };
}

/**
 * gap 题的题干：取输入框所在容器（label-item/td/li/p…）的文本窗口，
 * 把题号徽标与输入框替换为 " ___ "。t1 是 label 在前、t4 是 input 在前，窗口法两者兼容。
 */
function inputPrompt(html, k) {
  const before = html.slice(0, k);
  let start = null;
  for (const pat of ['<div class="label-item"', "<td", "<li", "<p ", '<div class="notes-card"', '<div class="data-table-wrap"']) {
    const idx = before.lastIndexOf(pat);
    if (idx >= 0 && (start == null || idx > start)) start = idx;
  }
  if (start == null) start = Math.max(0, k - 300);
  const after = html.slice(k);
  let end = null;
  for (const pat of ["</td>", "</li>", "</div>", "</p>"]) {
    const idx = after.indexOf(pat);
    if (idx >= 0 && (end == null || k + idx < end)) end = k + idx;
  }
  if (end == null) end = Math.min(html.length, k + 300);
  let seg = html.slice(start, end);
  seg = seg.replace(/<span class="qnum-prefix">\d+<\/span>/g, " ");
  seg = seg.replace(/<input[^>]*data-q="\d+"[^>]*>/g, " ___ ");
  const text = normalizeWs(toText(seg));
  return text.length > 400 ? text.slice(0, 400) : text;
}

/**
 * 解析单个 Section 的题面 HTML：q-label 范围分块（"Duties" 等子标题挂当前组），
 * gap / mcq / multi / letter_match 逐类落槽；返回的 groups 与 questions 用共享数组的全局下标。
 */
function parseSection(sec, html, groups, questions) {
  const landmarks = [];
  for (const m of html.matchAll(RE_QLABEL)) landmarks.push({ at: m.index, kind: "label", text: normalizeWs(toText(m[1])) });
  for (const m of html.matchAll(RE_INSTRUCTION)) landmarks.push({ at: m.index, kind: "instruction", text: normalizeWs(toText(m[1])) });
  for (const m of html.matchAll(RE_MCQ_OPEN)) landmarks.push({ at: m.index, kind: "mcq", block: divSpan(html, m.index) });
  for (const m of html.matchAll(RE_CHECK_OPEN)) landmarks.push({ at: m.index, kind: "check", block: divSpan(html, m.index), open: m[0] });
  for (const m of html.matchAll(RE_BANK_OPEN)) landmarks.push({ at: m.index, kind: "bank", block: divSpan(html, m.index) });
  for (const m of html.matchAll(RE_TABLE_OPEN)) landmarks.push({ at: m.index, kind: "table", block: divSpan(html, m.index) });
  for (const m of html.matchAll(RE_MAP_OPEN)) landmarks.push({ at: m.index, kind: "map", block: divSpan(html, m.index) });
  for (const m of html.matchAll(RE_FLOWCHART_OPEN)) landmarks.push({ at: m.index, kind: "flowchart", block: divSpan(html, m.index) });
  for (const m of html.matchAll(RE_INPUT)) landmarks.push({ at: m.index, kind: "input", number: Number(m[1]) });
  landmarks.sort((a, b) => a.at - b.at);

  let current = null;
  let currentBank = null;
  const ensureGroup = () => {
    if (!current) {
      current = { section: sec, label: null, from: null, to: null, instruction: null, sublabel: null, slots: [], assets: [], type: null, index: -1 };
      current.index = groups.push(current) - 1;
    }
    return current;
  };

  for (const lm of landmarks) {
    if (lm.kind === "label") {
      const range = parseRangeLabel(lm.text);
      if (range) {
        current = { section: sec, label: range.text, from: range.from, to: range.to, instruction: null, sublabel: null, slots: [], assets: [], type: null, index: -1 };
        current.index = groups.push(current) - 1;
        currentBank = null;
      } else if (current) {
        current.sublabel = lm.text;
      }
      continue;
    }
    if (lm.kind === "instruction") { ensureGroup().instruction = lm.text; continue; }
    if (lm.kind === "bank") { currentBank = parseBank(lm.block); continue; }
    if (lm.kind === "table" || lm.kind === "map" || lm.kind === "flowchart") {
      const g = ensureGroup();
      const asset = lm.kind === "table" ? parseTableAsset(lm.block)
        : lm.kind === "map" ? parseMapAsset(lm.block)
        : parseFlowchartAsset(lm.block, html, lm.at);
      if (asset) g.assets.push(asset);
      continue;
    }
    if (lm.kind === "mcq") {
      const q = parseMcqBlock(lm.block);
      if (!q) continue;
      const g = ensureGroup();
      questions.push({ number: q.number, section: sec, type: "mcq", prompt: q.prompt, options: q.options, group: g.index, sublabel: g.sublabel });
      g.slots.push(q.number);
      continue;
    }
    if (lm.kind === "check") {
      const g = ensureGroup();
      const qm = /data-questions="([^"]*)"/.exec(lm.open);
      const mm = /data-max="(\d+)"/.exec(lm.open);
      const numbers = qm ? qm[1].split(/[,\s]+/).map(Number).filter((n) => n >= 1) : [];
      const options = parseCheckOptions(lm.block);
      const hintM = /<div class="check-group-hint"[^>]*>([\s\S]*?)<\/div>/.exec(lm.block);
      const hint = hintM ? normalizeWs(toText(hintM[1])) : null;
      for (const n of numbers) {
        questions.push({ number: n, section: sec, type: "multi", prompt: g.instruction || "", options, group: g.index, group_slots: numbers.slice(), required_count: mm ? Number(mm[1]) : numbers.length, hint, sublabel: g.sublabel });
        g.slots.push(n);
      }
      continue;
    }
    if (lm.kind === "input") {
      const g = ensureGroup();
      const prompt = inputPrompt(html, lm.at);
      questions.push({ number: lm.number, section: sec, type: currentBank ? "letter_match" : "gap", prompt, options: currentBank ? currentBank.slice() : [], group: g.index, sublabel: g.sublabel });
      g.slots.push(lm.number);
      continue;
    }
  }

  for (const g of groups) {
    if (g.type == null && g.section === sec) {
      const types = new Set(g.slots.map((n) => {
        const q = questions.find((x) => x.number === n && x.section === sec);
        return q ? q.type : "unknown";
      }));
      g.type = types.size === 0 ? null : types.size === 1 ? [...types][0] : "mixed";
    }
  }
  return { groups, questions };
}

/**
 * 解析听力页（t{n}-listening.html）：
 * PARTS / TITLES / audioTracks / correctAnswers / multiCorrect / TRANSCRIPTS。
 * 每套 40 题槽；答案按槽展开（multiCorrect 的 inputs/accepted set 原样保留），
 * 原始键数与展开覆盖数分开记（147 raw / 160 slots 全册）。
 */
export function parseListeningHtml(html, meta = {}) {
  const js = dataScript(html);
  const warnings = [];
  const partsRaw = parseLiteral(js, "PARTS", warnings) || {};
  const titles = parseLiteral(js, "TITLES", warnings) || {};
  const tracks = parseLiteral(js, "audioTracks", warnings) || {};
  const answersRaw = parseLiteral(js, "correctAnswers", warnings) || {};
  const multiRaw = parseLiteral(js, "multiCorrect", warnings) || {};
  const scripts = parseLiteral(js, "TRANSCRIPTS", warnings) || {};

  const groups = [];
  const questions = [];
  const sections = [];
  for (const secKey of Object.keys(partsRaw).sort((a, b) => a - b)) {
    const sec = Number(secKey);
    parseSection(sec, String(partsRaw[secKey]), groups, questions);
    sections.push({ section: sec, title: titles[secKey] || null });
  }
  for (const q of questions) {
    const g = groups[q.group];
    if (g) q.group_type = g.type;
  }

  const multiGroups = [];
  const multiByNumber = new Map();
  for (const key of Object.keys(multiRaw)) {
    const m = multiRaw[key] || {};
    const inputsRaw = Array.isArray(m.inputs) ? m.inputs.slice() : [];
    const slots = inputsRaw.map(Number).filter((n) => n >= 1);
    if (!slots.length) continue;
    const accept = Array.isArray(m.accept) ? m.accept.map(String) : [];
    const rec = { key: String(key), inputs_raw: inputsRaw, slots, accept, required_count: slots.length, section: null };
    multiGroups.push(rec);
    for (const n of slots) multiByNumber.set(n, rec);
  }
  for (const q of questions) {
    const rec = multiByNumber.get(q.number);
    if (rec) {
      q.accept = rec.accept.slice();
      q.group_slots = rec.slots.slice();
      if (rec.section == null) rec.section = q.section;
    }
  }

  const answer_key = [];
  const missing_answers = [];
  for (const q of questions) {
    const rec = multiByNumber.get(q.number);
    if (rec) {
      answer_key.push({ number: q.number, kind: "multi_member", answer: null, accept: rec.accept.slice(), group_slots: rec.slots.slice(), required_count: rec.required_count });
      continue;
    }
    const v = answersRaw[q.number] ?? answersRaw[String(q.number)];
    if (v === undefined) { missing_answers.push(q.number); continue; }
    const accept = Array.isArray(v) ? v.map(String) : [String(v)];
    answer_key.push({ number: q.number, kind: "single", answer: accept[0], accept });
  }
  answer_key.sort((a, b) => a.number - b.number);
  questions.sort((a, b) => a.number - b.number);

  const slotNumbers = new Set(questions.map((q) => q.number));
  const questions_missing = [];
  for (let n = 1; n <= 40; n++) if (!slotNumbers.has(n)) questions_missing.push(n);

  const audio = Object.keys(tracks).sort((a, b) => a - b).map((k) => ({
    section: Number(k), url: RAW + tracks[k], cdn: CDN + tracks[k], type: "audio/mpeg",
  }));

  const transcript = Object.keys(scripts).sort((a, b) => a - b).map((k) => {
    const lines = (Array.isArray(scripts[k]) ? scripts[k] : []).map((l) => ({
      speaker: l.sp === "" || l.sp == null ? null : String(l.sp),
      text: l.h || "",
      time: l.t ?? null,
    }));
    return {
      section: Number(k),
      title: titles[k] || null,
      has_speakers: lines.some((l) => l.speaker != null),
      time_unit: null,
      lines,
    };
  });

  const rawKeyCount = Object.keys(answersRaw).length + Object.keys(multiRaw).length;
  return {
    ok: true,
    ...meta,
    warnings,
    sections,
    groups,
    questions,
    answer_key,
    answer_groups: multiGroups,
    audio,
    transcript,
    counts: {
      sections: sections.length,
      questions: questions.length,
      answer_keys_raw: rawKeyCount,
      answers: answer_key.length,
      missing_answers,
      questions_missing,
      multi_groups: multiGroups.length,
      audio: audio.length,
      transcript_sections: transcript.length,
      transcript_lines: transcript.reduce((n, s) => n + s.lines.length, 0),
    },
  };
}

/* ------------------------------ 导出 API ------------------------------ */

/** 阅读：原文 + 题目 + 答案（opts.html 可注入本地页用于离线解析/测试） */
export async function reading(test, opts = {}) {
  const t = Number(test);
  if (!TESTS.includes(t)) return { ok: false, source: SOURCE, error: "test 需为 1–4" };
  let body = opts.html, via = "local";
  if (body == null) {
    const r = await get("t" + t + "-reading.html");
    if (!r.ok) return { ok: false, source: SOURCE, error: r.error };
    body = r.body; via = r.via;
  }
  const parsed = parseReadingHtml(body, {
    source: SOURCE, book: 21, test: t, skill: "reading", via,
    title: "Cambridge IELTS 21 Test " + t + " Reading",
  });
  if (!parsed.counts.passages) return { ok: false, source: SOURCE, error: "未解析到 PASSAGES（页面结构变化）", warnings: parsed.warnings };
  return parsed;
}

/** 阅读索引 */
export async function readingIndex() {
  const tests = [];
  for (const t of TESTS) {
    const r = await reading(t);
    if (!r.ok) { tests.push({ test: t, ok: false, error: r.error }); continue; }
    tests.push({
      test: t, ok: true, titles: r.passages.map((p) => p.title),
      questions: r.counts.questions, answers: r.counts.answers, answer_keys_raw: r.counts.answer_keys_raw,
    });
  }
  return { ok: true, source: SOURCE, book: 21, tests };
}

/** 听力：题目 + 答案 + 音频 + 逐句原文（opts.html 可注入本地页用于离线解析/测试） */
export async function listening(test, opts = {}) {
  const t = Number(test);
  if (!TESTS.includes(t)) return { ok: false, source: SOURCE, error: "test 需为 1–4" };
  let body = opts.html, via = "local";
  if (body == null) {
    const r = await get("t" + t + "-listening.html");
    if (!r.ok) return { ok: false, source: SOURCE, error: r.error };
    body = r.body; via = r.via;
  }
  const parsed = parseListeningHtml(body, {
    source: SOURCE, book: 21, test: t, skill: "listening", via,
    title: "Cambridge IELTS 21 Test " + t + " Listening",
  });
  if (!parsed.counts.sections) return { ok: false, source: SOURCE, error: "未解析到 PARTS（页面结构变化）", warnings: parsed.warnings };
  return parsed;
}

/** 听力索引 */
export async function listeningIndex() {
  const tests = [];
  for (const t of TESTS) {
    const r = await listening(t);
    if (!r.ok) { tests.push({ test: t, ok: false, error: r.error }); continue; }
    tests.push({
      test: t, ok: true, sections: r.sections.map((s) => s.title),
      questions: r.counts.questions, answers: r.counts.answers,
      answer_keys_raw: r.counts.answer_keys_raw,
      audio: r.counts.audio, transcript_lines: r.counts.transcript_lines,
    });
  }
  return { ok: true, source: SOURCE, book: 21, tests };
}

/** 音频直链（单个 Section） */
export function audio(test, section = 1) {
  const valid = (v) => (typeof v === "number" || (typeof v === "string" && /^[1-4]$/.test(v)))
    && Number.isInteger(Number(v)) && Number(v) >= 1 && Number(v) <= 4;
  if (!valid(test) || !valid(section)) return { ok: false, source: SOURCE, book: 21, error: "test/section 需为 1–4" };
  const path = "audio/C21T" + test + "_Section_" + section + ".mp3";
  return { ok: true, source: SOURCE, book: 21, test, section, url: RAW + path, cdn: CDN + path, type: "audio/mpeg" };
}

/** 整本：阅读 + 听力 + 音频 */
export async function fullTest(test) {
  const [rd, ls] = await Promise.all([reading(test), listening(test)]);
  return {
    ok: rd.ok || ls.ok, source: SOURCE, book: 21, test,
    reading: rd, listening: ls,
    audio: SECTIONS.map((s) => audio(test, s)),
  };
}

/** 覆盖自检 */
export async function coverage() {
  const [r, l] = await Promise.all([readingIndex(), listeningIndex()]);
  const rOk = r.tests.filter((t) => t.ok).length;
  const lOk = l.tests.filter((t) => t.ok).length;
  return {
    ok: rOk === 4 && lOk === 4, source: SOURCE, book: 21,
    reading_tests: rOk, listening_tests: lOk,
    total_reading_answers: r.tests.reduce((n, t) => n + (t.answers || 0), 0),
    total_listening_answers: l.tests.reduce((n, t) => n + (t.answers || 0), 0),
    audio_files: l.tests.reduce((n, t) => n + (t.audio || 0), 0),
    reading: r.tests, listening: l.tests,
  };
}

export const __internals = {
  dataScript, literalAuto, jsToJson, sanitize, safeParse, toText, normalizeWs,
  parseOptions, divSpan, parseRangeLabel, parseBank, parseCheckOptions, parseMcqBlock,
  inputPrompt, parseSection, parseReadingHtml, parseListeningHtml,
  scanUnsupported, parseLiteral,
};
