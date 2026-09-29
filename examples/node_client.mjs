#!/usr/bin/env node
/**
 * examdata 统一网关（/api/v1）的 Node 客户端示例。
 *
 * 只用 Node 18+ 内置的全局 fetch（以及 node:fs / node:path），不装任何 npm 包。
 * 与 examples/python_client.py 等价，覆盖同样的四类调用：
 *
 *   1. GET /api/v1/boards              能力发现
 *   2. GET /api/v1/search              跨考试局检索（读数据库，不访问上游）
 *   3. GET /api/v1/paper               统一取卷（清单 / 二进制 / base64 JSON）
 *   4. GET /api/v1/question/{id}       单题聚合视图
 *
 * 用法（工作目录是仓库根）：
 *
 *   node examples/node_client.mjs boards
 *   node examples/node_client.mjs search --subject 0580 --leaves-only --limit 5
 *   node examples/node_client.mjs paper --subject 0580 --year 2024 --season Jun --paper 11 --no-download
 *   node examples/node_client.mjs paper --subject 0580 --year 2024 --season Jun --paper 11 --out ./out
 *   node examples/node_client.mjs question --id 1
 *   node examples/node_client.mjs demo
 *
 * base URL 默认 http://127.0.0.1:8000，可用 --base-url 或环境变量 EXAMDATA_BASE_URL 覆盖。
 * 服务端设了 EXAMDATA_API_KEY 时，用 --api-key 或环境变量 EXAMDATA_API_KEY 传同一个值，
 * 客户端会放进 X-API-Key 头。
 */

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const DEFAULT_BASE_URL = process.env.EXAMDATA_BASE_URL || "http://127.0.0.1:8000";
const DEFAULT_API_KEY = process.env.EXAMDATA_API_KEY || "";

/** 解析命令行：全局选项 + 子命令 + 子命令选项（选项一律 --name value 或 --flag）。 */
function parseArgs(argv) {
  const options = {};
  const rest = [];
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) {
      rest.push(token);
      continue;
    }
    const key = token.slice(2);
    const next = argv[i + 1];
    if (next === undefined || next.startsWith("--")) {
      options[key] = true;
    } else {
      options[key] = next;
      i += 1;
    }
  }
  return { command: rest[0] || "demo", options };
}

/** HTTP 4xx/5xx。detail 是 FastAPI 错误体里的原始说明。 */
class ApiError extends Error {
  constructor(status, detail) {
    super(`HTTP ${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

class Client {
  constructor(baseUrl, apiKey, timeoutMs) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.apiKey = apiKey;
    this.timeoutMs = timeoutMs;
    this.verbose = false;
  }

  headers(accept = "application/json") {
    const headers = { Accept: accept };
    if (this.apiKey) headers["X-API-Key"] = this.apiKey;
    return headers;
  }

  /** GET 一次；非 2xx 抛 ApiError。params 里 null/undefined 的键会被丢掉。 */
  async get(pathname, params = {}, accept = "application/json") {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value === null || value === undefined || value === "") continue;
      query.set(key, String(value));
    }
    const search = query.toString();
    const url = `${this.baseUrl}${pathname}${search ? `?${search}` : ""}`;
    if (this.verbose) console.error(`[verbose] GET ${url}`);
    const response = await fetch(url, {
      headers: this.headers(accept),
      signal: AbortSignal.timeout(this.timeoutMs),
    });
    if (!response.ok) {
      let detail = await response.text();
      try {
        const payload = JSON.parse(detail);
        if (payload && typeof payload === "object" && "detail" in payload) {
          // FastAPI 参数校验失败时 detail 是数组；转成文本，免得模板串渲染成 [object Object]。
          detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail);
        }
      } catch {
        /* 非 JSON 错误体，原样保留文本 */
      }
      throw new ApiError(response.status, detail);
    }
    return response;
  }

  async getJson(pathname, params = {}) {
    return (await this.get(pathname, params)).json();
  }
}

function printJson(payload) {
  console.log(JSON.stringify(payload, null, 2));
}

/** 从 Content-Disposition 里取服务端给的文件名。 */
function filenameFrom(disposition, fallback = "paper.bin") {
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition || "");
  return match ? match[1] : fallback;
}

async function save(outDir, name, data) {
  await mkdir(outDir, { recursive: true });
  const target = path.join(outDir, name);
  await writeFile(target, data);
  return target;
}

// ---------------------------------------------------------------------------
// 子命令
// ---------------------------------------------------------------------------

function searchParams(options) {
  return {
    keyword: options.keyword,
    subject: options.subject,
    board: options.board,
    year: options.year,
    session: options.session,
    paper: options.paper,
    marks_min: options["marks-min"],
    marks_max: options["marks-max"],
    leaves_only: options["leaves-only"] ? "true" : null,
    has_answer: options["has-answer"] ? "true" : null,
    limit: options.limit,
    offset: options.offset,
  };
}

async function cmdBoards(client, options) {
  const data = await client.getJson("/api/v1/boards");
  if (options.json) {
    printJson(data);
    return 0;
  }
  console.log(`schema_version = ${data.schema_version}`);
  if (data.auto_detect) console.log(`auto_detect    = ${JSON.stringify(data.auto_detect)}`);
  for (const board of data.boards || []) {
    console.log(`\n[${board.board}] ${board.name}`);
    console.log(`  别名       : ${(board.aliases || []).join(", ")}`);
    console.log(`  上游       : ${board.upstream}`);
    console.log(`  科目形态   : ${board.subject_hint}`);
    console.log(`  考季       : ${(board.seasons || []).join(", ")}`);
    console.log(`  模式       : ${(board.modes || []).join(", ")}（默认 ${board.default_mode}）`);
    console.log(`  按题裁剪   : ${board.question_crop ? "支持" : "不支持"}`);
  }
  return 0;
}

async function cmdSearch(client, options) {
  const data = await client.getJson("/api/v1/search", searchParams(options));
  if (options.json) {
    printJson(data);
    return 0;
  }
  const byBoard = data.by_board || {};
  console.log(
    `命中 ${data.total} 题（cambridge=${byBoard.cambridge ?? 0}, edexcel=${byBoard.edexcel ?? 0}）` +
      `  limit=${data.limit} offset=${data.offset}`,
  );
  for (const item of data.items || []) {
    let stem = (item.stem_text || "").replace(/\s+/g, " ");
    if (stem.length > 60) stem = `${stem.slice(0, 60)}…`;
    console.log(
      `  #${String(item.question_id).padEnd(6)} ${String(item.board).padEnd(10)} ` +
        `${String(item.subject_code ?? "-").padEnd(6)} ${item.year ?? "-"} ` +
        `${String(item.paper_code ?? "-").padEnd(8)} ${String(item.number_path ?? "-").padEnd(8)} ` +
        `${item.marks ?? "-"} 分  ${stem}`,
    );
  }
  return 0;
}

function paperParams(options) {
  return {
    subject: options.subject,
    year: options.year,
    season: options.season,
    board: options.board,
    paper: options.paper,
    question: options.question,
    mode: options.mode,
  };
}

async function cmdPaper(client, options) {
  if (options["no-download"]) {
    const data = await client.getJson("/api/v1/paper", {
      ...paperParams(options),
      download: "false",
    });
    if (options.json) {
      printJson(data);
      return 0;
    }
    const counts = data.counts || {};
    console.log(
      `board=${data.board}（${data.board_source}）` +
        `  documents=${counts.documents} files=${counts.files}`,
    );
    for (const doc of data.documents || []) {
      console.log(`  [${doc.role}] ${doc.name}  ${doc.url}`);
    }
    return 0;
  }

  if (options.format === "json") {
    const data = await client.getJson("/api/v1/paper", {
      ...paperParams(options),
      download: "true",
      format: "json",
    });
    const counts = data.counts || {};
    console.log(
      `board=${data.board}（${data.board_source}）  files=${counts.files} bytes=${counts.bytes}`,
    );
    for (const item of data.files || []) {
      console.log(
        `  ${item.name}  ${item.size} 字节  sha256=${String(item.sha256).slice(0, 12)}`,
      );
      if (item.data_base64 && options.out) {
        const target = await save(options.out, item.name, Buffer.from(item.data_base64, "base64"));
        console.log(`    -> 已保存 ${target}`);
      }
    }
    if (!options.out && (data.files || []).some((item) => item.data_base64)) {
      console.log("  （加 --out <目录> 可把 base64 载荷落盘）");
    }
    return 0;
  }

  const response = await client.get(
    "/api/v1/paper",
    { ...paperParams(options), download: "true" },
    "application/octet-stream",
  );
  const name = filenameFrom(response.headers.get("content-disposition"));
  const data = Buffer.from(await response.arrayBuffer());
  console.log(
    `${name}  ${data.length} 字节  Content-Type=${response.headers.get("content-type")}  ` +
      `Content-Length=${response.headers.get("content-length")}`,
  );
  if (options.out) {
    const target = await save(options.out, name, data);
    console.log(`-> 已保存 ${target}`);
  } else {
    console.log("（加 --out <目录> 落盘；或改用 --format json 走 base64）");
  }
  return 0;
}

async function cmdQuestion(client, options) {
  const id = options.id;
  if (!id) throw new Error("question 需要 --id");
  const data = await client.getJson(`/api/v1/question/${id}`);
  if (options.json) {
    printJson(data);
    return 0;
  }
  const source = data.source || {};
  const bundle = data.bundle || {};
  const question = bundle.question || bundle;
  console.log(`question_id = ${data.question_id}  board = ${data.board}`);
  console.log(
    `  source: ${source.subject_code} / ${source.year} ${source.session} / paper ${source.paper_code}` +
      `  (board_canonical=${source.board_canonical})`,
  );
  console.log(`  取卷链接: ${source.paper_endpoint}`);
  console.log(`  题目: ${question.number_path}  ${question.marks} 分  kind=${question.kind}`);
  const stem = (question.stem_text || "").trim().replace(/\s+/g, " ");
  console.log(`  题干: ${stem.slice(0, 120)}${stem.length > 120 ? "…" : ""}`);
  const children = bundle.children || [];
  if (children.length) console.log(`  子题: ${children.map((c) => c.number_path).join(", ")}`);
  console.log(`  bundle 顶层字段: ${Object.keys(bundle).sort().join(", ")}`);
  return 0;
}

async function cmdDemo(client, options) {
  const demo = {
    ...options,
    subject: options.subject || "0580",
    year: options.year || 2024,
    season: options.season || "Jun",
    paper: options.paper || "11",
    limit: options.limit || 3,
    "leaves-only": options["leaves-only"] ?? true,
    "no-download": true,
  };
  let failures = 0;
  const run = async (title, fn) => {
    console.log(`\n=== ${title} ===`);
    try {
      await fn();
    } catch (error) {
      failures += 1;
      console.log(`!! 失败: ${error.message}`);
    }
  };

  await run("能力发现 /api/v1/boards", () => cmdBoards(client, demo));
  await run("跨局检索 /api/v1/search", () => cmdSearch(client, demo));
  await run("单题聚合 /api/v1/question/{id}", async () => {
    const data = await client.getJson("/api/v1/search", { ...searchParams(demo), limit: 1 });
    const items = data.items || [];
    if (!items.length) {
      console.log("（检索没有命中，跳过；换一组过滤条件再试）");
      return;
    }
    await cmdQuestion(client, { ...demo, id: items[0].question_id });
  });
  await run("统一取卷 /api/v1/paper（只解析清单）", () => cmdPaper(client, demo));

  console.log(`\n完成：${4 - failures}/4 步成功`);
  return failures ? 1 : 0;
}

// ---------------------------------------------------------------------------

const USAGE = `examdata 统一网关（/api/v1）Node 客户端示例

用法:
  node examples/node_client.mjs [全局选项] <子命令> [子命令选项]

子命令:
  boards                           GET /api/v1/boards
  search                           GET /api/v1/search
  paper                            GET /api/v1/paper
  question --id <题目ID>           GET /api/v1/question/{id}
  demo                             依次跑上面四类（默认）

全局选项:
  --base-url <URL>   服务地址，默认 ${DEFAULT_BASE_URL}
  --api-key <KEY>    放进 X-API-Key 头（服务端设了 EXAMDATA_API_KEY 时才需要）
  --timeout <毫秒>   单请求超时，默认 120000
  --json             打印完整 JSON
  --verbose          打印实际请求的 URL

search 选项: --keyword --subject --board --year --session --paper --marks-min --marks-max
             --leaves-only --has-answer --limit --offset
paper  选项: --subject --year --season --board --paper --question --mode
             --no-download --format binary|json --out <目录>
`;

async function main() {
  const { command, options } = parseArgs(process.argv.slice(2));
  if (options.help || options.h) {
    console.log(USAGE);
    return 0;
  }
  // 与服务端契约一致：format 只认 binary / json；别的值不该被静默当成 binary。
  if (options.format !== undefined && options.format !== "binary" && options.format !== "json") {
    console.error(`--format 只能是 binary 或 json，收到: ${options.format}\n`);
    console.log(USAGE);
    return 2;
  }
  const client = new Client(
    options["base-url"] || DEFAULT_BASE_URL,
    options["api-key"] || DEFAULT_API_KEY,
    Number(options.timeout || 120000),
  );
  client.verbose = Boolean(options.verbose);

  try {
    switch (command) {
      case "boards":
        return await cmdBoards(client, options);
      case "search":
        return await cmdSearch(client, options);
      case "paper":
        return await cmdPaper(client, options);
      case "question":
        return await cmdQuestion(client, options);
      case "demo":
        return await cmdDemo(client, options);
      default:
        console.error(`未知子命令: ${command}\n`);
        console.log(USAGE);
        return 2;
    }
  } catch (error) {
    if (error instanceof ApiError) {
      console.error(`请求失败: ${error.message}`);
      return 1;
    }
    console.error(`调用失败: ${error.name}: ${error.message}`);
    return 2;
  }
}

process.exitCode = await main();
