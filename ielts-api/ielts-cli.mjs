#!/usr/bin/env node
/** ielts-cli.mjs — 命令行入口
 *  用法:
 *    node ielts-cli.mjs reading 19 1 1
 *    node ielts-cli.mjs listening-qa 20 1
 *    node ielts-cli.mjs listening-script 20
 *    node ielts-cli.mjs listening-audio 20 1 2
 *    node ielts-cli.mjs reading-index
 *    node ielts-cli.mjs mini-list 1
 *    node ielts-cli.mjs mini-solution 1518 australian-artist-margaret-preston
 *    node ielts-cli.mjs aggregate 19 1
 *    node ielts-cli.mjs coverage
 *    node ielts-cli.mjs verify-pdfs 1 20   # 剑1–20 PDF LFS 字节级回归（SHA256 vs oid，全量约 642 MiB 下载）
 *    node ielts-cli.mjs serve 8787      # 起 HTTP 服务
 */
import * as api from "./ielts-api.mjs";
import fs from "node:fs";
import http from "node:http";

const [cmd, ...a] = process.argv.slice(2);
const n = (x, d) => (x === undefined ? d : Number(x));
const j = (o) => JSON.stringify(o, null, 2);
const parseV2Query = (args) => {
  const out = {};
  for (const arg of args) {
    const m = /^--([a-z_]+)=(.*)$/.exec(String(arg));
    if (m) out[m[1]] = m[2];
  }
  return out;
};

const routes = {
  "reading": () => api.reading(n(a[0], 19), n(a[1], 1), a[2] === undefined ? null : n(a[2])),
  "reading-enriched": () => api.readingEnriched(n(a[0], 19), n(a[1], 1), n(a[2], 1)),
  "reading-index": () => api.readingIndex(),
  "listening-script": () => api.listeningScript(n(a[0], 20)),
  "listening-audio": () => api.listeningAudio(n(a[0], 20), n(a[1], 1), n(a[2], 1)),
  "listening-qa": () => api.listeningQA(n(a[0], 20), n(a[1], 1)),
  "listening-segments": () => api.listeningSegments(n(a[0], 19), n(a[1], 1), n(a[2], 1)),
  "listening-index": () => api.listeningIndex(),
  "pdf": () => api.pdf(n(a[0], 18)),
  "mini-list": () => api.miniList(n(a[0], 1)),
  "mini-solution": () => api.miniSolution(n(a[0]), a[1]),
  "pte-book": () => api.pteBook(n(a[0], 20)),
  "pte-reading": () => api.pteReading(n(a[0], 20), n(a[1], 1)),
  "pte-listening": () => api.pteListening(n(a[0], 20), n(a[1], 1)),
  "pte-audio": () => api.pteAudio(n(a[0], 20), n(a[1], 1)),
  "pdf-lfs": () => api.pdfLfs(n(a[0], 20)),
  "book20-set": () => api.book20Set(),
  "explain-pdf": () => api.explainPdf(n(a[0], 20)),
  "ito-script": () => api.itoScript(n(a[0], 21), n(a[1], 1)),
  "ito-listening": () => api.itoListening(n(a[0], 21), n(a[1], 1)),
  "ito-coverage": () => api.itoCoverage(),
  "iprog-listening": () => api.iprogListening(n(a[0], 3), n(a[1], 2)),
  "iprog-coverage": () => api.iprogCoverage(),
  "pdf21": () => api.pdf21(),
  "zhan-index": () => api.zhanIndex(n(a[0], 21)),
  "zhan-reading": () => api.zhanReading(n(a[0], 21), n(a[1], 1), n(a[2], 1)),
  "zhan-coverage": () => api.zhanCoverage(),
  "cam21-reading": () => api.cam21Reading(n(a[0], 1)),
  "cam21-listening": () => api.cam21Listening(n(a[0], 1)),
  "cam21-audio": () => api.cam21Audio(n(a[0], 1), n(a[1], 1)),
  "cam21-full": () => api.cam21Full(n(a[0], 1)),
  "cam21-index": () => api.cam21Index(),
  "cam21-coverage": () => api.cam21Coverage(),
  "lfs-coverage": () => api.lfsCoverage(),
  "verify-pdfs": async () => {
    const m = await import("./verify-pdfs.mjs");
    const { jobs, books, bad } = m.parseArgs(a);
    if (bad.length) { console.error("参数错误:", bad.join(" ")); process.exit(2); }
    return m.verifyPdfs({ jobs, books, onResult: (r) => console.error("  book " + r.book + ": " + (r.ok ? "PASS " + r.bytes + "B" : "FAIL " + (r.error || ""))) });
  },
  "aggregate": () => api.aggregate({ book: n(a[0], 19), test: n(a[1], 1) }),
  "coverage": () => api.coverage(),
  // ---- v2 规范化 API（S13）：本地索引解析，零网络；schema ielts.v2/1 ----
  "info": () => api.v2Info(),
  "books-v2": () => api.v2Books(),
  "test-v2": () => api.v2Test(a[0], a[1], parseV2Query(a.slice(2))),
  "questions-v2": () => api.v2Questions(a[0], a[1], parseV2Query(a.slice(2))),
  "question-v2": () => api.v2Question(a[0]),
  "coverage-v2": () => api.v2Coverage(parseV2Query(a)),
  "asset-v2": () => api.v2Asset(a[0]),
};

if (cmd === "serve") {
  const port = n(a[0], 8787);
  const server = http.createServer(async (req, res) => {
    const u = new URL(req.url, "http://x");
    const p = u.pathname.split("/").filter(Boolean);
    const send = (code, o) => { res.writeHead(code, { "content-type": "application/json; charset=utf-8" }); res.end(j(o)); };
    const sendAsset = (id) => {
      const asset = api.v2Asset(id);
      if (!asset || asset.ok !== true) return send(404, asset || { ok: false, error: "asset not found" });
      let st;
      try { st = fs.statSync(asset.file_path); } catch { return send(404, { ok: false, error: "asset file missing on disk", id: asset.id, file_path: asset.file_path }); }
      const mime = asset.mime || "application/octet-stream";
      const m = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range || "");
      if (m && (m[1] || m[2])) {
        let start = m[1] ? Number(m[1]) : null;
        let end = m[2] ? Number(m[2]) : null;
        if (start === null) { start = Math.max(0, st.size - end); end = st.size - 1; }
        else if (end === null || end >= st.size) end = st.size - 1;
        if (start >= st.size || start > end) { res.writeHead(416, { "content-range": "bytes */" + st.size }); return res.end(); }
        res.writeHead(206, { "content-type": mime, "content-length": end - start + 1, "content-range": "bytes " + start + "-" + end + "/" + st.size, "accept-ranges": "bytes" });
        return fs.createReadStream(asset.file_path, { start, end }).pipe(res);
      }
      res.writeHead(200, { "content-type": mime, "content-length": st.size, "accept-ranges": "bytes" });
      return fs.createReadStream(asset.file_path).pipe(res);
    };
    try {
      const [r, b, t, pp] = p;
      // /api/reading/:book/:test[/:passage]  —— 第三段既支持路径也支持 ?passage=；缺省=整卷 3 篇
      if (r === "api" && b === "reading") {
        const passageRaw = u.searchParams.get("passage") ?? p[4];
        return send(200, api.reading(n(t, 19), n(pp, 1), passageRaw == null || passageRaw === "" ? null : Number(passageRaw)));
      }
      // /api/reading-enriched/:book/:test[/:passage] —— reader 源精读（剑1–19；网络源，非法身份不发请求）
      if (r === "api" && b === "reading-enriched") {
        const passageRaw = u.searchParams.get("passage") ?? p[4];
        return send(200, await api.readingEnriched(n(t, 19), n(pp, 1), n(passageRaw, 1)));
      }
      if (r === "api" && b === "listening-qa") return send(200, await api.listeningQA(n(t, 20), n(pp, 1)));
      if (r === "api" && b === "listening-script") return send(200, await api.listeningScript(n(t, 20)));
      // /api/listening-audio/:book/:test[/:part]
      if (r === "api" && b === "listening-audio") return send(200, api.listeningAudio(n(t, 20), n(pp, 1), n(u.searchParams.get("part") ?? p[4], 1)));
      // /api/listening-segments/:book/:test[/:part]
      if (r === "api" && b === "listening-segments") return send(200, await api.listeningSegments(n(t, 19), n(pp, 1), n(u.searchParams.get("part") ?? p[4], 1)));
      if (r === "api" && b === "reading-index") return send(200, await api.readingIndex());
      if (r === "api" && b === "listening-index") return send(200, await api.listeningIndex());
      if (r === "api" && b === "mini-list") return send(200, await api.miniList(n(t, 1)));
      if (r === "api" && b === "mini-solution") return send(200, await api.miniSolution(n(t), pp));
      if (r === "api" && b === "aggregate") return send(200, await api.aggregate({ book: n(t, 19), test: n(pp, 1) }));
      if (r === "api" && b === "coverage") return send(200, await api.coverage());
      if (r === "api" && b === "pte-reading") return send(200, await api.pteReading(n(t, 20), n(pp, 1)));
      if (r === "api" && b === "pte-listening") return send(200, await api.pteListening(n(t, 20), n(pp, 1)));
      if (r === "api" && b === "pte-audio") return send(200, await api.pteAudio(n(t, 20), n(pp, 1)));
      if (r === "api" && b === "pte-book") return send(200, await api.pteBook(n(t, 20)));
      if (r === "api" && b === "pdf-lfs") return send(200, await api.pdfLfs(n(t, 20)));
      if (r === "api" && b === "book20-set") return send(200, await api.book20Set());
      if (r === "api" && b === "explain-pdf") return send(200, await api.explainPdf(n(t, 20)));
      if (r === "api" && b === "lfs-coverage") return send(200, await api.lfsCoverage());
      if (r === "api" && b === "ito-script") return send(200, await api.itoScript(n(t, 21), n(pp, 1)));
      if (r === "api" && b === "ito-listening") return send(200, await api.itoListening(n(t, 21), n(pp, 1)));
      if (r === "api" && b === "ito-coverage") return send(200, await api.itoCoverage());
      if (r === "api" && b === "iprog-listening") return send(200, await api.iprogListening(n(t, 3), n(pp, 2)));
      if (r === "api" && b === "iprog-coverage") return send(200, await api.iprogCoverage());
      if (r === "api" && b === "cam21-reading") return send(200, await api.cam21Reading(n(t, 1)));
      if (r === "api" && b === "cam21-listening") return send(200, await api.cam21Listening(n(t, 1)));
      if (r === "api" && b === "cam21-audio") return send(200, await api.cam21Audio(n(t, 1), n(pp, 1)));
      if (r === "api" && b === "cam21-full") return send(200, await api.cam21Full(n(t, 1)));
      if (r === "api" && b === "cam21-index") return send(200, await api.cam21Index());
      if (r === "api" && b === "cam21-coverage") return send(200, await api.cam21Coverage());
      if (r === "api" && b === "pdf") return send(200, api.pdf(n(t, 18)));
      if (r === "api" && b === "pdf21") return send(200, await api.pdf21());
      if (r === "api" && b === "zhan-index") return send(200, await api.zhanIndex(n(t, 21)));
      // /api/zhan-reading/:book/:test/:passage
      if (r === "api" && b === "zhan-reading") return send(200, await api.zhanReading(n(t, 21), n(pp, 1), n(u.searchParams.get("passage") ?? p[4], 1)));
      if (r === "api" && b === "zhan-coverage") return send(200, await api.zhanCoverage());
      // ---- v2 规范化 API（S13）：/api/ielts/v2/*（本地索引解析，零网络；schema ielts.v2/1） ----
      if (r === "api" && b === "ielts" && t === "v2") {
        const q = u.searchParams;
        if (pp === "info") return send(200, api.v2Info());
        if (pp === "books") return send(200, api.v2Books());
        if (pp === "test") return send(200, api.v2Test(p[4], p[5], { variant: q.get("variant") }));
        if (pp === "questions") return send(200, api.v2Questions(p[4], p[5], {
          skill: q.get("skill"), variant: q.get("variant"), part: q.get("part"),
          passage: q.get("passage"), type: q.get("type"), status: q.get("status"),
          alignment: q.get("alignment"), offset: q.get("offset"), limit: q.get("limit"),
        }));
        if (pp === "question") return send(200, api.v2Question(p[4]));
        if (pp === "coverage") return send(200, api.v2Coverage({ book: q.get("book"), test: q.get("test") }));
        if (pp === "asset") return sendAsset(p[4]);
        return send(404, { ok: false, error: "unknown v2 route", available: ["info", "books", "test", "questions", "question", "coverage", "asset"] });
      }
      send(404, { ok: false, error: "unknown route", available: Object.keys(routes) });
    } catch (e) { send(500, { ok: false, error: String(e && e.message || e) }); }
  });
  server.listen(port, "127.0.0.1", () => console.log("IELTS API listening on http://127.0.0.1:" + port));
} else if (cmd === "compare-official") {
  // S07 官方答案比较工具：作为子进程透传（保留工具自身的退出码 0/1/2 与输出语义）
  const { spawnSync } = await import("node:child_process");
  const { fileURLToPath } = await import("node:url");
  const tool = fileURLToPath(new URL("./tools/compare-official.mjs", import.meta.url));
  const r = spawnSync(process.execPath, [tool, ...a], { stdio: "inherit" });
  process.exit(r.status === null ? 1 : r.status);
} else if (routes[cmd]) {
  const out = await routes[cmd]();
  const s = j(out);
  // 仅交互终端做友好截断；重定向/管道时输出完整 JSON（供脚本消费）
  const truncated = process.stdout.isTTY && s.length > 6000;
  console.log(truncated ? s.slice(0, 6000) + "\n... [truncated, " + s.length + " bytes total]" : s);
} else {
  console.error("usage: node ielts-cli.mjs <" + Object.keys(routes).join("|") + "|compare-official|serve> [args]");
  process.exit(2);
}