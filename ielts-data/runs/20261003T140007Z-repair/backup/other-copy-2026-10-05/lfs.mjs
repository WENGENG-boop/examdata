/**
 * lfs.mjs — BaBaLiBoo/IELTS-Resources 源（Git LFS 镜像）
 *
 * ★★ 这是唯一同时提供 **剑1–剑20 全部整本 PDF** 的源（实测 20/20 均为真实 PDF）。
 *    另附「剑4/5/6 精讲合辑」与剑7–20 精讲解析 PDF。
 *
 * ⚠️ 该仓库所有大文件走 Git LFS：
 *   raw.githubusercontent.com        → 只返回 ~130 字节 LFS 指针
 *   media.githubusercontent.com/media → 真实文件（本模块默认通道）
 */

const OWNER = "BaBaLiBoo";
const REPO = "IELTS-Resources";
const BRANCH = "main";

const RAW = "https://raw.githubusercontent.com/" + OWNER + "/" + REPO + "/" + BRANCH + "/";
const MEDIA = "https://media.githubusercontent.com/media/" + OWNER + "/" + REPO + "/" + BRANCH + "/";
const CDN = "https://cdn.jsdelivr.net/gh/" + OWNER + "/" + REPO + "@" + BRANCH + "/";

const encPath = (p) => p.split("/").map(encodeURIComponent).join("/");

const D = "【真题】剑桥雅思真题A类/剑1-20/";
const J = "【精讲解析】剑桥雅思真题精讲pdf/";

/** 剑1–20 整本真题 PDF（路径全部经实测确认为真实 PDF） */
export const BOOK_PDF = {
  1:  D + "【1】剑桥雅思真题1.pdf",
  2:  D + "【2】剑桥雅思真题2.pdf",
  3:  D + "【3】剑桥雅思真题3.pdf",
  4:  D + "【4】剑桥雅思真题4.pdf",
  5:  D + "【5】剑桥雅思真题5.pdf",
  6:  D + "【6】剑桥雅思真题6.pdf",
  7:  D + "【7】剑桥雅思真题7.pdf",
  8:  D + "【8】剑桥雅思真题8.pdf",
  9:  D + "【9】剑桥雅思真题9.pdf",
  10: D + "【10】剑桥雅思真题10.pdf",
  11: D + "【11】剑桥雅思真题11.pdf",
  12: D + "【12】剑桥雅思真题12.pdf",
  13: D + "【13】剑桥雅思真题13.pdf",
  14: D + "【14】剑桥雅思真题14.pdf",
  15: D + "剑桥雅思官方真题集15 .pdf",        // 注意文件名尾部有空格
  16: D + "剑桥雅思官方真题集16 （学术类）.pdf",
  17: D + "剑桥雅思17（A类）.pdf",
  18: D + "剑雅真题18.pdf",
  19: D + "《剑19》真题A+G类/剑19完整版PDF（A类+G类）/剑19（A类）.pdf",
  20: D + "剑桥20真题（抢先版）/剑20-Test1.pdf",   // 剑20 为 4 个分册，见 BOOK20_TESTS
};

/** 剑9 备选版本（更小的 10.2MB 版，若主版本不可用可回落） */
export const BOOK_PDF_ALT = {
  9: D + "【9】剑桥雅思真题9（1）.pdf",
};

/** 剑20 抢先版 4 个分册 */
export const BOOK20_TESTS = {
  test1: D + "剑桥20真题（抢先版）/剑20-Test1.pdf",
  test2: D + "剑桥20真题（抢先版）/剑20-Test2.pdf",
  test3: D + "剑桥20真题（抢先版）/剑20Test3.pdf",
  test4: D + "剑桥20真题（抢先版）/剑20-Test4.pdf",
};

/** 剑20 听力音频（仅 T1/T2/T3 存在） */
export const BOOK20_AUDIO = {
  t1s1: D + "剑桥20真题（抢先版）/剑20 听力音频 T1/T1S1.mp3",
  t1s2: D + "剑桥20真题（抢先版）/剑20 听力音频 T1/T1S2.mp3",
  t1s3: D + "剑桥20真题（抢先版）/剑20 听力音频 T1/T1S3.mp3",
  t1s4: D + "剑桥20真题（抢先版）/剑20 听力音频 T1/T1S4.mp3",
  t2s3: D + "剑桥20真题（抢先版）/剑20 听力音频T2/T2S3.mp3",
  t3s1: D + "剑桥20真题（抢先版）/剑20 听力音频T3/T3S1.mp3",
};

/** 精讲解析 PDF（剑7–20 + 4/5/6 合辑） */
export const EXPLAIN_PDF = {
  7:  J + "【7】剑桥雅思真题精讲7.pdf",
  8:  J + "【8】剑桥雅思真题精讲8.pdf",
  9:  J + "【9】剑桥雅思真题精讲9.pdf",
  10: J + "【10】剑桥雅思真题精讲10.pdf",
  11: J + "【11】剑桥雅思真题精讲11.pdf",
  12: J + "【12】剑桥雅思真题精讲12.pdf",
  13: J + "【13】剑桥雅思真题精讲13.pdf",
  14: J + "【14】剑桥雅思真题精讲14.pdf",
  15: J + "【15】剑桥雅思真题精讲15.pdf",
  16: J + "剑16精讲.pdf",
  17: J + "剑桥雅思17 A类精讲.pdf",
  18: J + "剑18-雅思真题精讲.pdf",
  19: J + "剑19解析（A类）.pdf",
  20: J + "剑20真题精讲.pdf",
  "15b": J + "剑桥雅思十五真题解析2.pdf",
  "456": J + "合【456合辑】剑桥雅思真题精讲456合辑.pdf",
};

/** 其他资料 */
export const EXTRA = {
  speaking_bank_2026: "2026年1-4月最新雅思口语题库-0130.pdf",
  writing_band: "雅思写作评分标准.pdf",
  speaking_band: "雅思口语评分标准.pdf",
};

/** 生成直链（默认 LFS media 通道） */
export function url(path, { via = "media" } = {}) {
  const base = via === "raw" ? RAW : via === "cdn" ? CDN : MEDIA;
  return base + encPath(path);
}

/** 探测真实性：区分「真实文件」与「LFS 指针」，带重试 */
export async function probe(path, { via = "media", retries = 3 } = {}) {
  if (typeof path !== "string" || !path) return { ok: false, via, error: "path required" };
  const u = url(path, { via });
  let lastErr;
  for (let i = 0; i < retries; i++) {
    try {
      const r = await fetch(u, { headers: { "user-agent": "Mozilla/5.0", range: "bytes=0-300" }, redirect: "follow", signal: AbortSignal.timeout(45000) });
      const buf = new Uint8Array(await r.arrayBuffer());
      const head = new TextDecoder().decode(buf.slice(0, 80));
      const total = Number(((r.headers.get("content-range") || "").match(/\/(\d+)$/) || [])[1]) || null;
      return {
        ok: (r.ok || r.status === 206) && head.startsWith("%PDF"),
        status: r.status, url: u, via,
        bytes: total,
        mb: total ? +(total / 1048576).toFixed(1) : null,
        isPdf: head.startsWith("%PDF"),
        isLfsPointer: head.includes("git-lfs"),
        contentType: r.headers.get("content-type"),
      };
    } catch (e) { lastErr = e; if (i < retries - 1) await new Promise(s => setTimeout(s, 800 * (i + 1))); }
  }
  return { ok: false, url: u, via, error: String(lastErr && lastErr.message || lastErr) };
}

/** 整本真题 PDF 直链（剑1–20），主路径失败自动回落备用路径 */
export async function bookPdf(book, { verify = true } = {}) {
  const path = BOOK_PDF[book];
  if (!path) return { ok: false, source: "BaBaLiBoo/IELTS-Resources", book, error: "book " + book + " not in 剑1-20" };
  const u = url(path);
  if (!verify) return { ok: true, source: "BaBaLiBoo/IELTS-Resources", book, path, url: u, note: "未校验" };

  const p = await probe(path);
  if (p.ok) {
    return { ok: true, source: "BaBaLiBoo/IELTS-Resources", book, path, url: p.url, bytes: p.bytes, mb: p.mb, isPdf: true, note: "真实 PDF" };
  }
  // 回落备用路径
  const alt = BOOK_PDF_ALT[book];
  if (alt) {
    const q = await probe(alt);
    if (q.ok) return { ok: true, source: "BaBaLiBoo/IELTS-Resources", book, path: alt, url: q.url, bytes: q.bytes, mb: q.mb, isPdf: true, note: "真实 PDF（备用路径）" };
  }
  return { ok: false, source: "BaBaLiBoo/IELTS-Resources", book, path, url: u, isLfsPointer: p.isLfsPointer, error: p.error || "probe failed" };
}

/** 精讲解析 PDF */
export async function explainPdf(book) {
  const path = EXPLAIN_PDF[book];
  if (!path) return { ok: false, book, error: "no explain pdf for " + book };
  const p = await probe(path);
  return { ok: p.ok, source: "BaBaLiBoo/IELTS-Resources", book, kind: "explain", path, url: p.url, mb: p.mb, isPdf: p.isPdf };
}

/** 剑20 全套：4 个 Test PDF + 听力音频 */
export async function book20Set() {
  const out = { source: "BaBaLiBoo/IELTS-Resources", book: 20, pdfs: {}, audio: {} };
  for (const [k, path] of Object.entries(BOOK20_TESTS)) {
    const p = await probe(path);
    out.pdfs[k] = { ok: p.ok, url: p.url, bytes: p.bytes, mb: p.mb, isPdf: p.isPdf };
  }
  for (const [k, path] of Object.entries(BOOK20_AUDIO)) {
    const u = url(path);
    try {
      const r = await fetch(u, { headers: { "user-agent": "Mozilla/5.0", range: "bytes=0-100" }, signal: AbortSignal.timeout(30000) });
      out.audio[k] = { ok: r.status === 206 || r.ok, url: u, contentType: r.headers.get("content-type") };
    } catch (e) { out.audio[k] = { ok: false, url: u, error: String(e).slice(0, 80) }; }
  }
  out.ok = Object.values(out.pdfs).some(x => x.ok);
  return out;
}

/** 覆盖矩阵：剑1–20 真题 PDF 可用性（可传 {quick:true} 只测状态不校验 magic） */
export async function coverage({ books, explain = false } = {}) {
  const list = books || Object.keys(BOOK_PDF).map(Number);
  const out = { ok: true, source: "BaBaLiBoo/IELTS-Resources", real_pdf: 0, total: list.length, books: {} };
  const results = await Promise.all(list.map(async (b) => [b, await bookPdf(b)]));
  for (const [b, r] of results) {
    out.books[b] = { ok: r.ok, mb: r.mb ?? null };
    if (r.ok) out.real_pdf++;
  }
  if (explain) {
    out.explain = {};
    for (const k of Object.keys(EXPLAIN_PDF)) {
      const e = await explainPdf(isNaN(Number(k)) ? k : Number(k));
      out.explain[k] = { ok: e.ok, mb: e.mb ?? null };
    }
  }
  return out;
}
