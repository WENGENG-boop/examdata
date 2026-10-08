// ielts-api/tests/ielts-routes.test.mjs
// S13 acceptance: Node HTTP 入口（ielts-cli.mjs serve）—— v2 路由与 reading 整卷语义。
// 与 CLI 直调、FastAPI 网关共享同一 resolver/v2-api；全部本地索引解析，零网络请求。
// Run: node --test ielts-api/tests/ielts-routes.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const cli = path.join(here, "..", "ielts-cli.mjs");
const PORT = 18800 + (process.pid % 150);
const BASE = `http://127.0.0.1:${PORT}`;

let child = null;

test.before(async () => {
  child = spawn(process.execPath, [cli, "serve", String(PORT)], {
    cwd: path.join(here, ".."),
    stdio: ["ignore", "pipe", "pipe"],
  });
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("serve 启动超时（30s）")), 30000);
    let buf = "";
    child.stdout.on("data", (d) => {
      buf += d.toString();
      if (buf.includes("listening")) {
        clearTimeout(timer);
        resolve();
      }
    });
    child.stderr.on("data", (d) => {
      buf += d.toString();
    });
    child.on("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`serve 提前退出 code=${code}\n${buf}`));
    });
  });
});

test.after(() => {
  if (child && !child.killed) child.kill();
});

const get = async (p, opts) => {
  const res = await fetch(BASE + p, opts);
  const text = await res.text();
  let json = null;
  try {
    json = JSON.parse(text);
  } catch {
    /* 非 JSON（如 Range 流） */
  }
  return { res, json, text };
};

test("v2 info：schema/版本/run_id/路由清单", async () => {
  const { res, json } = await get("/api/ielts/v2/info");
  assert.equal(res.status, 200);
  assert.equal(json.ok, true);
  assert.equal(json.schema, "ielts.v2/1");
  assert.equal(json.version, "v2/1.0.0");
  assert.equal(json.board, "ielts");
  assert.ok(json.run_id, "带 run_id 证据");
  const paths = json.routes.map((r) => r.path);
  assert.ok(paths.includes("/api/ielts/v2/coverage?book=&test="));
  assert.ok(paths.includes("/api/ielts/v2/test/{book}/{test}?variant=academic|general"));
  assert.ok(paths.includes("/api/ielts/v2/questions/{book}/{test}?skill=&variant=&part=&passage=&type=&status=&alignment=&offset=&limit="));
});

test("v2 books：21 册目录 + book12 编号映射", async () => {
  const { res, json } = await get("/api/ielts/v2/books");
  assert.equal(res.status, 200);
  assert.equal(json.ok, true);
  assert.equal(json.books.length, 21);
  const b12 = json.books.find((b) => b.book === 12);
  assert.ok(b12, "book 12 在目录中");
  const readingTests = b12.tests["reading/academic"] || [];
  assert.deepEqual(readingTests, ["5", "6", "7", "8"], "book12 canonical 编号为 5–8");
  const b1 = json.books.find((b) => b.book === 1);
  assert.ok(b1.units > 0, "book 1 有单元");
});

test("v2 questions：剑10 T1 阅读 Q34 空答案保位（status=empty）", async () => {
  const { res, json } = await get("/api/ielts/v2/questions/10/1?skill=reading&status=empty");
  assert.equal(res.status, 200);
  assert.equal(json.ok, true);
  assert.equal(json.count, 1);
  const q = json.questions[0];
  assert.equal(q.question_id, "q-10-1-reading-academic-34");
  assert.equal(q.number, 34);
  assert.equal(q.answer.raw, "");
  assert.equal(q.answer.status, "empty");
});

test("v2 questions：剑1 T2 听力 41 题保留（39 答 2 缺）", async () => {
  const { json } = await get("/api/ielts/v2/questions/1/2?skill=listening");
  assert.equal(json.ok, true);
  assert.equal(json.count, 41);
  const nums = json.questions.map((q) => q.number);
  assert.deepEqual(nums, Array.from({ length: 41 }, (_, i) => i + 1));
  const hist = {};
  for (const q of json.questions) {
    const s = q.answer && q.answer.status;
    hist[s] = (hist[s] || 0) + 1;
  }
  assert.equal(hist.attached, 39);
  assert.equal(hist.missing, 2);
});

test("v2 questions：alignment 过滤（剑21 T1 听力仅 verified 题）", async () => {
  const { json } = await get("/api/ielts/v2/questions/21/1?skill=listening&alignment=verified");
  assert.equal(json.ok, true);
  assert.ok(json.count > 0, "至少有一题 verified");
  assert.ok(json.count <= 40);
  for (const q of json.questions) {
    assert.equal(q.audio_alignment.status, "verified");
  }
  const all = await get("/api/ielts/v2/questions/21/1?skill=listening");
  assert.equal(all.json.count, 40);
  assert.ok(json.count < all.json.count, "verified 是严格子集（其余 unverified/candidate）");
});

test("v2 question：单题按完整身份；非法 id 200+ok:false", async () => {
  const { res, json } = await get("/api/ielts/v2/question/q-10-1-reading-academic-34");
  assert.equal(res.status, 200);
  assert.equal(json.ok, true);
  assert.equal(json.question.question_id, "q-10-1-reading-academic-34");
  assert.equal(json.question.answer.raw, "");
  assert.equal(json.question.answer.status, "empty");

  const bad = await get("/api/ielts/v2/question/bad-id");
  assert.equal(bad.res.status, 200);
  assert.equal(bad.json.ok, false);
  assert.equal(bad.json.code, "bad_question_id");

  const nf = await get("/api/ielts/v2/question/q-10-1-reading-academic-99");
  assert.equal(nf.res.status, 200);
  assert.equal(nf.json.ok, false);
  assert.equal(nf.json.code, "not_found");
});

test("v2 coverage：单套 4 单元 + 完成度（partial 不冒充 complete）", async () => {
  const { res, json } = await get("/api/ielts/v2/coverage?book=20&test=4");
  assert.equal(res.status, 200);
  assert.equal(json.ok, true);
  assert.equal(json.level, "test");
  assert.equal(json.schema, "ielts.coverage/1");
  assert.equal(json.units.length, 4);
  const ids = json.units.map((u) => u.unit_id);
  assert.ok(ids.includes("cambridge:20:academic:reading:4"));
  assert.ok(ids.includes("cambridge:20:shared:listening:4"));
  assert.equal(typeof json.completion.fully_complete, "boolean");
});

test("reading 整卷缺省：3 篇 40 题（HTTP 直取）", async () => {
  const { json } = await get("/api/reading/20/4");
  assert.equal(json.ok, true);
  assert.equal(json.passage, null);
  assert.equal(json.passages.length, 3);
  assert.equal(json.questions.length, 40);
  assert.deepEqual(
    json.passages.map((p) => p.questions.length),
    [13, 13, 14]
  );
});

test("reading 单篇：/api/reading/10/1/2 → 13 题（14–26）", async () => {
  const { json } = await get("/api/reading/10/1/2");
  assert.equal(json.ok, true);
  assert.equal(json.passage, 2);
  assert.equal(json.questions.length, 13);
  assert.equal(json.questions[0].number, 14);
  assert.equal(json.questions[12].number, 26);
});

test("v2 asset：book-pdf-20 支持 Range（206）；坏 id 404", async () => {
  const r = await fetch(`${BASE}/api/ielts/v2/asset/book-pdf-20`, { headers: { range: "bytes=0-99" } });
  assert.equal(r.status, 206);
  assert.match(r.headers.get("content-range") || "", /^bytes 0-99\/\d+$/);
  assert.equal(r.headers.get("content-type"), "application/pdf");
  await r.body.cancel();

  const full = await fetch(`${BASE}/api/ielts/v2/asset/book-pdf-20`);
  assert.equal(full.status, 200);
  assert.equal(full.headers.get("content-type"), "application/pdf");
  assert.ok(Number(full.headers.get("content-length")) > 1000000);
  await full.body.cancel();

  const meta = spawnSync(process.execPath, [cli, "asset-v2", "book-pdf-20"], { encoding: "utf-8" });
  assert.equal(meta.status, 0);
  const md = JSON.parse(meta.stdout);
  assert.equal(md.ok, true);
  assert.equal(md.kind, "pdf");
  assert.ok(md.bytes > 1000000);

  const bad = await get("/api/ielts/v2/asset/zzz");
  assert.equal(bad.res.status, 404);
});

test("v2 未知路由 404；CLI 未知命令 exit 2（不冒充业务失败）", async () => {
  const { res, json } = await get("/api/ielts/v2/nope");
  assert.equal(res.status, 404);
  assert.equal(json.ok, false);

  const r = spawnSync(process.execPath, [cli, "definitely-not-a-command"], { encoding: "utf-8" });
  assert.equal(r.status, 2);
  assert.match(r.stderr, /usage:/);

  const biz = spawnSync(process.execPath, [cli, "test-v2", "99", "1"], { encoding: "utf-8" });
  assert.equal(biz.status, 0, "业务失败仍 exit 0");
  const d = JSON.parse(biz.stdout);
  assert.equal(d.ok, false);
  assert.equal(d.code, "invalid_book");
});

test("v2 test：gta/gtb 经 variant=general（HTTP）；academic 冲突拒绝", async () => {
  const gta = await get("/api/ielts/v2/test/1/gta?variant=general");
  assert.equal(gta.res.status, 200);
  assert.equal(gta.json.ok, true);
  assert.equal(gta.json.identity.variant, "general");
  assert.equal(gta.json.listening, null);
  const ids = gta.json.completion.units.map((u) => u.unit_id);
  assert.deepEqual(ids, ["cambridge:1:general:reading:gta", "cambridge:1:general:writing:gta"]);

  const mm = await get("/api/ielts/v2/test/1/gta?variant=academic");
  assert.equal(mm.res.status, 200);
  assert.equal(mm.json.ok, false);
  assert.equal(mm.json.code, "variant_mismatch");
});

test("v2 questions：offset/limit 分页 + 非法分页 bad_filter（HTTP）", async () => {
  const page = await get("/api/ielts/v2/questions/10/1?offset=39&limit=3");
  assert.equal(page.json.ok, true);
  assert.equal(page.json.count, 3);
  assert.equal(page.json.total, 80);
  assert.deepEqual(page.json.questions.map((q) => q.number), [40, 1, 2]);

  const bad = await get("/api/ielts/v2/questions/10/1?limit=501");
  assert.equal(bad.json.ok, false);
  assert.equal(bad.json.code, "bad_filter");
});

test("reading-enriched：非法身份零请求（HTTP + CLI）", async () => {
  const http = await get("/api/reading-enriched/99/1");
  assert.equal(http.res.status, 200);
  assert.equal(http.json.ok, false);
  assert.equal(http.json.source, "userheyy/ielts-reader");
  assert.match(http.json.error, /book/);

  const cliRun = spawnSync(process.execPath, [cli, "reading-enriched", "99", "1", "1"], { encoding: "utf-8" });
  assert.equal(cliRun.status, 0);
  const d = JSON.parse(cliRun.stdout);
  assert.equal(d.ok, false);
});

test("CLI：test-v2 gta variant 与 questions-v2 分页（直调）", async () => {
  const gta = spawnSync(process.execPath, [cli, "test-v2", "1", "gta", "--variant=general"], { encoding: "utf-8" });
  assert.equal(gta.status, 0);
  const gd = JSON.parse(gta.stdout);
  assert.equal(gd.ok, true);
  assert.equal(gd.identity.variant, "general");

  const q = spawnSync(process.execPath, [cli, "questions-v2", "10", "1", "--offset=39", "--limit=3"], { encoding: "utf-8" });
  assert.equal(q.status, 0);
  const qd = JSON.parse(q.stdout);
  assert.equal(qd.count, 3);
  assert.equal(qd.total, 80);

  const bad = spawnSync(process.execPath, [cli, "questions-v2", "10", "1", "--limit=501"], { encoding: "utf-8" });
  assert.equal(bad.status, 0);
  const bd = JSON.parse(bad.stdout);
  assert.equal(bd.ok, false);
  assert.equal(bd.code, "bad_filter");
});

test("compare-official CLI：透传退出码与三态汇总（fixture，候选带完整身份）", async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "ielts-cmp-"));
  try {
    const pdfPath = path.join(tmp, "pdf.json");
    const ansPath = path.join(tmp, "ans.json");
    fs.writeFileSync(
      pdfPath,
      JSON.stringify({
        source: "pdf_official",
        identity: { book: 1, test: 1, skill: "reading" },
        entries: [
          { number: 1, value: "TRUE", page: 5 },
          { number: 2, value: "FALSE", page: 5 },
          { number: 3, value: "NOT GIVEN", page: 6 },
        ],
      })
    );
    fs.writeFileSync(
      ansPath,
      JSON.stringify([
        {
          source: "practicepteonline",
          identity: { book: 1, test: 1, skill: "reading" },
          kind: "numbered",
          entries: [
            { number: 1, value: "TRUE" },
            { number: 2, value: "TRUE" },
          ],
        },
      ])
    );
    const r = spawnSync(
      process.execPath,
      [cli, "compare-official", "--identity", "book=1,test=1,skill=reading", "--pdf", pdfPath, "--answers", ansPath],
      { encoding: "utf-8" }
    );
    assert.equal(r.status, 0);
    const d = JSON.parse(r.stdout);
    assert.equal(d.summary.total, 3);
    assert.equal(d.summary.match, 1);
    assert.equal(d.summary.conflict, 1);
    assert.equal(d.summary.pdf_only, 1);

    const missing = spawnSync(process.execPath, [cli, "compare-official"], { encoding: "utf-8" });
    assert.equal(missing.status, 2, "缺参 exit 2");
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
});
