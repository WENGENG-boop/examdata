#!/usr/bin/env node
/**
 * build-alignment-gold.mjs — build the S10 alignment gold fixture from real,
 * independent label sources.
 *
 * Sources:
 *   * cam21 official site transcript pages (`audio/cam21-transcripts.json`),
 *     whose (Qn) markers give candidate windows; each window is clock-validated
 *     against the downloaded audio duration and cross-checked against the
 *     question's answer from the S08 question index.
 *   * optional local ASR words (from tools/run-alignment.mjs output) for
 *     maslow parts, cross-checked against the script text.
 *
 * Output: ielts-api/tests/fixtures/alignment-gold.json
 *
 * Usage:
 *   node tools/build-alignment-gold.mjs [--data-dir DIR] [--out FILE]
 *     [--asr-dir DIR]   (directory with <identity>.asr.json files to merge)
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { resolveDataDir } from '../data-store.mjs';
import { answerEvidenceScore, numberWordVariants, tokenize, validateClock } from '../audio-matcher.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.join(__dirname, '..', 'tests', 'fixtures', 'alignment-gold.json');

function parseArgs(argv) {
  const out = {};
  for (let i = 2; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === '--data-dir') out.dataDir = argv[++i];
    else if (a === '--out') out.out = argv[++i];
    else if (a === '--asr-dir') out.asrDir = argv[++i];
    else if (a === '--crosscheck') out.crosscheck = true;
  }
  return out;
}

function loadAsrMap(asrDir) {
  const map = new Map();
  if (!asrDir || !fs.existsSync(asrDir)) return map;
  for (const file of fs.readdirSync(asrDir).filter((f) => f.endsWith('.asr.json'))) {
    try {
      const doc = loadJson(path.join(asrDir, file));
      if (doc.identity) map.set(doc.identity, doc);
    } catch {
      // unreadable ASR file: skip, it cannot cross-check anything
    }
  }
  return map;
}

// Cross-check one transcript window against independently produced ASR words
// for the same audio. A window only becomes asr_confirmed when the answer
// variants are actually heard inside the window (score >= 0.9) and the ASR was
// produced from the same audio bytes (sha256 match).
function asrCrosscheck({ asr, windowStart, windowEnd, variants, matchForm, catalogSha }) {
  if (matchForm === 'letter_not_text_verifiable' || matchForm === 'group_set_not_text_verifiable' || matchForm === 'no_answer_entry') {
    return { status: 'not_text_verifiable', words_in_window: null, answer_score_asr: null };
  }
  if (!asr) return { status: 'no_asr', words_in_window: null, answer_score_asr: null };
  const audioHashMatch = !asr.audio_sha256 || !catalogSha || asr.audio_sha256 === catalogSha;
  const winWords = (asr.words ?? []).filter(
    (w) => Number.isFinite(w.start) && w.start >= windowStart - 0.01 && w.start < windowEnd,
  );
  const winToks = winWords.map((w) => tokenize(w.word)[0]).filter(Boolean);
  const score = winToks.length ? answerEvidenceScore(variants, winToks) : null;
  let status;
  if (!audioHashMatch) status = 'audio_hash_mismatch';
  else if (!winToks.length) status = 'no_asr_words';
  else if (score >= 0.9) status = 'asr_confirmed';
  else if (score > 0) status = 'asr_weak';
  else status = 'no_match';
  return {
    status,
    words_in_window: winToks.length,
    answer_score_asr: score,
    audio_sha256: asr.audio_sha256 ?? null,
    audio_hash_match: audioHashMatch,
    model_version: asr.model_version ?? null,
  };
}

function loadJson(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

function loadCatalog(dataDir) {
  const doc = loadJson(path.join(dataDir, 'runs', '20261003T140007Z-repair', 'audio', 'audio-catalog.json'));
  const map = new Map();
  for (const r of doc.records ?? []) {
    if (r.identity) map.set(r.identity, r);
  }
  return map;
}

function cam21Entries({ dataDir, index, catalog, asrByPart, crosscheck }) {
  const transcripts = loadJson(path.join(dataDir, 'runs', '20261003T140007Z-repair', 'audio', 'cam21-transcripts.json'));
  const answers = index.answers ?? {};
  const entries = [];
  const problems = [];
  for (const [testStr, page] of Object.entries(transcripts.pages ?? {})) {
    const test = Number(testStr);
    for (const [sectionStr, segments] of Object.entries(page.sections ?? {})) {
      const section = Number(sectionStr);
      const cat = catalog.get(`cambridge:21:shared:listening:${test}:P${section}`) ?? null;
      // Build marker list: [{number, t}] sorted by time, from all segments.
      const markers = [];
      for (const seg of segments) {
        for (const n of seg.q ?? []) markers.push({ number: Number(n), t: Number(seg.t), text: seg.text ?? '' });
      }
      markers.sort((a, b) => a.t - b.t);
      const clock = validateClock(
        segments.map((s) => ({ t_sec: Number(s.t), text: s.text })),
        { durationSec: cat?.duration_sec ?? page.duration_sec ?? null },
      );
      for (let i = 0; i < markers.length; i += 1) {
        const m = markers[i];
        const nextT = markers[i + 1]?.t;
        const end = Number.isFinite(nextT) && nextT > m.t ? Math.min(nextT, m.t + 45) : m.t + 20;
        // Window text: segments whose t in [m.t, end).
        const winSegs = segments.filter((s) => Number(s.t) >= m.t - 0.01 && Number(s.t) < end);
        const winText = winSegs.map((s) => s.text).join(' ');
        const answerEntry = answers[`cambridge:21:shared:listening:${test}:P${section}:Q${m.number}`];
        const raw = typeof answerEntry?.raw === 'string' ? answerEntry.raw.trim() : null;
        const accept = Array.isArray(answerEntry?.accept) ? answerEntry.accept : null;
        const isLetter = raw != null && /^[A-Za-z]$/.test(raw);
        let variants = [];
        let matchForm = null;
        if (raw == null && accept) matchForm = 'group_set_not_text_verifiable';
        else if (raw == null) matchForm = 'no_answer_entry';
        else if (isLetter) matchForm = 'letter_not_text_verifiable';
        else {
          variants = [raw];
          const words = numberWordVariants(raw);
          if (words.length) variants = variants.concat(words);
          matchForm = words.length ? 'raw_or_number_word' : 'raw';
        }
        const winToks = tokenize(winText);
        let answerScore = null;
        if (variants.length) {
          const base = answerEvidenceScore([raw], winToks);
          const all = answerEvidenceScore(variants, winToks);
          answerScore = all;
          if (all > base) matchForm = 'number_word';
        }
        const asrX = crosscheck
          ? asrCrosscheck({
            asr: asrByPart?.get(`cambridge:21:shared:listening:${test}:P${section}`) ?? null,
            windowStart: m.t,
            windowEnd: end,
            variants,
            matchForm,
            catalogSha: cat?.content_sha256 ?? null,
          })
          : null;
        entries.push({
          book: 21,
          variant: 'shared',
          skill: 'listening',
          test,
          part: `P${section}`,
          number: m.number,
          start_sec: m.t,
          end_sec: end,
          labeler: 'cam21-site-transcript',
          source: `maqsudjon-cell/cambridge-21 page sha256=${page.page_sha256 ?? 'unknown'}`,
          audio_sha256: cat?.content_sha256 ?? null,
          evidence: {
            window_text: winText.slice(0, 240),
            answer_raw: raw,
            answer_match_form: matchForm,
            answer_match_score: answerScore,
            clock_valid: clock.valid,
            clock_reasons: clock.reasons,
            audio_duration_sec: cat?.duration_sec ?? null,
            ...(asrX ? { asr_crosscheck: asrX } : {}),
          },
        });
        if (answerScore != null && answerScore < 0.9) {
          const stem = raw.length > 3 && raw.endsWith('s') ? raw.slice(0, -1) : null;
          const stemInWindow = stem != null && winToks.includes(stem);
          problems.push({
            test, section, number: m.number,
            reason: stemInWindow ? 'answer_form_mismatch' : 'answer_not_in_window',
            score: answerScore,
            answer_raw: raw,
            stem,
            stem_in_window: stemInWindow,
          });
        }
      }
    }
  }
  return { entries, problems, page_sha: Object.fromEntries(Object.entries(transcripts.pages ?? {}).map(([t, p]) => [t, p.page_sha256])) };
}

function asrEntries({ asrDir, index }) {
  // Optional: merge ASR-derived gold entries (maslow). Each file:
  // { identity, part, audio_sha256, model_version, words: [...], script_match: {...} }
  if (!asrDir || !fs.existsSync(asrDir)) return { entries: [], problems: [] };
  const entries = [];
  const problems = [];
  for (const file of fs.readdirSync(asrDir).filter((f) => f.endsWith('.asr.json'))) {
    const doc = loadJson(path.join(asrDir, file));
    const identity = doc.identity;
    const m = /^cambridge:(\d+):shared:listening:(\d+):(P\d+)$/.exec(identity ?? '');
    if (!m) {
      problems.push({ file, reason: 'identity_unparsed' });
      continue;
    }
    entries.push({
      book: Number(m[1]), variant: 'shared', skill: 'listening', test: Number(m[2]), part: m[3],
      number: null,
      labeler: 'local-asr',
      source: `whisperx ${doc.model_version?.whisperx ?? '?'} whisper=${doc.model_version?.whisper_model ?? '?'}`,
      audio_sha256: doc.audio_sha256 ?? null,
      asr_segments: doc.segments ?? [],
      words_total: doc.words?.length ?? 0,
      evidence: { script_match: doc.script_match ?? null },
    });
  }
  return { entries, problems };
}

function main() {
  const args = parseArgs(process.argv);
  const dataDir = args.dataDir || resolveDataDir();
  const outPath = args.out || FIXTURE;
  const runDir = path.join(dataDir, 'runs', '20261003T140007Z-repair');
  const index = loadJson(path.join(runDir, 'index', 'question-index.json'));
  const catalog = loadCatalog(dataDir);

  const cam = cam21Entries({ dataDir, index, catalog, asrByPart: loadAsrMap(args.asrDir), crosscheck: Boolean(args.crosscheck) });
  const asr = asrEntries({ asrDir: args.asrDir, index });

  const crosscheckStats = {};
  for (const e of cam.entries) {
    const st = e.evidence?.asr_crosscheck?.status;
    if (st) crosscheckStats[st] = (crosscheckStats[st] ?? 0) + 1;
  }

  const parts = new Map();
  const addEntry = (e, kind) => {
    const key = `cambridge:${e.book}:${e.variant}:${e.skill}:${e.test}:${e.part}`;
    if (!parts.has(key)) parts.set(key, { identity: key, book: e.book, variant: e.variant, test: e.test, part: e.part, windows: [], asr: [] });
    if (kind === 'window') parts.get(key).windows.push(e);
    else parts.get(key).asr.push(e);
  };
  for (const e of cam.entries) addEntry(e, 'window');
  for (const e of asr.entries) addEntry(e, 'asr');

  const doc = {
    schema: 'ielts.alignment-gold/1',
    generated_at: new Date().toISOString(),
    label_policy: 'See tests/fixtures/alignment-gold.json header; windows come from independent label sources (site transcript with (Qn) markers, or local ASR cross-checked against script). Agent/tool identity recorded honestly; not human review.',
    calibration: {
      threshold_version: 's10-thresholds/2026-10-04.a',
      status: args.crosscheck ? 'asr_crosscheck_applied' : 'pending_asr_crosscheck',
      notes: args.crosscheck
        ? 'cam21 windows clock-validated against page transcripts and cross-checked against local ASR words for the same audio sha256; only asr_confirmed windows may upgrade a question.'
        : 'cam21 windows clock-validated against page transcripts; ASR cross-check pending for maslow parts.',
    },
    source_pages: cam.page_sha,
    parts: [...parts.values()],
    problems: [...cam.problems, ...asr.problems],
    stats: {
      parts_with_windows: [...parts.values()].filter((p) => p.windows.length).length,
      windows_total: cam.entries.length,
      asr_parts: [...parts.values()].filter((p) => p.asr.length).length,
      crosscheck: crosscheckStats,
      windows_confirmed: crosscheckStats.asr_confirmed ?? 0,
    },
  };
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, JSON.stringify(doc, null, 1));
  console.log(JSON.stringify({
    out: outPath,
    parts_with_windows: doc.stats.parts_with_windows,
    windows_total: doc.stats.windows_total,
    problems: doc.problems.length,
    crosscheck: crosscheckStats,
  }, null, 1));
}

main();
