// S10: audio <-> transcript <-> per-question alignment matcher.
//
// Pure logic module (no I/O, no network). The provider layer
// (`alignment-provider.mjs`) supplies already-verified audio records, official
// transcripts and local ASR output; this module only decides candidate
// windows, validates clocks, estimates full-test<->part offsets and selects
// windows via dynamic programming.
//
// Hard rules from the S10 plan section:
//   * never divide a Part's duration evenly by question number;
//   * a single word occurrence is never proof of a correct window;
//   * `verified` is only ever assigned from independent labels
//     (config.verified_windows), never by the matcher itself;
//   * thresholds only gate `needs_review`, they are not proof.

export const MATCHER_SCHEMA = "ielts.audio-alignment/1";
export const MATCHER_VERSION = "audio-matcher/1.0.0";
export const THRESHOLD_VERSION = "s10-thresholds/2026-10-04.a";

export const ALIGN_STATUS = Object.freeze({
  UNVERIFIED: "unverified",
  SECTION_ONLY: "section_only",
  NEEDS_REVIEW: "needs_review",
  VERIFIED: "verified",
  MISSING: "missing",
});

export const AUTO_THRESHOLDS = Object.freeze({
  anchor_similarity: 0.9,
  aligner_word_confidence: 0.8,
  max_residual_sec: 1.0,
  ambiguity_margin: 0.15,
  min_anchors: 3,
  speed_min: 0.2,
  speed_max: 5.0,
  marker_window_max_sec: 30,
  marker_window_default_sec: 12,
  answer_window_pad_sec: 2,
  dp_weights: Object.freeze({
    context: 0.6,
    anchor: 0.25,
    skip: 0.5,
    reverse: 0.8,
    reverse_overlap: 0.2,
  }),
});

// ---------------------------------------------------------------------------
// Text utilities
// ---------------------------------------------------------------------------

export function normalizeText(value) {
  return String(value ?? "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[^a-z0-9']+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function tokenize(value) {
  const n = normalizeText(value);
  return n ? n.split(" ") : [];
}

// Fraction of phrase tokens found in order (greedy subsequence) inside window.
export function phraseMatchScore(phraseTokens, windowTokens) {
  if (!phraseTokens.length) return 0;
  let i = 0;
  for (const tok of windowTokens) {
    if (i < phraseTokens.length && tok === phraseTokens[i]) i += 1;
  }
  return i / phraseTokens.length;
}

// Fraction of phrase tokens present in window regardless of order (recall only).
export function keywordScore(phraseTokens, windowTokens) {
  if (!phraseTokens.length) return 0;
  const set = new Set(windowTokens);
  let hit = 0;
  for (const tok of phraseTokens) if (set.has(tok)) hit += 1;
  return hit / phraseTokens.length;
}

// Longest contiguous run of phrase tokens inside window / phrase length.
export function contiguousScore(phraseTokens, windowTokens) {
  if (!phraseTokens.length) return 0;
  let best = 0;
  let run = 0;
  let i = 0;
  for (const tok of windowTokens) {
    if (i < phraseTokens.length && tok === phraseTokens[i]) {
      run += 1;
      i += 1;
      if (run > best) best = run;
    } else {
      run = 0;
      i = 0;
      if (i < phraseTokens.length && tok === phraseTokens[i]) {
        run = 1;
        i = 1;
        if (run > best) best = run;
      }
    }
  }
  return best / phraseTokens.length;
}

export function answerEvidenceScore(variants, windowTokens) {
  let best = 0;
  for (const variant of variants ?? []) {
    const toks = tokenize(variant);
    if (!toks.length) continue;
    const score = Math.max(phraseMatchScore(toks, windowTokens), contiguousScore(toks, windowTokens));
    if (score > best) best = score;
  }
  return best;
}

const NUM_ONES = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen'];
const NUM_TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety'];

/** Digit answer -> spoken word variants (0..999999). Modest scope: ones/tens/compound/hundred/thousand. */
export function numberWordVariants(raw) {
  const digits = String(raw ?? '').replace(/[£$€]/g, '').trim();
  if (!/^\d{1,6}$/.test(digits)) return [];
  const n = Number(digits);
  const below100 = (x) => (x < 20 ? NUM_ONES[x] : (x % 10 ? `${NUM_TENS[Math.floor(x / 10)]}-${NUM_ONES[x % 10]}` : NUM_TENS[Math.floor(x / 10)]));
  const below1000 = (x) => {
    if (x < 100) return below100(x);
    const h = Math.floor(x / 100), r = x % 100;
    const head = `${NUM_ONES[h]} hundred`;
    return r ? `${head} and ${below100(r)}` : head;
  };
  const out = [];
  const push = (w) => { out.push(w); if (w.includes('-')) out.push(w.replace(/-/g, ' ')); };
  if (n < 1000) push(below1000(n));
  else {
    const th = Math.floor(n / 1000), r = n % 1000;
    const head = `${below1000(th)} thousand`;
    push(r ? `${head} ${below1000(r)}` : head);
  }
  if (n === 100) out.push('a hundred');
  if (n > 100 && n < 200) push(`a hundred and ${below100(n % 100)}`);
  if (n === 1000) out.push('a thousand');
  if (n > 1000 && n < 2000) push(`a thousand ${below1000(n % 1000)}`);
  return out;
}

const STOPWORDS = new Set([
  "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "by", "for",
  "is", "are", "was", "were", "be", "with", "from", "that", "this", "it",
  "as", "your", "you", "their", "its", "will", "would", "can", "could",
  "choose", "write", "complete", "below", "above", "following", "questions",
  "question", "answer", "answers", "one", "two", "three", "words", "word",
  "number", "numbers", "letters", "letter", "correct", "box", "list",
  "options", "option", "each", "which", "what", "where", "when", "who",
  "why", "how", "more", "than", "not", "no", "yes",
]);

export function stemKeywords(prompt) {
  return tokenize(prompt).filter((t) => t.length >= 4 && !STOPWORDS.has(t));
}

// ---------------------------------------------------------------------------
// Clock handling (sec vs millisecond, bounds, monotonicity)
// ---------------------------------------------------------------------------

export function detectTimestampUnit(values, durationSec) {
  const nums = (values ?? []).filter((v) => Number.isFinite(v));
  if (!nums.length) return { unit: null, confidence: 0, reason: "no_values" };
  const max = Math.max(...nums);
  if (!Number.isFinite(durationSec) || durationSec <= 0) {
    if (max > 7200) return { unit: "ms", confidence: 0.6, reason: "magnitude_heuristic" };
    if (max > 3600) return { unit: "ambiguous", confidence: 0.3, reason: "magnitude_ambiguous" };
    return { unit: "sec", confidence: 0.4, reason: "magnitude_heuristic_weak" };
  }
  const high = durationSec * 1.2 + 5;
  if (max <= high) {
    return { unit: "sec", confidence: 0.95, reason: "fits_duration_as_sec" };
  }
  if (max / 1000 <= high) {
    // A millisecond rescue is only credible when the converted span covers a
    // plausible part of the recording (>= 25% of its duration). Tiny converted
    // spans stay seconds so bounds validation reports the real overflow.
    if (max / 1000 >= durationSec * 0.25) {
      return { unit: "ms", confidence: 0.95, reason: "fits_duration_as_ms" };
    }
    return { unit: "sec", confidence: 0.5, reason: "ms_span_implausible_keep_sec" };
  }
  return { unit: "invalid", confidence: 0.9, reason: "exceeds_duration_both_scales" };
}

// entries: [{t_sec, text?, sp?, q?}] in source order.
// Returns normalized entries (t_sec always seconds) + validation verdict.
export function validateClock(entries, { durationSec = null, allowSlackSec = 2 } = {}) {
  const reasons = [];
  const list = (entries ?? []).filter((e) => Number.isFinite(e?.t_sec));
  if (!list.length) {
    return { valid: false, reasons: ["no_timestamps"], entries: [], unit: null };
  }
  const detected = detectTimestampUnit(list.map((e) => e.t_sec), durationSec);
  let unitUsed = detected.unit;
  let out = list;
  if (detected.unit === "ms") {
    out = list.map((e) => ({ ...e, t_sec: e.t_sec / 1000 }));
  } else if (detected.unit === "ambiguous" || detected.unit === "invalid" || detected.unit === null) {
    reasons.push(`clock_unit_${detected.reason}`);
    unitUsed = detected.unit === "ambiguous" ? "ambiguous" : detected.unit;
  }
  let monotonic = true;
  for (let i = 1; i < out.length; i += 1) {
    if (out[i].t_sec < out[i - 1].t_sec - 0.001) {
      monotonic = false;
      break;
    }
  }
  if (!monotonic) reasons.push("non_monotonic");
  let inBounds = true;
  if (Number.isFinite(durationSec) && durationSec > 0) {
    for (const e of out) {
      if (e.t_sec < -allowSlackSec || e.t_sec > durationSec + allowSlackSec) {
        inBounds = false;
        break;
      }
    }
    if (!inBounds) reasons.push("out_of_bounds");
  }
  const unitOk = detected.unit === "sec" || detected.unit === "ms";
  const valid = monotonic && inBounds && unitOk;
  return {
    valid,
    reasons,
    entries: out,
    unit: unitUsed,
    unit_confidence: detected.confidence,
    unit_reason: detected.reason,
  };
}

// ---------------------------------------------------------------------------
// full_test <-> part offset estimation
// ---------------------------------------------------------------------------

// anchors: [{source_sec, target_sec}]. Fit t_target = a * t_source + b.
export function estimateOffset(anchors, { maxResidual = AUTO_THRESHOLDS.max_residual_sec, minAnchors = AUTO_THRESHOLDS.min_anchors, speedMin = AUTO_THRESHOLDS.speed_min, speedMax = AUTO_THRESHOLDS.speed_max } = {}) {
  const pts = (anchors ?? []).filter((p) => Number.isFinite(p?.source_sec) && Number.isFinite(p?.target_sec));
  if (pts.length < minAnchors) {
    return { ok: false, reason: "insufficient_anchors", n: pts.length, residuals: [], max_abs_residual: null };
  }
  const n = pts.length;
  const xMean = pts.reduce((s, p) => s + p.source_sec, 0) / n;
  const yMean = pts.reduce((s, p) => s + p.target_sec, 0) / n;
  let sxx = 0;
  let sxy = 0;
  for (const p of pts) {
    sxx += (p.source_sec - xMean) ** 2;
    sxy += (p.source_sec - xMean) * (p.target_sec - yMean);
  }
  if (sxx <= 1e-9) {
    return { ok: false, reason: "degenerate_anchors", n, residuals: [], max_abs_residual: null };
  }
  const a = sxy / sxx;
  const b = yMean - a * xMean;
  const residuals = pts.map((p) => p.target_sec - (a * p.source_sec + b));
  const maxAbs = Math.max(...residuals.map((r) => Math.abs(r)));
  const reasons = [];
  if (!(a >= speedMin && a <= speedMax)) reasons.push("speed_out_of_range");
  if (maxAbs > maxResidual) reasons.push("residual_exceeds_limit");
  const sorted = [...pts].sort((p1, p2) => p1.source_sec - p2.source_sec);
  for (let i = 1; i < sorted.length; i += 1) {
    if (sorted[i].target_sec < sorted[i - 1].target_sec - 1e-6) {
      reasons.push("non_monotonic_targets");
      break;
    }
  }
  return {
    ok: reasons.length === 0,
    reason: reasons.length ? reasons.join(",") : "ok",
    a,
    b,
    n,
    residuals,
    max_abs_residual: maxAbs,
  };
}

export function applyOffset(offset, sourceSec) {
  if (!offset || !offset.ok) return null;
  return offset.a * sourceSec + offset.b;
}

// ---------------------------------------------------------------------------
// Candidate construction
// ---------------------------------------------------------------------------

function segmentBounds(segments, index, maxGapSec, defaultSec) {
  const seg = segments[index];
  const next = segments[index + 1];
  const start = Number.isFinite(seg.start_sec) ? seg.start_sec : seg.t_sec;
  let end;
  if (next && Number.isFinite(next.start_sec ?? next.t_sec)) {
    end = next.start_sec ?? next.t_sec;
    if (end - start > maxGapSec) end = start + maxGapSec;
  } else {
    end = start + defaultSec;
  }
  if (end <= start) end = start + 1;
  return { start_sec: start, end_sec: end };
}

// questions: [{number, group_id, prompt, answer_variants, stem_keywords?}]
// transcript: {segments:[{t_sec, start_sec?, end_sec?, text, q?:[..]}], source, sha256?}
export function buildCandidates({ questions, transcript, config = {} }) {
  const segments = (transcript?.segments ?? [])
    .map((s) => ({
      ...s,
      t_sec: Number.isFinite(s.t_sec) ? s.t_sec : (Number.isFinite(s.start_sec) ? s.start_sec : null),
    }))
    .filter((s) => Number.isFinite(s.t_sec))
    .sort((a, b) => a.t_sec - b.t_sec);
  const maxGap = config.marker_window_max_sec ?? AUTO_THRESHOLDS.marker_window_max_sec;
  const defaultWin = config.marker_window_default_sec ?? AUTO_THRESHOLDS.marker_window_default_sec;
  const pad = config.answer_window_pad_sec ?? AUTO_THRESHOLDS.answer_window_pad_sec;
  const byNumber = new Map();
  for (const q of questions ?? []) byNumber.set(Number(q.number), q);

  // Precompute per-segment token arrays lazily with a small cache.
  const tokensCache = new Map();
  const segTokens = (seg) => {
    const key = seg;
    if (!tokensCache.has(key)) tokensCache.set(key, tokenize(seg.text ?? ""));
    return tokensCache.get(key);
  };

  const candidates = new Map(); // number -> [cand]
  const push = (number, cand) => {
    if (!candidates.has(number)) candidates.set(number, []);
    candidates.get(number).push(cand);
  };

  for (let i = 0; i < segments.length; i += 1) {
    const seg = segments[i];
    const bounds = segmentBounds(segments, i, maxGap, defaultWin);
    const segToks = segTokens(seg);
    const qnums = Array.isArray(seg.q) ? seg.q.map(Number) : [];
    // (a) official transcript Qn markers.
    for (const n of qnums) {
      if (!byNumber.has(n)) continue;
      push(n, {
        start_sec: bounds.start_sec,
        end_sec: bounds.end_sec,
        source: "transcript_qn_marker",
        context_score: 0.55,
        evidence_refs: [seg.source_ref ?? `segment@${bounds.start_sec}`],
        segment_text: seg.text ?? "",
      });
    }
    // (b) answer phrase occurrences.
    for (const [n, q] of byNumber) {
      const variants = q.answer_variants ?? [];
      if (!variants.length) continue;
      const score = answerEvidenceScore(variants, segToks);
      if (score < 0.9) continue;
      const isMarker = qnums.includes(n);
      push(n, {
        start_sec: Math.max(0, bounds.start_sec - pad),
        end_sec: bounds.end_sec + pad,
        source: isMarker ? "answer_in_marker_window" : "answer_occurrence",
        context_score: isMarker ? 0.85 : 0.55,
        evidence_refs: [seg.source_ref ?? `segment@${bounds.start_sec}`],
        segment_text: seg.text ?? "",
        answer_score: score,
      });
    }
  }

  // (c) stem keyword candidates (weak, only when nothing else exists).
  for (const [n, q] of byNumber) {
    if (candidates.has(n) && candidates.get(n).length) continue;
    const kws = q.stem_keywords ?? stemKeywords(q.prompt ?? "");
    if (!kws.length) continue;
    let best = null;
    for (let i = 0; i < segments.length; i += 1) {
      const score = keywordScore(kws, segTokens(segments[i]));
      if (score >= 0.6 && (!best || score > best.score)) {
        const bounds = segmentBounds(segments, i, maxGap, defaultWin);
        best = { score, bounds, seg: segments[i] };
      }
    }
    if (best) {
      push(n, {
        start_sec: best.bounds.start_sec,
        end_sec: best.bounds.end_sec,
        source: "stem_keywords",
        context_score: 0.2 * best.score,
        evidence_refs: [best.seg.source_ref ?? `segment@${best.bounds.start_sec}`],
        segment_text: best.seg.text ?? "",
      });
    }
  }

  // Deduplicate near-identical windows per question.
  for (const [n, list] of candidates) {
    list.sort((a, b) => (b.context_score - a.context_score) || (a.start_sec - b.start_sec));
    const dedup = [];
    for (const c of list) {
      const dup = dedup.find((d) => Math.abs(d.start_sec - c.start_sec) < 1.5 && Math.abs(d.end_sec - c.end_sec) < 3);
      if (dup) {
        if (c.context_score > dup.context_score) Object.assign(dup, c);
        continue;
      }
      dedup.push({ ...c });
    }
    candidates.set(n, dedup);
  }
  return candidates;
}

// ---------------------------------------------------------------------------
// Dynamic programming window selection
// ---------------------------------------------------------------------------

// nodes: [{key, numbers, candidates:[cand], required:boolean}]
// Returns per-node choice plus margin (best vs forced-different cost).
export function selectWindowsDP(nodes, { anchors = [], anchorScale = 30, weights = AUTO_THRESHOLDS.dp_weights } = {}) {
  const anchorList = (anchors ?? []).filter((a) => Number.isFinite(a?.t_sec ?? a?.start_sec));
  const anchorPenalty = (cand) => {
    if (!cand || !anchorList.length) return 0;
    let best = Infinity;
    for (const a of anchorList) {
      const at = a.t_sec ?? a.start_sec;
      const d = Math.abs(cand.start_sec - at);
      if (d < best) best = d;
    }
    return Math.min(1, best / anchorScale);
  };
  const nodeCost = (cand, node) => {
    if (!cand) return weights.skip * (node.required ? 1.5 : 1);
    return weights.context * (1 - (cand.context_score ?? 0)) + weights.anchor * anchorPenalty(cand);
  };
  const transCost = (prev, cur) => {
    if (!prev || !cur) return 0;
    if (cur.start_sec >= prev.start_sec) return 0;
    const overlap = Math.min(prev.end_sec, cur.end_sec) - Math.max(prev.start_sec, cur.start_sec);
    const overlapPen = overlap > 0 ? Math.min(1, overlap / 10) : 0;
    return weights.reverse + weights.reverse_overlap * overlapPen;
  };

  const n = nodes.length;
  if (n === 0) return { picks: [], total_cost: 0 };
  const options = nodes.map((node) => [null, ...(node.candidates ?? [])]);
  const dp = options.map(() => []);
  const back = options.map(() => []);
  for (let j = 0; j < options[0].length; j += 1) {
    dp[0][j] = nodeCost(options[0][j], nodes[0]);
    back[0][j] = -1;
  }
  for (let i = 1; i < n; i += 1) {
    for (let j = 0; j < options[i].length; j += 1) {
      let best = Infinity;
      let bestK = -1;
      for (let k = 0; k < options[i - 1].length; k += 1) {
        const total = dp[i - 1][k] + transCost(options[i - 1][k], options[i][j]);
        if (total < best) {
          best = total;
          bestK = k;
        }
      }
      dp[i][j] = best + nodeCost(options[i][j], nodes[i]);
      back[i][j] = bestK;
    }
  }
  let bestJ = 0;
  for (let j = 1; j < options[n - 1].length; j += 1) {
    if (dp[n - 1][j] < dp[n - 1][bestJ]) bestJ = j;
  }
  const totalCost = dp[n - 1][bestJ];
  const picks = new Array(n);
  let j = bestJ;
  for (let i = n - 1; i >= 0; i -= 1) {
    picks[i] = { chosen: options[i][j], option_index: j };
    j = back[i][j];
  }
  // Exact backward DP: bdp[i][j] = min cost from node i (option j) through the end.
  const bdp = options.map(() => []);
  for (let j = 0; j < options[n - 1].length; j += 1) {
    bdp[n - 1][j] = nodeCost(options[n - 1][j], nodes[n - 1]);
  }
  for (let i = n - 2; i >= 0; i -= 1) {
    for (let k = 0; k < options[i].length; k += 1) {
      let best = Infinity;
      for (let m = 0; m < options[i + 1].length; m += 1) {
        const total = transCost(options[i][k], options[i + 1][m]) + bdp[i + 1][m];
        if (total < best) best = total;
      }
      bdp[i][k] = nodeCost(options[i][k], nodes[i]) + best;
    }
  }
  // Margins: best cost vs best cost with this node forced to a different
  // candidate (the skip option is not counted as an alternative candidate).
  for (let i = 0; i < n; i += 1) {
    const chosen = picks[i].chosen;
    const altOptions = options[i].filter((c) => c !== chosen && c !== null);
    if (!altOptions.length) {
      picks[i].margin = null;
      picks[i].margin_reason = "single_candidate";
      continue;
    }
    let altTotal = Infinity;
    for (const alt of altOptions) {
      const nodeCostAlt = nodeCost(alt, nodes[i]);
      let prevBest = 0;
      if (i > 0) {
        prevBest = Infinity;
        for (let k = 0; k < options[i - 1].length; k += 1) {
          const total = dp[i - 1][k] + transCost(options[i - 1][k], alt);
          if (total < prevBest) prevBest = total;
        }
      }
      let suffix = 0;
      if (i + 1 < n) {
        suffix = Infinity;
        for (let m = 0; m < options[i + 1].length; m += 1) {
          const total = transCost(alt, options[i + 1][m]) + bdp[i + 1][m];
          if (total < suffix) suffix = total;
        }
      }
      altTotal = Math.min(altTotal, prevBest + nodeCostAlt + suffix);
    }
    picks[i].margin = Number.isFinite(altTotal) ? Math.max(0, altTotal - totalCost) : null;
    picks[i].margin_reason = "alt_path_delta";
  }
  return { picks, total_cost: totalCost };
}

// ---------------------------------------------------------------------------
// Confidence composition and gating
// ---------------------------------------------------------------------------

export function composeConfidence({ identity_valid = false, clock_valid = false, text_anchor_score = 0, aligner_word_confidence = null, ambiguity_margin = null } = {}) {
  const marginFactor = ambiguity_margin == null ? 1 : Math.max(0, Math.min(1, 0.5 + ambiguity_margin));
  const score = (identity_valid ? 1 : 0)
    * (clock_valid ? 1 : 0)
    * Math.max(0, Math.min(1, text_anchor_score))
    * (aligner_word_confidence == null ? 1 : Math.max(0, Math.min(1, aligner_word_confidence)))
    * marginFactor;
  return {
    score,
    parts: { identity_valid, clock_valid, text_anchor_score, aligner_word_confidence, ambiguity_margin },
  };
}

export function gateNeedsReview(confidence, method, thresholds = AUTO_THRESHOLDS) {
  const failures = [];
  const p = confidence?.parts ?? {};
  if (!p.identity_valid) failures.push("identity_not_verified");
  if (!p.clock_valid) failures.push("clock_not_valid");
  if (!(p.text_anchor_score >= thresholds.anchor_similarity)) failures.push("anchor_similarity_below_threshold");
  if (p.ambiguity_margin != null && p.ambiguity_margin < thresholds.ambiguity_margin) failures.push("ambiguity_margin_below_threshold");
  if (method === "asr_forced_align" && !(p.aligner_word_confidence >= thresholds.aligner_word_confidence)) {
    failures.push("aligner_word_confidence_below_threshold");
  }
  return { passes: failures.length === 0, failures };
}

// ---------------------------------------------------------------------------
// Main entry: alignQuestions
// ---------------------------------------------------------------------------

function buildNodes({ questions, groups, candidatesByNumber, verifiedWindows, config }) {
  const groupList = [];
  const groupIndex = new Map();
  const ordered = [...(questions ?? [])].sort((a, b) => Number(a.number) - Number(b.number));
  for (const q of ordered) {
    const gid = q.group_id ?? `q:${q.number}`;
    if (!groupIndex.has(gid)) {
      groupIndex.set(gid, {
        key: gid,
        group_id: q.group_id ?? null,
        numbers: [],
        type: (groups ?? []).find((g) => g.id === gid)?.type ?? q.type ?? null,
        required: true,
      });
      groupList.push(groupIndex.get(gid));
    }
    groupIndex.get(gid).numbers.push(Number(q.number));
  }
  return groupList.map((node) => {
    const cands = [];
    for (const n of node.numbers) {
      for (const c of candidatesByNumber.get(n) ?? []) {
        cands.push({ ...c, for_number: n });
      }
    }
    // Group-level candidates: prefer windows where multiple member answers co-occur.
    if (node.numbers.length > 1 && cands.length > 1) {
      const byWindow = new Map();
      for (const c of cands) {
        const key = `${Math.round(c.start_sec)}:${Math.round(c.end_sec)}`;
        if (!byWindow.has(key)) byWindow.set(key, []);
        byWindow.get(key).push(c);
      }
      const groupCands = [];
      for (const [, list] of byWindow) {
        const numbersHit = new Set(list.map((c) => c.for_number));
        if (numbersHit.size >= Math.min(2, node.numbers.length)) {
          const base = list.reduce((best, c) => (c.context_score > best.context_score ? c : best), list[0]);
          groupCands.push({
            ...base,
            source: `${base.source}+group_window`,
            context_score: Math.min(1, base.context_score + 0.1 * (numbersHit.size - 1)),
            group_numbers: [...numbersHit],
            shared_window: true,
          });
        }
      }
      if (groupCands.length) cands.push(...groupCands);
    }
    // Deduplicate again at node level.
    const dedup = [];
    for (const c of cands.sort((a, b) => b.context_score - a.context_score)) {
      const dup = dedup.find((d) => Math.abs(d.start_sec - c.start_sec) < 1.5 && Math.abs(d.end_sec - c.end_sec) < 3);
      if (dup) continue;
      dedup.push(c);
    }
    node.candidates = dedup;
    return node;
  });
}

function findVerifiedWindow(number, verifiedWindows, tolerance = 1.0) {
  for (const w of verifiedWindows ?? []) {
    if (Number(w.number) !== Number(number)) continue;
    if (!Number.isFinite(w.start_sec) || !Number.isFinite(w.end_sec)) continue;
    return { ...w, tolerance_used: tolerance };
  }
  return null;
}

export function alignQuestions({ identity, part, questions, groups, audio, transcript, candidateTimestamps, config = {} } = {}) {
  const warnings = [];
  const verifiedWindows = config.verified_windows ?? [];
  const sectionRange = config.section_range ?? (transcript?.section_range ?? null);
  const base = {
    schema: MATCHER_SCHEMA,
    matcher_version: MATCHER_VERSION,
    threshold_version: THRESHOLD_VERSION,
    identity: identity ?? null,
    part: part ?? null,
    audio_id: audio?.audio_id ?? null,
    method: "none",
    model_version: config.model_version ?? null,
    clock: null,
    questions: [],
    groups: [],
    coverage: null,
    warnings,
  };

  if (!audio || !audio.audio_id) {
    warnings.push("no_audio_record");
    base.coverage = coverageOf(base.questions, base.groups);
    return base;
  }
  if (audio.identity_status !== "verified") {
    warnings.push("audio_identity_not_verified");
    base.questions = (questions ?? []).map((q) => ({
      number: Number(q.number),
      group_id: q.group_id ?? null,
      status: ALIGN_STATUS.UNVERIFIED,
      intervals: [],
      confidence: composeConfidence({ identity_valid: false }),
      evidence_refs: [],
      reasons: ["audio_identity_not_verified"],
    }));
    base.coverage = coverageOf(base.questions, base.groups);
    return base;
  }

  // Clock validation over candidate timestamps.
  let clock = { valid: false, reasons: ["no_candidates"], entries: [] };
  let transcriptSegments = transcript?.segments ?? [];
  if (candidateTimestamps?.length) {
    const raw = candidateTimestamps.map((c) => ({
      t_sec: Number.isFinite(c.t_sec) ? c.t_sec : c.t,
      text: c.text,
      q: c.q,
      source_ref: c.source_ref,
    }));
    clock = validateClock(raw, { durationSec: audio.duration_sec });
    if (clock.valid) {
      transcriptSegments = clock.entries;
    } else {
      warnings.push(`clock_invalid:${clock.reasons.join("+")}`);
    }
  } else if (transcriptSegments.length) {
    clock = validateClock(transcriptSegments, { durationSec: audio.duration_sec });
    if (clock.valid) transcriptSegments = clock.entries;
    else warnings.push(`clock_invalid:transcript:${clock.reasons.join("+")}`);
  }
  base.clock = { valid: clock.valid, unit: clock.unit ?? null, reasons: clock.reasons, duration_sec: audio.duration_sec ?? null };

  const effectiveTranscript = clock.valid ? { ...transcript, segments: transcriptSegments } : { segments: [] };
  const candidatesByNumber = buildCandidates({ questions, transcript: effectiveTranscript, config });
  const nodes = buildNodes({ questions, groups, candidatesByNumber, verifiedWindows, config });
  const dp = selectWindowsDP(nodes, { anchors: config.anchors ?? [] });

  const method = config.method ?? (clock.valid ? "official_transcript_candidates+dp" : "none");
  base.method = method;

  const questionResults = new Map();
  const groupResults = [];
  for (let i = 0; i < nodes.length; i += 1) {
    const node = nodes[i];
    const pick = dp.picks[i];
    const chosen = pick.chosen;
    const sharedWindow = Boolean(chosen?.shared_window);
    for (const n of node.numbers) {
      const q = (questions ?? []).find((x) => Number(x.number) === n) ?? { number: n };
      const gold = findVerifiedWindow(n, verifiedWindows, config.verified_tolerance_sec ?? 1.0);
      const textAnchor = chosen
        ? Math.max(
          chosen.answer_score ?? 0,
          chosen.source === "transcript_qn_marker" ? 0.55 : 0,
          chosen.context_score ?? 0,
        )
        : 0;
      const confidence = composeConfidence({
        identity_valid: true,
        clock_valid: clock.valid,
        text_anchor_score: textAnchor,
        aligner_word_confidence: chosen?.aligner_word_confidence ?? null,
        ambiguity_margin: pick.margin,
      });
      const gate = gateNeedsReview(confidence, method);
      let status;
      const reasons = [];
      // Agreement with an independent label = both point at the same region:
      // a positive overlap covering at least half of the smaller window. The
      // question's own candidate windows count here as well, so a group-level
      // pick that landed on a different member window cannot block a question
      // whose own candidate agrees with the independent label.
      let goldMatch = null;
      if (gold) {
        const pool = chosen
          ? [chosen, ...(candidatesByNumber.get(n) ?? [])]
          : (candidatesByNumber.get(n) ?? []);
        for (const c of pool) {
          const overlap = Math.max(0, Math.min(c.end_sec, gold.end_sec) - Math.max(c.start_sec, gold.start_sec));
          const smaller = Math.min(c.end_sec - c.start_sec, gold.end_sec - gold.start_sec);
          if (overlap > 0 && overlap >= 0.5 * smaller) { goldMatch = c; break; }
        }
      }
      const goldCovered = Boolean(gold && goldMatch);
      if (goldCovered) {
        status = ALIGN_STATUS.VERIFIED;
      } else if (!chosen) {
        status = sectionRange ? ALIGN_STATUS.SECTION_ONLY : ALIGN_STATUS.UNVERIFIED;
        reasons.push("no_candidate_window");
      } else if (gate.passes) {
        status = ALIGN_STATUS.NEEDS_REVIEW;
      } else {
        status = ALIGN_STATUS.UNVERIFIED;
        reasons.push(...gate.failures);
      }
      if (sharedWindow) reasons.push("shared_group_window");
      // A verified question reports the independent gold window itself; the
      // matcher's own candidate window is kept in candidate_window for audit.
      const intervals = goldCovered
        ? [{ start_sec: gold.start_sec, end_sec: gold.end_sec, role: "answer_evidence" }]
        : chosen
          ? [{ start_sec: chosen.start_sec, end_sec: chosen.end_sec, role: "question_context" }]
          : [];
      const result = {
        number: n,
        group_id: q.group_id ?? null,
        status,
        intervals,
        shared_window: sharedWindow,
        candidate_source: chosen?.source ?? null,
        candidate_window: chosen ? { start_sec: chosen.start_sec, end_sec: chosen.end_sec } : null,
        candidates_considered: (candidatesByNumber.get(n) ?? []).length,
        confidence,
        evidence_refs: chosen?.evidence_refs ?? [],
        reasons,
        section_range: !chosen && sectionRange ? sectionRange : undefined,
      };
      if (gold) {
        result.verified_by = { labeler: gold.labeler ?? "unknown", source: gold.source ?? "unknown", window: { start_sec: gold.start_sec, end_sec: gold.end_sec } };
        if (goldCovered && goldMatch && goldMatch !== chosen) {
          result.gold_match_source = goldMatch.source ?? null;
          result.gold_match_window = { start_sec: goldMatch.start_sec, end_sec: goldMatch.end_sec };
        }
        if (status !== ALIGN_STATUS.VERIFIED) reasons.push("gold_window_mismatch");
      }
      questionResults.set(n, result);
    }
    groupResults.push({
      group_id: node.group_id,
      numbers: node.numbers,
      status: questionResults.get(node.numbers[0])?.status ?? ALIGN_STATUS.UNVERIFIED,
      shared_window: sharedWindow,
      intervals: chosen ? [{ start_sec: chosen.start_sec, end_sec: chosen.end_sec, role: "answer_evidence" }] : [],
      margin: pick.margin,
      margin_reason: pick.margin_reason,
    });
  }

  base.questions = [...questionResults.values()].sort((a, b) => a.number - b.number);
  base.groups = groupResults;
  base.coverage = coverageOf(base.questions, base.groups);
  return base;
}

export function coverageOf(questions, groups) {
  const counts = {
    questions_total: (questions ?? []).length,
    verified: 0,
    needs_review: 0,
    section_only: 0,
    unverified: 0,
    missing: 0,
    groups_total: (groups ?? []).length,
    groups_shared_window: 0,
  };
  for (const q of questions ?? []) {
    if (counts[q.status] != null) counts[q.status] += 1;
  }
  for (const g of groups ?? []) {
    if (g.shared_window) counts.groups_shared_window += 1;
  }
  return counts;
}

export const __internals = {
  segmentBounds,
  buildNodes,
  findVerifiedWindow,
};
