/**
 * html-questions.mjs — 零依赖 HTML DOM 解析与雅思题面/答案结构提取（计划 S04）
 *
 * 设计目标（对应审计 A02–A04）：
 *  - 不执行上游脚本；script/style 内容直接跳过。
 *  - 手写 tokenizer + 树构建，含 HTML 隐式闭合（p 被块级元素闭合、li/td/th/tr/option 等），
 *    使 practicepteonline 的 malformed HTML（div 嵌在 p 内、span 跨闭合）能正确成树。
 *  - 答案提取基于 DOM：OL 读 start / LI value，空 LI 保留（禁 filter(Boolean)）；
 *    编号段落形态解析显式题号与范围，保留空值与重复冲突；小数与正文年份不识别为题号。
 *  - 题目提取按 "Questions N-M" 范围建组，再提编号行 / (N) 占位 / input / 表格格 / 选项池。
 *  - 提示词不截断到 400 字符；异常体积（默认 >4000 字符）记 warning 并报 partial。
 *  - 纯函数、无网络、无全局状态；source_ref 记录 DOM 路径以便溯源。
 */

/* ============================ 1. Tokenizer ============================ */

const VOID_ELEMENTS = new Set([
  "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
  "param", "source", "track", "wbr",
]);
const RAW_TEXT_ELEMENTS = new Set(["script", "style", "xmp", "iframe", "noembed", "noframes", "plaintext"]);
const TEXT_ONLY_ELEMENTS = new Set(["textarea", "title"]);

const BLOCK_ELEMENTS = new Set([
  "address", "article", "aside", "blockquote", "details", "div", "dl", "fieldset",
  "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6",
  "header", "hgroup", "hr", "main", "menu", "nav", "ol", "p", "pre", "section",
  "table", "ul", "li", "tr", "td", "th", "thead", "tbody", "tfoot", "caption",
]);

/** 开始标签会隐式闭合栈中最近的未闭合 p（HTML 规范子集 + malformed 容错扩展） */
const CLOSES_P = new Set([
  "address", "article", "aside", "blockquote", "caption", "dd", "details", "div",
  "dl", "dt", "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2",
  "h3", "h4", "h5", "h6", "header", "hgroup", "hr", "li", "main", "menu", "nav",
  "ol", "optgroup", "option", "p", "pre", "section", "table", "tbody", "td",
  "tfoot", "th", "thead", "tr", "ul",
]);

const ENTITY_MAP = {
  amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: "\u00a0",
  ndash: "\u2013", mdash: "\u2014", hellip: "\u2026", rsquo: "\u2019",
  lsquo: "\u2018", rdquo: "\u201d", ldquo: "\u201c", copy: "\u00a9",
  reg: "\u00ae", trade: "\u2122", times: "\u00d7", divide: "\u00f7",
  middot: "\u00b7", bull: "\u2022", deg: "\u00b0", pound: "\u00a3",
  euro: "\u20ac", sect: "\u00a7", para: "\u00b6", frac12: "\u00bd",
  frac14: "\u00bc", frac34: "\u00be", laquo: "\u00ab", raquo: "\u00bb",
  eacute: "\u00e9", egrave: "\u00e8", agrave: "\u00e0", ccedil: "\u00e7",
  uuml: "\u00fc", ouml: "\u00f6", auml: "\u00e4", szlig: "\u00df",
};

export function decodeEntities(s) {
  if (!s || s.indexOf("&") < 0) return s;
  return s.replace(/&(#x?[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]*);/g, (m, body) => {
    if (body[0] === "#") {
      const hex = body[1] === "x" || body[1] === "X";
      const code = parseInt(body.slice(hex ? 2 : 1), hex ? 16 : 10);
      if (Number.isFinite(code) && code >= 0 && code <= 0x10ffff) {
        try { return String.fromCodePoint(code); } catch { return m; }
      }
      return m;
    }
    const v = ENTITY_MAP[body.toLowerCase()];
    return v !== undefined ? v : m;
  });
}

function parseAttrs(src) {
  const attrs = {};
  const re = /([^\s"'<>\/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'<>`]+)))?/g;
  let m;
  while ((m = re.exec(src))) {
    const name = m[1].toLowerCase();
    if (name === "" || attrs[name] !== undefined) continue;
    const value = m[2] !== undefined ? m[2] : m[3] !== undefined ? m[3] : m[4] !== undefined ? m[4] : "";
    attrs[name] = decodeEntities(value);
  }
  return attrs;
}

/**
 * Tokenizer：产出 {type:'text'|'start'|'end'|'comment', ...} 流。
 * script/style 内容整体跳过；textarea/title 内容作为文本 token。
 */
export function tokenizeHtml(html) {
  const tokens = [];
  let i = 0;
  const n = html.length;
  while (i < n) {
    const lt = html.indexOf("<", i);
    if (lt < 0) {
      tokens.push({ type: "text", text: decodeEntities(html.slice(i)) });
      break;
    }
    if (lt > i) tokens.push({ type: "text", text: decodeEntities(html.slice(i, lt)) });
    if (html.startsWith("<!--", lt)) {
      const end = html.indexOf("-->", lt + 4);
      const stop = end < 0 ? n : end + 3;
      tokens.push({ type: "comment", text: html.slice(lt + 4, end < 0 ? n : end) });
      i = stop;
      continue;
    }
    if (html.startsWith("<!", lt) || html.startsWith("<?", lt)) {
      const end = html.indexOf(">", lt);
      i = end < 0 ? n : end + 1;
      continue;
    }
    if (html.startsWith("</", lt)) {
      const end = html.indexOf(">", lt);
      const raw = html.slice(lt + 2, end < 0 ? n : end);
      const name = (raw.match(/^\s*([a-zA-Z][a-zA-Z0-9:-]*)/) || [])[1];
      if (name) tokens.push({ type: "end", name: name.toLowerCase() });
      i = end < 0 ? n : end + 1;
      continue;
    }
    const nameMatch = /^<([a-zA-Z][a-zA-Z0-9:-]*)/.exec(html.slice(lt));
    if (!nameMatch) {
      tokens.push({ type: "text", text: "<" });
      i = lt + 1;
      continue;
    }
    const name = nameMatch[1].toLowerCase();
    // 找到属性区结束的 '>'（属性值内的 '>' 由引号保护）
    let j = lt + 1 + nameMatch[1].length;
    let quote = null;
    let selfClosing = false;
    let end = -1;
    for (; j < n; j++) {
      const ch = html[j];
      if (quote) {
        if (ch === quote) quote = null;
        continue;
      }
      if (ch === '"' || ch === "'") { quote = ch; continue; }
      if (ch === ">") { end = j; break; }
    }
    if (end < 0) { tokens.push({ type: "text", text: html.slice(lt) }); break; }
    const attrSrc = html.slice(lt + 1 + nameMatch[1].length, end);
    selfClosing = /\/\s*$/.test(attrSrc);
    const attrs = parseAttrs(attrSrc.replace(/\/\s*$/, ""));
    tokens.push({ type: "start", name, attrs, selfClosing });
    i = end + 1;
    if (RAW_TEXT_ELEMENTS.has(name) && !selfClosing) {
      const closeRe = new RegExp("</" + name + "\\s*>", "i");
      const rest = html.slice(i);
      const cm = closeRe.exec(rest);
      const stop = cm ? i + cm.index : n;
      tokens.push({ type: "comment", text: html.slice(i, stop) }); // 内容丢弃（不执行、不解析）
      i = cm ? i + cm.index + cm[0].length : n;
      continue;
    }
    if (TEXT_ONLY_ELEMENTS.has(name) && !selfClosing) {
      const closeRe = new RegExp("</" + name + "\\s*>", "i");
      const rest = html.slice(i);
      const cm = closeRe.exec(rest);
      const stop = cm ? i + cm.index : n;
      tokens.push({ type: "text", text: decodeEntities(html.slice(i, stop)) });
      i = cm ? i + cm.index + cm[0].length : n;
      continue;
    }
  }
  return tokens;
}

/* ============================ 2. Tree builder ============================ */

function makeElement(tag, attrs) {
  return { type: "element", tag, attrs: attrs || {}, children: [], parent: null };
}

function appendChild(parent, node) {
  node.parent = parent;
  parent.children.push(node);
}

/** 自栈顶向下找最近满足 pred 的元素并弹出（含该元素及其上全部）；返回是否弹出 */
function closeNearest(stack, pred) {
  for (let k = stack.length - 1; k >= 1; k--) {
    const el = stack[k];
    if (el.type === "element" && pred(el)) { stack.length = k; return true; }
  }
  return false;
}

/** 有边界的隐式闭合：自栈顶向下，先遇到 target 则弹出，先遇到 stop 则放弃（不跨边界） */
function closeNearestBounded(stack, targets, stops) {
  for (let k = stack.length - 1; k >= 1; k--) {
    const el = stack[k];
    if (el.type !== "element") continue;
    if (targets.includes(el.tag)) { stack.length = k; return true; }
    if (stops.includes(el.tag)) return false;
  }
  return false;
}

/**
 * 解析 HTML → DOM 根节点。
 * 节点：{type:'root'|'element'|'text', tag?, attrs?, children?, parent?, text?}
 * 隐式闭合：p（跨 inline 元素查找，兼容 <p><span>…<div> 这类 malformed 页面）、
 * li/td/th/tr/option/optgroup/dt/dd（带列表/表格边界，不跨 ul/ol/table 闭合）；
 * 找不到的闭合标签忽略。
 */
export function parseHtml(html) {
  const root = { type: "root", tag: "#root", attrs: {}, children: [], parent: null };
  const stack = [root];
  const tokens = tokenizeHtml(html || "");
  for (const tok of tokens) {
    const top = () => stack[stack.length - 1];
    if (tok.type === "text") {
      if (tok.text) appendChild(top(), { type: "text", text: tok.text, parent: null });
      continue;
    }
    if (tok.type === "comment") continue;
    if (tok.type === "start") {
      const tag = tok.name;
      // 隐式闭合：自栈顶向下找最近的未闭合 p（跨 inline 元素，如 <p><span>…<div>）
      if (CLOSES_P.has(tag)) closeNearest(stack, (el) => el.tag === "p");
      if (tag === "li") closeNearestBounded(stack, ["li"], ["ul", "ol"]);
      if (tag === "td" || tag === "th") closeNearestBounded(stack, ["td", "th"], ["tr", "table", "thead", "tbody", "tfoot"]);
      if (tag === "tr") closeNearestBounded(stack, ["tr"], ["table", "thead", "tbody", "tfoot"]);
      if (tag === "option") closeNearestBounded(stack, ["option"], ["optgroup", "select", "datalist"]);
      if (tag === "optgroup") closeNearestBounded(stack, ["optgroup"], ["select", "datalist"]);
      if (tag === "dt" || tag === "dd") closeNearestBounded(stack, ["dt", "dd"], ["dl"]);
      if (tag === "br" || tag === "hr") {
        appendChild(top(), makeElement(tag, tok.attrs));
        if (VOID_ELEMENTS.has(tag) || tok.selfClosing) continue;
      }
      const el = makeElement(tag, tok.attrs);
      appendChild(top(), el);
      if (!VOID_ELEMENTS.has(tag) && !tok.selfClosing) stack.push(el);
      continue;
    }
    if (tok.type === "end") {
      const tag = tok.name;
      let depth = -1;
      for (let k = stack.length - 1; k >= 1; k--) {
        if (stack[k].type === "element" && stack[k].tag === tag) { depth = k; break; }
      }
      if (depth >= 0) stack.length = depth;
      continue;
    }
  }
  return root;
}

/* ============================ 3. 节点工具 ============================ */

export function attr(node, name) {
  return node && node.type === "element" ? (node.attrs[name.toLowerCase()] ?? null) : null;
}

export function hasClass(node, cls) {
  const c = attr(node, "class");
  return !!c && c.split(/\s+/).includes(cls);
}

export function isElement(node, tag) {
  return !!node && node.type === "element" && (tag ? node.tag === tag : true);
}

export function walk(node, fn) {
  if (!node) return;
  fn(node);
  if (node.children) for (const ch of node.children) walk(ch, fn);
}

export function findAll(node, pred) {
  const out = [];
  walk(node, (n) => { if (pred(n)) out.push(n); });
  return out;
}

export function findFirst(node, pred) {
  if (!node) return null;
  if (pred(node)) return node;
  for (const ch of node.children || []) {
    const r = findFirst(ch, pred);
    if (r) return r;
  }
  return null;
}

/** 元素子树内的原始文本（不含块级换行），br → \n */
export function rawText(node) {
  if (!node) return "";
  if (node.type === "text") return node.text;
  if (node.type === "element" && (node.tag === "script" || node.tag === "style")) return "";
  if (node.type === "element" && node.tag === "br") return "\n";
  return (node.children || []).map(rawText).join("");
}

/** 块级感知文本：块级元素结束后补 \n */
export function nodeText(node, opts = {}) {
  if (!node) return "";
  if (node.type === "text") return node.text;
  if (node.type === "element" && (node.tag === "script" || node.tag === "style")) return "";
  if (node.type === "element" && node.tag === "br") return "\n";
  const sep = opts.block !== false;
  let s = (node.children || []).map((c) => nodeText(c, opts)).join("");
  if (sep && node.type === "element" && BLOCK_ELEMENTS.has(node.tag)) s += "\n";
  return s;
}

export function normalizeWs(s) {
  return String(s == null ? "" : s).replace(/[\u00a0]/g, " ").replace(/[ \t]+/g, " ").replace(/ *\n */g, "\n").trim();
}

/** 块级感知的文本行（trim 后非空）；opts.preserveSpaces 保留行内多空格（行内多选项判别用） */
export function textLines(node, opts = {}) {
  const t = nodeText(node, { block: true });
  return t.split("\n").map((l) => {
    let s = l.replace(/[\u00a0]/g, " ");
    if (!opts.preserveSpaces) s = s.replace(/[ \t]+/g, " ");
    return s.trim();
  }).filter((l) => l.length > 0);
}

/** 稳定 DOM 路径（source_ref 用） */
export function nodePath(node) {
  if (!node || node.type === "root") return "#root";
  const parent = node.parent;
  if (!parent) return "orphan";
  const parentPath = parent.type === "root" ? "#root" : nodePath(parent);
  if (node.type === "text") {
    let idx = 0;
    for (const ch of parent.children) {
      if (ch === node) break;
      if (ch.type === "text") idx++;
    }
    return `${parentPath}/#text[${idx}]`;
  }
  const tag = node.tag;
  const id = node.attrs && node.attrs.id ? `#${node.attrs.id}` : "";
  let idx = 0;
  for (const ch of parent.children) {
    if (ch === node) break;
    if (ch.type === "element" && ch.tag === tag) idx++;
  }
  return `${parentPath}/${tag}${id}[${idx}]`;
}

/* ============================ 4. 答案槽提取 ============================ */

export function isAnswerContainer(node) {
  if (!node || node.type !== "element") return false;
  const id = node.attrs && node.attrs.id;
  if (id && /^bg-showmore-hidden/i.test(id)) return true;
  if (hasClass(node, "bg-showmore-hidden")) return true;
  return false;
}

const RE_ANS_SINGLE = /^(\d{1,3})[ \t]*[.\uFF0E][ \t]+(\S[\s\S]*)$/;
const RE_ANS_EMPTY = /^(\d{1,3})[ \t]*[.\uFF0E][ \t]*$/;
const RE_ANS_RANGE = /^(\d{1,3})[ \t]*[-\u2013\u2014][ \t]*(\d{1,3})[ \t]*[.\uFF0E][ \t]*([\s\S]*)$/;
const RE_ANS_PAIR = /^(\d{1,3})[ \t]*(?:and|&|,|\/)[ \t]*(\d{1,3})[ \t]*[.\uFF0E][ \t]*([\s\S]*)$/;

function cleanAnswerValue(v) {
  return normalizeWs(v).replace(/[\s;]+$/, "");
}

export function splitAlternatives(raw) {
  if (raw == null || raw === "") return [];
  const parts = String(raw).split(/[;|]/).map((s) => s.trim()).filter((s) => s.length > 0);
  return parts.length > 1 ? parts : [String(raw).trim()];
}

/**
 * 从答案容器提取答案条目。
 * 返回 {entries, containers, notes}；entries 按 DOM 顺序，空值保留为 raw:""。
 * entry: {number, numbers, raw, alternatives, source_ref, form, container_ref}
 */
export function collectAnswerSlots(root, opts = {}) {
  const maxNumber = Number.isFinite(opts.maxNumber) ? opts.maxNumber : 999;
  const containers = findAll(root, isAnswerContainer);
  const entries = [];
  const notes = [];
  const containerMeta = [];

  for (const container of containers) {
    const ref = nodePath(container);
    const meta = { source_ref: ref, id: attr(container, "id") || null, form: null, entry_count: 0 };
    const ol = findFirst(container, (n) => isElement(n, "ol"));
    let usedOl = false;
    if (ol) {
      const lis = (ol.children || []).filter((c) => isElement(c, "li"));
      if (lis.length > 0) {
        usedOl = true;
        meta.form = "ol";
        let counter = 1;
        const startAttr = attr(ol, "start");
        if (startAttr && /^\d+$/.test(startAttr.trim())) counter = Number(startAttr.trim());
        for (const li of lis) {
          const valueAttr = attr(li, "value");
          if (valueAttr && /^\d+$/.test(valueAttr.trim())) counter = Number(valueAttr.trim());
          const raw = cleanAnswerValue(rawText(li));
          entries.push({
            number: counter, numbers: [counter], raw,
            alternatives: splitAlternatives(raw),
            source_ref: nodePath(li), form: "ol", container_ref: ref,
          });
          counter++;
        }
      }
    }
    if (!usedOl) {
      meta.form = "numbered";
      const lines = nodeText(container, { block: true })
        .split("\n")
        .map((l) => l.replace(/[\u00a0]/g, " ").replace(/[ \t]+/g, " ").trim())
        .filter((l) => l.length > 0);
      for (const line of lines) {
        let m;
        if ((m = RE_ANS_RANGE.exec(line))) {
          const a = Number(m[1]), b = Number(m[2]);
          if (a <= b && b <= maxNumber && a >= 1) {
            const raw = cleanAnswerValue(m[3]);
            for (let k = a; k <= b; k++) {
              entries.push({ number: k, numbers: [a, b], raw, alternatives: splitAlternatives(raw), source_ref: ref, form: "numbered_range", container_ref: ref });
            }
            continue;
          }
        }
        if ((m = RE_ANS_PAIR.exec(line))) {
          const a = Number(m[1]), b = Number(m[2]);
          if (a >= 1 && b <= maxNumber) {
            const raw = cleanAnswerValue(m[3]);
            for (const k of [a, b]) {
              entries.push({ number: k, numbers: [a, b], raw, alternatives: splitAlternatives(raw), source_ref: ref, form: "numbered_pair", container_ref: ref });
            }
            continue;
          }
        }
        if ((m = RE_ANS_SINGLE.exec(line))) {
          const k = Number(m[1]);
          if (k >= 1 && k <= maxNumber) {
            const raw = cleanAnswerValue(m[2]);
            entries.push({ number: k, numbers: [k], raw, alternatives: splitAlternatives(raw), source_ref: ref, form: "numbered", container_ref: ref });
          }
          continue;
        }
        if ((m = RE_ANS_EMPTY.exec(line))) {
          const k = Number(m[1]);
          if (k >= 1 && k <= maxNumber) {
            entries.push({ number: k, numbers: [k], raw: "", alternatives: [], source_ref: ref, form: "numbered_empty", container_ref: ref });
          }
          continue;
        }
      }
    }
    meta.entry_count = entries.length - containerMeta.reduce((s, c) => s + c.entry_count, 0);
    containerMeta.push(meta);
  }

  if (containers.length === 0) notes.push({ kind: "answer_container_missing" });
  return { entries, containers: containerMeta, notes };
}

/* ============================ 5. 题组提取 ============================ */

const ROMAN = "(?=[ivx])(?:x{0,3}(?:ix|iv|v?i{0,3}))";
const RE_Q_HEADING = /^(?:(?:Part|Section|Passage)\s+\d+\s*[:.\-\u2013\u2014]\s*(?:[-\u2013\u2014]\s*)?)?Questions?\s+(\d{1,3})(?:\s*[-\u2013\u2014]\s*(\d{1,3})|\s*(?:and|&|,|\/)\s*(\d{1,3}))?/i;
const RE_LETTER_OPT = /^([A-H])(?:[ \t]*[.):]|[ \t]+)[ \t]*(\S[\s\S]*)$/;
// 扩展字母标签 I-L：仅在 <strong>/<b> 包裹时视为选项（避免正文 "I hope…" 被误判）
const RE_LETTER_OPT_EXT = /^([I-L])(?:[ \t]*[.):]|[ \t]+)[ \t]*(\S[\s\S]*)$/;
const RE_ROMAN_OPT = new RegExp("^(" + ROMAN + ")(?:[ \\t]*[.):]|[ \\t]+)[ \\t]*(\\S[\\s\\S]*)$", "i");
const RE_TFNG_OPT = /^(TRUE|FALSE|NOT GIVEN|YES|NO)(?:[ \t]*[.):]|[ \t]+if\b|[ \t]*$)[ \t]*([\s\S]*)$/i;
const RE_Q_LINE_DOT = /^(\d{1,3})[ \t]*[.\uFF0E](?:[ \t]+([0-9][\s\S]*)|[ \t]*((?![0-9])\S[\s\S]*))$/;
const RE_Q_LINE_ELL = /^(\d{1,3})[ \t]*[.\uFF0E\u2026]{2,}[ \t]*(\S[\s\S]*)$/;
const RE_Q_LINE_PAREN = /^(\d{1,3})[ \t]*[)\uFF09][ \t]+(\S[\s\S]*)$/;
const RE_Q_LINE_PLAIN = /^(\d{1,3})[ \t]+([A-Za-z(\u2018\u201c"'\[][\s\S]*)$/;
const RE_Q_LINE_EMPTY = /^(\d{1,3})[ \t]*[.\uFF0E][ \t]*$/;
const RE_GAP_MARKER = /\((\d{1,3})\)/g;
const RE_EXPLAIN_MARKER = /^(?:(?:ANSWER|ANSWERS)\s+)?EXPLANATIONS?(?:\s+OF\s+ANSWERS)?\s*[:.]?$/i;
const RE_WORD_LIMIT = /(NO MORE THAN (?:ONE|TWO|THREE|FOUR|FIVE) WORDS?(?: AND\/OR A NUMBER)?|ONE WORD ONLY|TWO WORDS(?: AND\/OR A NUMBER)?|ONE WORD AND\/OR A NUMBER|A NUMBER)/i;
// 指令声明的 "boxes N-M"/"boxes N and M"/"boxes N, M" 范围（用于标题范围偏窄时的越界题行转正）
const RE_BOX = /boxes?\s+(\d{1,3})\s*(?:[-\u2013\u2014]\s*(\d{1,3})|(?:and|&|,|\/)\s*(\d{1,3}))?/gi;
// 指令声明的 "next to Questions N-M" 范围（如 "write the correct letter, A-G, next to Questions 15-20"）
const RE_NEXT_TO = /next to\s+questions?\s+(\d{1,3})\s*(?:[-\u2013\u2014]\s*(\d{1,3})|(?:and|&|,|\/)\s*(\d{1,3}))?/gi;

/** 行是否像题行（编号 + 题干/空题） */
function isQuestionLineLike(line) {
  return RE_Q_LINE_ELL.test(line) || RE_Q_LINE_DOT.test(line) || RE_Q_LINE_PAREN.test(line)
    || RE_Q_LINE_PLAIN.test(line) || RE_Q_LINE_EMPTY.test(line);
}

function parseHeadingText(text) {
  const t = normalizeWs(text).replace(/\n/g, " ");
  const m = RE_Q_HEADING.exec(t);
  if (!m) return null;
  const a = Number(m[1]);
  const b = m[2] ? Number(m[2]) : m[3] ? Number(m[3]) : a;
  if (!(a >= 1) || !(b >= a)) return null;
  const consumed = m[0].length;
  return { a, b, rest: t.slice(consumed).replace(/^[\s:.\-\u2013\u2014]+/, "").trim() };
}

function isOptionLine(line) {
  return RE_LETTER_OPT.test(line) || RE_ROMAN_OPT.test(line) || RE_TFNG_OPT.test(line);
}

function parseOptionLine(line, ctx = {}) {
  let m;
  if ((m = RE_TFNG_OPT.exec(line))) {
    return { label: m[1].toUpperCase(), text: normalizeWs(m[2]) };
  }
  if ((m = RE_ROMAN_OPT.exec(line))) {
    // 单字母罗马数字只认 i/v/x（小写）；大写 "I" 仅在罗马上下文（标题列表含 ii/iii…）中按罗马 i 处理，
    // 否则让位给字母选项 I / 正文（如 "I hope…"）
    const raw = m[1];
    const lower = raw.toLowerCase();
    if (lower.length > 1 || ["i", "v", "x"].includes(lower)) {
      if (lower.length === 1 && raw === "I" && !ctx.romanContext) {
        // fall through：由字母扩展分支或正文处理
      } else {
        return { label: raw, text: normalizeWs(m[2]) };
      }
    }
  }
  if ((m = RE_LETTER_OPT.exec(line))) {
    return { label: m[1], text: normalizeWs(m[2]) };
  }
  if ((m = RE_LETTER_OPT_EXT.exec(line))) {
    const L = m[1].toUpperCase();
    if (ctx.strongLetters && ctx.strongLetters.has(L)) {
      return { label: L, text: normalizeWs(m[2]) };
    }
    return null;
  }
  return null;
}

/** 元素内 <strong>/<b> 包裹的单字母（A-L）集合：扩展字母选项的判别信号 */
function strongLetterSet(node) {
  const set = new Set();
  walk(node, (n) => {
    if (n.type === "element" && (n.tag === "strong" || n.tag === "b")) {
      const t = normalizeWs(nodeText(n, { block: false }));
      const m = /^([A-L])$/.exec(t);
      if (m) set.add(m[1]);
    }
  });
  return set;
}

/** 元素内是否存在多字符罗马数字标签行（ii/iii/iv…）：用于区分标题列表中的大写 "I" 与字母选项 */
function hasRomanContext(lines) {
  return lines.some((l) => {
    const m = RE_ROMAN_OPT.exec(normalizeWs(l));
    return !!(m && m[1].length >= 2);
  });
}

/**
 * 行内多选项：一行内以 2+ 空格分隔的连续字母标签（如 "A daylight     B hot weather     C melatonin"）。
 * 仅在首个标签可判定、后续标签与前一标签按字母表连续、且（I-L）被 strong 包裹时拆分；否则返回 null。
 */
function splitInlineOptions(line, ctx = {}) {
  const m0 = /^([A-L])(?:[ \t]*[.):]|[ \t])[ \t]*(\S[\s\S]*)$/.exec(line);
  if (!m0) return null;
  const firstLabel = m0[1];
  if (firstLabel > "H" && !(ctx.strongLetters && ctx.strongLetters.has(firstLabel))) return null;
  const rest = m0[2];
  const re = /[ \t]{2,}([A-L])(?=[ \t]*[.):]|[ \t])(?:[ \t]*[.):])?[ \t]*/g;
  const parts = [];
  let label = firstLabel;
  let last = 0;
  let expect = firstLabel.charCodeAt(0) + 1;
  let m;
  while ((m = re.exec(rest))) {
    const L = m[1];
    if (L.charCodeAt(0) !== expect) continue;
    if (L > "H" && !(ctx.strongLetters && ctx.strongLetters.has(L))) continue;
    parts.push({ label, text: rest.slice(last, m.index).trim() });
    label = L;
    last = re.lastIndex;
    expect = L.charCodeAt(0) + 1;
  }
  parts.push({ label, text: rest.slice(last).trim() });
  if (parts.length < 2) return null;
  return parts.map((p) => ({ label: p.label, text: normalizeWs(p.text) }));
}

function optionPoolKind(options) {
  if (options.some((o) => /^(TRUE|FALSE|NOT GIVEN|YES|NO)$/.test(o.label))) return "true_false";
  if (options.every((o) => /^[ivx]+$/i.test(o.label)) && options.some((o) => o.label.length > 1)) return "headings";
  if (options.every((o) => /^[A-L]$/.test(o.label))) return "letters";
  return "mixed";
}

function isHeadingElement(node) {
  return isElement(node) && /^h[1-6]$/.test(node.tag);
}

/* ---------- 块单元与 ownText 工具（避免父子元素重复计文本） ---------- */

/** 参与题组/篇目扫描的块级单元标签 */
const BLOCK_UNIT_TAGS = new Set([
  "p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "figcaption", "blockquote",
  "dd", "dt", "pre", "section", "article", "aside", "header", "footer", "main",
  "nav", "form", "fieldset", "figure", "table", "caption", "address", "details",
  "td", "th", "ul", "ol", "img",
]);

/** ownText 递归时的块级边界：块级子元素的文本由该子元素自身贡献 */
const BLOCK_BOUNDARY_TAGS = new Set([
  "address", "article", "aside", "blockquote", "caption", "dd", "details", "div",
  "dl", "dt", "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2",
  "h3", "h4", "h5", "h6", "header", "hgroup", "hr", "ins", "li", "main", "menu",
  "nav", "ol", "p", "pre", "section", "table", "tbody", "td", "tfoot", "th",
  "thead", "tr", "ul",
]);

/** 可以承载 "Questions N-M" 标题的标签 */
const HEADING_HOST_TAGS = new Set([
  "p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "figcaption", "blockquote",
  "dd", "dt", "caption", "section", "article", "td", "th",
]);

/** 纯 UI/脚本标签：不贡献任何题目文本（按钮如 "Show Answers"、广告 ins 等） */
const SKIP_TEXT_TAGS = new Set(["script", "style", "ins", "button", "noscript", "template"]);

/**
 * 元素自身贡献的文本：递归 inline 子元素，但不进入块级子元素（其文本由其自身贡献），
 * br → \n；script/style/ins（广告）/button（Show Answers 等）跳过。避免同一段文本在父子元素上重复计数。
 */
export function ownText(node) {
  if (!node) return "";
  if (node.type === "text") return node.text;
  if (node.type !== "element") return "";
  if (node.tag === "br") return "\n";
  if (SKIP_TEXT_TAGS.has(node.tag)) return "";
  const parts = [];
  for (const ch of node.children || []) {
    if (ch.type === "text") { parts.push(ch.text); continue; }
    if (ch.type !== "element") continue;
    if (ch.tag === "br") { parts.push("\n"); continue; }
    if (SKIP_TEXT_TAGS.has(ch.tag)) continue;
    if (BLOCK_BOUNDARY_TAGS.has(ch.tag)) continue;
    parts.push(ownText(ch));
  }
  return parts.join("");
}

/** ownText 的按行形态（trim 后非空）；opts.preserveSpaces 保留行内多空格 */
export function ownTextLines(node, opts = {}) {
  return ownText(node)
    .split("\n")
    .map((l) => {
      let s = l.replace(/[\u00a0]/g, " ");
      if (!opts.preserveSpaces) s = s.replace(/[ \t]+/g, " ");
      return s.trim();
    })
    .filter((l) => l.length > 0);
}

/** 文档序块级单元列表（跳过答案容器、ins 广告与 UI 噪音子树） */
export function collectBlocks(root) {
  const out = [];
  (function visit(node, insideAnswer) {
    for (const ch of node.children || []) {
      if (ch.type !== "element") continue;
      const isAnswer = insideAnswer || isAnswerContainer(ch);
      if (isAnswer || SKIP_TEXT_TAGS.has(ch.tag)) continue;
      if (BLOCK_UNIT_TAGS.has(ch.tag)) out.push(ch);
      visit(ch, isAnswer);
    }
  })(root, false);
  return out;
}

/** "Choose/Which TWO|THREE|FOUR …" 类多选组判定 */
function isMultiSelectInstruction(text) {
  const t = String(text || "").toUpperCase();
  if (/\b(TWO|THREE|FOUR|FIVE)\s+(?:CORRECT\s+)?(?:LETTERS?|OPTIONS?|ITEMS?|ANSWERS?|HEADINGS?)\b/.test(t)) return true;
  if (/\b(TWO|THREE|FOUR|FIVE)\s+OTHER\b/.test(t)) return true;
  if (/\b(TWO|THREE|FOUR|FIVE)\s+OF\s+(?:THE\s+)?(?:FOLLOWING|OPTIONS?|LETTERS?|LIST|ABOVE|BELOW)\b/.test(t)) return true;
  if (/\b(CHOOSE|SELECT|CIRCLE|WHICH|PICK)\b[^.\n]{0,60}\b(TWO|THREE|FOUR|FIVE)\b(?!\s+(?:WORDS?|NUMBERS?|PIECES?|TIMES?|BLANKS?|GAPS?))/.test(t)) return true;
  return false;
}

/**
 * 按 "Questions N-M" 范围提取题组。
 * opts: {maxNumber, stopAtHeadings=true}
 *  - stopAtHeadings: 阅读页用 true（h1-h6 为文章标题，遇到即结束题组正文）；
 *    听力页用 false（h2 可能是题内表格标题，如 "ANTARCTIC TREATY"）。
 * 返回 {groups, notes}；group.block_span=[startK,endK) 为 collectBlocks 下标，供篇目排除题组区。
 */
export function collectQuestionGroups(root, opts = {}) {
  const maxNumber = Number.isFinite(opts.maxNumber) ? opts.maxNumber : 999;
  const stopAtHeadings = opts.stopAtHeadings !== false;
  const groups = [];
  const notes = [];

  const blocks = collectBlocks(root);
  // 讲解区截断：出现 "EXPLANATION OF ANSWERS"/"Explanations:" 标题后，后续文本是讲解而非题组
  let explainStart = blocks.length;
  for (let k = 0; k < blocks.length; k++) {
    if (RE_EXPLAIN_MARKER.test(normalizeWs(ownText(blocks[k])))) { explainStart = k; break; }
  }
  const headingIdx = [];
  for (let k = 0; k < blocks.length; k++) {
    const el = blocks[k];
    if (k >= explainStart) break;
    if (!HEADING_HOST_TAGS.has(el.tag)) continue;
    const text = normalizeWs(ownText(el)).replace(/\n/g, " ");
    if (!text || text.length > 4000) continue;
    const h = parseHeadingText(text);
    if (h && h.a <= maxNumber) headingIdx.push({ k, el, heading: h, text });
  }

  for (let gi = 0; gi < headingIdx.length; gi++) {
    const { k, el, heading, text } = headingIdx[gi];
    let endK = gi + 1 < headingIdx.length ? headingIdx[gi + 1].k : blocks.length;
    if (endK > explainStart) endK = explainStart;
    // 篇目标题/页分隔符截断：阻止组正文吞掉下一篇文章标题与正文（阅读页专用）
    if (opts.stopBlocks && opts.stopBlocks.size > 0) {
      for (let k2 = k + 1; k2 < endK; k2++) {
        if (opts.stopBlocks.has(k2)) { endK = k2; break; }
      }
    }
    const numbers = [];
    for (let n = heading.a; n <= heading.b; n++) numbers.push(n);
    if (stopAtHeadings) {
      for (let k2 = k + 1; k2 < endK; k2++) {
        const hEl = blocks[k2];
        if (!isHeadingElement(hEl) || normalizeWs(ownText(hEl)).length === 0) continue;
        // 表格/图块标题（h2）：其后到下一标题前的 figure/table/img 含本组范围 (N) 缺口时视为表标题，不截断
        let assetGap = false;
        for (let k3 = k2 + 1; k3 < endK; k3++) {
          const el3 = blocks[k3];
          if (isHeadingElement(el3)) break;
          if (el3.tag !== "figure" && el3.tag !== "table" && el3.tag !== "img") continue;
          const t3 = normalizeWs(nodeText(el3, { block: true }));
          RE_GAP_MARKER.lastIndex = 0;
          let gm;
          while ((gm = RE_GAP_MARKER.exec(t3))) {
            if (numbers.includes(Number(gm[1]))) { assetGap = true; break; }
          }
          if (assetGap) break;
        }
        if (assetGap) continue;
        endK = k2;
        break;
      }
    }

    const group = {
      index: gi,
      range: [heading.a, heading.b],
      numbers,
      heading_text: text,
      instruction: heading.rest || "",
      shared_prompt: "",
      word_limit: null,
      pools: [],
      options: [],
      slots: [],
      assets: [],
      out_of_range: [],
      block_span: [k, endK],
      source_ref: nodePath(el),
      heading_source_ref: nodePath(el),
    };

    const bodyEls = blocks.slice(k + 1, endK);
    const preQuestionTexts = [];
    let currentSlot = null;
    let firstQuestionSeen = false;
    let elementPool = null;
    let sawOption = false;      // 首次出现选项后，后续行不再计入题干候选
    const stemLines = [];       // 选项前的题干行（单题组补齐时使用）

    // 标题块中标题行之后的剩余行也属于题组正文（如 "<p>Part 1: Questions 1-4<br />1. …<br />A …</p>"）
    const carryLines = [];
    {
      const hl = ownTextLines(el, { preserveSpaces: true });
      let found = -1;
      let restText = "";
      for (let li = 0; li < hl.length; li++) {
        const t = normalizeWs(hl[li]);
        const m = RE_Q_HEADING.exec(t);
        if (m && Number(m[1]) === heading.a) { found = li; restText = t.slice(m[0].length); break; }
      }
      if (found >= 0) {
        if (restText.trim()) carryLines.push(restText);
        for (let li = found + 1; li < hl.length; li++) {
          if (RE_Q_HEADING.test(normalizeWs(hl[li]))) break;
          carryLines.push(hl[li]);
        }
      }
    }

    const pushOptions = (opts, bel, ctx) => {
      sawOption = true;
      if (!ctx.forcePool && firstQuestionSeen && currentSlot) {
        currentSlot.options.push(...opts);
      } else {
        if (!elementPool) {
          elementPool = { kind: null, options: [], source_ref: nodePath(bel) };
          group.pools.push(elementPool);
        }
        elementPool.options.push(...opts);
      }
    };

    const processLine = (rawLine, bel, ctx) => {
      // 行内多选项（同一行以 2+ 空格分隔的连续字母标签）
      const inlineOpts = splitInlineOptions(rawLine, ctx);
      if (inlineOpts) { pushOptions(inlineOpts, bel, ctx); return; }
      const line = normalizeWs(rawLine);
      let m;
      let num = null;
      let prompt = null;
      let kind = "line";
      if ((m = RE_Q_LINE_ELL.exec(line))) { num = Number(m[1]); prompt = m[2]; kind = "line_ellipsis"; }
      else if ((m = RE_Q_LINE_DOT.exec(line))) { num = Number(m[1]); prompt = m[2] !== undefined ? m[2] : m[3]; kind = "line"; }
      else if ((m = RE_Q_LINE_PAREN.exec(line))) { num = Number(m[1]); prompt = m[2]; kind = "line_paren"; }
      else if ((m = RE_Q_LINE_PLAIN.exec(line))) { num = Number(m[1]); prompt = m[2]; kind = "line_plain"; }
      else if ((m = RE_Q_LINE_EMPTY.exec(line))) { num = Number(m[1]); prompt = ""; kind = "line_empty"; }
      if (num != null) {
        if (!numbers.includes(num)) {
          // 越界行内也可能含本组范围的 (N) 缺口（如 "2. The information should be combined in one (39)"）
          RE_GAP_MARKER.lastIndex = 0;
          const og = [];
          while ((m = RE_GAP_MARKER.exec(line))) {
            const gn = Number(m[1]);
            if (numbers.includes(gn)) og.push(gn);
          }
          if (og.length > 0) {
            firstQuestionSeen = true;
            const hasInput = findAll(bel, (n) => isElement(n, "input")).length > 0;
            for (const gn of og) {
              if (group.slots.some((s) => s.number === gn)) continue;
              group.slots.push({ number: gn, kind: hasInput ? "input" : "gap", prompt: line, options: [], source_ref: nodePath(bel) });
            }
            return;
          }
          // 只记录“像题号”的越界行（≤99）；年份/数量（如 "850 AD"）不算题号
          if (num <= 99) group.out_of_range.push({ number: num, line, kind, prompt: normalizeWs(prompt), source_ref: nodePath(bel) });
          return;
        }
        if (group.slots.some((s) => s.number === num && s.kind.startsWith("line"))) return;
        firstQuestionSeen = true;
        currentSlot = { number: num, kind, prompt: normalizeWs(prompt), options: [], source_ref: nodePath(bel) };
        group.slots.push(currentSlot);
        return;
      }
      // (N) 内嵌占位（输入/填空）：先于选项判定，避免 "A 3,000-year-old … (27)…" 这类正文段被当成字母选项
      RE_GAP_MARKER.lastIndex = 0;
      const gaps = [];
      while ((m = RE_GAP_MARKER.exec(line))) {
        const gn = Number(m[1]);
        if (numbers.includes(gn)) gaps.push(gn);
      }
      if (gaps.length > 0) {
        firstQuestionSeen = true;
        const hasInput = findAll(bel, (n) => isElement(n, "input")).length > 0;
        for (const gn of gaps) {
          if (group.slots.some((s) => s.number === gn)) continue;
          group.slots.push({ number: gn, kind: hasInput ? "input" : "gap", prompt: line, options: [], source_ref: nodePath(bel) });
        }
        return;
      }
      // 断括号窄回退：input 元素把 "(10)" 拆成 "(not 10 )" 等 → 仅括号内文字为 not/no/except 时按缺口处理
      {
        const reRelaxed = /\(([^()]{1,24}?)(\d{1,3})[ \t]*\)/g;
        let rm;
        while ((rm = reRelaxed.exec(line))) {
          const word = rm[1].trim().toLowerCase();
          const gn = Number(rm[2]);
          if ((word === "not" || word === "no" || word === "except") && numbers.includes(gn)) {
            firstQuestionSeen = true;
            if (!group.slots.some((s) => s.number === gn)) {
              const hasInput = findAll(bel, (n) => isElement(n, "input")).length > 0;
              group.slots.push({ number: gn, kind: hasInput ? "input" : "gap", prompt: line, options: [], source_ref: nodePath(bel) });
            }
            return;
          }
        }
      }
      // "B 2 Section" 交错形态（"1 Section B" 被换行拆散）：不建字母选项，按题号槽处理
      if ((m = /^([A-Z])[ \t]+(\d{1,3})[ \t]+Section\b([\s\S]*)$/.exec(line))) {
        const sn = Number(m[2]);
        if (numbers.includes(sn)) {
          if (!group.slots.some((s) => s.number === sn)) {
            firstQuestionSeen = true;
            currentSlot = { number: sn, kind: "line_section", prompt: line, options: [], source_ref: nodePath(bel) };
            group.slots.push(currentSlot);
          }
          return;
        }
      }
      const opt = parseOptionLine(line, ctx);
      if (opt) {
        if (opt.text.length > 160) return;
        pushOptions([opt], bel, ctx);
        return;
      }
      preQuestionTexts.push(line);
      if (!sawOption) stemLines.push(line);
      if (!group.word_limit) {
        const wm = RE_WORD_LIMIT.exec(line);
        if (wm) group.word_limit = wm[1];
      }
    };

    // 段序列：标题块剩余行 → 后续正文块
    const segments = [];
    if (carryLines.length) segments.push({ el, lines: carryLines, carry: true });
    for (const bel of bodyEls) {
      segments.push({ el: bel, lines: ownTextLines(bel, { preserveSpaces: true }), carry: false });
    }

    for (const seg of segments) {
      const bel = seg.el;
      if (!seg.carry) {
        // 组内表格/图片资产
        if (bel.tag === "figure" || bel.tag === "img" || bel.tag === "table") {
          group.assets.push({ kind: bel.tag === "img" ? "image" : bel.tag, source_ref: nodePath(bel) });
        }
        if (bel.tag === "table") {
          // 表格格内 (N) 占位符 → cell gap 槽
          const cells = findAll(bel, (n) => isElement(n, "td") || isElement(n, "th"));
          for (const cell of cells) {
            const lines = normalizeWs(nodeText(cell, { block: true })).split("\n").map((l) => l.trim()).filter(Boolean);
            for (const line of lines) {
              let m;
              RE_GAP_MARKER.lastIndex = 0;
              const found = [];
              while ((m = RE_GAP_MARKER.exec(line))) {
                const num = Number(m[1]);
                if (numbers.includes(num)) found.push(num);
              }
              for (const num of found) {
                if (group.slots.some((s) => s.number === num)) continue;
                group.slots.push({ number: num, kind: "cell_gap", prompt: line, options: [], source_ref: nodePath(cell) });
              }
            }
          }
        }
      }
      // 文本元素：逐行处理（ownText 只取本元素自身文本，避免父子重复）
      if (seg.lines.length === 0) continue;
      elementPool = null;
      // 纯选项块（无题行）中的选项进入组池，不挂到最后一道题上（如 "best ending from the box"）
      const segHasQ = seg.lines.some((l) => isQuestionLineLike(normalizeWs(l)));
      const ctx = { strongLetters: strongLetterSet(bel), romanContext: hasRomanContext(seg.lines), forcePool: firstQuestionSeen && !segHasQ };
      for (const rawLine of seg.lines) processLine(rawLine, bel, ctx);
      if (elementPool) elementPool.kind = optionPoolKind(elementPool.options);
    }

    if (group.word_limit == null) {
      const wm = RE_WORD_LIMIT.exec(group.instruction);
      if (wm) group.word_limit = wm[1];
    }
    group.shared_prompt = normalizeWs(preQuestionTexts.join("\n"));
    // 指令声明的范围（"boxes N-M" / "next to Questions N-M"）超出标题范围时
    // （如标题 "Questions 15-16"、指令 "next to Questions 15-20"）：
    // 落在声明范围内的越界题行转正为槽（保留 kind/prompt），并记录 range_extended provenance
    {
      const rangeText = group.instruction + "\n" + preQuestionTexts.join("\n");
      const declaredRanges = [];
      for (const [re, source] of [[RE_BOX, "instruction_boxes"], [RE_NEXT_TO, "instruction_next_to"]]) {
        re.lastIndex = 0;
        let rm;
        while ((rm = re.exec(rangeText))) {
          const ra = Number(rm[1]);
          const rb = rm[2] ? Number(rm[2]) : rm[3] ? Number(rm[3]) : ra;
          if (ra >= 1 && rb >= ra) declaredRanges.push({ a: ra, b: rb, source });
        }
      }
      if (declaredRanges.length > 0 && group.out_of_range.length > 0) {
        const kept = [];
        const matchedSources = new Set();
        let extendedTo = null;
        for (const o of group.out_of_range) {
          const hit = declaredRanges.find((r) => o.number >= r.a && o.number <= r.b);
          if (hit && o.number > heading.b && o.number <= maxNumber && !numbers.includes(o.number)) {
            numbers.push(o.number);
            group.slots.push({ number: o.number, kind: o.kind || "line", prompt: o.prompt || "", options: [], source_ref: o.source_ref });
            matchedSources.add(hit.source);
            if (extendedTo == null || o.number > extendedTo) extendedTo = o.number;
          } else {
            kept.push(o);
          }
        }
        group.out_of_range = kept;
        if (extendedTo != null) {
          group.range_extended = { from: [heading.a, heading.b], to: [heading.a, extendedTo], source: [...matchedSources].join("+") };
        }
      }
    }
    // 裸数字标记行（"… not entire 36" / 单独行 "17" / "…of 26……"）：为无槽题号提供题干来源
    const bareMarker = (n) => {
      const pre = "(?:^|[\\s(\\u2022\\-\\u2013])";
      const reEnd = new RegExp(pre + n + "[ \\t]*$");
      const reEll = new RegExp(pre + n + "[ \\t]*[.\\uFF0E\\u2026]{2,}");
      for (let i = k + 1; i < endK; i++) {
        const lines = ownTextLines(blocks[i], { preserveSpaces: false });
        for (const line of lines) {
          if (RE_Q_HEADING.test(line)) continue;
          if (reEll.test(line) || reEnd.test(line)) return line;
        }
      }
      return null;
    };
    // 补齐组范围内未出现槽位的题号（多选组等）
    const covered = new Set(group.slots.map((s) => s.number));
    const letterPool = group.pools.find((p) => p.options.length > 0 && p.options.every((o) => /^[A-L]$/.test(o.label)));
    const multi = isMultiSelectInstruction(group.instruction + "\n" + group.shared_prompt);
    const single = numbers.length === 1;
    for (const n of numbers) {
      if (covered.has(n)) continue;
      const marker = multi ? null : bareMarker(n);
      let prompt = marker || "";
      if (!prompt && single && stemLines.length) {
        const inst = normalizeWs(group.instruction);
        prompt = stemLines.filter((l) => normalizeWs(l) !== inst).join("\n");
      }
      const attachPool = (multi || single) && letterPool;
      group.slots.push({
        number: n,
        kind: marker ? "gap" : multi ? "multi_select" : "derived",
        prompt,
        options: attachPool ? letterPool.options.map((o) => ({ label: o.label, text: o.text })) : [],
        source_ref: group.source_ref,
      });
    }
    group.slots.sort((a, b) => a.number - b.number || a.kind.localeCompare(b.kind));
    group.options = group.pools.flatMap((p, pi) => p.options.map((o) => ({ ...o, pool: pi })));
    groups.push(group);
  }

  // 部分级容器标题（如 "Part 2: Questions 11 – 20"）：整组均为无正文补齐槽且被后续组完整覆盖时，
  // 标记为结构化头，不产生幻影题位
  for (let gi = 0; gi < groups.length; gi++) {
    const g = groups[gi];
    if (g.slots.length === 0) continue;
    if (!g.slots.every((s) => s.kind === "derived" || (s.kind === "multi_select" && !s.prompt))) continue;
    const covered = new Set();
    for (let gj = gi + 1; gj < groups.length; gj++) {
      for (const n of groups[gj].numbers) covered.add(n);
    }
    if (!g.numbers.every((n) => covered.has(n))) continue;
    g.structural = true;
    g.slots = [];
  }

  if (groups.length === 0) notes.push({ kind: "question_groups_missing" });
  return { groups, notes };
}

/* ============== 5b. 篇目标题候选（题组截断与篇目切分共用） ============== */

// 题内容块判定：强信号（编号行/空位行/"(N)………"）直接计内容；
// 仅 "数字+空格+字母"（PLAIN）时，需短块（<180 字符）才算，避免正文段误报拉长内容区。
const RE_GAP_RUN = /\(\d{1,3}\)\s*[.\u2026]{2,}/;
function isQuestionContentBlock(el) {
  const lines = ownTextLines(el, { preserveSpaces: false });
  for (const line of lines) {
    if (RE_Q_LINE_ELL.test(line) || RE_Q_LINE_DOT.test(line) || RE_Q_LINE_PAREN.test(line) || RE_Q_LINE_EMPTY.test(line)) return true;
    if (RE_GAP_RUN.test(line)) return true;
  }
  let plain = 0;
  for (const line of lines) if (RE_Q_LINE_PLAIN.test(line)) plain++;
  if (plain >= 2) return true;
  if (plain === 1 && normalizeWs(ownText(el)).length < 180) return true;
  return false;
}
// 每组题内容区 [k, contentEnd)：候选标题落在其中则排除（题区内的表格/摘要标题）
function questionContentEnds(groups, blocks) {
  return groups.map((g) => {
    if (!Array.isArray(g.block_span) || g.block_span.length !== 2) return null;
    const [k, endK] = g.block_span;
    let lastC = -1;
    for (let i = k; i < endK; i++) if (isQuestionContentBlock(blocks[i])) lastC = i;
    return lastC >= 0 ? lastC + 1 : k + 1;
  });
}
function isInQuestionContent(i, groups, ends) {
  for (let gi = 0; gi < groups.length; gi++) {
    const ce = ends[gi];
    if (ce == null) continue;
    const k = groups[gi].block_span[0];
    if (i >= k && i < ce) return true;
  }
  return false;
}
const headingTextOf = (el) => normalizeWs(ownText(el));
// 题组标题（含 "Part One/Section IV" 词形数字）不作为篇目标题候选
const RE_PART_LABEL = /^(?:part|section|passage)\s+(?:\d+|[ivxlcdm]+|one|two|three|four|five|six|seven|eight|nine|ten)\b/i;
function isQuestionHeadingTextOf(t) { return !!parseHeadingText(t.replace(/\n/g, " ")) || RE_PART_LABEL.test(t); }
// unwrap 单 span 链（≤3 层）：<p><span><span><strong>T</strong></span></span></p>
function unwrapSingleSpans(el, maxDepth = 3) {
  let cur = el;
  for (let d = 0; d < maxDepth; d++) {
    const kids = (cur.children || []).filter((c) => c.type === "element");
    const texts = (cur.children || []).filter((c) => c.type === "text" && c.text.trim());
    if (texts.length || kids.length !== 1 || kids[0].tag !== "span") break;
    cur = kids[0];
  }
  return cur;
}
// 单 <strong>/<b> 全包裹的段落（可经 span 链）：PTE 阅读篇目标题常见形态
function strongTitleTextOf(el) {
  if (el.tag !== "p") return null;
  const inner = unwrapSingleSpans(el);
  const kids = (inner.children || []).filter((c) => c.type === "element");
  const texts = (inner.children || []).filter((c) => c.type === "text" && c.text.trim());
  if (texts.length || kids.length !== 1) return null;
  const k = kids[0];
  if (k.tag !== "strong" && k.tag !== "b") return null;
  const t = normalizeWs(nodeText(k, { block: false }));
  return t || null;
}
// 居中 + capitalize 的纯文本段（如 <p style="text-transform: capitalize; text-align: center;">Title</p>）
function centeredCapTextOf(el) {
  if (el.tag !== "p") return null;
  const style = (attr(el, "style") || "").toLowerCase();
  if (!/text-align\s*:\s*center/.test(style) || !/text-transform\s*:\s*capitalize/.test(style)) return null;
  const t = normalizeWs(ownText(el));
  return t || null;
}
// 指令块标题（TRUE/FALSE/NOT GIVEN、YES/NO 等）不作为标题
const RE_TFNG_TITLE = /^(?:true|false|yes|no|not[\s-]+given)(?:[\s\/,]*(?:true|false|yes|no|not[\s-]+given))*$/i;
function isTitleLikeText(t) {
  if (t.length < 3 || t.length > 120) return false;
  if (isQuestionLineLike(t)) return false;
  if (isQuestionHeadingTextOf(t)) return false;
  if (RE_TFNG_TITLE.test(t)) return false;
  if (/^(?:list of|type of|notes?|table|diagram|summary|example)s?\b/i.test(t)) return false;
  if (/cambridge ielts|ielts test|practice pte/i.test(t)) return false;
  return true;
}
// 标题与首段合并形态：<p style="text-align:center"><strong>Title</strong><br><span>首段…</span></p>（剑 21 常见）
// 仅居中段落视为篇目标题：justify 下的 "Section A"/"Locations"/"Introduction" 等为篇内小节/列表头
function mergedTitleInfoOf(el) {
  if (el.tag !== "p") return null;
  const style = (attr(el, "style") || "").toLowerCase();
  if (!/text-align\s*:\s*center/.test(style)) return null;
  const children = el.children || [];
  const first = children.find((c) => (c.type === "text" && c.text.trim()) || c.type === "element");
  if (!first || first.type !== "element" || (first.tag !== "strong" && first.tag !== "b")) return null;
  const after = children.slice(children.indexOf(first) + 1);
  const next = after.find((c) => (c.type === "text" && c.text.trim()) || c.type === "element");
  if (!next || next.type !== "element" || next.tag !== "br") return null;
  const title = normalizeWs(nodeText(first, { block: false }));
  if (!title || !isTitleLikeText(title)) return null;
  const restParts = [];
  for (const c of children.slice(children.indexOf(next) + 1)) {
    if (c.type === "text") { if (c.text.trim()) restParts.push(c.text); }
    else restParts.push(nodeText(c, { block: false }));
  }
  const rest = normalizeWs(restParts.join(" "));
  return { title, rest: rest || null };
}
// 下一非空块：figure/table/img 块自身可能无文本，直接返回以支持图块标题排除
function nextNonEmptyBlockOf(i, blocks) {
  for (let j = i + 1; j < blocks.length; j++) {
    const el = blocks[j];
    if (el.tag === "figure" || el.tag === "table" || el.tag === "img") return el;
    if (normalizeWs(ownText(el)).length > 0) return el;
  }
  return null;
}
// 篇目标题候选检测：供 collectPassages 切分与 collectReadingGroupStops 截断共用
function findPassageTitleCandidates(root, groups) {
  const blocks = collectBlocks(root);
  const notes = [];
  const ends = questionContentEnds(groups, blocks);
  const candidates = [];
  for (let i = 0; i < blocks.length; i++) {
    const el = blocks[i];
    if (isInQuestionContent(i, groups, ends)) continue;
    let title = null;
    let firstParagraph = null;
    if (isHeadingElement(el)) {
      const t = headingTextOf(el);
      if (t.length > 0 && !isQuestionHeadingTextOf(t)) title = t;
    } else {
      const st = strongTitleTextOf(el);
      if (st && isTitleLikeText(st)) title = st;
      else {
        const mt = mergedTitleInfoOf(el);
        if (mt) { title = mt.title; firstParagraph = mt.rest; }
        else {
          const ct = centeredCapTextOf(el);
          if (ct && isTitleLikeText(ct)) title = ct;
        }
      }
    }
    if (title == null) continue;
    // 答案讲解区标题不作为篇目
    if (RE_EXPLAIN_MARKER.test(title) || /^answer\s*key\b/i.test(title)) continue;
    // 表格/图块标题排除：下一非空块为 figure/table（含内嵌 table 的 figure）
    const nb = nextNonEmptyBlockOf(i, blocks);
    if (nb && (nb.tag === "figure" || nb.tag === "table")) continue;
    candidates.push({ i, el, title, isLabel: /^reading\s+passage\b/i.test(title), firstParagraph });
  }
  // 篇内小节标题排除：与前一个保留候选之间无题组且中间有长正文 → 视为小节标题而非篇目
  const kept = [];
  for (const c of candidates) {
    if (kept.length === 0) { kept.push(c); continue; }
    const prev = kept[kept.length - 1];
    let hasGroupBetween = false;
    for (const g of groups) {
      if (!Array.isArray(g.block_span)) continue;
      const gk = g.block_span[0];
      if (gk > prev.i && gk < c.i) { hasGroupBetween = true; break; }
    }
    if (hasGroupBetween) { kept.push(c); continue; }
    let longBody = false;
    for (let j = prev.i + 1; j < c.i; j++) {
      if (blocks[j].tag === "p" && normalizeWs(ownText(blocks[j])).length >= 180) { longBody = true; break; }
    }
    if (longBody) {
      notes.push({ kind: "candidate_section_heading_skipped", title: c.title });
      continue;
    }
    kept.push(c);
  }
  return { blocks, ends, kept, notes };
}

/**
 * 阅读题组截断点：篇目标题候选块 + 页内 "Cambridge IELTS Tests N to M" 分隔链接块。
 * 供 collectQuestionGroups(opts.stopBlocks) 使用，阻止组正文吞掉下一篇文章标题与正文；
 * 听力页不使用（听力题干本身即正文）。返回 {stopBlocks:Set<blockIdx>, titles, separators}
 */
const RE_CAMBRIDGE_SEPARATOR = /^Cambridge\s+IELTS\s+Tests?\s+\d+\s+to\s+\d+\s*$/i;
export function collectReadingGroupStops(root, groups = []) {
  const { blocks, ends, kept } = findPassageTitleCandidates(root, groups);
  const stopBlocks = new Set();
  const titles = [];
  const separators = [];
  for (const c of kept) { stopBlocks.add(c.i); titles.push({ block: c.i, title: c.title }); }
  for (let i = 0; i < blocks.length; i++) {
    if (isInQuestionContent(i, groups, ends)) continue;
    const t = normalizeWs(ownText(blocks[i]));
    if (t && RE_CAMBRIDGE_SEPARATOR.test(t)) { stopBlocks.add(i); separators.push({ block: i, text: t }); }
  }
  return { stopBlocks, titles, separators };
}

/* ============================ 6. 篇目与资产 ============================ */

/**
 * 阅读篇目：按标题候选（h1-h6、strong 全包裹段、标题+首段合并段、居中 capitalize 段）切分；
 * 排除题区标题、表格/图块标题、答案讲解区标题与篇内小节标题；返回 {passages, notes}
 * passage: {index, title, title_is_label, title_source_ref, paragraphs:[{text,letter}], tables, figures, images, question_groups:[index], range}
 */
export function collectPassages(root, opts = {}) {
  const expected = Number.isFinite(opts.expectedPassages) ? opts.expectedPassages : null;
  const groups = opts.groups || [];
  const notes = [];

  const { blocks, ends: contentEnds, kept: keptCandidates, notes: candidateNotes } = findPassageTitleCandidates(root, groups);
  const inQuestionContent = (i) => isInQuestionContent(i, groups, contentEnds);
  for (const n of candidateNotes) notes.push(n);
  const passages = [];
  if (keptCandidates.length === 0) {
    // 无标题：整页作为单一 passage（不合并、如实标注）
    const paragraphs = [];
    for (let i = 0; i < blocks.length; i++) {
      const el = blocks[i];
      if (el.tag !== "p" || inQuestionContent(i)) continue;
      const text = normalizeWs(ownText(el));
      if (text.length > 40 && !/cookie|advertisement|subscribe|share this/i.test(text)) {
        paragraphs.push({ text, letter: null, source_ref: nodePath(el) });
      }
    }
    if (paragraphs.length > 0) {
      passages.push({ index: 0, title: null, title_is_label: false, title_source_ref: null, paragraphs, tables: [], figures: [], images: [], question_groups: groups.map((g) => g.index), range: null });
    }
    notes.push({ kind: "passage_headings_missing" });
  } else {
    for (let hi = 0; hi < keptCandidates.length; hi++) {
      const c = keptCandidates[hi];
      const nextC = hi + 1 < keptCandidates.length ? keptCandidates[hi + 1] : null;
      const title = c.title;
      const startPos = c.i;
      const endPos = nextC ? nextC.i : blocks.length;
      // 段落范围：到本标题之后第一个题组标题（或下一候选标题）为止
      let paraEnd = endPos;
      for (const g of groups) {
        if (!Array.isArray(g.block_span)) continue;
        const gk = g.block_span[0];
        if (gk > startPos && gk < paraEnd) paraEnd = gk;
      }
      const paragraphs = [], tables = [], figures = [], images = [];
      // 标题与首段合并形态：合并块内的首段作为本篇第 0 段
      if (c.firstParagraph) {
        const t = normalizeWs(c.firstParagraph);
        if (t.length >= 2 && !/cookie|advertisement|subscribe|share this/i.test(t) && !/^\d+\.\s/.test(t)) {
          paragraphs.push({ text: t, letter: null, source_ref: nodePath(c.el) });
        }
      }
      for (let i = startPos + 1; i < paraEnd; i++) {
        const el = blocks[i];
        if (inQuestionContent(i)) continue;
        if (el.tag === "p") {
          const text = normalizeWs(ownText(el));
          if (text.length < 2) continue;
          if (/cookie|advertisement|subscribe|share this/i.test(text)) continue;
          if (/^\d+\.\s/.test(text)) continue; // 答案行
          let letter = null;
          const firstEl = (el.children || []).find((c2) => c2.type === "element");
          if (firstEl && firstEl.tag === "strong") {
            const lt = normalizeWs(ownText(firstEl));
            if (/^[A-Z]$/.test(lt)) letter = lt;
          }
          paragraphs.push({ text, letter, source_ref: nodePath(el) });
        } else if (el.tag === "table") {
          const rows = findAll(el, (n) => isElement(n, "tr"));
          const cells = findAll(el, (n) => isElement(n, "td") || isElement(n, "th"));
          tables.push({ kind: "table", rows: rows.length, cols: rows.length ? findAll(rows[0], (n) => isElement(n, "td") || isElement(n, "th")).length : 0, cells: cells.length, source_ref: nodePath(el) });
        } else if (el.tag === "figure") {
          const imgs = findAll(el, (n) => isElement(n, "img"));
          const hasTable = !!findFirst(el, (n) => isElement(n, "table"));
          figures.push({ kind: "figure", has_table: hasTable, images: imgs.length, source_ref: nodePath(el) });
        } else if (el.tag === "img") {
          images.push({ kind: "image", src: attr(el, "src"), alt: attr(el, "alt"), source_ref: nodePath(el) });
        }
      }
      const gids = [];
      for (const g of groups) {
        if (!Array.isArray(g.block_span)) continue;
        if (g.block_span[0] > startPos && g.block_span[0] < endPos) gids.push(g.index);
      }
      let range = null;
      if (gids.length) {
        const nums = gids.map((gid) => groups.find((g) => g.index === gid)).flatMap((g) => g.numbers);
        range = [Math.min(...nums), Math.max(...nums)];
      }
      passages.push({
        index: hi, title, title_is_label: !!c.isLabel, title_source_ref: nodePath(c.el),
        paragraphs, tables, figures, images,
        question_groups: gids, range,
      });
    }
    // 仅标签且无内容的篇目（如 "READING PASSAGE 2" 后紧跟真标题）：并入下一篇，不重复计数
    const kept = [];
    const droppedLabels = [];
    for (let hi = 0; hi < passages.length; hi++) {
      const p = passages[hi];
      const empty = p.paragraphs.length === 0 && p.tables.length === 0 && p.figures.length === 0 && p.images.length === 0 && p.question_groups.length === 0;
      if (empty && p.title_is_label && hi + 1 < passages.length) {
        droppedLabels.push(p.title);
        continue;
      }
      kept.push(p);
    }
    if (droppedLabels.length) notes.push({ kind: "passage_label_merged", titles: droppedLabels });
    passages.length = 0;
    kept.forEach((p, idx) => { p.index = idx; passages.push(p); });
    if (expected != null && passages.length !== expected) {
      notes.push({ kind: "passage_count_mismatch", expected, actual: passages.length });
    }
  }
  return { passages, notes };
}

/** 全页资产（图片/音频/表格/图块），含绝对 URL 与位置 */
export function collectAssets(root, opts = {}) {
  const baseUrl = opts.baseUrl || "";
  const resolve = (u) => {
    if (!u) return null;
    const clean = u.trim();
    if (/^https?:\/\//i.test(clean)) return clean;
    if (clean.startsWith("//")) return "https:" + clean;
    if (clean.startsWith("/")) return baseUrl.replace(/\/+$/, "") + clean;
    return clean;
  };
  const assets = [];
  walk(root, (n) => {
    if (n.type !== "element") return;
    if (n.tag === "img") {
      assets.push({ kind: "image", url: resolve(attr(n, "src")), alt: attr(n, "alt") || "", width: attr(n, "width"), height: attr(n, "height"), source_ref: nodePath(n), position: positionOf(n) });
    } else if (n.tag === "audio") {
      const src = attr(n, "src") || (findFirst(n, (c) => isElement(c, "source")) ? attr(findFirst(n, (c) => isElement(c, "source")), "src") : null);
      if (src) assets.push({ kind: "audio", url: resolve(src), source_ref: nodePath(n), position: positionOf(n) });
    } else if (n.tag === "source") {
      const src = attr(n, "src");
      if (src && /\.mp3(\?|$)/i.test(src)) assets.push({ kind: "audio", url: resolve(src), source_ref: nodePath(n), position: positionOf(n) });
    } else if (n.tag === "a") {
      const href = attr(n, "href");
      if (href && /\.mp3(\?|$)/i.test(href)) assets.push({ kind: "audio_link", url: resolve(href), source_ref: nodePath(n), position: positionOf(n) });
    } else if (n.tag === "table") {
      const rows = findAll(n, (x) => isElement(x, "tr"));
      assets.push({ kind: "table", rows: rows.length, source_ref: nodePath(n), position: positionOf(n) });
    } else if (n.tag === "figure") {
      assets.push({ kind: "figure", source_ref: nodePath(n), position: positionOf(n) });
    }
  });
  return assets;
}

function positionOf(node) {
  const parent = node.parent;
  if (!parent) return null;
  let idx = 0;
  for (const ch of parent.children) {
    if (ch === node) break;
    idx++;
  }
  return { parent_tag: parent.type === "root" ? "#root" : parent.tag, index: idx };
}

/* ============================ 7. 指令 / 解析 / 音频 ============================ */

export function collectInstructions(groups) {
  const out = [];
  for (const g of groups) {
    for (const s of [g.instruction, g.shared_prompt]) {
      const t = normalizeWs(s).replace(/\n/g, " ");
      if (t.length > 8 && !out.includes(t)) out.push(t);
    }
  }
  return out;
}

export function extractExplanations(root) {
  const out = {};
  const all = [];
  walk(root, (n) => {
    if (n.type !== "element") return;
    if (n.tag === "p" || n.tag === "div" || /^h[1-6]$/.test(n.tag)) {
      const t = normalizeWs(nodeText(n, { block: true }));
      if (t) all.push({ t, ref: nodePath(n) });
    }
  });
  let started = false;
  let buf = [];
  for (const { t } of all) {
    if (!started) {
      if (/^Explanations?\s*:/i.test(t)) { started = true; buf.push(t.replace(/^Explanations?\s*:/i, "")); }
      continue;
    }
    buf.push(t);
  }
  if (!started) return out;
  const text = buf.join("\n");
  const re = /Question\s+(\d{1,3})\s*[.):]?\s*([\s\S]*?)(?=Question\s+\d{1,3}\s*[.):]|$)/gi;
  let m;
  while ((m = re.exec(text))) {
    const n = Number(m[1]);
    const body = normalizeWs(m[2]).replace(/\n/g, " ");
    if (body.length > 20) out[n] = body.slice(0, 4000);
  }
  return out;
}

export function extractAudio(root, opts = {}) {
  const assets = collectAssets(root, opts).filter((a) => a.kind === "audio" || a.kind === "audio_link");
  const urls = [];
  for (const a of assets) {
    const u = a.url ? a.url.replace(/\?.*$/, "") : null;
    if (u && !urls.includes(u)) urls.push(u);
  }
  return urls;
}

export const __internals = { parseHeadingText, isOptionLine, optionPoolKind, RE_WORD_LIMIT, splitInlineOptions, strongLetterSet, hasRomanContext, isMultiSelectInstruction, isQuestionLineLike };
