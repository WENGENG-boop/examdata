// S08：抓 1 个真实 writing 题目页样本（小预算），用于设计 writing 解析器与 fixture。
// 用法：node fetch-writing-sample.mjs [slug]
import { createFetcher } from "../../../../../ielts-api/fetch-source.mjs";
import { resolveDataDir } from "../../../../../ielts-api/data-store.mjs";

const slug = process.argv[2] || "ielts-writing-test-125";
const root = resolveDataDir();
const f = createFetcher({
  root,
  runId: "20261003T140007Z-repair",
  limits: { maxRequests: 3, maxBytes: 8 * 1024 * 1024 },
});
const url = `https://practicepteonline.com/wp-json/wp/v2/pages?slug=${encodeURIComponent(slug)}&_fields=id,slug,title,content`;
const r = await f.fetchToRaw({
  source: "practicepteonline",
  url,
  headers: {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    accept: "application/json",
  },
  parserVersion: "s08-writing-probe",
  meta: { kind: "wp-page", skill: "writing", note: "S08 writing page sample", slug },
});
console.log(JSON.stringify({
  slug,
  sha256: r.sha256,
  bytes: r.bytes,
  deduped: !!r.deduped,
  bodyPath: r.bodyPath,
  metaPath: r.metaPath,
  status: r.status ?? null,
  budget: f.budgetStatus(),
}, null, 2));
