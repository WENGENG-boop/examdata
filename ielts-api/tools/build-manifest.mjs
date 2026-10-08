#!/usr/bin/env node
// ielts-api/tools/build-manifest.mjs
// S02: build data/expected-manifest.json from local evidence (no network).
//
// Inputs (all local):
//   - ielts-api/catalog.mjs                         (book identity + GT rulings)
//   - ielts-api/data/expected-structure.json        (curated S02 probe tables)
//   - ielts-data/runs/<run>/evidence/pdf-answer-keys.json   (v5 extraction)
//   - tmp_audit_ielts/completeness_20261003/pte-*.json      (PTE web snapshots)
//   - tmp_audit_ielts/completeness_20261003/cam21-*.json    (book-21 web snapshots)
// Outputs:
//   - ielts-api/data/expected-manifest.json
//   - ielts-data/runs/<run>/evidence/expected-manifest.json (copy)
//   - ielts-api/data/printed-pages.json                     (page-number cache)

import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { SERIES, RUN_ID, BOOKS, bookEntry } from "../catalog.mjs";
import { makeId, validateManifest, computeCoverage } from "../schema.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const API = path.resolve(__dirname, "..");
const REPO = path.resolve(API, "..");
const RUN = path.join(REPO, "ielts-data", "runs", RUN_ID);
const EVID = path.join(RUN, "evidence");
const SCRATCH = path.join(RUN, "scratch");
const SNAP = path.join(REPO, "tmp_audit_ielts", "completeness_20261003");

const STRUCTURE = path.join(API, "data", "expected-structure.json");
const OUT_API = path.join(API, "data", "expected-manifest.json");
const OUT_EVID = path.join(EVID, "expected-manifest.json");
const OUT_PRINTED = path.join(API, "data", "printed-pages.json");

// extraction completeness from the S02 v5 answer-key run
const EXTRACTION = {
  1: "complete", 3: "complete", 4: "complete", 5: "complete", 6: "complete",
  7: "complete", 8: "complete", 11: "complete", 12: "complete", 14: "complete",
  17: "complete",
  2: "partial", 10: "partial", 13: "partial", 15: "partial",
  9: "none", 16: "none", 18: "none", 19: "none", 20: "none", 21: "none",
};
const EXTRACTION_NOTES = {
  2: "v5: reading only; no listening / no GT extracted",
  10: "v5: T2L missing 11-20; T2R only 27-40; T4R declared 26; gt_a only 15-27",
  13: "v5: T1L only 11-40; T2L only 11-40; T3R only 1-26; T4L only 11-40",
  15: "v5: T1L/T1R/T2R/T4R only 26-30 numbers each",
  9: "no text layer", 16: "no text layer", 18: "no text layer", 19: "no text layer",
  20: "no text layer; local PDF is a 34-page Test-1 booklet",
  21: "no local PDF; web snapshots only",
};

function readJson(p) {
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

function sha256File(p) {
  return new Promise((resolve, reject) => {
    const h = crypto.createHash("sha256");
    const s = fs.createReadStream(p, { highWaterMark: 4 * 1024 * 1024 });
    s.on("data", (d) => h.update(d));
    s.on("end", () => resolve(h.digest("hex")));
    s.on("error", reject);
  });
}

function expand(ranges) {
  const out = [];
  for (const [a, b] of ranges || []) for (let n = a; n <= b; n++) out.push(n);
  return out;
}

function evidSource(book, variant, skill) {
  if (skill === "listening") {
    return [15, 17].includes(book) ? "evidence/listening-sections-b1517.json" : "evidence/listening-sections.json";
  }
  if (variant === "general") return "evidence/reading-sections.json (GT band) + probe-gt";
  if (skill === "reading") return "evidence/reading-sections.json";
  return "evidence/probe-w";
}

function makeItem({ book, edition, variant, skill, test, test_index, part, ranges, pages, status, reason, note, source, assets }) {
  const b = bookEntry(book);
  const expected_numbers = expand(ranges);
  const evidence = [];
  if (Array.isArray(pages)) {
    for (const p of pages) evidence.push({ file_page: p, printed_page: null, source, note: p == null ? note || "page unconfirmed" : null });
  }
  if (note && !pages?.length) evidence.push({ file_page: null, printed_page: null, source, note });
  const item = {
    id: makeId(book, variant, skill, test, part, edition),
    book, edition, variant, skill,
    test, test_index,
    part,
    expected_numbers,
    expected_groups: [],
    expected_assets: assets || [],
    evidence,
    status,
    reason: reason || null,
  };
  if (pages && pages.some((p) => p == null)) item.page_unconfirmed = true;
  if (!evidence.length && status === "verified") item.evidence = [{ file_page: null, printed_page: null, source, note: "missing evidence" }];
  return item;
}

async function main() {
  const structure = readJson(STRUCTURE);
  const v5 = readJson(path.join(EVID, "pdf-answer-keys.json"));
  const booksOut = [];
  const allPairs = new Map(); // "book:page" -> {book, page}

  for (const sb of structure.books) {
    const book = sb.book;
    const cat = bookEntry(book);
    const edition = cat.edition;
    const items = [];

    for (const t of sb.tests) {
      const tToken = String(t.test);
      // listening
      for (const p of t.listening.parts) {
        items.push(makeItem({
          book, edition, variant: "shared", skill: "listening", test: tToken, test_index: t.test_index,
          part: p.part, ranges: p.ranges, pages: p.pages, status: t.listening.status,
          reason: t.listening.reason, note: p.note, source: evidSource(book, "shared", "listening"),
        }));
      }
      // academic reading
      for (const p of t.academic_reading.parts) {
        items.push(makeItem({
          book, edition, variant: "academic", skill: "reading", test: tToken, test_index: t.test_index,
          part: p.part, ranges: p.ranges, pages: p.pages, status: t.academic_reading.status,
          reason: t.academic_reading.reason, source: evidSource(book, "academic", "reading"),
        }));
      }
      // academic writing
      for (const task of t.academic_writing.tasks) {
        items.push(makeItem({
          book, edition, variant: "academic", skill: "writing", test: tToken, test_index: t.test_index,
          part: task.part, ranges: [], pages: task.pages, status: t.academic_writing.status,
          reason: t.academic_writing.reason, source: evidSource(book, "academic", "writing"),
        }));
      }
      // speaking
      for (const p of t.speaking.parts) {
        items.push(makeItem({
          book, edition, variant: "shared", skill: "speaking", test: tToken, test_index: t.test_index,
          part: p.part, ranges: [], pages: p.pages, status: t.speaking.status,
          reason: t.speaking.reason, source: evidSource(book, "shared", "speaking"),
        }));
      }
    }

    // general
    for (const g of sb.general.tests) {
      for (const p of g.reading.parts) {
        items.push(makeItem({
          book, edition, variant: "general", skill: "reading", test: g.test, test_index: g.test_index,
          part: p.part, ranges: p.ranges, pages: p.pages, status: g.reading.status,
          reason: g.reading.reason, source: evidSource(book, "general", "reading"),
        }));
      }
      for (const task of g.writing.tasks) {
        items.push(makeItem({
          book, edition, variant: "general", skill: "writing", test: g.test, test_index: g.test_index,
          part: task.part, ranges: [], pages: task.pages, status: g.writing.status,
          reason: g.writing.reason, note: g.writing.note, source: evidSource(book, "general", "writing"),
        }));
      }
    }

    // expected assets (S02 seed; extended in later stages)
    if (book === 1) {
      const it = items.find((i) => i.variant === "shared" && i.skill === "listening" && i.test === "2" && i.part === "P4");
      if (it) it.expected_assets.push({ id: "b1-t2-l-p4-diagram", kind: "diagram", note: "Questions 40-41 Complete the diagram (evidence p45)" });
    }

    // collect pages for printed-page resolution
    for (const it of items) for (const e of it.evidence) if (e.file_page != null) allPairs.set(`${book}:${e.file_page}`, { book, page: e.file_page });

    const v5b = v5[String(book)];
    const extraction = { status: EXTRACTION[book], note: EXTRACTION_NOTES[book] || null };
    if (v5b) {
      extraction.v5 = {
        pdf_sha256: v5b.pdf_sha256, pdf_pages: v5b.pdf_pages,
        key_pages: v5b.key_pages, anomalies: v5b.anomalies || [],
        tests: Object.fromEntries(Object.entries(v5b.tests || {}).map(([k, t]) => [k, Object.fromEntries(Object.entries(t).map(([sk, e]) => [sk, {
          numbers: (e.numbers || []).length, declared: (e.declared_numbers || []).length, pages: e.pages,
        }]))])),
      };
    }

    booksOut.push({
      book, edition,
      source: cat.source,
      pdf: cat.pdf ? { relpath: cat.pdf.relpath, sha256: cat.pdf.sha256, pages: cat.pdf.pages } : null,
      text_layer: cat.text_layer,
      note: cat.note || null,
      items,
      general: { status: sb.general.status, reason: sb.general.reason || null, probe: sb.general.probe || null, tests: sb.general.tests.map((g) => g.test) },
      extraction,
    });
  }

  // ---------------------------------------------------------- printed pages
  fs.mkdirSync(SCRATCH, { recursive: true });
  const pairs = [...allPairs.values()].filter((p) => {
    const c = bookEntry(p.book);
    return c.pdf && fs.existsSync(path.join(REPO, c.pdf.relpath));
  }).map((p) => ({ key: `${p.book}:${p.page}`, pdf: path.join(REPO, bookEntry(p.book).pdf.relpath).replace(/\\/g, "/"), page: p.page }));
  let printed = {};
  let printedStatus = "not_run";
  const itemsPath = path.join(SCRATCH, "printed-pages-items.json");
  const outPath = path.join(SCRATCH, "printed-pages-out.json");
  fs.writeFileSync(itemsPath, JSON.stringify({ items: pairs }));
  const py = path.join(REPO, "examdata", ".venv", "Scripts", "python.exe");
  try {
    execFileSync(fs.existsSync(py) ? py : "python", [path.join(API, "tools", "printed_page.py"), itemsPath, outPath], {
      env: { ...process.env, PYTHONIOENCODING: "utf-8" }, stdio: "pipe",
    });
    const res = readJson(outPath);
    printed = res.results || {};
    printedStatus = res.ok ? "ok" : "failed";
  } catch (e) {
    printedStatus = "failed";
    console.error("printed_page.py failed:", e.message);
  }
  // merge printed numbers into evidence
  for (const b of booksOut) {
    for (const it of b.items) {
      for (const e of it.evidence) {
        if (e.file_page != null) {
          const r = printed[`${b.book}:${e.file_page}`];
          if (r && r.chosen != null) e.printed_page = r.chosen;
        }
      }
    }
  }
  fs.writeFileSync(OUT_PRINTED, JSON.stringify({ status: printedStatus, generated_at_utc: new Date().toISOString(), pairs: pairs.length, results: printed }, null, 1));

  // ---------------------------------------------------------- pdf hash verification
  const hashChecks = [];
  for (const b of booksOut) {
    if (!b.pdf) continue;
    const abs = path.join(REPO, b.pdf.relpath);
    if (!fs.existsSync(abs)) {
      hashChecks.push({ book: b.book, relpath: b.pdf.relpath, status: "file_missing", catalog_sha256: b.pdf.sha256, actual_sha256: null, v5_sha256: b.extraction.v5 ? b.extraction.v5.pdf_sha256 : null });
      continue;
    }
    const actual = await sha256File(abs);
    const v5sha = b.extraction.v5 ? b.extraction.v5.pdf_sha256 : null;
    hashChecks.push({
      book: b.book, relpath: b.pdf.relpath,
      status: actual === b.pdf.sha256 ? "match" : "mismatch",
      catalog_sha256: b.pdf.sha256, actual_sha256: actual, v5_sha256: v5sha,
      v5_match: v5sha == null ? null : v5sha === actual,
    });
  }

  // ---------------------------------------------------------- v5 number cross-check
  const curatedIndex = new Map(); // "book|variant|skill|test" -> numbers[]
  for (const b of booksOut) {
    for (const it of b.items) {
      const k = `${b.book}|${it.variant}|${it.skill}|${String(it.test)}`;
      if (!curatedIndex.has(k)) curatedIndex.set(k, []);
      curatedIndex.get(k).push(...it.expected_numbers);
    }
  }
  const v5Checks = [];
  for (const [bk, b] of Object.entries(v5)) {
    const book = Number(bk);
    const severity = EXTRACTION[book] === "complete" ? "error" : "note";
    for (const [tKey, t] of Object.entries(b.tests || {})) {
      for (const [sk, e] of Object.entries(t)) {
        let variant = sk === "listening" ? "shared" : "academic";
        let test = tKey;
        if (tKey === "gt" || tKey === "gt_a") { variant = "general"; test = "gta"; }
        if (tKey === "gt_b") { variant = "general"; test = "gtb"; }
        const curated = curatedIndex.get(`${book}|${variant}|${sk === "listening" ? "listening" : sk === "reading" ? "reading" : sk}|${test}`);
        const v5nums = new Set(e.numbers || []);
        const curSet = new Set(curated || []);
        const missingInV5 = [...curSet].filter((n) => !v5nums.has(n)).sort((a, b2) => a - b2);
        const extraInV5 = [...v5nums].filter((n) => !curSet.has(n)).sort((a, b2) => a - b2);
        v5Checks.push({
          book, test: tKey, skill: sk, variant, curated_key_test: test,
          curated_count: curSet.size, v5_count: v5nums.size,
          v5_declared: (e.declared_numbers || []).length,
          missing_in_v5: missingInV5, extra_in_v5: extraInV5,
          severity: (missingInV5.length || extraInV5.length) ? severity : "ok",
          curated_available: curated != null,
        });
      }
    }
  }

  // ---------------------------------------------------------- web snapshot cross-checks
  const cam21Checks = [];
  for (let t = 1; t <= 4; t++) {
    for (const sk of ["reading", "listening"]) {
      const f = path.join(SNAP, `cam21-${t}-${sk}.json`);
      if (!fs.existsSync(f)) { cam21Checks.push({ book: 21, test: t, skill: sk, status: "missing_snapshot" }); continue; }
      const d = readJson(f);
      cam21Checks.push({
        book: 21, test: t, skill: sk, status: d.ok ? "ok" : "not_ok",
        via: d.via, questions: (d.questions || []).length, answers: (d.answer_key || []).length,
        counts: d.counts || null,
        severity: "note",
      });
    }
  }
  const pteChecks = [];
  for (const f of fs.readdirSync(SNAP)) {
    const m = /^pte-(\d+)-(\d+)-(reading|listening)\.json$/.exec(f);
    if (!m) continue;
    const d = readJson(path.join(SNAP, f));
    pteChecks.push({
      book: Number(m[1]), test: Number(m[2]), skill: m[3],
      status: d.ok ? "ok" : "not_ok",
      questions: d.question_count ?? (d.questions || []).length,
      answers: d.answer_count ?? (d.answer_key || []).length,
      missing: d.questions_missing || [],
      title: d.title || null,
      severity: "note",
    });
  }
  pteChecks.sort((a, b) => a.book - b.book || a.test - b.test || a.skill.localeCompare(b.skill));

  // ---------------------------------------------------------- variant rulings
  const variantRulings = BOOKS.map((b) => ({
    book: b.book,
    question: "does this book contain a General Training variant (reading/writing)?",
    ruling: b.gt.status,
    reason: b.gt.reason || (b.gt.status === "in_book" ? "GT material located in book body" : null),
    evidence: b.gt.evidence || null,
    tests: b.gt.tests || [],
  }));

  // ---------------------------------------------------------- assemble + validate
  const manifest = {
    schema: "ielts.expected-manifest/1",
    series: SERIES,
    run_id: RUN_ID,
    generated_at_utc: new Date().toISOString(),
    generated_by: "ielts-api/tools/build-manifest.mjs",
    books: booksOut,
    variant_rulings: variantRulings,
    cross_checks: {
      pdf_hash: hashChecks,
      v5_numbers: v5Checks,
      cam21_web: cam21Checks,
      pte_web: pteChecks,
      printed_pages: { status: printedStatus, pairs: pairs.length },
    },
  };
  const v = validateManifest(manifest);
  manifest.validation = { ok: v.ok, errors: v.errors, warnings: v.warnings };
  manifest.coverage = v.coverage;

  fs.mkdirSync(path.dirname(OUT_API), { recursive: true });
  fs.writeFileSync(OUT_API, JSON.stringify(manifest, null, 1));
  fs.mkdirSync(EVID, { recursive: true });
  fs.writeFileSync(OUT_EVID, JSON.stringify(manifest, null, 1));

  const nItems = booksOut.reduce((n, b) => n + b.items.length, 0);
  console.log(JSON.stringify({
    out_api: OUT_API, out_evidence: OUT_EVID,
    books: booksOut.length, items: nItems,
    validation_ok: v.ok, errors: v.errors.length, warnings: v.warnings.length,
    coverage: manifest.coverage.by_skill,
    complete_books: manifest.coverage.complete_books,
    incomplete_books: manifest.coverage.incomplete_books,
    pdf_hash: hashChecks.map((h) => h.status),
    printed_pages: printedStatus,
  }, null, 1));
  if (!v.ok) {
    console.error("VALIDATION ERRORS:");
    for (const e of v.errors.slice(0, 40)) console.error(" -", e);
    process.exitCode = 1;
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
