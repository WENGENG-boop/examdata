#!/usr/bin/env node
// ielts-api/tools/build-question-index.mjs
// S08: build the unified question index from local evidence (no network).
//
// Inputs (all local):
//   - ielts-data/runs/<run>/evidence/S04-raw-index.json     (PTE snapshot index)
//   - tmp_audit_ielts/completeness_20261003/raw-<N>.txt     (PTE raw pages)
//   - tmp_audit_ielts/cam21/t<test>-{reading,listening}.html (book 21 canonical source)
//   - ielts-api/data/expected-manifest.json                 (expected inventory)
// Outputs:
//   - ielts-data/runs/<run>/index/question-index.json
//   - stdout: stats summary + issue list
//
// Boundary: writes only under the ielts data root (default <repo>/ielts-data,
// override EXAMDATA_IELTS_DATA_DIR). No network access.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { RUN_ID } from "../catalog.mjs";
import { expectedFor, parsePtePage } from "../pte.mjs";
import { parseReadingHtml, parseListeningHtml } from "../cam21.mjs";
import { buildBook3ListeningTests } from "../book3-listening.mjs";
import { buildIndex, summarize, skillVariantOf, applyGroupVerifications } from "../question-index.mjs";
import { GROUP_VERIFICATIONS } from "../adjudications.mjs";
import { sha256FileSync, writeJsonAtomic } from "../data-store.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const API = path.resolve(__dirname, "..");
const REPO = path.resolve(API, "..");
const DATA_ROOT = process.env.EXAMDATA_IELTS_DATA_DIR || path.join(REPO, "ielts-data");
const RUN = path.join(DATA_ROOT, "runs", RUN_ID);
const EVID = path.join(RUN, "evidence");
const OUT_DIR = path.join(RUN, "index");
const OUT = path.join(OUT_DIR, "question-index.json");
const SNAP = path.join(REPO, "tmp_audit_ielts", "completeness_20261003");
const CAM21 = path.join(REPO, "tmp_audit_ielts", "cam21");
const MANIFEST = path.join(API, "data", "expected-manifest.json");

const rel = (p) => path.relative(REPO, p).replace(/\\/g, "/");
const readJson = (p) => JSON.parse(fs.readFileSync(p, "utf8"));

// 跨源测试编号冲突：book 12 原书内部编号为 Test 5-8（目录页 "Test 5 10 / Test 6 30 /
// Test 7 53 / Test 8 74"），practicepteonline 按每册顺序编号 1-4。
// 内容比对证据：PTE t1="Cyclists need/kitchen assistants"=Test 5；t2="Kenton Festival"=Test 6；
// t3="library re-opened"=Test 7；t4="Cycle tour leader: Margaret"=Test 8；阅读同映射
// （Cork harvesting / Shenggen Fan / Flying tortoises / Glass）。
// 裁决：以原书内部编号为准（与 expected-manifest 一致）；网页原编号保留于 page.source_test。
const TEST_NUMBER_MAP = { 12: { 1: 5, 2: 6, 3: 7, 4: 8 } };
const TEST_NUMBER_EVIDENCE = {
  12: [
    "book_12.pdf 目录页: Test 5 p10 / Test 6 p30 / Test 7 p53 / Test 8 p74",
    "内容比对: PTE t1-t4 听力/阅读与 Test 5-8 逐套命中（Kenton Festival, Flying tortoises, Glass 等）",
  ],
};
const canonicalTestOf = (book, test) => {
  const m = TEST_NUMBER_MAP[book];
  const mapped = m ? m[Number(test)] : undefined;
  return mapped != null ? String(mapped) : test;
};

function main() {
  const rawIndex = readJson(path.join(EVID, "S04-raw-index.json"));
  const manifest = readJson(MANIFEST);

  const pages = [];
  const cam21Pages = [];
  const alternate_sources = [];
  const issues = [];
  const sources = [];
  const b3Built = buildBook3ListeningTests({ repoRoot: REPO });

  for (const e of rawIndex) {
    const variantOf = skillVariantOf(e.skill);
    if (e.book === 21 && e.raw_index == null) {
      const file = path.join(CAM21, `t${e.test}-${e.skill}.html`);
      if (!fs.existsSync(file)) {
        issues.push({ kind: "source_missing", book: e.book, variant: variantOf.variant, skill: variantOf.skill, test: e.test, note: `cam21 HTML 缺失: ${rel(file)}` });
        continue;
      }
      const html = fs.readFileSync(file, "utf8");
      const parsed = e.skill === "listening"
        ? parseListeningHtml(html, { book: 21, test: e.test, skill: "listening" })
        : parseReadingHtml(html, { book: 21, test: e.test, skill: "reading" });
      if (!parsed.ok) {
        issues.push({ kind: "parse_failed", book: e.book, variant: variantOf.variant, skill: variantOf.skill, test: e.test, note: `cam21 解析失败: ${rel(file)}` });
        continue;
      }
      cam21Pages.push({
        parsed,
        meta: {
          book: 21, test: e.test, skill: e.skill,
          file: rel(file), source: "cam21-html", source_refs: [rel(file)],
          page_key: `cam21:21:${e.test}:${e.skill}`,
        },
      });
      sources.push({ file: rel(file), sha256: sha256FileSync(file) });
      continue;
    }
    if (e.raw_index != null) {
      const file = path.join(SNAP, `raw-${e.raw_index}.txt`);
      if (!fs.existsSync(file)) {
        issues.push({ kind: "source_missing", book: e.book, variant: variantOf.variant, skill: variantOf.skill, test: e.test, note: `raw 文件缺失: ${rel(file)}` });
        continue;
      }
      const sha256 = sha256FileSync(file);
      if (e.book === 21) {
        alternate_sources.push({
          book: 21, test: e.test, skill: e.skill, source: "practicepteonline",
          slug: e.slug, url: e.url, raw_index: e.raw_index,
          raw_file: rel(file), sha256,
          note: "cam21 规范来源为 cam21-html；PTE raw 仅作备用对照，不进主索引",
        });
        sources.push({ file: rel(file), sha256 });
        continue;
      }
      const mappedSkill = e.skill === "listening" ? "listening" : "academic_reading";
      const canonicalTest = canonicalTestOf(e.book, e.test);
      const expected = expectedFor(e.book, canonicalTest, mappedSkill);
      const text = fs.readFileSync(file, "utf8");
      const parsed = parsePtePage(text, { book: e.book, test: canonicalTest, skill: mappedSkill, slug: e.slug, page_id: e.page_id }, expected);
      if (!parsed.ok) {
        issues.push({ kind: "parse_failed", book: e.book, variant: variantOf.variant, skill: variantOf.skill, test: canonicalTest, note: `parsePtePage 失败: ${parsed.error || "unknown"}` });
        continue;
      }
      pages.push({
        parsed,
        meta: {
          book: e.book, test: canonicalTest, skill: mappedSkill,
          slug: e.slug, url: e.url, source_page_id: e.page_id,
          raw_index: e.raw_index, raw_file: rel(file),
          source: "practicepteonline", source_refs: [rel(file), e.url],
          expected,
          source_test: e.test !== canonicalTest ? e.test : undefined,
        },
      });
      sources.push({ file: rel(file), sha256 });
      continue;
    }
    if (e.book === 3 && e.skill === "listening") {
      const hit = b3Built.find((x) => String(x.meta.test) === String(e.test));
      if (!hit || !hit.ok) {
        issues.push({ kind: "source_missing", book: e.book, variant: variantOf.variant, skill: variantOf.skill, test: e.test, note: "book3-listening 转换器无此套数据" });
        continue;
      }
      pages.push({ parsed: hit.parsed, meta: hit.meta });
      for (const s of hit.sources) if (!sources.some((x) => x.file === s.file)) sources.push(s);
      continue;
    }
    // raw_index == null 且 book != 21：PDF 侧提取（S06/S07 已做）待 S12 融合
    issues.push({
      kind: "source_missing", book: e.book, variant: variantOf.variant, skill: variantOf.skill, test: e.test,
      note: "PTE raw_index=null；PDF 侧已提取内容待 S12 融合",
    });
  }

  const index = buildIndex({
    pages, cam21Pages, manifest, alternate_sources,
    options: { run_id: RUN_ID },
  });

  // 来源哈希挂到 page 记录（按 raw_file 匹配），并保留顶层 sources 清单
  const shaByFile = new Map(sources.map((s) => [s.file, s.sha256]));
  for (const page of index.pages) {
    if (page.raw_file && shaByFile.has(page.raw_file)) page.source_sha256 = shaByFile.get(page.raw_file);
  }
  // 官方 PDF 组级核验覆盖（S08）：b9t1r 分类/答案表示/字数限制（GROUP_VERIFICATIONS，from 守卫）
  const verification = applyGroupVerifications(index, GROUP_VERIFICATIONS);
  index.official_verifications = verification.applied;
  index.verification_issues = verification.issues;

  // 跨源测试编号冲突记录（网页原编号 → 原书编号）
  for (const [book, map] of Object.entries(TEST_NUMBER_MAP)) {
    for (const page of index.pages.filter((p) => p.book === Number(book))) {
      const srcTest = Object.entries(map).find(([, canon]) => String(canon) === String(page.test));
      if (srcTest) page.source_test = srcTest[0];
    }
  }
  const numberingConflicts = Object.entries(TEST_NUMBER_MAP).map(([book, map]) => ({
    kind: "test_numbering",
    book: Number(book),
    canonical: { system: "book-internal", tests: Object.values(map).map(String) },
    source: { system: "practicepteonline", tests: Object.keys(map), mapping: Object.fromEntries(Object.entries(map).map(([k, v]) => [k, String(v)])) },
    evidence: TEST_NUMBER_EVIDENCE[book] || [],
    ruling: "以原书内部编号为准（与 expected-manifest 一致）；网页原编号保留于 page.source_test",
  }));
  index.cross_source_conflicts = (index.cross_source_conflicts || []).concat(numberingConflicts);
  index.sources = sources;
  index.build_issues = issues;
  for (const it of issues) {
    index.gaps.push({ kind: it.kind, book: it.book, variant: it.variant, skill: it.skill, test: it.test, part: null, note: it.note });
  }
  index.stats = summarize(index);

  fs.mkdirSync(OUT_DIR, { recursive: true });
  writeJsonAtomic(OUT, index);

  const s = index.stats;
  console.log(`wrote ${rel(OUT)}`);
  console.log(`pages=${s.pages} groups=${s.groups} questions=${s.questions} answers=${s.answers} answer_groups=${s.answer_groups}`);
  console.log(`fully_complete=${s.fully_complete}/${s.questions}`);
  console.log(`content_status=${JSON.stringify(s.by_content_status)}`);
  console.log(`answer_status=${JSON.stringify(s.by_answer_status)}`);
  console.log(`classification=${JSON.stringify(s.by_classification_status)}`);
  console.log(`gaps_by_kind=${JSON.stringify(s.gaps_by_kind)}`);
  console.log(`official_verifications=${verification.applied.length} verification_issues=${verification.issues.length}`);
  for (const a of verification.applied) console.log(`  verified ${a.decision_id} ${a.group_id} range=${JSON.stringify(a.range)}`);
  for (const it of verification.issues) console.log(`  verification-issue ${it.kind} ${it.decision_id || ""} ${it.group_id || it.question_id || ""}`);
  console.log(`issues=${issues.length}`);
  for (const it of issues) console.log(`  issue ${it.kind} b${it.book}t${it.test} ${it.skill}: ${it.note}`);
}

main();
