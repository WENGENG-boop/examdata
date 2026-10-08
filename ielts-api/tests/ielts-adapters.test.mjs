// ielts-api/tests/ielts-adapters.test.mjs
// S05 acceptance tests for the cross-source adapters (ito / iprog / zhan / TaroFlink wrappers).
// Offline: every network path is exercised through the new opts injection (opts.html / opts.json);
// the ito answer-key regression uses the real saved raw page under ielts-data/raw (skipped if absent).
// Run: node --test ielts-api/tests/ielts-adapters.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { extractItoAnswerKey, listeningTest, __internals as itoInternals } from "../ito.mjs";
import { listeningAnswers, __internals as iprogInternals } from "../iprog.mjs";
import { index as zhanIndex, passage as zhanPassage, reading as zhanReading } from "../zhan.mjs";
import { listeningQA, listeningSegments } from "../ielts-api.mjs";
import { resolveDataDir } from "../data-store.mjs";

const { practiceSlugs, toText } = itoInternals;
const { extractAnswerTable } = iprogInternals;

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/* ============================== ito: pure key extraction ============================== */

test("ito A1: extractItoAnswerKey parses numbered lines, paired rows, and rejects headers/out-of-range", () => {
  const key = extractItoAnswerKey([
    "Answer Cam10 Listening Test 01",
    "Part 1",
    "1   Ardleigh",
    "6   beach / beaches",
    "11&12   A, C",
    "41 beyond range",
    "100 TOPICS",
    "8-9 Samples",
    "no leading number",
    "5",
  ].join("\n"));
  assert.deepEqual(key.map((k) => k.number), [1, 6, 11]);
  assert.equal(key[0].answer, "Ardleigh");
  assert.equal(key[0].paired, null);
  assert.equal(key[1].answer, "beach / beaches");
  assert.equal(key[2].answer, "A, C");
  assert.equal(key[2].paired, 12);
});

test("ito A2: extractItoAnswerKey dedups first-seen and ignores Part/Answer/Cam value lines", () => {
  const key = extractItoAnswerKey(["1 first", "1 second", "2 Answer", "3 Cam 10", "4 ok"].join("\n"));
  assert.deepEqual(key.map((k) => [k.number, k.answer]), [[1, "first"], [4, "ok"]]);
});

test("ito A3: practiceSlugs includes the -with-answer variant (real Cam10 practice slug)", () => {
  const slugs = practiceSlugs(10, 1);
  assert.ok(slugs.includes("practice-cam-10-listening-test-01-with-answer"));
  assert.ok(slugs.includes("practice-cam-10-listening-test-01-with-answer-and-audioscripts"));
});

/* ============================== ito: real raw regression ============================== */

function findItoRaw(slug) {
  const rawDir = path.join(resolveDataDir(), "raw", "ieltstrainingonline.com");
  if (!fs.existsSync(rawDir)) return null;
  for (const f of fs.readdirSync(rawDir)) {
    if (!f.endsWith(".meta.json")) continue;
    let meta;
    try { meta = JSON.parse(fs.readFileSync(path.join(rawDir, f), "utf8")); } catch { continue; }
    if (meta.slug !== slug || !meta.sha256) continue;
    const bodyPath = path.join(rawDir, meta.sha256 + ".body");
    if (!fs.existsSync(bodyPath)) continue;
    return { meta, bodyPath };
  }
  return null;
}

test("ito B1: real Cam10 T1 practice raw → 39 rows covering 40 questions with exact values", (t) => {
  const hit = findItoRaw("practice-cam-10-listening-test-01-with-answer");
  if (!hit) return t.skip("raw practice-cam-10-listening-test-01-with-answer not stored");
  const page = JSON.parse(fs.readFileSync(hit.bodyPath, "utf8"));
  const post = Array.isArray(page) ? page[0] : page;
  const text = toText(post.content.rendered);
  const ai = text.search(/\bAnswers?\s+(?:Cam|Cambridge|IELTS)/i);
  assert.ok(ai >= 0, "answer heading found");
  const key = extractItoAnswerKey(text.slice(ai));
  assert.equal(key.length, 39);
  assert.equal(key.reduce((n, k) => n + 1 + (k.paired ? 1 : 0), 0), 40, "covers 40 question numbers");
  const byNum = new Map(key.map((k) => [k.number, k]));
  assert.equal(byNum.get(1).answer, "Ardleigh");
  assert.equal(byNum.get(6).answer, "beach / beaches");
  assert.equal(byNum.get(7).answer, "2020");
  assert.equal(byNum.get(9).answer, "429");
  assert.equal(byNum.get(11).answer, "A, C");
  assert.equal(byNum.get(11).paired, 12);
  assert.equal(byNum.get(20).answer, "photo card / photo cards");
  assert.equal(byNum.get(40).answer, "expansion");
});

test("ito B2: listeningTest with injected raw html → answer_only contract + provenance", (t) => {
  const hit = findItoRaw("practice-cam-10-listening-test-01-with-answer");
  if (!hit) return t.skip("raw practice-cam-10-listening-test-01-with-answer not stored");
  const page = JSON.parse(fs.readFileSync(hit.bodyPath, "utf8"));
  const post = Array.isArray(page) ? page[0] : page;
  return listeningTest(10, 1, { html: post.content.rendered, slug: hit.meta.slug, title: "Practice Cam 10 Listening Test 01" }).then((r) => {
    assert.equal(r.ok, true);
    assert.equal(r.skill, "listening");
    assert.equal(r.answer_only, true);
    assert.equal(r.answer_count, 39);
    assert.equal(r.slug, hit.meta.slug);
    assert.ok(r.provenance && r.provenance.source === "ieltstrainingonline.com");
    assert.equal(r.provenance.slug, hit.meta.slug);
    assert.ok(typeof r.provenance.fetched === "string");
  });
});

test("ito B3: page without an answer heading does not fall back to question numbers", async () => {
  const html = "<p>SECTION 1</p><p>1 Write your name</p><p>2 Write a date</p>";
  const r = await listeningTest(10, 1, { html, slug: "practice-cam-10-listening-test-01", title: "no answers" });
  assert.equal(r.ok, true);
  assert.equal(r.answer_count, 0);
  assert.deepEqual(r.answer_key, []);
});

/* ============================== iprog ============================== */

test("iprog A1: extractAnswerTable picks the densest cell and maps 1..40 positions", () => {
  const cell = Array.from({ length: 40 }, (_, i) => `${i + 1}. answer${i + 1}`).join("<br>");
  const html = `<figure class="wp-block-table"><table><tr><td>junk</td><td>${cell}</td></tr></table></figure>`;
  const answers = extractAnswerTable(html);
  assert.equal(answers.length, 40);
  assert.equal(answers[0], "answer1");
  assert.equal(answers[39], "answer40");
  assert.deepEqual(extractAnswerTable("<table><tr><td>x</td></tr></table>"), []);
});

test("iprog A2: listeningAnswers opts.html → answer_only contract, numbered identity, no questions", async () => {
  const cell = Array.from({ length: 40 }, (_, i) => `${i + 1}. val${i + 1}`).join("<br>");
  const html = `<table><tr><td>${cell}</td></tr></table>`;
  const r = await listeningAnswers(3, 2, { html });
  assert.equal(r.ok, true);
  assert.equal(r.skill, "listening");
  assert.equal(r.answer_only, true);
  assert.deepEqual(r.questions, []);
  assert.equal(r.qa_complete, false);
  assert.equal(r.answer_count, 40);
  assert.deepEqual(r.answer_key_numbered[0], { number: 1, answer: "val1" });
  assert.deepEqual(r.answer_key_numbered[39], { number: 40, answer: "val40" });
  assert.ok(r.provenance && r.provenance.url.includes("cambridge-ielts-3-listening-test-2-answers"));
});

test("iprog A3: non-book-3 guard still rejects before any fetch", async () => {
  const r = await listeningAnswers(10, 1);
  assert.equal(r.ok, false);
  assert.match(r.error, /仅覆盖剑3/);
});

/* ============================== zhan ============================== */

test("zhan A1: index opts.html → tests map + answer_authority=false + close_reading provenance", async () => {
  const html = '<h2>剑雅 21 – Test1</h2><a data-ielts-row="101"></a><a data-ielts-row="102"></a><a data-ielts-row="103"></a>'
    + '<h2>剑雅 21 – Test2</h2><a data-ielts-row="201"></a>';
  const r = await zhanIndex(20, { html });
  assert.equal(r.ok, true);
  assert.deepEqual(r.tests.test1, [101, 102, 103]);
  assert.deepEqual(r.tests.test2, [201]);
  assert.equal(r.total, 4);
  assert.equal(r.answer_authority, false);
  assert.equal(r.close_reading, true);
  assert.equal(r.provenance.kind, "close_reading_translation");
});

test("zhan A2: passage opts.html → sentence pairs + answer_authority=false", async () => {
  const html = '<span class="phase" data-translation="这是译文。"><span class="text">This is the English sentence.</span></span>'
    + '<span class="phase" data-translation="第二句"><span class="text">Second sentence.</span></span>';
  const r = await zhanPassage(101, { html });
  assert.equal(r.ok, true);
  assert.equal(r.count, 2);
  assert.deepEqual(r.sentences[0], { en: "This is the English sentence.", zh: "这是译文。" });
  assert.equal(r.answer_authority, false);
  assert.equal(r.close_reading, true);
  assert.equal(r.provenance.kind, "close_reading_translation");
});

test("zhan A3: reading passes opts through index and passage (combined fixture)", async () => {
  const html = '<h2>剑雅 20 – Test1</h2><a data-ielts-row="555"></a>'
    + '<span class="phase" data-translation="译"><span class="text">En.</span></span>';
  const r = await zhanReading(20, 1, 1, { html });
  assert.equal(r.ok, true);
  assert.equal(r.book, 20);
  assert.equal(r.test, 1);
  assert.equal(r.passage, 1);
  assert.equal(r.section_id, 555);
  assert.deepEqual(r.sentences, [{ en: "En.", zh: "译" }]);
  assert.equal(r.answer_authority, false);
});

/* ============================== TaroFlink wrappers (ielts-api.mjs) ============================== */

test("tarof A1: listeningQA opts.json → number alias, unverified alignment, timestamps preserved", async () => {
  const master = {
    test_title: "Cambridge 16 Test 1",
    total_questions: 40,
    parts_count: 4,
    questions: [
      {
        q_num: 1, part: 1, type: "fill", instruction: "Write ONE WORD ONLY", prompt: "Name: …",
        options: null, target_answer: "Ardleigh", acceptable_variants: ["ardleigh"], distractors: ["Ardley"],
        timestamps: { start: 12.5, end: 15.2 }, acoustic_profile: { noise: "low" },
      },
      {
        q_num: 2, part: 1, type: "fill", instruction: "Write ONE WORD ONLY", prompt: "Buy a …",
        options: null, target_answer: "newspaper", acceptable_variants: [], distractors: [],
        timestamps: null, acoustic_profile: null,
      },
    ],
  };
  const qa = await listeningQA(16, 1, { json: master });
  assert.equal(qa.ok, true);
  assert.equal(qa.skill, "listening");
  assert.equal(qa.questions.length, 2);
  assert.equal(qa.questions[0].number, 1);
  assert.equal(qa.questions[0].q_num, 1);
  assert.equal(qa.questions[0].alignment_status, "unverified");
  assert.deepEqual(qa.questions[0].timestamps, { start: 12.5, end: 15.2 });
  assert.deepEqual(qa.questions[0].acceptable, ["ardleigh"]);
  assert.equal(qa.questions[0].answer, "Ardleigh");
  assert.equal(qa.provenance.alignment, "unverified");
  assert.equal(qa.provenance.path, "data/ielts_16_test_1/ielts_16_test_1_master.json");
  assert.match(qa.provenance.note, /S10/);
});

test("tarof A2: listeningSegments opts.json → unverified alignment + provenance", async () => {
  const seg = {
    source: "reader c16 l2",
    audio: "https://example.invalid/audio.mp3",
    practice_unit: "unit-16-2",
    segments: [
      { id: 0, start: 1.5, speaker: "A", en: "Hello", zh: "你好", words: [{ w: "Hello", s: 1.5 }] },
    ],
  };
  const r = await listeningSegments(16, 1, 2, { json: seg });
  assert.equal(r.ok, true);
  assert.equal(r.label, "reader c16 l2");
  assert.equal(r.segments[0].en, "Hello");
  assert.equal(r.alignment_status, "unverified");
  assert.equal(r.provenance.alignment, "unverified");
  assert.equal(r.provenance.path, "data/listening/c16-test1-l2.json");
});
