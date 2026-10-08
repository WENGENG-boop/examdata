// S11: transcript (listening script) per-Part selection and cross-source
// fallback.
//
// Pure logic module (no I/O, no network). Source adapters (maslow markdown,
// reader segment timelines, ieltstrainingonline sections, cam21 site
// transcripts, PDF audioscripts) hand in per-Part candidates; this module
// compares them per Part, selects the most complete usable text, records
// conflicts for review, and keeps source identity/hash provenance.
//
// Hard rules from the S11 plan section:
//   * length / segment count / ellipsis are quality signals, never proof of
//     completeness; only cross-source agreement may mark a Part complete;
//   * a fallback source must carry the same identity (book/test/part), else it
//     is rejected as wrong-edition / wrong-test;
//   * HTML error pages and advertisement scaffolding are rejected outright;
//   * text status and audio status are separate dimensions: text found without
//     audio must not read as audio available, and vice versa;
//   * `format=raw` whole-book text without Part structure never yields an
//     ok:true empty test text.
import { tokenize } from "./audio-matcher.mjs";

export const TRANSCRIPT_SCHEMA = "ielts.transcript-match/1";
export const TRANSCRIPT_MATCHER_VERSION = "transcript-matcher/1.0.0";

export const SCRIPT_STATUS = Object.freeze({
  OK: "ok",
  REVIEW: "review",
  PARTIAL: "partial",
  MISSING: "missing",
});

export const SCRIPT_THRESHOLDS = Object.freeze({
  min_part_chars: 200,
  tail_tokens: 16,
  head_tokens: 12,
  words_per_sec_min: 1.0,
  words_per_sec_max: 4.5,
});

// ---------------------------------------------------------------------------
// Text quality signals
// ---------------------------------------------------------------------------

/** Cheap structural signals. Signals only — never proof of completeness. */
export function assessTranscriptText(text) {
  const raw = String(text ?? "");
  const trimmed = raw.trim();
  const lines = trimmed ? trimmed.split(/\n+/).map((s) => s.trim()).filter(Boolean) : [];
  const chars = trimmed.length;
  const words = trimmed ? trimmed.split(/\s+/).filter(Boolean).length : 0;
  const lastLine = lines.length ? lines[lines.length - 1] : "";
  const firstLine = lines.length ? lines[0] : "";
  const tailEllipsis = /(?:\.\.\.|…)\s*$/.test(trimmed);
  const endsWithTerminal = !tailEllipsis && /[.!?»"')\]]\s*$/.test(lastLine);
  const htmlLike = /<(?:!doctype|html|head|body|script|div|p|meta)\b/i.test(trimmed);
  const adLike = /(?:adsbygoogle|document\.createElement)/i.test(trimmed) || /^Advertisements$/im.test(trimmed);
  const speakerLines = lines.filter((l) => /^[A-Z][A-Za-z .'-]{1,24}:\s/.test(l)).length;
  const startsWithMarker = /^(?:PART|SECTION)\s*[1-4]\b/i.test(firstLine);
  return {
    chars,
    words,
    lines: lines.length,
    ends_with_terminal: endsWithTerminal,
    tail_ellipsis: tailEllipsis,
    html_like: htmlLike,
    ad_like: adLike,
    speaker_lines: speakerLines,
    starts_with_marker: startsWithMarker,
  };
}

// ---------------------------------------------------------------------------
// Head/tail token relations
// ---------------------------------------------------------------------------

export function headTokens(text, n = SCRIPT_THRESHOLDS.head_tokens) {
  return tokenize(text).slice(0, n);
}

export function tailTokens(text, n = SCRIPT_THRESHOLDS.tail_tokens) {
  const toks = tokenize(text);
  return toks.slice(Math.max(0, toks.length - n));
}

/** Contiguous containment of `needle` inside `haystack`. */
export function seqContains(haystack, needle) {
  if (!needle.length || needle.length > haystack.length) return false;
  outer: for (let i = 0; i + needle.length <= haystack.length; i += 1) {
    for (let j = 0; j < needle.length; j += 1) {
      if (haystack[i + j] !== needle[j]) continue outer;
    }
    return true;
  }
  return false;
}

/**
 * Containment that tolerates partial edge tokens: a source cut mid-word leaves
 * a fragment token at the cut edge, so allow dropping up to `dropEdge` tokens
 * from the cut side before matching. The probe must keep `minLen` tokens, so
 * this never degenerates into matching a phrase fragment.
 */
export function containedWithEdges(haystack, needle, { dropFront = 0, dropBack = 0, minLen = 10 } = {}) {
  const need = Math.min(minLen, needle.length);
  for (let f = 0; f <= dropFront; f += 1) {
    for (let b = 0; b <= dropBack; b += 1) {
      const probe = needle.slice(f, needle.length - b);
      if (probe.length >= need && seqContains(haystack, probe)) return true;
    }
  }
  return false;
}

/**
 * Relation between two texts' tails, truncation-aware:
 *   same         identical tail tokens
 *   extends      b's tail appears inside a's full text (a extends b, b truncated)
 *   extended_by  a's tail appears inside b's full text (b extends a, a truncated)
 *   differ       unrelated tails (genuine conflict)
 *
 * A tail is matched against the *other source's whole text*, not only its last
 * N tokens: a truncated source's ending sits in the middle of the complete
 * source, and that is exactly the truncation signal we want to see.
 */
export function tailRelation(aText, bText) {
  const a = tailTokens(aText);
  const b = tailTokens(bText);
  if (a.join(" ") === b.join(" ")) return "same";
  const aFull = tokenize(aText);
  const bFull = tokenize(bText);
  const aTailInB = containedWithEdges(bFull, a, { dropBack: 3, minLen: 10 });
  const bTailInA = containedWithEdges(aFull, b, { dropBack: 3, minLen: 10 });
  if (aTailInB && bTailInA) return "same";
  if (bTailInA) return "extends";
  if (aTailInB) return "extended_by";
  return "differ";
}

export function headRelation(aText, bText) {
  const a = headTokens(aText);
  const b = headTokens(bText);
  if (a.join(" ") === b.join(" ")) return "same";
  if (seqContains(a, b)) return "extends";
  if (seqContains(b, a)) return "extended_by";
  return "differ";
}

// ---------------------------------------------------------------------------
// Per-Part comparison
// ---------------------------------------------------------------------------

function normalizeIdentity(identity) {
  if (!identity) return null;
  if (typeof identity === "string") {
    const m = /^cambridge:(\d+):(\w+):(\w+):(\d+):(P\d+)$/.exec(identity);
    if (!m) return null;
    return { book: Number(m[1]), variant: m[2], skill: m[3], test: Number(m[4]), part: m[5] };
  }
  const part = String(identity.part ?? "").replace(/^part/i, "P").replace(/^p(\d)$/i, "P$1");
  return {
    book: Number(identity.book),
    variant: identity.variant ?? null,
    skill: identity.skill ?? null,
    test: Number(identity.test),
    part: /^P\d+$/.test(part) ? part : null,
  };
}

function identityMatches(requested, claimed) {
  if (!requested || !claimed) return null; // unstated
  return requested.book === claimed.book
    && String(requested.test) === String(claimed.test)
    && String(requested.part).toUpperCase() === String(claimed.part).toUpperCase();
}

/**
 * Compare per-Part candidates and pick the most complete usable one.
 *
 * candidates: [{ source, text, meta: { identity?, identity_basis?, source_ref?, sha256?, fetched_at? } }]
 * audio:      { available?, duration_sec?, source? } — the *actual* Part audio (if any).
 */
export function comparePartScript({ identity, candidates, audio = null } = {}) {
  const requested = normalizeIdentity(identity);
  const assessed = (candidates ?? []).map((c) => {
    const quality = assessTranscriptText(c.text);
    const claimed = c.meta?.identity ? normalizeIdentity(c.meta.identity) : null;
    const identityOk = identityMatches(requested, claimed);
    let rejected = null;
    if (!quality.chars) rejected = "empty";
    else if (quality.html_like) rejected = "html_error_page";
    else if (quality.ad_like) rejected = "advertisement_scaffold";
    else if (identityOk === false) rejected = "identity_mismatch";
    else if (quality.chars < SCRIPT_THRESHOLDS.min_part_chars) rejected = "too_short";
    return {
      source: c.source ?? "unknown",
      text: String(c.text ?? ""),
      quality,
      identity_ok: identityOk,
      identity_basis: c.meta?.identity_basis ?? null,
      source_ref: c.meta?.source_ref ?? null,
      sha256: c.meta?.sha256 ?? null,
      rejected,
    };
  });

  const usable = assessed
    .filter((a) => !a.rejected)
    .sort((x, y) => {
      const xt = x.quality.tail_ellipsis ? 1 : 0;
      const yt = y.quality.tail_ellipsis ? 1 : 0;
      if (xt !== yt) return xt - yt;
      return y.quality.chars - x.quality.chars;
    });

  const conflicts = [];
  let status;
  let completeBasis = null;
  let chosen = null;

  if (!usable.length) {
    status = SCRIPT_STATUS.MISSING;
  } else {
    chosen = usable[0];
    const chosenFull = tokenize(chosen.text);
    let tailAgreement = false;
    let headAgreement = false;
    for (const other of usable.slice(1)) {
      const otherFull = tokenize(other.text);
      if (containedWithEdges(otherFull, tailTokens(chosen.text), { dropBack: 3, minLen: 10 })) tailAgreement = true;
      if (containedWithEdges(otherFull, headTokens(chosen.text), { dropFront: 3, minLen: 8 })) headAgreement = true;
      const tail = tailRelation(chosen.text, other.text);
      if (tail === "differ") {
        conflicts.push({ type: "tail_conflict", sources: [chosen.source, other.source] });
      } else if (tail === "extended_by") {
        conflicts.push({ type: "chosen_tail_truncated", sources: [chosen.source, other.source], detail: `${other.source} tail extends ${chosen.source}` });
      } else if (tail === "extends") {
        conflicts.push({ type: "alternative_tail_truncated", sources: [other.source, chosen.source] });
      }
      const head = headRelation(chosen.text, other.text);
      if (head === "differ") {
        conflicts.push({ type: "head_conflict", sources: [chosen.source, other.source] });
      }
    }
    const hasReviewConflict = conflicts.some((c) => c.type === "tail_conflict" || c.type === "chosen_tail_truncated" || c.type === "head_conflict");
    if (hasReviewConflict) {
      status = SCRIPT_STATUS.REVIEW;
    } else if (chosen.quality.tail_ellipsis) {
      status = SCRIPT_STATUS.PARTIAL;
    } else {
      status = SCRIPT_STATUS.OK;
    }
    if (status === SCRIPT_STATUS.OK) {
      if (tailAgreement) completeBasis = "cross_source_agreement";
      else if (headAgreement) completeBasis = "cross_source_prefix_agreement";
      else completeBasis = "single_source_signals";
    }
  }

  const audioInfo = audio
    ? {
      available: Boolean(audio.available ?? (Number.isFinite(audio.duration_sec) && audio.duration_sec > 0)),
      duration_sec: Number.isFinite(audio.duration_sec) ? audio.duration_sec : null,
      source: audio.source ?? null,
    }
    : { available: false, duration_sec: null, source: null };
  if (audioInfo.duration_sec && chosen) {
    audioInfo.words_per_sec = Number((chosen.quality.words / audioInfo.duration_sec).toFixed(2));
    audioInfo.ratio_ok = audioInfo.words_per_sec >= SCRIPT_THRESHOLDS.words_per_sec_min
      && audioInfo.words_per_sec <= SCRIPT_THRESHOLDS.words_per_sec_max;
    if (!audioInfo.ratio_ok) {
      conflicts.push({ type: "duration_ratio", sources: [chosen.source], detail: `words/sec ${audioInfo.words_per_sec} outside [${SCRIPT_THRESHOLDS.words_per_sec_min},${SCRIPT_THRESHOLDS.words_per_sec_max}]` });
      if (status === SCRIPT_STATUS.OK) status = SCRIPT_STATUS.REVIEW;
    }
  }

  return {
    identity: requested,
    status,
    complete_basis: completeBasis,
    chosen: chosen
      ? {
        source: chosen.source,
        text: chosen.text,
        sha256: chosen.sha256,
        source_ref: chosen.source_ref,
        identity_basis: chosen.identity_basis,
        quality: chosen.quality,
      }
      : null,
    alternatives: usable.slice(1).map((a) => ({ source: a.source, chars: a.quality.chars, tail_ellipsis: a.quality.tail_ellipsis })),
    rejected: assessed.filter((a) => a.rejected).map((a) => ({ source: a.source, reason: a.rejected, identity_detail: a.identity_ok === false ? { claimed: a.identity_basis } : undefined })),
    conflicts,
    audio: audioInfo,
  };
}

/**
 * Match a whole test (or book) from per-Part candidate lists.
 *
 * candidatesByPart: { "1:1": [cand...], ... } keyed by `<test>:<part-number>`.
 * audioByPart:      { "1:1": {duration_sec, source}, ... }
 */
export function matchTranscripts({ book, candidatesByPart = {}, audioByPart = {} } = {}) {
  const parts = {};
  const review = [];
  const missing = [];
  for (const [key, cands] of Object.entries(candidatesByPart)) {
    const [testStr, partStr] = String(key).split(":");
    const result = comparePartScript({
      identity: { book, test: Number(testStr), part: `P${Number(partStr)}` },
      candidates: cands,
      audio: audioByPart[key] ?? null,
    });
    parts[key] = result;
    if (result.status === SCRIPT_STATUS.REVIEW || result.status === SCRIPT_STATUS.PARTIAL) review.push({ key, status: result.status, conflicts: result.conflicts });
    if (result.status === SCRIPT_STATUS.MISSING) missing.push(key);
  }
  const total = Object.keys(parts).length;
  const ok = Object.values(parts).filter((p) => p.status === SCRIPT_STATUS.OK).length;
  return {
    schema: TRANSCRIPT_SCHEMA,
    matcher_version: TRANSCRIPT_MATCHER_VERSION,
    book,
    parts,
    review,
    missing_parts: missing,
    summary: {
      parts_total: total,
      ok,
      review: review.filter((r) => r.status === SCRIPT_STATUS.REVIEW).length,
      partial: review.filter((r) => r.status === SCRIPT_STATUS.PARTIAL).length,
      missing: missing.length,
      cross_source_agreement: Object.values(parts).filter((p) => p.complete_basis === "cross_source_agreement").length,
    },
  };
}

/**
 * Whole-book markdown without Part structure stays unsegmented: callers must
 * not turn it into an ok:true empty test map. Returns null when the text
 * cannot be used at all.
 */
export function unsegmentedFallback(text) {
  const quality = assessTranscriptText(text);
  if (!quality.chars || quality.html_like || quality.ad_like) return null;
  return {
    format: "raw",
    tests: {},
    text: String(text),
    parts: 0,
    bytes: quality.chars,
    warning: "该本未按 Part 分节",
    quality,
  };
}

export const __internals = { normalizeIdentity, identityMatches, seqContains };
