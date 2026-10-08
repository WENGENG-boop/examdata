/** util.mjs — 共享工具：缓存、HTTP、参数解析、信封。零 npm 依赖。 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const LIBS = path.dirname(fileURLToPath(import.meta.url));
export const ROOT = path.dirname(LIBS);
export const DATA_DIR = path.join(ROOT, 'data');
export const CACHE_DIR = path.join(ROOT, '.data', 'cache');

export function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

export function readJson(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

export function writeJson(p, obj) {
  ensureDir(path.dirname(p));
  fs.writeFileSync(p, JSON.stringify(obj, null, 1));
}

export function readJsonIfExists(p) {
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8'));
  } catch {
    return null;
  }
}

export function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

export function ok(obj) {
  return { ok: true, board: 'toefl', ...obj };
}

export function fail(error, extra = {}) {
  return { ok: false, board: 'toefl', error: String(error && error.message || error), ...extra };
}

export function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = String(argv[i]);
    const m = /^--([A-Za-z0-9_-]+)(?:=(.*))?$/.exec(a);
    if (m) {
      out[m[1]] = m[2] === undefined ? true : m[2];
    } else {
      out._.push(a);
    }
  }
  return out;
}

export function asInt(v, dflt = undefined) {
  if (v === undefined || v === null || v === '') return dflt;
  const n = Number(v);
  return Number.isFinite(n) ? Math.trunc(n) : dflt;
}

export async function httpGet(url, { timeoutMs = 20000, headers = {}, validateRedirect = null, maxRedirects = 5 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const reqHeaders = { 'user-agent': 'toefl-api-research/1.0 (educational aggregation)', ...headers };
  try {
    if (typeof validateRedirect !== 'function') {
      const res = await fetch(url, {
        redirect: 'follow',
        signal: controller.signal,
        headers: reqHeaders,
      });
      const body = await res.text();
      return { status: res.status, body, url: res.url };
    }
    // 手动跟随重定向：每一跳都先校验目标，校验失败/超过 maxRedirects 即报错。
    let current = String(url);
    for (let hop = 0; hop <= maxRedirects; hop += 1) {
      const res = await fetch(current, { redirect: 'manual', signal: controller.signal, headers: reqHeaders });
      if (res.status >= 300 && res.status < 400) {
        let loc = null;
        try {
          loc = res.headers.get('location');
        } catch {
          loc = null;
        }
        try {
          if (res.body) await res.body.cancel();
        } catch {
          /* 丢弃重定向响应体 */
        }
        if (!loc) throw new Error(`重定向缺少 Location（HTTP ${res.status}）`);
        let next;
        try {
          next = new URL(loc, current).href;
        } catch {
          throw new Error(`重定向 Location 非法：${loc}`);
        }
        const why = validateRedirect(next);
        if (why) throw new Error(`重定向目标被拒绝（${why}）：${next}`);
        current = next;
        continue;
      }
      const body = await res.text();
      return { status: res.status, body, url: res.url || current };
    }
    throw new Error(`重定向超过 ${maxRedirects} 跳`);
  } finally {
    clearTimeout(timer);
  }
}

export function htmlToText(html) {
  return String(html)
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/(p|div|li|h\d)>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/[ \t\u00a0]+/g, ' ')
    .replace(/\n{2,}/g, '\n')
    .trim();
}

export function normalize(s) {
  return String(s).replace(/\s+/g, ' ').trim();
}

export function snippet(text, idx, len = 120) {
  const start = Math.max(0, idx - Math.floor(len / 2));
  const end = Math.min(text.length, start + len);
  return (start > 0 ? '…' : '') + text.slice(start, end).replace(/\s+/g, ' ') + (end < text.length ? '…' : '');
}

export function countOccurrences(haystack, needle) {
  const h = haystack.toLowerCase();
  const n = needle.toLowerCase();
  let count = 0;
  let idx = h.indexOf(n);
  const first = idx;
  while (idx !== -1) {
    count += 1;
    idx = h.indexOf(n, idx + n.length);
  }
  return { count, first };
}
