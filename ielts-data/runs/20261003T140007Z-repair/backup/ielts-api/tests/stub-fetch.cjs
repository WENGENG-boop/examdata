/**
 * stub-fetch.cjs — 测试专用 fetch 打桩（通过 NODE_OPTIONS=--require 预加载到子进程）
 *
 * 模式（env STUB_FETCH_MODE）:
 *   throw（默认）: 任何 fetch 立即抛错 —— 用于断言「非法参数不产生任何网络请求」
 *   serve        : 返回自洽的假 LFS 指针 + 假 PDF 流 —— 用于验证选册逻辑与退出码
 * 退出时把 {count, urls, code} 写入 STUB_FETCH_LOG 指定的文件。
 */
const fs = require("node:fs");
const crypto = require("node:crypto");

const mode = process.env.STUB_FETCH_MODE || "throw";
const calls = [];

const BODY = Buffer.from("%PDF-1.4\n% stub-fetch test fixture\n" + "x".repeat(2048) + "\n%%EOF\n");
const OID = crypto.createHash("sha256").update(BODY).digest("hex");
const POINTER = "version https://git-lfs.github.com/spec/v1\noid sha256:" + OID + "\nsize " + BODY.length + "\n";

globalThis.fetch = async (url) => {
  calls.push(String(url));
  if (mode === "serve") {
    if (String(url).includes("media.githubusercontent.com")) {
      return new Response(BODY, { status: 200, headers: { "content-type": "application/pdf" } });
    }
    return new Response(POINTER, { status: 200, headers: { "content-type": "text/plain" } });
  }
  throw new Error("stub-fetch: network disabled");
};

process.on("exit", (code) => {
  const log = process.env.STUB_FETCH_LOG;
  if (!log) return;
  try { fs.writeFileSync(log, JSON.stringify({ count: calls.length, urls: calls, code })); } catch {}
});
