// ielts-api/catalog.mjs
// S02: Cambridge IELTS book catalog (21 books) with PDF identity, text-layer
// facts and General-Training rulings. Data-only module; consumed by
// tools/build-manifest.mjs and later stages (resolver, coverage).
//
// sha256 values were extracted from the S02 answer-key extraction run
// (evidence/pdf-answer-keys.json) and re-verified by build-manifest.mjs
// against the actual files under tmp_audit_ielts/downloads/.

export const SERIES = "cambridge_ielts";
export const RUN_ID = "20261003T140007Z-repair";

export const BOOK_IDS = [
  1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21,
];

const PDF_BASE = "tmp_audit_ielts/downloads";

// edition = "c<book>-<sha8>" (content-addressed); book 21 has no local PDF.
function pdfEntry(book, sha256, pages) {
  return { relpath: `${PDF_BASE}/book_${book}.pdf`, sha256, pages };
}

export const BOOKS = [
  { book: 1, edition: "c1-93ba03c1", source: "pdf", pdf: pdfEntry(1, "93ba03c19ef5ab281e7282a60a6da5224e5b77cbe2bd66c75e81c180a784e527", 162), text_layer: true,
    gt: { status: "in_book", tests: ["gta"], evidence: [{ probe: "probe-gt", note: "GT Reading p100-108, GT Writing p111-112" }] } },
  { book: 2, edition: "c2-c4cda460", source: "pdf", pdf: pdfEntry(2, "c4cda460f7db248583e91509813829a5944e6a459cdf3b11501968216dfda32d", 81), text_layer: true,
    gt: { status: "in_book", tests: ["gta", "gtb"], evidence: [{ probe: "reading-sections", note: "GT-A p47-53, GT-B p54-60" }] } },
  { book: 3, edition: "c3-da273b47", source: "pdf", pdf: pdfEntry(3, "da273b47cbfa1fe324b2f289374bcfdbc7276a763e216be4f86ae6a070f06845", 179), text_layer: true,
    gt: { status: "in_book", tests: ["gta", "gtb"], evidence: [{ probe: "reading-sections", note: "GT-A p104-117, GT-B p118-130" }] } },
  { book: 4, edition: "c4-b2543245", source: "pdf", pdf: pdfEntry(4, "b254324578e8f7a5187810aa36f5e1bf3049537b49bd7cc2c34fc2c963185bed", 178), text_layer: true,
    gt: { status: "in_book", tests: ["gta", "gtb"], evidence: [{ probe: "reading-sections", note: "GT-A p104-116, GT-B p117-130" }] } },
  { book: 5, edition: "c5-852607dd", source: "pdf", pdf: pdfEntry(5, "852607dd3c8aa7e0d7cd6d66cae312337696997635902629fcadbf65c12eef5a", 177), text_layer: true,
    gt: { status: "in_book", tests: ["gta", "gtb"], evidence: [{ probe: "reading-sections", note: "GT-A p102-114, GT-B p115-128" }] } },
  { book: 6, edition: "c6-67748f68", source: "pdf", pdf: pdfEntry(6, "67748f68b0ab33d90b1c2f5864dc4aa8eada76949830422a3d230090522d9573", 177), text_layer: true,
    gt: { status: "in_book", tests: ["gta", "gtb"], evidence: [{ probe: "reading-sections", note: "GT-A p102-114, GT-B p115-127" }] } },
  { book: 7, edition: "c7-a219bf46", source: "pdf", pdf: pdfEntry(7, "a219bf469ba75c39938a2a9d8bfd4bf15caf206e8c249d70d188ff4e36ad3b00", 181), text_layer: true,
    gt: { status: "in_book", tests: ["gta", "gtb"], evidence: [{ probe: "reading-sections", note: "GT-A p109-121, GT-B p122-133" }] } },
  { book: 8, edition: "c8-5d813013", source: "pdf", pdf: pdfEntry(8, "5d8130130febf26f1a61bf2161c8066556256e7b1b00c36e76e4409bc43a0b17", 173), text_layer: true,
    gt: { status: "in_book", tests: ["gta", "gtb"], evidence: [{ probe: "reading-sections", note: "GT-A p103-115, GT-B p116-128" }] } },
  { book: 9, edition: "c9-b25f954d", source: "pdf", pdf: pdfEntry(9, "b25f954dd25e058dfc05913c8f3b9ffead6581aa23bb10f8f2e98e6314f7af24", 165), text_layer: false,
    gt: { status: "unverified", reason: "no_text_layer" } },
  { book: 10, edition: "c10-3f1c5328", source: "pdf", pdf: pdfEntry(10, "3f1c532893532971b2a1fd1a47425c1895908d3a593f95a9699e4c80ca129c82", 166), text_layer: true,
    gt: { status: "in_book", tests: ["gta", "gtb"], evidence: [{ probe: "reading-sections", note: "GT-A p97-109, GT-B p110-122" }] } },
  { book: 11, edition: "c11-c9672f9f", source: "pdf", pdf: pdfEntry(11, "c9672f9f8dc9fbd4ca7f965a50a3a599bf86a144efbe5e777010b5958baaf9db", 139), text_layer: true,
    gt: { status: "not_in_book", reason: "table of contents (p2) lists no General Training test; no GT markers in book body", evidence: [{ probe: "probe-gt", note: "p2-6 checked" }] } },
  { book: 12, edition: "c12-f7913009", source: "pdf", pdf: pdfEntry(12, "f791300937f11d8380eba7b7997db1da751d66802a96aed996db704947e52407", 138), text_layer: true,
    gt: { status: "not_in_book", reason: "copyright page (p3) states Academic; no GT markers in book body", evidence: [{ probe: "gt-probe", note: "p2-5 checked" }] } },
  { book: 13, edition: "c13-f6bbbbf9", source: "pdf", pdf: pdfEntry(13, "f6bbbbf97633bc8dfd71f11b68b8fff4da607cbe2408cfebdbe54cf05c6b18cf", 143), text_layer: true,
    gt: { status: "not_in_book", reason: "p3 shows a different ISBN/edition imprint (Academic only)", evidence: [{ probe: "gt-probe", note: "p3 checked" }] } },
  { book: 14, edition: "c14-d163b41d", source: "pdf", pdf: pdfEntry(14, "d163b41dd4284aaed910c920af9e83afc7d90887db4f8f27993f99f0c0a115aa", 143), text_layer: true,
    gt: { status: "not_in_book", reason: "p3 shows a different ISBN/edition imprint (Academic only)", evidence: [{ probe: "gt-probe", note: "p3 checked" }] } },
  { book: 15, edition: "c15-c86d084b", source: "pdf", pdf: pdfEntry(15, "c86d084b20be89232eebd6fd6eb533b32ba4f24a9cbe14952b85665c3a3ca141", 146), text_layer: true,
    gt: { status: "not_in_book", reason: "p3 Chinese front-matter page identifies Academic; no GT markers", evidence: [{ probe: "gt-probe", note: "p3 checked" }] } },
  { book: 16, edition: "c16-11675fa3", source: "pdf", pdf: pdfEntry(16, "11675fa3dcb124e93afbf44371c174f676a78a260b01ebc190aae5f5fed3912e", 144), text_layer: false,
    gt: { status: "unverified", reason: "no_text_layer" } },
  { book: 17, edition: "c17-90ae888c", source: "pdf", pdf: pdfEntry(17, "90ae888c4cd495761fe5639418ca894e63c9e7066382ed9ffad6bd74a409726a", 144), text_layer: true,
    gt: { status: "not_in_book", reason: "table of contents (p3) lists no General Training test", evidence: [{ probe: "gt-probe", note: "p3 checked" }] } },
  { book: 18, edition: "c18-69aae9f2", source: "pdf", pdf: pdfEntry(18, "69aae9f240f1e3de4c72f1f4c4421bf892d09a455c1946ad41752fdab998e663", 147), text_layer: false,
    gt: { status: "unverified", reason: "no_text_layer" } },
  { book: 19, edition: "c19-e9bab34e", source: "pdf", pdf: pdfEntry(19, "e9bab34e9fafdc012c7407c43931e806144354b92b2ba59619ee59dbe6a7bf78", 145), text_layer: false,
    gt: { status: "unverified", reason: "no_text_layer" } },
  { book: 20, edition: "c20-71e6a364", source: "pdf", pdf: pdfEntry(20, "71e6a364ec47479dbb8352cc039f83ed20bfe2e4055100759894da2de779a829", 34), text_layer: false,
    gt: { status: "unverified", reason: "no_text_layer" },
    note: "local PDF is a 34-page Test-1 booklet only; cannot confirm T2-T4 pages from this file" },
  { book: 21, edition: "c21-web", source: "web", pdf: null, text_layer: null,
    gt: { status: "unverified", reason: "no_local_pdf" },
    note: "no local PDF; cam21.mjs web source (raw.githubusercontent.com/maqsudjon-cell/cambridge-21) provides reading/listening snapshots" },
];

const byBook = new Map(BOOKS.map((b) => [b.book, b]));

export function bookEntry(n) {
  const b = byBook.get(Number(n));
  if (!b) throw new Error(`unknown book: ${n}`);
  return b;
}

export function editionOf(n) {
  return bookEntry(n).edition;
}

// Third-party web sources reachable from this repo. None of these count
// toward the "21 books complete" denominator; they are auxiliary caches.
export const EXTERNAL_SOURCES = [
  { id: "mini-ielts", module: "ielts-api.mjs", base: "https://mini-ielts.com/", role: "recent-actual-tests-supplement" },
  { id: "ieltsprogress", module: "ielts-api.mjs,iprog.mjs", base: "https://ieltsprogress.com/", role: "supplement" },
  { id: "ieltstrainingonline", module: "ito.mjs", base: "https://ieltstrainingonline.com/", role: "supplement" },
  { id: "zhan", module: "zhan.mjs", base: "https://top.zhan.com/", role: "supplement" },
  { id: "practicepteonline", module: "pte.mjs", base: "https://practicepteonline.com/", role: "cambridge-mirror" },
  { id: "cam21-github", module: "cam21.mjs", base: "https://raw.githubusercontent.com/maqsudjon-cell/cambridge-21/main/", role: "book-21-web-cache" },
];
