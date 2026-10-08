#!/usr/bin/env node
/**
 * check-route-inventory.mjs — S15 路由清单核对（Node HTTP / CLI / FastAPI 三面一致）
 *
 * 用法：
 *   node tools/check-route-inventory.mjs [--port <n>] [--data-dir <dir>]
 *
 * 检查：
 *   A CLI 七命令：node ielts-cli.mjs（无参数）usage 行包含 info/books-v2/test-v2/
 *     questions-v2/question-v2/coverage-v2/asset-v2 及 serve/compare-official。
 *   B Node HTTP：spawn `node ielts-cli.mjs serve <port>`，实测七条 /api/ielts/v2/* 路由
 *     （info/books/test/questions/question/coverage/asset），asset 用 Range: bytes=0-99
 *     断言 206 + content-range + content-length=100；未知 v2 路由 404。
 *   C v2Info().routes：与 B 的路径集合一致（7 条）。
 *   D FastAPI：解析 examdata/src/examdata/api/ielts.py 的 @router.get("/v2/...") 集合，
 *     与 Node 七条一一对应。
 *
 * 退出码：0 = 全部通过；1 = 存在失败；2 = 参数错误。
 */
import fs from "node:fs";
import path from "node:path";
import http from "node:http";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

import { resolveDataDir } from "../data-store.mjs";
import { v2Info } from "../ielts-api.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const API_DIR = path.resolve(HERE, "..");
const CLI = path.join(API_DIR, "ielts-cli.mjs");
const FASTAPI_PY = path.resolve(API_DIR, "..", "examdata", "src", "examdata", "api", "ielts.py");

const opts = { port: 8799, dataDir: null };
for (let i = 2; i < process.argv.length; i++) {
  const a = process.argv[i];
  if (a === "--port") opts.port = Number(process.argv[++i]);
  else if (a === "--data-dir") opts.dataDir = process.argv[++i];
  else {
    console.error(`unknown argument: ${a}`);
    process.exit(2);
  }
}
if (!Number.isInteger(opts.port) || opts.port < 1 || opts.port > 65535) {
  console.error("bad --port");
  process.exit(2);
}

let passed = 0;
const failures = [];
function check(id, cond, detail = "") {
  if (cond) {
    passed++;
    console.log(`PASS ${id}${detail ? " " + detail : ""}`);
  } else {
    failures.push({ id, detail });
    console.log(`FAIL ${id}${detail ? " " + detail : ""}`);
  }
}

const EXPECTED_V2 = [
  "/api/ielts/v2/info",
  "/api/ielts/v2/books",
  "/api/ielts/v2/test/{book}/{test}",
  "/api/ielts/v2/questions/{book}/{test}",
  "/api/ielts/v2/question/{question_id}",
  "/api/ielts/v2/coverage",
  "/api/ielts/v2/asset/{id}",
];

// ---------------------------------------------------------------- A CLI 七命令

function runCliNoArgs() {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, [CLI], { cwd: API_DIR });
    let err = "";
    child.stderr.on("data", (d) => (err += d));
    child.on("close", (code) => resolve({ code, err }));
  });
}

const cliUsage = await runCliNoArgs();
const cliCmds = ["info", "books-v2", "test-v2", "questions-v2", "question-v2", "coverage-v2", "asset-v2", "serve", "compare-official"];
check(
  "A01-cli-commands",
  cliUsage.code === 2 && cliCmds.every((c) => cliUsage.err.includes(c)),
  `exit=${cliUsage.code} missing=${cliCmds.filter((c) => !cliUsage.err.includes(c)).join(",") || "none"}`
);

// ---------------------------------------------------------------- B Node HTTP 实测

function request(port, method, urlPath, headers = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: "127.0.0.1", port, method, path: urlPath, headers }, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () =>
        resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks) })
      );
    });
    req.on("error", reject);
    req.end();
  });
}

function startServer(port, dataDir) {
  return new Promise((resolve, reject) => {
    const env = { ...process.env };
    if (dataDir) env.EXAMDATA_IELTS_DATA_DIR = dataDir;
    const child = spawn(process.execPath, [CLI, "serve", String(port)], { cwd: API_DIR, env });
    let out = "";
    let settled = false;
    const timer = setTimeout(() => {
      if (!settled) {
        settled = true;
        child.kill();
        reject(new Error("server did not start in 60s: " + out.slice(0, 300)));
      }
    }, 60000);
    child.stdout.on("data", (d) => {
      out += d;
      if (!settled && out.includes("IELTS API listening")) {
        settled = true;
        clearTimeout(timer);
        resolve(child);
      }
    });
    child.stderr.on("data", (d) => (out += d));
    child.on("exit", (code) => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        reject(new Error(`server exited early code=${code}: ${out.slice(0, 300)}`));
      }
    });
  });
}

const dataDir = resolveDataDir(opts.dataDir);
let server = null;
try {
  server = await startServer(opts.port, opts.dataDir);
  const base = `http://127.0.0.1:${opts.port}`;

  const probes = [
    ["B01-info", "/api/ielts/v2/info", (r) => r.status === 200 && r.json.ok === true && Array.isArray(r.json.routes) && r.json.routes.length === 7],
    ["B02-books", "/api/ielts/v2/books", (r) => r.status === 200 && r.json.ok === true],
    ["B03-test", "/api/ielts/v2/test/10/1", (r) => r.status === 200 && r.json.ok === true],
    ["B04-questions", "/api/ielts/v2/questions/10/1?skill=reading&limit=2", (r) => r.status === 200 && r.json.ok === true && r.json.count === 2],
    ["B05-question", "/api/ielts/v2/question/q-10-1-reading-academic-1", (r) => r.status === 200 && r.json.ok === true && r.json.question && r.json.question.question_id === "q-10-1-reading-academic-1"],
    ["B06-coverage", "/api/ielts/v2/coverage", (r) => r.status === 200 && r.json.ok === true],
  ];
  for (const [id, urlPath, pred] of probes) {
    try {
      const r = await request(opts.port, "GET", urlPath);
      let json = null;
      try {
        json = JSON.parse(r.body.toString("utf8"));
      } catch {}
      const ok = pred({ status: r.status, headers: r.headers, json });
      check(id, ok, `${urlPath} -> ${r.status}${json && json.ok === false ? " ok=false" : ""}`);
    } catch (e) {
      check(id, false, `${urlPath} -> error ${e.message}`);
    }
  }

  // asset Range 实测：book-pdf-1 bytes=0-99
  try {
    const r = await request(opts.port, "GET", "/api/ielts/v2/asset/book-pdf-1", { Range: "bytes=0-99" });
    const cr = r.headers["content-range"] || "";
    const okRange =
      r.status === 206 &&
      /^bytes 0-99\/\d+$/.test(cr) &&
      r.headers["accept-ranges"] === "bytes" &&
      Number(r.headers["content-length"]) === 100 &&
      r.body.length === 100;
    check("B07-asset-range", okRange, `status=${r.status} content-range=${cr} len=${r.body.length}`);
  } catch (e) {
    check("B07-asset-range", false, `error ${e.message}`);
  }

  // 未知 v2 路由 → 404 + available 清单
  try {
    const r = await request(opts.port, "GET", "/api/ielts/v2/nope");
    let json = null;
    try {
      json = JSON.parse(r.body.toString("utf8"));
    } catch {}
    const ok404 = r.status === 404 && json && json.ok === false && Array.isArray(json.available) && json.available.length === 7;
    check("B08-unknown-route", ok404, `status=${r.status}`);
  } catch (e) {
    check("B08-unknown-route", false, `error ${e.message}`);
  }

  // ---------------------------------------------------------------- C v2Info().routes

  const info = v2Info();
  const infoPaths = (info.routes || []).map((r) => String(r.path).split("?")[0]);
  const expectedBase = EXPECTED_V2.map((p) => (p === "/api/ielts/v2/asset/{id}" ? "/api/ielts/v2/asset/{id}" : p));
  const infoSet = new Set(infoPaths.map((p) => p.replace("/api/ielts/v2/asset/{asset_id}", "/api/ielts/v2/asset/{id}")));
  const infoOk =
    info.routes.length === 7 &&
    expectedBase.every((p) => infoSet.has(p));
  check("C01-v2info-routes", infoOk, infoPaths.join(" | "));
} catch (e) {
  check("B00-server", false, e.message);
} finally {
  if (server) {
    server.kill();
    await new Promise((r) => setTimeout(r, 300));
  }
}

// ---------------------------------------------------------------- D FastAPI 对齐

try {
  const src = fs.readFileSync(FASTAPI_PY, "utf8");
  const v2Paths = [];
  const re = /@router\.get\(\s*"(\/v2\/[^"]+)"/g;
  let m;
  while ((m = re.exec(src))) v2Paths.push(m[1]);
  const expectedFastapi = [
    "/v2/info",
    "/v2/books",
    "/v2/test/{book}/{test}",
    "/v2/questions/{book}/{test}",
    "/v2/question/{question_id}",
    "/v2/coverage",
    "/v2/asset/{asset_id}",
  ];
  const fastapiOk =
    v2Paths.length === 7 && expectedFastapi.every((p) => v2Paths.includes(p));
  check("D01-fastapi-routes", fastapiOk, v2Paths.join(" | "));
} catch (e) {
  check("D01-fastapi-routes", false, `cannot read ${FASTAPI_PY}: ${e.message}`);
}

// ---------------------------------------------------------------- 汇总

const ok = failures.length === 0;
console.log(`check-route-inventory: ${passed} passed, ${failures.length} failed (port=${opts.port}, data-dir=${dataDir})`);
console.log("RESULT " + JSON.stringify({ ok, passed, failed: failures.length, failures }));
process.exit(ok ? 0 : 1);
