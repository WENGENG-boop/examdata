// ielts-api/schema.mjs
// S02: manifest schema, validation and coverage computation.
// The manifest (data/expected-manifest.json) is the single source of truth for
// "what must exist": per book, per variant/skill/test/part with expected
// question numbers, evidence pages and status.

export const VARIANTS = ["academic", "general", "shared"];
export const SKILLS = ["listening", "reading", "writing", "speaking"];
export const ITEM_STATUS = ["verified", "unverified", "not_in_book"];
export const RUNTIME_STATUS = ["missing", "partial", "available", "verified", "conflict", "unverified", "not_applicable"];

export const PART_PATTERNS = {
  listening: /^P[1-4]$/,
  reading: /^P[1-3]$/,
  writing: /^WT[12]$/,
  speaking: /^SP$/,
};

// variant <-> skill compatibility (listening/speaking are shared between
// academic and general variants; reading/writing are variant-specific)
export const SKILL_VARIANTS = {
  listening: ["shared"],
  speaking: ["shared"],
  reading: ["academic", "general"],
  writing: ["academic", "general"],
};

export function makeId(book, variant, skill, test, part, edition) {
  return `cambridge:${book}:${variant}:${skill}:${test}:${part}:${edition}`;
}

export function normalizeTestToken(test) {
  return String(test).toLowerCase();
}

function expandNumbers(ranges) {
  const out = [];
  for (const [a, b] of ranges || []) for (let n = a; n <= b; n++) out.push(n);
  return out;
}

// item level: numbers must be gap-free (may start anywhere, e.g. part 2 = 11-20)
function isContiguous(nums) {
  if (!nums.length) return false;
  const sorted = [...nums].sort((a, b) => a - b);
  for (let i = 1; i < sorted.length; i++) if (sorted[i] !== sorted[i - 1] + 1) return false;
  return true;
}

// test level: union of all parts must be gap-free and start at 1
function isContiguousFrom1(nums) {
  if (!nums.length) return false;
  const sorted = [...nums].sort((a, b) => a - b);
  if (sorted[0] !== 1) return false;
  for (let i = 1; i < sorted.length; i++) if (sorted[i] !== sorted[i - 1] + 1) return false;
  return true;
}

// ---------------------------------------------------------------- validation
export function validateManifest(manifest) {
  const errors = [];
  const warnings = [];
  if (!manifest || !Array.isArray(manifest.books)) {
    return { ok: false, errors: ["manifest.books missing"], warnings, coverage: null };
  }
  const seenIds = new Set();
  for (const book of manifest.books) {
    if (!Array.isArray(book.items)) { errors.push(`book ${book.book}: items missing`); continue; }
    // group items by (variant, skill, test)
    const groups = new Map();
    for (const item of book.items) {
      // -- duplicate ids
      if (seenIds.has(item.id)) errors.push(`duplicate item id: ${item.id}`);
      seenIds.add(item.id);
      // -- status / variant / skill legality
      if (!ITEM_STATUS.includes(item.status)) errors.push(`${item.id}: illegal status ${item.status}`);
      if (!VARIANTS.includes(item.variant)) errors.push(`${item.id}: illegal variant ${item.variant}`);
      if (!SKILLS.includes(item.skill)) errors.push(`${item.id}: illegal skill ${item.skill}`);
      const allowed = SKILL_VARIANTS[item.skill];
      if (allowed && !allowed.includes(item.variant)) errors.push(`${item.id}: variant ${item.variant} not allowed for skill ${item.skill}`);
      const pp = PART_PATTERNS[item.skill];
      if (pp && !pp.test(item.part)) errors.push(`${item.id}: part ${item.part} invalid for skill ${item.skill}`);
      // -- verified requires evidence
      if (item.status === "verified") {
        if (!Array.isArray(item.evidence) || item.evidence.length === 0) {
          errors.push(`${item.id}: status=verified without evidence`);
        } else if (item.evidence.every((e) => e.file_page == null)) {
          warnings.push(`${item.id}: verified but no confirmed page evidence`);
        }
      }
      // -- expected numbers within the item must be gap-free
      const nums = item.expected_numbers || [];
      if (nums.length && !isContiguous(nums)) errors.push(`${item.id}: expected_numbers not gap-free`);
      // -- dangling group/asset refs
      const assetIds = new Set((item.expected_assets || []).map((a) => a.id));
      for (const g of item.expected_groups || []) {
        if (g.asset_ref && !assetIds.has(g.asset_ref)) errors.push(`${item.id}: group ${g.id} references unknown asset ${g.asset_ref}`);
        for (const p of g.parts || []) {
          if (pp && !pp.test(p)) errors.push(`${item.id}: group ${g.id} references invalid part ${p}`);
        }
      }
      const key = `${item.variant}:${item.skill}:${normalizeTestToken(item.test)}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(item);
    }
    // -- per test/skill: parts disjoint, union contiguous 1..N
    for (const [key, items] of groups) {
      if (items.every((i) => !(i.expected_numbers || []).length)) continue; // writing/speaking
      const all = [];
      for (const i of items) all.push(...(i.expected_numbers || []));
      const sorted = [...all].sort((a, b) => a - b);
      for (let i = 1; i < sorted.length; i++) {
        if (sorted[i] === sorted[i - 1]) errors.push(`book ${book.book} ${key}: overlapping question number ${sorted[i]}`);
      }
      if (!isContiguousFrom1(sorted)) errors.push(`book ${book.book} ${key}: union of parts not contiguous from 1`);
    }
  }
  return { ok: errors.length === 0, errors, warnings, coverage: computeCoverage(manifest) };
}

// ---------------------------------------------------------------- coverage
export function computeCoverage(manifest) {
  const units = new Map(); // unitKey -> {variant, skill, book, test, statuses[]}
  const questions = new Map(); // variant_skill -> count
  for (const book of manifest.books) {
    for (const item of book.items) {
      const uk = `${book.book}:${item.variant}:${item.skill}:${normalizeTestToken(item.test)}`;
      if (!units.has(uk)) units.set(uk, { book: book.book, variant: item.variant, skill: item.skill, test: item.test, statuses: [] });
      units.get(uk).statuses.push(item.status);
      const qk = `${item.variant}_${item.skill}`;
      questions.set(qk, (questions.get(qk) || 0) + (item.expected_numbers || []).length);
    }
  }
  const bySkill = {};
  for (const u of units.values()) {
    const k = `${u.variant}_${u.skill}`;
    if (!bySkill[k]) bySkill[k] = { expected_units: 0, verified_units: 0, unverified_units: 0, not_in_book_units: 0 };
    bySkill[k].expected_units += 1;
    if (u.statuses.every((s) => s === "verified")) bySkill[k].verified_units += 1;
    else if (u.statuses.every((s) => s === "not_in_book")) bySkill[k].not_in_book_units += 1;
    else bySkill[k].unverified_units += 1;
  }
  const complete = [];
  const incomplete = [];
  for (const book of manifest.books) {
    (isBookComplete(manifest, book.book) ? complete : incomplete).push(book.book);
  }
  return {
    by_skill: bySkill,
    questions_expected: Object.fromEntries(questions),
    complete_books: complete,
    incomplete_books: incomplete,
  };
}

// A book is complete only when: every item is structure-verified AND answer
// extraction is complete AND the General-Training question is resolved
// (in_book or not_in_book — never left unverified).
export function isBookComplete(manifest, book) {
  const b = manifest.books.find((x) => x.book === Number(book));
  if (!b) return false;
  if (!Array.isArray(b.items) || b.items.length === 0) return false;
  if (!b.items.every((i) => i.status === "verified")) return false;
  const ex = b.extraction || {};
  if (ex.status !== "complete") return false;
  const gt = (b.general || {}).status || (b.gt || {}).status;
  if (!(gt === "in_book" || gt === "not_in_book")) return false;
  return true;
}

// ---------------------------------------------------------------- lookup
export function findItems(manifest, book, variant, skill, test) {
  const b = manifest.books.find((x) => x.book === Number(book));
  if (!b) return [];
  const t = normalizeTestToken(test);
  return b.items.filter((i) => i.variant === variant && i.skill === skill && normalizeTestToken(i.test) === t);
}

export function validateQuestionNumber(manifest, book, variant, skill, test, n) {
  const items = findItems(manifest, book, variant, skill, test);
  if (!items.length) return { ok: false, reason: "no_item" };
  for (const item of items) {
    if ((item.expected_numbers || []).includes(Number(n))) return { ok: true, part: item.part, item_id: item.id };
  }
  return { ok: false, reason: "number_not_expected" };
}

export { expandNumbers };
