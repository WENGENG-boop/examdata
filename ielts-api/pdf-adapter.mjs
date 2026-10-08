#!/usr/bin/env node
// ielts-api/pdf-adapter.mjs
// S06: Node adapter around tools/pdf_extract.py (structured extraction from IELTS source PDFs).
//
// Spawns the examdata venv Python (PyMuPDF), validates the emitted envelope
// (tool/version/pdf.sha256/pages) and returns the parsed document plus provenance
// fields. Read-only with respect to the source PDFs; never rewrites an input.
//
// API:
//   extractPdf({ book|pdf, pages, out?, ocrJson?, textdir?, assets?, renderPages?, minFigArea?,
//                python?, script?, timeoutMs?, verifyHash? })
//     -> { doc, outPath, pdfPath, sha256, requestedPages, pages, missingPages, summary, stdout, stderr }
//   validateExtractDoc(doc, { requestedPages }) -> { sha256, pages, missingPages }
//   parsePagesSpec("33-41,155") -> [33..41, 155]
//   normalizePagesSpec([45, 46]) -> "45,46"
//   sha256FileHex(path), resolvePython(), resolveScript(), resolvePdfPath({book, pdf})
//
// CLI: node ielts-api/pdf-adapter.mjs --book 3 --pages 37,41 [--ocr-json f] [--assets dir]
//        [--textdir dir] [--out f] [--render-pages] [--min-fig-area n]

import { spawnSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const TOOL_NAME = "pdf_extract";
export const SUPPORTED_VERSIONS = Object.freeze([1]);

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const API_DIR = path.resolve(__dirname);
export const REPO_ROOT = path.resolve(API_DIR, "..");

export class PdfAdapterError extends Error {
  constructor(message, { code = "pdf_adapter_error", detail = null } = {}) {
    super(message);
    this.name = "PdfAdapterError";
    this.code = code;
    if (detail !== null) this.detail = detail;
  }
}

export function resolvePython(explicit) {
  return (
    explicit ||
    process.env.EXAMDATA_IELTS_PYTHON ||
    path.join(REPO_ROOT, "examdata", ".venv", "Scripts", "python.exe")
  );
}

export function resolveScript(explicit) {
  return explicit || path.join(API_DIR, "tools", "pdf_extract.py");
}

export function resolvePdfPath({ book, pdf } = {}) {
  if (pdf) return path.resolve(pdf);
  if (book !== undefined && book !== null) {
    return path.join(REPO_ROOT, "tmp_audit_ielts", "downloads", `book_${book}.pdf`);
  }
  throw new PdfAdapterError("need book or pdf", { code: "bad_input" });
}

export function parsePagesSpec(spec) {
  const out = [];
  for (const part of String(spec).split(",")) {
    const t = part.trim();
    if (!t) continue;
    const m = t.match(/^(\d+)\s*-\s*(\d+)$/);
    if (m) {
      const a = Number(m[1]);
      const b = Number(m[2]);
      if (b < a) throw new PdfAdapterError(`descending page range: ${t}`, { code: "bad_input" });
      for (let i = a; i <= b; i++) out.push(i);
      continue;
    }
    if (/^\d+$/.test(t)) {
      const n = Number(t);
      if (n < 1) throw new PdfAdapterError(`page must be >= 1: ${t}`, { code: "bad_input" });
      out.push(n);
      continue;
    }
    throw new PdfAdapterError(`bad page token: ${t}`, { code: "bad_input" });
  }
  if (!out.length) throw new PdfAdapterError("empty pages spec", { code: "bad_input" });
  return out;
}

export function normalizePagesSpec(pages) {
  if (Array.isArray(pages)) {
    if (!pages.length) throw new PdfAdapterError("pages array is empty", { code: "bad_input" });
    for (const n of pages) {
      if (!Number.isInteger(n) || n < 1) {
        throw new PdfAdapterError(`bad page number: ${n}`, { code: "bad_input" });
      }
    }
    return pages.join(",");
  }
  if (typeof pages === "string" && pages.trim()) {
    parsePagesSpec(pages); // validates
    return pages.trim();
  }
  throw new PdfAdapterError("pages must be a non-empty array or spec string", { code: "bad_input" });
}

export function sha256FileHex(filePath) {
  const h = crypto.createHash("sha256");
  const fd = fs.openSync(filePath, "r");
  try {
    const buf = Buffer.alloc(1 << 20);
    let n;
    while ((n = fs.readSync(fd, buf, 0, buf.length, null)) > 0) h.update(buf.subarray(0, n));
  } finally {
    fs.closeSync(fd);
  }
  return h.digest("hex");
}

export function validateExtractDoc(doc, { requestedPages } = {}) {
  if (!doc || typeof doc !== "object" || Array.isArray(doc)) {
    throw new PdfAdapterError("extract doc is not an object", { code: "invalid_doc" });
  }
  const problems = [];
  if (doc.tool !== TOOL_NAME) problems.push(`tool != ${TOOL_NAME} (got ${JSON.stringify(doc.tool)})`);
  if (!SUPPORTED_VERSIONS.includes(doc.version)) {
    problems.push(`unsupported tool version ${JSON.stringify(doc.version)}`);
  }
  const pdf = doc.pdf || {};
  if (typeof pdf.sha256 !== "string" || !/^[0-9a-f]{64}$/.test(pdf.sha256)) {
    problems.push("pdf.sha256 missing or not 64-hex");
  }
  if (typeof pdf.path !== "string" || !pdf.path) problems.push("pdf.path missing");
  if (!Array.isArray(doc.pages) || doc.pages.length === 0) {
    problems.push("pages missing or empty");
  }
  const seen = new Set();
  for (const p of doc.pages || []) {
    if (!p || !Number.isInteger(p.file_page)) {
      problems.push("page entry without integer file_page");
      break;
    }
    if (seen.has(p.file_page)) problems.push(`duplicate page ${p.file_page}`);
    seen.add(p.file_page);
    if (!Array.isArray(p.lines)) problems.push(`page ${p.file_page}: lines is not an array`);
    if (!Array.isArray(p.figures)) problems.push(`page ${p.file_page}: figures is not an array`);
    if (typeof p.text_layer !== "boolean") problems.push(`page ${p.file_page}: text_layer is not boolean`);
    if (p.ocr != null && (!Array.isArray(p.ocr.words) || !Array.isArray(p.ocr.lines))) {
      problems.push(`page ${p.file_page}: ocr block malformed`);
    }
  }
  if (problems.length) {
    throw new PdfAdapterError(`invalid pdf_extract output: ${problems.join("; ")}`, {
      code: "invalid_doc",
      detail: problems,
    });
  }
  const missingPages = [];
  if (requestedPages && requestedPages.length) {
    for (const n of requestedPages) if (!seen.has(n)) missingPages.push(n);
  }
  return { sha256: pdf.sha256, pages: doc.pages.map((p) => p.file_page), missingPages };
}

export function parseSummary(stdout) {
  const lines = String(stdout || "")
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  for (let i = lines.length - 1; i >= 0; i--) {
    try {
      const j = JSON.parse(lines[i]);
      if (j && typeof j === "object" && "ok" in j) return j;
    } catch {
      /* not the summary line */
    }
  }
  return null;
}

export function extractPdf(opts = {}) {
  const {
    book,
    pdf,
    pages,
    out,
    ocrJson,
    textdir,
    assets,
    renderPages = false,
    minFigArea,
    python,
    script,
    timeoutMs = 300000,
    verifyHash = true,
  } = opts;

  const pdfPath = resolvePdfPath({ book, pdf });
  if (!fs.existsSync(pdfPath)) {
    throw new PdfAdapterError(`pdf not found: ${pdfPath}`, { code: "pdf_missing" });
  }
  const spec = normalizePagesSpec(pages);
  const requestedPages = parsePagesSpec(spec);
  const py = resolvePython(python);
  if (!fs.existsSync(py)) {
    throw new PdfAdapterError(`python not found: ${py}`, { code: "python_missing" });
  }
  const sc = resolveScript(script);
  if (!fs.existsSync(sc)) {
    throw new PdfAdapterError(`pdf_extract.py not found: ${sc}`, { code: "script_missing" });
  }
  if (ocrJson && !fs.existsSync(ocrJson)) {
    throw new PdfAdapterError(`ocr json not found: ${ocrJson}`, { code: "bad_input" });
  }

  const outPath = out
    ? path.resolve(out)
    : path.join(API_DIR, ".tmp", `pdf-extract-${process.pid}-${Date.now()}-${crypto.randomBytes(4).toString("hex")}.json`);
  fs.mkdirSync(path.dirname(outPath), { recursive: true });

  const args = [sc, "--pages", spec, "--out", outPath];
  if (book !== undefined && book !== null) args.push("--book", String(book));
  else args.push("--pdf", pdfPath);
  if (ocrJson) args.push("--ocr-json", path.resolve(ocrJson));
  if (textdir) args.push("--textdir", path.resolve(textdir));
  if (assets) args.push("--assets", path.resolve(assets));
  if (renderPages) args.push("--render-pages");
  if (minFigArea !== undefined && minFigArea !== null) args.push("--min-fig-area", String(minFigArea));

  const res = spawnSync(py, args, {
    encoding: "utf8",
    timeout: timeoutMs,
    maxBuffer: 256 * 1024 * 1024,
    windowsHide: true,
  });
  if (res.error) {
    throw new PdfAdapterError(`spawn failed: ${res.error.message}`, {
      code: res.error.code === "ETIMEDOUT" ? "timeout" : "spawn_failed",
    });
  }
  if (res.status !== 0) {
    const tail = String(res.stderr || "").trim().split(/\r?\n/).slice(-6).join(" | ");
    throw new PdfAdapterError(`pdf_extract exited with ${res.status}: ${tail}`, {
      code: "extract_failed",
      detail: { status: res.status, stderr: res.stderr || "" },
    });
  }
  if (!fs.existsSync(outPath)) {
    throw new PdfAdapterError(`pdf_extract did not write ${outPath}`, { code: "extract_failed" });
  }
  let doc;
  try {
    doc = JSON.parse(fs.readFileSync(outPath, "utf8"));
  } catch (e) {
    throw new PdfAdapterError(`pdf_extract output is not valid JSON: ${e.message}`, { code: "invalid_doc" });
  }
  const { sha256, pages: gotPages, missingPages } = validateExtractDoc(doc, { requestedPages });
  if (verifyHash) {
    const fileHash = sha256FileHex(pdfPath);
    if (fileHash !== sha256) {
      throw new PdfAdapterError(`pdf hash mismatch: file ${fileHash} != doc ${sha256}`, {
        code: "hash_mismatch",
      });
    }
  }
  return {
    doc,
    outPath,
    pdfPath,
    sha256,
    requestedPages,
    pages: gotPages,
    missingPages,
    summary: parseSummary(res.stdout),
    stdout: res.stdout || "",
    stderr: res.stderr || "",
  };
}

export const __internals = { parseSummary, parsePagesSpec, normalizePagesSpec };

function cliMain(argv) {
  const args = { renderPages: false };
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
      case "--textdir":
        args.textdir = next();
        break;
      case "--assets":
        args.assets = next();
        break;
      case "--render-pages":
        args.renderPages = true;
        break;
      case "--min-fig-area":
        args.minFigArea = Number(next());
        break;
      default:
        throw new PdfAdapterError(`unknown argument: ${a}`, { code: "bad_input" });
    }
  }
  const res = extractPdf(args);
  console.log(
    JSON.stringify(
      {
        ok: true,
        out: res.outPath,
        pdf: res.pdfPath,
        sha256: res.sha256,
        pages: res.pages,
        missing_pages: res.missingPages,
      },
      null,
      1
    )
  );
  return 0;
}

const isMain =
  process.argv[1] && path.resolve(process.argv[1]).toLowerCase() === fileURLToPath(import.meta.url).toLowerCase();
if (isMain) {
  try {
    process.exit(cliMain(process.argv.slice(2)));
  } catch (e) {
    console.error(`${e.name}: ${e.message}`);
    process.exit(1);
  }
}
