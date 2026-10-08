#!/usr/bin/env node
// ielts-api/tools/import-pdf.mjs
// S06: import a pdf_extract.py extraction into the ielts-data store with provenance.
//
// Runs the extraction through pdf-adapter.mjs (or reuses an existing extract JSON),
// then persists, under the data root (default ielts-data/, override EXAMDATA_IELTS_DATA_DIR):
//
//   derived/pdf/<book>/<pdf_sha8>/extract-<pages8>.json     canonical extraction copy
//   derived/pdf/<book>/<pdf_sha8>/provenance-<pages8>.json  per-import provenance record
//   derived/pdf/<book>/<pdf_sha8>/assets/*.png              rendered figure assets (when given)
//   raw/pdf-extract/<sha256>.body(.meta.json)               content-addressed extract JSON
//   raw/pdf-ocr/<sha256>.body(.meta.json)                   content-addressed OCR JSON (when given)
//   manifests/pdf-provenance.json                           append-merge provenance index
//   runs/<run>/evidence/import-pdf-<book>-<pages8>.json     evidence copy (when --run given)
//
// With --copy-pdf the source PDF is stored content-addressed under pdf/<sha256>.pdf;
// by default the PDF stays where it is and provenance records its path + sha256.
//
// Usage:
//   node ielts-api/tools/import-pdf.mjs --book 3 --pages 33-41,57-63,79-87,155,157,159 \
//        [--ocr-json PATH] [--assets-src DIR] [--textdir DIR] [--extract-json PATH] \
//        [--data-dir DIR] [--run RUN_ID] [--copy-pdf]

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  extractPdf,
  validateExtractDoc,
  sha256FileHex,
  parsePagesSpec,
  normalizePagesSpec,
} from "../pdf-adapter.mjs";
import {
  resolveDataDir,
  ensureLayout,
  storeRaw,
  storeBinaryFromFile,
  writeJsonAtomic,
  readJson,
  sanitizeSegment,
} from "../data-store.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const API = path.resolve(__dirname, "..");
const REPO = path.resolve(API, "..");

export class ImportPdfError extends Error {
  constructor(message, { code = "import_pdf_error", detail = null } = {}) {
    super(message);
    this.name = "ImportPdfError";
    this.code = code;
    if (detail !== null) this.detail = detail;
  }
}

function relTo(root, p) {
  const r = path.relative(root, p);
  return r.split(path.sep).join("/");
}

export function importPdf(opts = {}) {
  const root = resolveDataDir(opts.dataDir);
  ensureLayout(root);

  let doc;
  let extraction = null;
  let requestedPages;
  let pdfPath;
  let sha256;
  let pages;
  let missingPages;

  if (opts.extractJson) {
    const p = path.resolve(opts.extractJson);
    if (!fs.existsSync(p)) throw new ImportPdfError(`extract json not found: ${p}`, { code: "bad_input" });
    doc = JSON.parse(fs.readFileSync(p, "utf8"));
    requestedPages = opts.pages ? parsePagesSpec(normalizePagesSpec(opts.pages)) : null;
    ({ sha256, pages, missingPages } = validateExtractDoc(doc, { requestedPages }));
    pdfPath = doc.pdf.path;
    if (opts.verifyHash !== false && fs.existsSync(pdfPath)) {
      const fileHash = sha256FileHex(pdfPath);
      if (fileHash !== sha256) {
        throw new ImportPdfError(`pdf hash mismatch: file ${fileHash} != doc ${sha256}`, {
          code: "hash_mismatch",
        });
      }
    }
  } else {
    extraction = extractPdf({
      book: opts.book,
      pdf: opts.pdf,
      pages: opts.pages,
      out: opts.out,
      ocrJson: opts.ocrJson,
      textdir: opts.textdir,
      assets: opts.assetsDir,
      renderPages: opts.renderPages,
      minFigArea: opts.minFigArea,
      python: opts.python,
      script: opts.script,
    });
    ({ doc, pdfPath, sha256, requestedPages, pages, missingPages } = extraction);
  }

  if (missingPages && missingPages.length) {
    // extraction skipped pages outside the document — record, do not silently drop
    console.error(`warning: pages not returned by extractor: ${missingPages.join(",")}`);
  }

  const pagesSpec = (requestedPages || pages).join(",");
  const pages8 = crypto.createHash("sha256").update(pagesSpec).digest("hex").slice(0, 8);
  const sha8 = sha256.slice(0, 8);
  const bookLabel =
    opts.book !== undefined && opts.book !== null
      ? `book${opts.book}`
      : sanitizeSegment(path.basename(pdfPath, path.extname(pdfPath)), "book label");
  const baseDir = path.join(root, "derived", "pdf", bookLabel, sha8);
  fs.mkdirSync(baseDir, { recursive: true });

  // 1. canonical extraction copy (pretty JSON, deterministic bytes)
  const extractText = JSON.stringify(doc, null, 1);
  const extractOut = path.join(baseDir, `extract-${pages8}.json`);
  const prev = fs.existsSync(extractOut) ? fs.readFileSync(extractOut, "utf8") : null;
  if (prev !== extractText) fs.writeFileSync(extractOut, extractText, "utf8");

  // 2. content-addressed raw copies (extract + ocr)
  const raw = storeRaw({
    root,
    source: "pdf-extract",
    body: Buffer.from(extractText, "utf8"),
    meta: {
      kind: "pdf-extract",
      book: bookLabel,
      pdf_path: pdfPath,
      pdf_sha256: sha256,
      pages: requestedPages || pages,
      tool: doc.tool,
      tool_version: doc.version,
      ocr: Boolean(opts.ocrJson),
      derived_path: relTo(root, extractOut),
    },
  });
  let ocrRaw = null;
  if (opts.ocrJson) {
    const ocrPath = path.resolve(opts.ocrJson);
    if (!fs.existsSync(ocrPath)) throw new ImportPdfError(`ocr json not found: ${ocrPath}`, { code: "bad_input" });
    const ocrBody = fs.readFileSync(ocrPath);
    ocrRaw = storeRaw({
      root,
      source: "pdf-ocr",
      body: ocrBody,
      meta: {
        kind: "pdf-ocr",
        book: bookLabel,
        pdf_sha256: sha256,
        source_path: ocrPath,
        engine: JSON.parse(ocrBody.toString("utf8")).engine ?? null,
      },
    });
  }

  // 3. figure assets (rendered PNGs) into derived + content-addressed assets store
  const assetRecords = [];
  const missingAssets = [];
  const referencedAssets = new Set();
  for (const p of doc.pages || []) {
    for (const f of p.figures || []) if (f.asset) referencedAssets.add(path.basename(f.asset));
  }
  const assetsSrc = opts.assetsSrc || opts.assetsDir || null;
  if (referencedAssets.size) {
    if (!assetsSrc || !fs.existsSync(assetsSrc)) {
      missingAssets.push(...[...referencedAssets].sort());
      console.error(`warning: doc references ${referencedAssets.size} asset(s) but assets dir is missing`);
    } else {
      const assetDirOut = path.join(baseDir, "assets");
      fs.mkdirSync(assetDirOut, { recursive: true });
      for (const name of [...referencedAssets].sort()) {
        const src = path.join(assetsSrc, name);
        if (!fs.existsSync(src) || !fs.statSync(src).isFile()) {
          missingAssets.push(name);
          continue;
        }
        const stored = storeBinaryFromFile({ root, kind: "assets", ext: path.extname(name) || "png", filePath: src });
        const outPath = path.join(assetDirOut, name);
        if (!fs.existsSync(outPath) || sha256FileHex(outPath) !== stored.sha256) {
          fs.copyFileSync(src, outPath);
        }
        assetRecords.push({ name, sha256: stored.sha256, stored: relTo(root, stored.path), derived: relTo(root, outPath) });
      }
      if (missingAssets.length) {
        console.error(`warning: referenced assets not found in source dir: ${missingAssets.join(",")}`);
      }
    }
  }

  // 4. provenance record
  const provenance = {
    kind: "pdf-import",
    imported_at: new Date().toISOString(),
    book: bookLabel,
    pdf: { path: pdfPath, sha256 },
    pages: requestedPages || pages,
    returned_pages: pages,
    missing_pages: missingPages || [],
    tool: doc.tool,
    tool_version: doc.version,
    extract: { derived: relTo(root, extractOut), raw_sha256: raw.sha256, raw_body: relTo(root, raw.bodyPath) },
    ocr: opts.ocrJson
      ? { path: path.resolve(opts.ocrJson), raw_sha256: ocrRaw ? ocrRaw.sha256 : null, raw_body: ocrRaw ? relTo(root, ocrRaw.bodyPath) : null }
      : null,
    assets: assetRecords,
    missing_assets: missingAssets,
    pdf_stored: null,
  };
  if (opts.copyPdf) {
    const stored = storeBinaryFromFile({ root, kind: "pdf", ext: "pdf", filePath: pdfPath });
    provenance.pdf_stored = { sha256: stored.sha256, path: relTo(root, stored.path), deduped: stored.deduped };
  }
  const provPath = path.join(baseDir, `provenance-${pages8}.json`);
  writeJsonAtomic(provPath, provenance);

  // 5. append-merge provenance index
  const aggPath = path.join(root, "manifests", "pdf-provenance.json");
  const agg = readJson(aggPath, { missingOk: true }) || { version: 1, entries: [] };
  if (!Array.isArray(agg.entries)) agg.entries = [];
  const key = `${bookLabel}:${sha8}:${pages8}`;
  const idx = agg.entries.findIndex((e) => e.key === key);
  const entry = { key, ...provenance };
  if (idx >= 0) agg.entries[idx] = entry;
  else agg.entries.push(entry);
  writeJsonAtomic(aggPath, agg);

  // 6. optional run evidence copy
  let evidencePath = null;
  if (opts.runId) {
    const evDir = path.join(root, "runs", sanitizeSegment(opts.runId, "run id"), "evidence");
    fs.mkdirSync(evDir, { recursive: true });
    evidencePath = path.join(evDir, `import-pdf-${bookLabel}-${pages8}.json`);
    writeJsonAtomic(evidencePath, provenance);
  }

  return {
    root,
    baseDir,
    extractOut,
    provenancePath: provPath,
    evidencePath,
    provenance,
    rawSha256: raw.sha256,
    ocrRawSha256: ocrRaw ? ocrRaw.sha256 : null,
    assets: assetRecords,
    missingAssets,
    pdfPath,
    sha256,
    requestedPages: requestedPages || pages,
    pages,
    missingPages: missingPages || [],
  };
}

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    switch (a) {
      case "--book":
        args.book = Number(next());
        break;
      case "--pdf":
        args.pdf = next();
        break;
      case "--pages":
        args.pages = next();
        break;
      case "--out":
        args.out = next();
        break;
      case "--ocr-json":
        args.ocrJson = next();
        break;
      case "--assets-src":
        args.assetsDir = next();
        break;
      case "--textdir":
        args.textdir = next();
        break;
      case "--extract-json":
        args.extractJson = next();
        break;
      case "--data-dir":
        args.dataDir = next();
        break;
      case "--run":
        args.runId = next();
        break;
      case "--copy-pdf":
        args.copyPdf = true;
        break;
      default:
        throw new ImportPdfError(`unknown argument: ${a}`, { code: "bad_input" });
    }
  }
  if (!args.extractJson && !args.pages) {
    throw new ImportPdfError("need --pages (or --extract-json)", { code: "bad_input" });
  }
  return args;
}

const isMain =
  process.argv[1] && path.resolve(process.argv[1]).toLowerCase() === fileURLToPath(import.meta.url).toLowerCase();
if (isMain) {
  try {
    const res = importPdf(parseArgs(process.argv.slice(2)));
    console.log(
      JSON.stringify(
        {
          ok: true,
          root: res.root,
          derived: relTo(res.root, res.extractOut),
          provenance: relTo(res.root, res.provenancePath),
          evidence: res.evidencePath ? relTo(res.root, res.evidencePath) : null,
          pdf_sha256: res.sha256,
          pages: res.requestedPages,
          returned_pages: res.pages,
          missing_pages: res.missingPages,
          extract_raw_sha256: res.rawSha256,
          assets: res.assets.length,
          missing_assets: res.missingAssets,
        },
        null,
        1
      )
    );
    process.exit(0);
  } catch (e) {
    console.error(`${e.name}: ${e.message}`);
    process.exit(1);
  }
}
