// ielts-api/tests/ielts-manifest.test.mjs
// S02 acceptance tests for the expected-manifest pipeline.
// Run: node --test ielts-api/tests/ielts-manifest.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { validateManifest, validateQuestionNumber, isBookComplete, makeId, computeCoverage } from "../schema.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "data", "expected-manifest.json"), "utf8"));

function bookOf(n) {
  return manifest.books.find((b) => b.book === n);
}
function nums(items) {
  return items.flatMap((i) => i.expected_numbers);
}

// ---------------------------------------------------------------- book-1 anomalies
test("book 1 test 2 listening has 41 questions; Q41 valid, Q42 invalid", () => {
  const items = bookOf(1).items.filter((i) => i.skill === "listening" && i.test === "2");
  assert.equal(nums(items).length, 41);
  assert.equal(validateQuestionNumber(manifest, 1, "shared", "listening", "2", 41).ok, true);
  assert.equal(validateQuestionNumber(manifest, 1, "shared", "listening", "2", 42).ok, false);
});

test("book 1 test 3 listening has 42 questions; T1/T4 also 41/42", () => {
  const t3 = bookOf(1).items.filter((i) => i.skill === "listening" && i.test === "3");
  assert.equal(nums(t3).length, 42);
  assert.equal(validateQuestionNumber(manifest, 1, "shared", "listening", "3", 42).ok, true);
  assert.equal(validateQuestionNumber(manifest, 1, "shared", "listening", "3", 43).ok, false);
  const t1 = bookOf(1).items.filter((i) => i.skill === "listening" && i.test === "1");
  assert.equal(nums(t1).length, 41);
  const t4 = bookOf(1).items.filter((i) => i.skill === "listening" && i.test === "4");
  assert.equal(nums(t4).length, 42);
});

test("book 1 reading deltas: T2=41, T3=38, T4=39", () => {
  const totals = {};
  for (const t of ["1", "2", "3", "4"]) {
    totals[t] = nums(bookOf(1).items.filter((i) => i.skill === "reading" && i.test === t)).length;
  }
  assert.deepEqual(totals, { 1: 40, 2: 41, 3: 38, 4: 39 });
  assert.equal(validateQuestionNumber(manifest, 1, "academic", "reading", "2", 41).ok, true);
});

// ---------------------------------------------------------------- specific structures
test("book 2 test 1 reading: 13/14-27/28-40, total 40", () => {
  const items = bookOf(2).items.filter((i) => i.skill === "reading" && i.test === "1");
  const byPart = Object.fromEntries(items.map((i) => [i.part, [i.expected_numbers[0], i.expected_numbers.at(-1)]]));
  assert.deepEqual(byPart, { P1: [1, 13], P2: [14, 27], P3: [28, 40] });
  assert.equal(nums(items).length, 40);
  assert.equal(validateQuestionNumber(manifest, 2, "academic", "reading", "1", 41).ok, false);
});

test("book 3 test 3 reading: 1-12/13-25/26-40", () => {
  const items = bookOf(3).items.filter((i) => i.skill === "reading" && i.test === "3");
  const byPart = Object.fromEntries(items.map((i) => [i.part, [i.expected_numbers[0], i.expected_numbers.at(-1)]]));
  assert.deepEqual(byPart, { P1: [1, 12], P2: [13, 25], P3: [26, 40] });
});

test("book 12 uses tests 5-8 with test_index 1-4", () => {
  const b = bookOf(12);
  const pairs = [...new Set(b.items.map((i) => `${i.test}/${i.test_index}`))].sort();
  assert.deepEqual(pairs, ["5/1", "6/2", "7/3", "8/4"]);
});

test("book 1 general training exists with 41-question reading", () => {
  const items = bookOf(1).items.filter((i) => i.variant === "general");
  assert.equal(nums(items.filter((i) => i.skill === "reading")).length, 41);
  assert.equal(bookOf(1).general.status, "in_book");
});

test("book 1 test 2 listening part 4 carries the diagram asset", () => {
  const it = bookOf(1).items.find((i) => i.skill === "listening" && i.test === "2" && i.part === "P4");
  assert.equal(it.expected_assets.length, 1);
  assert.equal(it.expected_assets[0].kind, "diagram");
});

// ---------------------------------------------------------------- variant rules
test("all listening items are variant=shared; 84 listening units", () => {
  const units = new Set();
  for (const b of manifest.books) {
    for (const i of b.items.filter((x) => x.skill === "listening")) {
      assert.equal(i.variant, "shared");
      units.add(`${b.book}:${i.test}`);
    }
  }
  assert.equal(units.size, 84);
});

test("academic/general isolation: books 11-17 have no general items", () => {
  for (const n of [11, 12, 13, 14, 15, 17]) {
    const b = bookOf(n);
    assert.equal(b.items.filter((i) => i.variant === "general").length, 0, `book ${n}`);
    assert.equal(b.general.status, "not_in_book", `book ${n}`);
  }
  for (const n of [1, 2, 3, 4, 5, 6, 7, 8, 10]) {
    const b = bookOf(n);
    assert.ok(b.items.filter((i) => i.variant === "general").length > 0, `book ${n}`);
    assert.equal(b.general.status, "in_book", `book ${n}`);
  }
});

// ---------------------------------------------------------------- unverified denominator
test("books 9/16/18/19/20/21 keep full denominator with unverified items", () => {
  for (const n of [9, 16, 18, 19, 20, 21]) {
    const b = bookOf(n);
    assert.equal(b.items.length, 40, `book ${n}`);
    assert.ok(b.items.every((i) => i.status === "unverified"), `book ${n}`);
    assert.equal(nums(b.items.filter((i) => i.skill === "listening")).length, 160, `book ${n}`);
    assert.equal(isBookComplete(manifest, n), false, `book ${n}`);
  }
});

test("book 20 tests 2-4 exist and are unverified", () => {
  const b = bookOf(20);
  for (const t of ["2", "3", "4"]) {
    const items = b.items.filter((i) => i.test === t);
    assert.equal(items.length, 10, `T${t}`);
    assert.ok(items.every((i) => i.status === "unverified"), `T${t}`);
  }
});

test("book 21 has 4x10 unverified items with standard numbers", () => {
  const b = bookOf(21);
  assert.equal(b.items.length, 40);
  assert.ok(b.items.every((i) => i.status === "unverified" && i.reason === "no_local_pdf"));
  assert.equal(nums(b.items.filter((i) => i.skill === "listening" && i.test === "1")).length, 40);
});

// ---------------------------------------------------------------- coverage
test("coverage: unit counts and question denominators", () => {
  const c = manifest.coverage;
  assert.equal(c.by_skill.shared_listening.expected_units, 84);
  assert.equal(c.by_skill.shared_listening.verified_units, 60);
  assert.equal(c.by_skill.academic_reading.expected_units, 84);
  assert.equal(c.by_skill.general_reading.expected_units, 17);
  assert.equal(c.by_skill.general_reading.verified_units, 17);
  assert.equal(c.by_skill.academic_writing.expected_units, 84);
  assert.equal(c.by_skill.shared_speaking.expected_units, 84);
  assert.equal(c.questions_expected.shared_listening, 3366);
  assert.equal(c.questions_expected.academic_reading, 3358);
  assert.equal(c.questions_expected.general_reading, 681);
  assert.equal(c.questions_expected.academic_writing, 0);
  assert.equal(c.questions_expected.shared_speaking, 0);
});

test("complete books are exactly the 11 expected", () => {
  assert.deepEqual(manifest.coverage.complete_books, [1, 3, 4, 5, 6, 7, 8, 11, 12, 14, 17]);
  assert.equal(isBookComplete(manifest, 11), true);
  assert.equal(isBookComplete(manifest, 9), false);
  assert.equal(isBookComplete(manifest, 10), false); // extraction partial
});

// ---------------------------------------------------------------- manifest integrity
test("manifest validates clean; warnings only for page-unconfirmed items", () => {
  const v = validateManifest(manifest);
  assert.equal(v.ok, true, JSON.stringify(v.errors.slice(0, 5)));
  assert.equal(v.errors.length, 0);
  assert.equal(v.warnings.length, 3);
  assert.ok(v.warnings.every((w) => w.includes("no confirmed page evidence")));
});

test("item ids unique; every book has an edition", () => {
  const ids = new Set();
  for (const b of manifest.books) {
    assert.ok(b.edition && b.edition.length > 2, `book ${b.book}`);
    for (const i of b.items) {
      assert.ok(!ids.has(i.id), `duplicate ${i.id}`);
      ids.add(i.id);
    }
  }
  assert.equal(ids.size, 925);
});

test("pdf hash cross-check: all 20 local pdfs match catalog sha256", () => {
  const checks = manifest.cross_checks.pdf_hash;
  assert.equal(checks.length, 20);
  assert.ok(checks.every((c) => c.status === "match"));
  assert.ok(checks.every((c) => c.v5_match === true));
});

test("v5 number cross-check: no errors on complete-extraction books", () => {
  const errs = manifest.cross_checks.v5_numbers.filter((c) => c.severity === "error");
  assert.deepEqual(errs, []);
  const notes = manifest.cross_checks.v5_numbers.filter((c) => c.severity === "note");
  assert.ok(notes.every((c) => [10, 13, 15].includes(c.book)));
});

test("web snapshots recorded: 8 cam21, 168 pte", () => {
  assert.equal(manifest.cross_checks.cam21_web.length, 8);
  assert.equal(manifest.cross_checks.pte_web.length, 168);
  assert.equal(manifest.cross_checks.pte_web.filter((p) => p.status !== "ok").length, 3);
});

// ---------------------------------------------------------------- schema rejection cases
function baseItem(over = {}) {
  const it = {
    id: makeId(1, "shared", "listening", "1", "P1", "c1-test"),
    book: 1, edition: "c1-test", variant: "shared", skill: "listening", test: "1", test_index: 1,
    part: "P1", expected_numbers: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    expected_groups: [], expected_assets: [],
    evidence: [{ file_page: 10, source: "test" }], status: "verified", reason: null,
  };
  return { ...it, ...over };
}
function baseManifest(items, extra = {}) {
  return { books: [{ book: 1, edition: "c1-test", items, extraction: { status: "complete" }, general: { status: "not_in_book" }, ...extra }] };
}

test("schema rejects duplicate item ids", () => {
  const v = validateManifest(baseManifest([baseItem(), baseItem()]));
  assert.equal(v.ok, false);
  assert.ok(v.errors.some((e) => e.includes("duplicate item id")));
});

test("schema rejects overlapping parts", () => {
  const v = validateManifest(baseManifest([
    baseItem(),
    baseItem({ id: makeId(1, "shared", "listening", "1", "P2", "c1-test"), part: "P2", expected_numbers: [5, 6, 7, 8, 9, 10, 11, 12, 13, 14] }),
  ]));
  assert.equal(v.ok, false);
  assert.ok(v.errors.some((e) => e.includes("overlapping question number")));
});

test("schema rejects gaps in the union of parts", () => {
  const v = validateManifest(baseManifest([
    baseItem(),
    baseItem({ id: makeId(1, "shared", "listening", "1", "P2", "c1-test"), part: "P2", expected_numbers: [12, 13, 14, 15, 16, 17, 18, 19, 20, 21] }),
  ]));
  assert.equal(v.ok, false);
  assert.ok(v.errors.some((e) => e.includes("not contiguous from 1")));
});

test("schema rejects non-gap-free item numbers", () => {
  const v = validateManifest(baseManifest([baseItem({ expected_numbers: [1, 2, 3, 5, 6] })]));
  assert.equal(v.ok, false);
  assert.ok(v.errors.some((e) => e.includes("not gap-free")));
});

test("schema rejects dangling group->asset references", () => {
  const v = validateManifest(baseManifest([baseItem({
    expected_groups: [{ id: "g1", asset_ref: "nope", parts: ["P1"] }],
  })]));
  assert.equal(v.ok, false);
  assert.ok(v.errors.some((e) => e.includes("references unknown asset")));
});

test("schema rejects invalid part inside group", () => {
  const v = validateManifest(baseManifest([baseItem({
    expected_groups: [{ id: "g1", parts: ["P7"] }],
  })]));
  assert.equal(v.ok, false);
  assert.ok(v.errors.some((e) => e.includes("references invalid part")));
});

test("schema rejects verified items without evidence", () => {
  const v = validateManifest(baseManifest([baseItem({ evidence: [] })]));
  assert.equal(v.ok, false);
  assert.ok(v.errors.some((e) => e.includes("verified without evidence")));
});

test("schema rejects wrong skill-part combinations", () => {
  const v = validateManifest(baseManifest([
    baseItem({ id: makeId(1, "academic", "reading", "1", "P4", "c1-test"), variant: "academic", skill: "reading", part: "P4" }),
  ]));
  assert.equal(v.ok, false);
  assert.ok(v.errors.some((e) => e.includes("invalid for skill reading")));
});

test("schema rejects variant/skill mismatch", () => {
  const v = validateManifest(baseManifest([baseItem({ variant: "academic" })]));
  assert.equal(v.ok, false);
  assert.ok(v.errors.some((e) => e.includes("not allowed for skill listening")));
});

test("schema rejects illegal status", () => {
  const v = validateManifest(baseManifest([baseItem({ status: "done" })]));
  assert.equal(v.ok, false);
  assert.ok(v.errors.some((e) => e.includes("illegal status")));
});

test("computeCoverage counts units and question denominators", () => {
  const c = computeCoverage(baseManifest([baseItem()]));
  assert.equal(c.by_skill.shared_listening.expected_units, 1);
  assert.equal(c.by_skill.shared_listening.verified_units, 1);
  assert.equal(c.questions_expected.shared_listening, 10);
});
