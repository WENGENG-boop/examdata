const TICK = String.fromCharCode(96);
/**
 * cam21.mjs — 剑桥21 官方题库适配器（maqsudjon-cell/cambridge-21）
 *
 * 站点把结构化数据直接内嵌在 HTML 的 <script> 里：
 *   阅读页: PASSAGES / GROUPS / HEADINGS / ENDINGS / QUESTIONS / ANSWERS
 *   听力页: PARTS / TITLES / audioTracks / correctAnswers / multiCorrect / TRANSCRIPTS
 *
 * 实测（4 套 Test，2026-10 复核）：
 *   t1-reading 40题/40答案  t2-reading 39题/40答案
 *   t3-reading 40题/40答案  t4-reading 40题/40答案（合计 160 答案）
 *   listening 35–38 答案/套（合计 147）+ 每套 4 段官方音频
 *   + 逐句原文 738 行（含时间戳；t1 有说话人，t2–t4 源侧 sp 为空）
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

/** 带重试与 CDN 回落的抓取 */
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
  const all = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/gi)].map((m) => m[1]);
  return all.sort((a, b) => b.length - a.length)[0] || "";
}

/** 从 `const NAME = {` 起，按花括号配平截取完整字面量 */
function literal(src, name, open = "{") {
  const close = open === "{" ? "}" : "]";
  const re = new RegExp("const\\s+" + name + "\\s*=\\s*\\" + open);
  const start = src.search(re);
  if (start < 0) return null;
  const bodyStart = src.indexOf(open, start);
  let depth = 0, i = bodyStart, inStr = null, esc = false;
  for (; i < src.length; i++) {
    const ch = src[i];
    if (inStr) {
      if (esc) { esc = false; continue; }
      if (ch === "\\") { esc = true; continue; }
      if (ch === inStr) inStr = null;
      continue;
    }
    if (ch === '"' || ch === "'" || ch === TICK) { inStr = ch; continue; }
    if (ch === open) depth++;
    else if (ch === close) { depth--; if (!depth) { i++; break; } }
  }
  return src.slice(bodyStart, i);
}

/** 宽容解析：模板串转普通串、裸 key 加引号、单引号转双引号、去尾逗号 */
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

function looseParse(lit) {
  if (!lit) return null;
  try { return JSON.parse(jsToJson(lit)); } catch { return null; }
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

/* -------------------------------- 阅读 -------------------------------- */

/** 阅读：原文 + 题目 + 答案 */
export async function reading(test) {
  const t = Number(test);
  if (!TESTS.includes(t)) return { ok: false, source: SOURCE, error: "test 需为 1–4" };
  const r = await get("t" + t + "-reading.html");
  if (!r.ok) return { ok: false, source: SOURCE, error: r.error };
  const js = dataScript(r.body);

  const passages = looseParse(literal(js, "PASSAGES")) || {};
  const questions = looseParse(literal(js, "QUESTIONS", "[")) || [];
  const answers = looseParse(literal(js, "ANSWERS")) || {};

  const out = Object.keys(passages).sort((a, b) => a - b).map((k) => {
    const p = passages[k];
    const body = toText(p.html || p.text || "");
    return {
      passage: Number(k),
      title: p.title || null,
      range: p.qr || null,
      text: body,
      paragraphs: body.split(/\n{2,}/).filter((x) => x.length > 40),
    };
  });

  const qs = questions.map((q) => ({
    number: q.id,
    passage: q.p ?? null,
    group: q.g ?? null,
    type: q.type || "unknown",
    prompt: toText(q.text || "").replace(/\s+/g, " ").trim(),
  })).filter((q) => q.number);

  const key = Object.keys(answers).sort((a, b) => a - b).map((n) => ({ number: Number(n), answer: answers[n] }));

  return {
    ok: true, source: SOURCE, book: 21, test, skill: "reading",
    via: r.via, title: "Cambridge IELTS 21 Test " + test + " Reading",
    passages: out, questions: qs, answer_key: key,
    counts: { passages: out.length, questions: qs.length, answers: key.length },
  };
}

/** 阅读索引 */
export async function readingIndex() {
  const tests = [];
  for (const t of TESTS) {
    const r = await reading(t);
    if (!r.ok) { tests.push({ test: t, ok: false, error: r.error }); continue; }
    tests.push({ test: t, ok: true, titles: r.passages.map((p) => p.title), questions: r.counts.questions, answers: r.counts.answers });
  }
  return { ok: true, source: SOURCE, book: 21, tests };
}

/* -------------------------------- 听力 -------------------------------- */

/** 听力：题目 + 答案 + 音频 + 逐句原文 */
export async function listening(test) {
  const t = Number(test);
  if (!TESTS.includes(t)) return { ok: false, source: SOURCE, error: "test 需为 1–4" };
  const r = await get("t" + t + "-listening.html");
  if (!r.ok) return { ok: false, source: SOURCE, error: r.error };
  const js = dataScript(r.body);

  const parts = looseParse(literal(js, "PARTS")) || {};
  const titles = looseParse(literal(js, "TITLES")) || {};
  const tracks = looseParse(literal(js, "audioTracks")) || {};
  const answers = looseParse(literal(js, "correctAnswers")) || {};
  const multi = looseParse(literal(js, "multiCorrect")) || {};
  const scripts = looseParse(literal(js, "TRANSCRIPTS")) || {};

  const qs = [];
  for (const [sec, html] of Object.entries(parts)) {
    const flat = String(html);
    for (const m of flat.matchAll(/data-q=["'](\d+)["']/g)) {
      const n = Number(m[1]);
      if (qs.some((q) => q.number === n)) continue;
      const before = flat.slice(Math.max(0, m.index - 320), m.index);
      qs.push({ number: n, section: Number(sec), type: "gap", prompt: toText(before).replace(/\s+/g, " ").trim().slice(-260) });
    }
  }
  qs.sort((a, b) => a.number - b.number);

  const key = Object.keys(answers).sort((a, b) => Number(a) - Number(b)).map((n) => {
    const v = answers[n];
    return { number: Number(n), answer: Array.isArray(v) ? v[0] : v, accept: Array.isArray(v) ? v : [v] };
  });
  for (const [n, m] of Object.entries(multi)) {
    if (!key.some((k) => k.number === Number(n))) {
      key.push({ number: Number(n), answer: (m.accept || []).join(""), accept: m.accept || [], inputs: m.inputs });
    }
  }
  key.sort((a, b) => a.number - b.number);

  const audio = Object.keys(tracks).sort((a, b) => a - b).map((k) => ({
    section: Number(k), url: RAW + tracks[k], cdn: CDN + tracks[k], type: "audio/mpeg",
  }));

  const transcript = Object.keys(scripts).sort((a, b) => a - b).map((k) => ({
    section: Number(k),
    title: titles[k] || null,
    lines: (scripts[k] || []).map((l) => ({ speaker: l.sp || null, text: l.h || "", time: l.t ?? null })),
  }));

  return {
    ok: true, source: SOURCE, book: 21, test, skill: "listening",
    via: r.via, title: "Cambridge IELTS 21 Test " + test + " Listening",
    sections: Object.keys(parts).sort((a, b) => a - b).map((k) => ({ section: Number(k), title: titles[k] || null })),
    questions: qs, answer_key: key, audio, transcript,
    counts: {
      sections: Object.keys(parts).length,
      questions: qs.length,
      answers: key.length,
      audio: audio.length,
      transcript_sections: transcript.length,
      transcript_lines: transcript.reduce((n, s) => n + s.lines.length, 0),
    },
  };
}

/** 听力索引 */
export async function listeningIndex() {
  const tests = [];
  for (const t of TESTS) {
    const r = await listening(t);
    if (!r.ok) { tests.push({ test: t, ok: false, error: r.error }); continue; }
    tests.push({ test: t, ok: true, sections: r.sections.map((s) => s.title), answers: r.counts.answers, audio: r.counts.audio, transcript_lines: r.counts.transcript_lines });
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
