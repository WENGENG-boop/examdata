#!/usr/bin/env node
/**
 * verify-pdfs.mjs — 剑1–20 真题 PDF（剑20 为 Test1 分册）的 LFS 字节级回归验证（零依赖）
 *
 * 对每本书：
 *   1. 从 raw.githubusercontent.com 拉 Git LFS 指针（~130 字节），解析 oid sha256 + size
 *   2. 从 media.githubusercontent.com 流式下载真实文件，边下边算 SHA256（不落盘）
 *   3. 比对：sha256 === oid、字节数 === size、首字节为 %PDF-
 *
 * 用法:
 *   node verify-pdfs.mjs                # 全量 20 本
 *   node verify-pdfs.mjs 1 20           # 只验证指定册（非法册号/未知参数退出 2，不发任何请求）
 *   node verify-pdfs.mjs --jobs 3       # 并发数（仅 1..64 整数，默认 3）
 *   node verify-pdfs.mjs --json         # 输出机器可读 JSON
 *
 * 退出码: 0 全部通过 / 1 有失败 / 2 参数或环境错误（在任何网络请求之前）
 */
import crypto from "node:crypto";
import { pathToFileURL } from "node:url";
import * as lfs from "./lfs.mjs";

const ALL_BOOKS = Object.keys(lfs.BOOK_PDF).map(Number).sort((a, b) => a - b);

function parsePointer(text) {
  const oid = (text.match(/oid sha256:([0-9a-f]{64})/) || [])[1] || null;
  const size = Number((text.match(/(?:^|\n)size (\d+)/) || [])[1]) || null;
  return { oid, size, isPointer: /^version https:\/\/git-lfs/.test(text) };
}

async function withRetry(fn, { retries = 3, delay = 900 } = {}) {
  let last;
  for (let i = 0; i < retries; i++) {
    try {
      const r = await fn();
      if (r && r.ok !== false) return r;
      last = r;
    } catch (e) { last = { ok: false, error: String((e && e.message) || e) }; }
    if (i < retries - 1) await new Promise((s) => setTimeout(s, delay * (i + 1)));
  }
  return last;
}

/** 拉 LFS 指针：raw 主通道，jsDelivr 回落（jsDelivr 对 LFS 文件同样返回指针） */
async function fetchPointer(path) {
  const urls = [lfs.url(path, { via: "raw" }), lfs.url(path, { via: "cdn" })];
  let lastErr = "";
  for (const u of urls) {
    const r = await withRetry(async () => {
      const res = await fetch(u, { headers: { "user-agent": "Mozilla/5.0" }, signal: AbortSignal.timeout(45000) });
      if (!res.ok) return { ok: false, error: "HTTP " + res.status, url: u };
      return { ok: true, body: await res.text(), url: u };
    });
    if (r.ok) {
      const p = parsePointer(r.body);
      if (p.oid && p.size) return { ...p, url: r.url };
      lastErr = "not an LFS pointer (" + r.body.length + " bytes)";
    } else lastErr = r.error || "fetch failed";
  }
  return { oid: null, size: null, isPointer: false, error: lastErr };
}

/** 流式下载 + SHA256（不落盘）；返回 { ok, bytes, sha256, isPdf, contentType, ms } */
async function streamHash(url, { timeout = 600000 } = {}) {
  const t0 = Date.now();
  const res = await fetch(url, { headers: { "user-agent": "Mozilla/5.0" }, signal: AbortSignal.timeout(timeout) });
  if (!res.ok) return { ok: false, status: res.status, error: "HTTP " + res.status, ms: Date.now() - t0 };
  const hash = crypto.createHash("sha256");
  let bytes = 0;
  let head = null;
  const reader = res.body.getReader();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    if (!head && value && value.length) head = value.slice(0, 8);
    hash.update(value);
    bytes += value.length;
  }
  return {
    ok: true, status: res.status, bytes, sha256: hash.digest("hex"),
    isPdf: !!(head && String.fromCharCode(...head.slice(0, 5)) === "%PDF-"),
    contentType: res.headers.get("content-type"),
    contentLength: Number(res.headers.get("content-length")) || null,
    ms: Date.now() - t0,
  };
}

async function verifyBook(book) {
  const path = lfs.BOOK_PDF[book];
  if (!path) return { book, ok: false, error: "book " + book + " not in 剑1-20" };
  const ptr = await fetchPointer(path);
  if (!ptr.oid) return { book, ok: false, error: "pointer: " + (ptr.error || "parse failed"), path };
  const media = lfs.url(path, { via: "media" });
  const dl = await withRetry(() => streamHash(media), { retries: 3, delay: 1500 });
  if (!dl.ok) return { book, ok: false, error: "download: " + dl.error, path, oid: ptr.oid, size: ptr.size, url: media };
  const matchOid = dl.sha256 === ptr.oid;
  const matchSize = dl.bytes === ptr.size;
  const ok = matchOid && matchSize && dl.isPdf;
  return {
    book, ok, path,
    oid: ptr.oid, size: ptr.size,
    bytes: dl.bytes, sha256: dl.sha256,
    match_oid: matchOid, match_size: matchSize, is_pdf: dl.isPdf,
    content_type: dl.contentType, content_length: dl.contentLength,
    ms: dl.ms, url: media,
  };
}

async function pool(items, jobs, fn) {
  const out = new Array(items.length);
  let next = 0;
  const workers = Array.from({ length: Math.max(1, Math.min(jobs, items.length)) }, async () => {
    for (;;) {
      const i = next++;
      if (i >= items.length) return;
      out[i] = await fn(items[i]);
    }
  });
  await Promise.all(workers);
  return out;
}

const fmt = (n) => n === null || n === undefined ? "-" : Number(n).toLocaleString("en-US");
const mb = (n) => (n / 1048576).toFixed(1);
const short = (s, n = 12) => s ? s.slice(0, n) + "…" : "-";

/** 核心入口（供 CLI / 其他脚本复用）：非法非空 books 直接抛错（在任何网络请求之前）；空/未传才默认全量 */
export async function verifyPdfs({ books, jobs = 3, onResult } = {}) {
  if (books !== undefined && books !== null) {
    if (!Array.isArray(books)) throw new Error("非法册号: books 必须是数组");
    const invalid = books.filter((b) => !Number.isInteger(b) || !lfs.BOOK_PDF[b]);
    if (invalid.length) throw new Error("非法册号: " + invalid.join(","));
  }
  const list = (books && books.length ? books : ALL_BOOKS).filter((b) => lfs.BOOK_PDF[b]);
  const t0 = Date.now();
  const results = await pool(list, jobs, async (b) => {
    const r = await verifyBook(b);
    if (onResult) onResult(r);
    return r;
  });
  const passed = results.filter((r) => r.ok).length;
  const totalBytes = results.reduce((n, r) => n + (r.bytes || 0), 0);
  return {
    ok: passed === results.length && results.length > 0,
    source: "BaBaLiBoo/IELTS-Resources",
    checked: results.length, passed, failed: results.length - passed,
    total_bytes: totalBytes, total_mb: +(totalBytes / 1048576).toFixed(1),
    seconds: +((Date.now() - t0) / 1000).toFixed(1),
    books: Object.fromEntries(results.map((r) => [r.book, r])),
  };
}

/** 解析 CLI 参数：非法册号 / 未知参数 / --jobs 非 1..64 整数一律进 bad；调用方须在任何网络请求前退出 2 */
export function parseArgs(args) {
  let jsonOut = false;
  let jobs = 3;
  let jobsSeen = false;
  const books = [];
  const bad = [];
  for (let i = 0; i < args.length; i++) {
    const x = args[i];
    if (x === "--json") { jsonOut = true; continue; }
    if (x === "--jobs") {
      const v = args[++i];
      if (jobsSeen) {
        bad.push("--jobs");
        if (v !== undefined) bad.push(v);
        continue;
      }
      jobsSeen = true;
      if (v === undefined || !/^\d+$/.test(v) || Number(v) < 1 || Number(v) > 64) {
        bad.push("--jobs");
        if (v !== undefined) bad.push(v);
        continue;
      }
      jobs = Number(v);
      continue;
    }
    if (/^\d+$/.test(x)) {
      const b = Number(x);
      if (!lfs.BOOK_PDF[b]) { bad.push(x); continue; }
      if (!books.includes(b)) books.push(b);
      continue;
    }
    bad.push(x);
  }
  return { jsonOut, jobs, books, bad };
}

/* ------------------------------ 独立运行入口 ------------------------------ */
const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  const { jsonOut, jobs, books, bad } = parseArgs(process.argv.slice(2));
  if (bad.length) { console.error("参数错误:", bad.join(" ")); process.exit(2); }

  if (!jsonOut) console.log("剑1–20 PDF LFS 回归验证（" + (books.length ? books.join(",") + " 册" : "全量") + ", jobs=" + jobs + "）");
  const summary = await verifyPdfs({
    books,
    jobs,
    onResult: jsonOut ? undefined : (r) => {
      const mark = r.ok ? "✓ PASS" : "✗ FAIL";
      const speed = r.ms ? "  " + (r.bytes / 1048576 / (r.ms / 1000)).toFixed(2) + " MB/s" : "";
      console.log(
        "  book " + String(r.book).padStart(2) + ": " + fmt(r.bytes) + " B  sha " + short(r.sha256) +
        "  oid " + short(r.oid) + "  " + (r.is_pdf ? "PDF" : "非PDF") + "  " + mark +
        (r.error ? "  [" + r.error + "]" : "") + speed
      );
    },
  });
  if (jsonOut) {
    console.log(JSON.stringify(summary, null, 2));
  } else {
    console.log("—".repeat(60));
    console.log(
      "总计 " + summary.checked + " 册: 通过 " + summary.passed + " / 失败 " + summary.failed +
      "  下载 " + fmt(summary.total_bytes) + " B (" + summary.total_mb + " MiB)  用时 " + summary.seconds + "s"
    );
  }
  process.exit(summary.ok ? 0 : 1);
}
