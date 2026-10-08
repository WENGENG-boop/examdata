/**
 * ito.mjs — ieltstrainingonline.com 适配器（第二听力原文源）
 *
 * 该站是 WordPress，每套听力有两类页：
 *   Practice Cam N Listening Test MM ... with answer and audioscripts  (题目 + 答案 + 原文)
 *   Audioscripts Cam N Listening Test MM                               (仅原文)
 * 实测覆盖剑10–21（含剑21），是 practicepteonline 之外的独立交叉源。
 * 注意：部分帖子的 Part 结尾以 "…" 截断（源侧行为，抽查 10-1/20-2 原始 post 确认，非解析问题）。
 */
// 注意：该站的听力内容是 **posts**（不是 pages），slug 查询必须走 /posts
const WP = "https://ieltstrainingonline.com/wp-json/wp/v2/posts";
export const SOURCE = "ieltstrainingonline.com";
export const COVERS = { listening: [10, 21] };

async function req(url, { retries = 3 } = {}) {
  let last = "";
  for (let i = 0; i < retries; i++) {
    try {
      const r = await fetch(url, { headers: { "user-agent": "Mozilla/5.0", accept: "application/json" }, signal: AbortSignal.timeout(30000) });
      if (r.ok) return { ok: true, body: await r.json() };
      // 404 = 该 slug 不存在，重试无意义（省请求、避免无谓负载）
      if (r.status === 404) return { ok: false, error: "HTTP 404" };
      last = "HTTP " + r.status;
    } catch (e) { last = String((e && e.message) || e); }
    if (i < retries - 1) await new Promise((r) => setTimeout(r, 1200 * (i + 1)));
  }
  return { ok: false, error: last };
}

function toText(h) {
  return String(h || "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|li|h\d)>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&#8217;|&rsquo;/g, "'")
    .replace(/&quot;|&ldquo;|&rdquo;/g, '"').replace(/&#(\d+);/g, (_, d) => String.fromCharCode(+d))
    .replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim();
}

/** 按 slug 取页面 */
async function bySlug(slug) {
  const r = await req(WP + "?slug=" + encodeURIComponent(slug) + "&_fields=id,title,slug,content");
  if (!r.ok) return null;
  const p = Array.isArray(r.body) ? r.body[0] : r.body;
  return p && p.id ? p : null;
}

/** 试多种 slug 命名（该站历史命名不统一） */
async function trySlugs(candidates) {
  for (const s of candidates) {
    const p = await bySlug(s);
    if (p) return { page: p, slug: s };
  }
  return null;
}

/** 该套听力的 slug 候选（不同册的命名规则不一样） */
function scriptSlugs(book, test) {
  const b2 = String(book).padStart(2, "0");
  const b3 = String(book).padStart(3, "0");
  const t = String(test).padStart(2, "0");
  const t1 = String(test);
  return [
    "audioscripts-cam-" + book + "-listening-test-" + t,
    "audioscripts-cam-" + book + "-listening-test-" + t1,
    "audioscripts-cambridge-ielts-" + b3 + "-listening-test-" + t,
    "audioscripts-cambridge-ielts-" + b2 + "-listening-test-" + t,
    "audio-script-cambridge-ielts-" + book + "-listening-test-" + t,
    "transcript-cambridge-ielts-" + book + "-listening-test-" + t,
  ];
}

function practiceSlugs(book, test) {
  const t = String(test).padStart(2, "0");
  return [
    "practice-cam-" + book + "-listening-test-" + t + "-with-answer-and-audioscripts",
    "practice-cam-" + book + "-listening-test-" + t,
  ];
}

/** 听力原文（剑10–21） */
export async function listeningScript(book, test) {
  const hit = await trySlugs(scriptSlugs(book, test));
  if (!hit) return { ok: false, source: SOURCE, error: "no script page" };
  const raw = toText(hit.page.content?.rendered || "");
  // 该页结构：PART 1..4 原文 → "Answer Cam N Listening Test MM" → 答案表
  // 因此从 "Answer" 处截断，答案表交给 listeningTest()
  // 答案表标题形如 "Answer Cam 20 Listening Test 01"（站点偶尔写错册号，故只认 "Answer" 词本身）
  const ai = raw.search(/\bAnswer\s+Cam\b|\bAnswer\s*\n|\bAnswers?\s*:\s*\n/i);
  const text = ai > 200 ? raw.slice(0, ai) : raw;
  // 按 PART / SECTION 切分（只认行首的大写标题，避免匹配 "part1.MP3" 之类）
  const sections = {};
  // 先把正文按 "PART N" / "SECTION N" 标题切成块（标题可能被空行和空格包围）
  const marks = [...text.matchAll(/(?:PART|SECTION)\s*([1-4])\b/gi)]
    .filter((m) => {
      // 排除 part1.MP3 这类音频文件名里的误匹配
      const around = text.slice(Math.max(0, m.index - 12), m.index + m[0].length + 12);
      return !/\.(mp3|MP3)/.test(around) && !/\/|_/.test(around.slice(0, 12));
    });
  for (let i = 0; i < marks.length; i++) {
    const n = Number(marks[i][1]);
    const from = marks[i].index + marks[i][0].length;
    const to = i + 1 < marks.length ? marks[i + 1].index : text.length;
    let body = text.slice(from, to);
    // 去掉广告残留与音频直链
    // 注意：不能写 /^[\s\S]*?Advertisements[\s\S]*?\n/ —— 当正文里没有 Advertisements 时，
    // [\s\S]*? 仍会跨行匹配到行尾，把整段正文删光。
    body = body.split("\n")
      .filter((line) => {
        const t = line.trim();
        if (!t) return false;
        if (/^https?:\S+$/i.test(t)) return false;                  // 音频直链
        if (/document\.createElement/.test(t)) return false;         // 播放器脚本
        if (/\(adsbygoogle/.test(t)) return false;                   // 广告脚本
        if (/^Advertisements$/i.test(t)) return false;                // 广告标题
        if (/^(Cam|Cambridge)\s*\d+\s*Listening/i.test(t)) return false; // 相关文章链接
        return true;
      })
      .join("\n")
      .replace(/^\s*\n+/, "")
      .trim();
    if (body.length > 100 && !sections["section" + n]) sections["section" + n] = body;
  }
  if (!Object.keys(sections).length && text.length > 400) sections.section1 = text;
  return {
    ok: true, source: SOURCE, book, test, slug: hit.slug, title: toText(hit.page.title?.rendered || ""),
    sections, section_count: Object.keys(sections).length, bytes: text.length, text,
  };
}

/** 听力题目 + 答案（剑10–21） */
export async function listeningTest(book, test) {
  const hit = await trySlugs(practiceSlugs(book, test));
  if (!hit) return { ok: false, source: SOURCE, error: "no practice page" };
  const html = hit.page.content?.rendered || "";
  const text = toText(html);

  // 答案表在页面末尾，形如 "Part 1 | 1 10/ten | 2 weather | ..."
  const ai = text.search(/\bAnswers?\s+(?:Cam|Cambridge|IELTS)/i);
  const answerText = ai >= 0 ? text.slice(ai) : text;
  const key = [];
  const seen = new Set();
  for (const m of answerText.matchAll(/(\d{1,2})\s*&?\s*(\d{1,2})?\s*([A-Za-z0-9\/\$£,\.\-\(\)' ]{1,60})/g)) {
    const n = Number(m[1]);
    if (!(n >= 1 && n <= 40) || seen.has(n)) continue;
    const v = (m[3] || "").trim().replace(/\s+/g, " ");
    if (!v || /^(Part|Answer|Cam)/i.test(v)) continue;
    seen.add(n);
    key.push({ number: n, answer: v, paired: m[2] ? Number(m[2]) : null });
  }
  key.sort((a, b) => a.number - b.number);

  return {
    ok: true, source: SOURCE, book, test, slug: hit.slug, title: toText(hit.page.title?.rendered || ""),
    url: "https://ieltstrainingonline.com/" + hit.slug + "/",
    answer_key: key, answer_count: key.length, text,
  };
}

/** 覆盖自检（并发 3，控制对源站负载；总请求数与串行一致） */
export async function coverage() {
  const jobs = [];
  for (let b = 10; b <= 21; b++) for (let t = 1; t <= 4; t++) jobs.push([b, t]);
  const results = new Map();
  let cursor = 0;
  const workers = Array.from({ length: 3 }, async () => {
    while (cursor < jobs.length) {
      const [b, t] = jobs[cursor++];
      const s = await listeningScript(b, t);
      results.set(b + "-" + t, { test: t, ok: s.ok, sections: s.section_count || 0, bytes: s.bytes || 0 });
    }
  });
  await Promise.all(workers);
  const books = {};
  for (let b = 10; b <= 21; b++) {
    const tests = [];
    for (let t = 1; t <= 4; t++) tests.push(results.get(b + "-" + t) || { test: t, ok: false, sections: 0, bytes: 0 });
    books[b] = { scripts: tests.filter((x) => x.ok).length, tests };
  }
  const total = Object.values(books).reduce((n, x) => n + x.scripts, 0);
  return { ok: total > 0, source: SOURCE, covers: COVERS, total_scripts: total, books };
}