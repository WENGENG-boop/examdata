#!/usr/bin/env node
/**
 * run-alignment.mjs — S10 batch runner: audio -> transcript -> per-question
 * alignment for listening Parts, persisting per-Part alignment output and ASR
 * word evidence for the gold cross-check.
 *
 * Targets:
 *   verified         catalog parts with identity_status === 'verified' (cam21)
 *   maslow-priority  parts the audit calls out for early cross-check
 *                    (b1t2 P1-4, b3 t2-t4 P1-4, b20t2 P4)
 *   all              every catalog part with a local file
 *
 * Per part it writes:
 *   <out-dir>/<identity with ':' -> '_'>.json       full provider output
 *   <out-dir>/<identity with ':' -> '_'>.asr.json   ASR words/segments (when ok)
 *   <out-dir>/summary.json                          run summary (rewritten per part)
 *
 * Usage:
 *   node tools/run-alignment.mjs [--data-dir DIR] [--run-id ID] [--out-dir DIR]
 *     [--only IDENTITY]... [--targets verified|maslow-priority|all]
 *     [--no-asr] [--force] [--limit N] [--gold FILE]
 */
import fs from 'node:fs';
import path from 'node:path';
import { resolveDataDir } from '../data-store.mjs';
import { buildAlignmentWithProvider, checkAlignmentSetup } from '../alignment-provider.mjs';
import { numberWordVariants, tokenize } from '../audio-matcher.mjs';

const DEFAULT_RUN_ID = '20261003T140007Z-repair';

const MASLOW_PRIORITY = [
  'cambridge:1:shared:listening:2:P1',
  'cambridge:1:shared:listening:2:P2',
  'cambridge:1:shared:listening:2:P3',
  'cambridge:1:shared:listening:2:P4',
  'cambridge:3:shared:listening:2:P1',
  'cambridge:3:shared:listening:2:P2',
  'cambridge:3:shared:listening:2:P3',
  'cambridge:3:shared:listening:2:P4',
  'cambridge:3:shared:listening:3:P1',
  'cambridge:3:shared:listening:3:P2',
  'cambridge:3:shared:listening:3:P3',
  'cambridge:3:shared:listening:3:P4',
  'cambridge:3:shared:listening:4:P1',
  'cambridge:3:shared:listening:4:P2',
  'cambridge:3:shared:listening:4:P3',
  'cambridge:3:shared:listening:4:P4',
  'cambridge:20:shared:listening:2:P4',
];

function parseArgs(argv) {
  const out = { only: [] };
  for (let i = 2; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === '--data-dir') out.dataDir = argv[++i];
    else if (a === '--run-id') out.runId = argv[++i];
    else if (a === '--out-dir') out.outDir = argv[++i];
    else if (a === '--only') out.only.push(argv[++i]);
    else if (a === '--targets') out.targets = argv[++i];
    else if (a === '--no-asr') out.noAsr = true;
    else if (a === '--reuse-asr') out.reuseAsr = true;
    else if (a === '--force') out.force = true;
    else if (a === '--limit') out.limit = Number(argv[++i]);
    else if (a === '--gold') out.gold = argv[++i];
    else throw new Error(`unknown arg: ${a}`);
  }
  return out;
}

function loadJson(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

function writeJsonAtomic(p, doc) {
  const tmp = `${p}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(doc, null, 1));
  fs.renameSync(tmp, p);
}

const IDENTITY_RE = /^cambridge:(\d+):(\w+):(\w+):(\d+):(P\d+)$/;

function parseIdentity(identity) {
  const m = IDENTITY_RE.exec(identity ?? '');
  if (!m) return null;
  return { book: Number(m[1]), variant: m[2], skill: m[3], test: m[4], part: m[5] };
}

function safeName(identity) {
  return identity.replace(/:/g, '_');
}

// Answer variants for text matching. Single letters and 1-char answers are
// excluded outright: a lone "A"/"5" would match any occurrence and the plan
// forbids single-letter substring matching. Numeric answers also get their
// spoken word forms.
function buildAnswerVariants(entry) {
  const raw = typeof entry?.raw === 'string' ? entry.raw.trim() : null;
  const accept = Array.isArray(entry?.accept) ? entry.accept.map((x) => String(x).trim()) : [];
  const candidates = [];
  if (raw) candidates.push(raw);
  for (const a of accept) if (a) candidates.push(a);
  const used = [];
  const excluded = [];
  const seen = new Set();
  for (const c of candidates) {
    if (c.length < 2 || /^[A-Za-z]$/.test(c)) {
      excluded.push(c);
      continue;
    }
    if (!seen.has(c)) {
      seen.add(c);
      used.push(c);
    }
    for (const w of numberWordVariants(c)) {
      if (!seen.has(w)) {
        seen.add(w);
        used.push(w);
      }
    }
  }
  return { used, excluded };
}

function multisetCounts(tokens) {
  const m = new Map();
  for (const t of tokens) m.set(t, (m.get(t) ?? 0) + 1);
  return m;
}

function multisetIntersection(a, b) {
  const ca = multisetCounts(a);
  const cb = multisetCounts(b);
  let inter = 0;
  for (const [t, n] of ca) inter += Math.min(n, cb.get(t) ?? 0);
  return inter;
}

// ASR words vs site transcript text: multiset token recall/precision.
function scriptMatch(siteText, words) {
  const siteToks = tokenize(siteText);
  const asrToks = (words ?? []).map((w) => tokenize(w.word)[0]).filter(Boolean);
  const inter = multisetIntersection(siteToks, asrToks);
  return {
    site_tokens: siteToks.length,
    asr_tokens: asrToks.length,
    intersection: inter,
    recall: siteToks.length ? Number((inter / siteToks.length).toFixed(4)) : null,
    precision: asrToks.length ? Number((inter / asrToks.length).toFixed(4)) : null,
  };
}

function loadTranscripts(runDir) {
  const p = path.join(runDir, 'audio', 'cam21-transcripts.json');
  return fs.existsSync(p) ? loadJson(p) : null;
}

function siteTranscriptSegments(transcripts, test, part) {
  const page = transcripts?.pages?.[String(Number(test))];
  const sectionKey = String(Number(String(part).replace(/^P/, '')));
  const segments = page?.sections?.[sectionKey];
  if (!Array.isArray(segments) || !segments.length) return null;
  return {
    source: 'cam21-site-transcript',
    page_sha256: page.page_sha256 ?? null,
    segments: segments.map((s) => ({
      t_sec: Number(s.t),
      text: s.text ?? '',
      q: Array.isArray(s.q) ? s.q.map(Number) : [],
      source_ref: `cam21-site-transcript:t${Number(test)}:s${sectionKey}@${s.t}`,
    })),
  };
}

function goldWindowsFor(gold, identity) {
  if (!gold) return null;
  const part = (gold.parts ?? []).find((p) => p.identity === identity);
  if (!part) return null;
  const windows = (part.windows ?? [])
    .filter((w) => Number.isFinite(w.number) && Number.isFinite(w.start_sec) && Number.isFinite(w.end_sec))
    // Only windows whose independent label survived the ASR cross-check may
    // upgrade a question to verified; everything else stays unverified.
    .filter((w) => w.evidence?.asr_crosscheck?.status === 'asr_confirmed')
    .map((w) => ({
      number: w.number,
      start_sec: w.start_sec,
      end_sec: w.end_sec,
      labeler: w.labeler ?? null,
      source: w.source ?? null,
      crosscheck: {
        status: w.evidence.asr_crosscheck.status,
        answer_score_asr: w.evidence.asr_crosscheck.answer_score_asr ?? null,
      },
    }));
  return windows.length ? windows : null;
}

function selectTargets({ targets, only, catalog }) {
  const byIdentity = new Map();
  for (const r of catalog.records ?? []) if (r.identity) byIdentity.set(r.identity, r);
  if (only.length) {
    return only.map((identity) => ({ identity, record: byIdentity.get(identity) ?? null }));
  }
  const list = [];
  for (const r of catalog.records ?? []) {
    if (!r.identity) continue;
    if (targets === 'all') {
      if (r.scope === 'part' && r.file_path) list.push({ identity: r.identity, record: r });
    } else if (targets === 'verified') {
      if (r.identity_status === 'verified') list.push({ identity: r.identity, record: r });
    }
  }
  if (targets === 'maslow-priority') {
    for (const identity of MASLOW_PRIORITY) list.push({ identity, record: byIdentity.get(identity) ?? null });
  }
  return list;
}

function partInputs({ index, identity, parsed }) {
  const questions = index.questions.filter(
    (q) => q.book === parsed.book && q.skill === parsed.skill
      && String(q.test) === String(parsed.test) && q.part === parsed.part,
  );
  const groups = index.groups.filter(
    (g) => g.identity?.book === parsed.book && g.identity?.skill === parsed.skill
      && String(g.identity?.test) === String(parsed.test) && g.identity?.part === parsed.part,
  );
  const answers = index.answers ?? {};
  const matcherQuestions = questions.map((q) => {
    const entry = answers[q.id] ?? null;
    const { used, excluded } = buildAnswerVariants(entry);
    return {
      number: q.number,
      group_id: q.group_id ?? null,
      prompt: q.prompt ?? '',
      answer_variants: used,
      answer_form: entry?.form ?? null,
      answer_status: entry?.status ?? null,
      excluded_variants: excluded,
    };
  });
  const matcherGroups = groups.map((g) => ({ id: g.id, type: g.type ?? null, numbers: g.numbers ?? [] }));
  return { matcherQuestions, matcherGroups };
}

async function main() {
  const args = parseArgs(process.argv);
  const dataDir = args.dataDir || resolveDataDir();
  const runId = args.runId || DEFAULT_RUN_ID;
  const runDir = path.join(dataDir, 'runs', runId);
  const outDir = args.outDir || path.join(runDir, 'alignment');
  const targets = args.targets || 'verified';
  const force = Boolean(args.force);
  const noAsr = Boolean(args.noAsr);
  const reuseAsr = Boolean(args.reuseAsr);
  const limit = Number.isFinite(args.limit) ? args.limit : Infinity;
  const gold = args.gold ? loadJson(args.gold) : null;

  const catalog = loadJson(path.join(runDir, 'audio', 'audio-catalog.json'));
  const index = loadJson(path.join(runDir, 'index', 'question-index.json'));
  const transcripts = loadTranscripts(runDir);
  const setupInfo = checkAlignmentSetup({ dataDir });
  if (!noAsr && setupInfo.status !== 'ready') {
    console.error(`alignment setup not ready: ${setupInfo.reason}`);
    process.exit(2);
  }
  fs.mkdirSync(outDir, { recursive: true });

  const list = selectTargets({ targets, only: args.only, catalog });
  const summary = {
    schema: 'ielts.alignment-run-summary/1',
    generated_at: new Date().toISOString(),
    data_dir: dataDir,
    run_dir: runDir,
    out_dir: outDir,
    targets,
    only: args.only,
    no_asr: noAsr,
    reuse_asr: reuseAsr,
    gold: args.gold ?? null,
    setup_status: setupInfo.status,
    tool_sha256: setupInfo.tool_sha256 ?? null,
    counts: {
      selected: list.length, processed: 0, skipped_existing: 0,
      skipped_no_audio: 0, skipped_no_questions: 0, no_question_parts: 0, errors: 0,
      asr_ok: 0, asr_failed: 0, asr_not_requested: 0,
    },
    parts: [],
  };
  const summaryPath = path.join(outDir, 'summary.json');

  for (const { identity, record } of list) {
    if (summary.counts.processed >= limit) break;
    const parsed = parseIdentity(identity);
    const outPath = path.join(outDir, `${safeName(identity)}.json`);
    const asrPath = path.join(outDir, `${safeName(identity)}.asr.json`);
    const base = {
      identity,
      book: parsed?.book ?? null,
      test: parsed?.test ?? null,
      part: parsed?.part ?? null,
      output: outPath,
      asr_output: asrPath,
      status: 'pending',
    };
    if (!parsed) {
      base.status = 'error';
      base.reason = 'identity_unparsed';
      summary.parts.push(base);
      summary.counts.errors += 1;
      continue;
    }
    if (fs.existsSync(outPath) && !force) {
      base.status = 'skipped_existing';
      summary.parts.push(base);
      summary.counts.skipped_existing += 1;
      continue;
    }
    if (!record || !record.file_path || !fs.existsSync(record.file_path)) {
      base.status = 'skipped_no_audio';
      base.reason = record ? 'file_missing' : 'catalog_record_missing';
      summary.parts.push(base);
      summary.counts.skipped_no_audio += 1;
      writeJsonAtomic(summaryPath, summary);
      continue;
    }
    const { matcherQuestions, matcherGroups } = partInputs({ index, identity, parsed });
    const noQuestions = !matcherQuestions.length;
    if (noQuestions && noAsr) {
      base.status = 'skipped_no_questions';
      base.reason = 'no_questions_in_index';
      summary.parts.push(base);
      summary.counts.skipped_no_questions += 1;
      writeJsonAtomic(summaryPath, summary);
      continue;
    }

    const isCam21 = record.source === 'cam21';
    const site = isCam21 ? siteTranscriptSegments(transcripts, parsed.test, parsed.part) : null;
    const audioRecord = {
      audio_id: record.audio_id ?? null,
      identity_status: record.identity_status ?? record.status ?? null,
      duration_sec: record.duration_sec ?? null,
      content_sha256: record.content_sha256 ?? null,
      file_path: record.file_path,
    };
    const config = {
      use_asr: !noAsr,
      asr_transcript: site ? 'fallback' : 'prefer',
      compute_type: 'int8',
    };
    const goldWindows = goldWindowsFor(gold, identity);
    if (goldWindows) config.verified_windows = goldWindows;

    // --reuse-asr: reuse a previous ASR transcript for this identity when its
    // audio hash still matches the catalog record (ASR is the expensive step;
    // the hash is the identity gate). Mismatch falls back to a fresh run.
    let precomputedAsr = null;
    if (reuseAsr && !noAsr && fs.existsSync(asrPath)) {
      try {
        const prev = loadJson(asrPath);
        const hashOk = Boolean(prev.audio_sha256 && audioRecord.content_sha256 && prev.audio_sha256 === audioRecord.content_sha256);
        if (hashOk && Array.isArray(prev.words) && prev.words.length) {
          precomputedAsr = {
            status: 'ok',
            audio_sha256: prev.audio_sha256,
            model_version: prev.model_version ?? null,
            segments: prev.segments ?? [],
            words: prev.words,
            duration_sec: prev.duration_sec ?? null,
            elapsed_sec: 0,
          };
        }
      } catch {
        // unreadable previous ASR: fall back to a fresh run
      }
    }

    const started = Date.now();
    let out;
    try {
      out = await buildAlignmentWithProvider({
        dataDir,
        identity,
        part: parsed.part,
        questions: matcherQuestions.map((q) => ({
          number: q.number,
          group_id: q.group_id,
          prompt: q.prompt,
          answer_variants: q.answer_variants,
        })),
        groups: matcherGroups,
        audioRecord,
        precomputedAsr,
        transcript: site ? { source: site.source, sha256: site.page_sha256, segments: site.segments } : null,
        candidateTimestamps: site ? site.segments : null,
        config,
      });
    } catch (err) {
      base.status = 'error';
      base.reason = `provider_threw: ${err?.message ?? err}`;
      base.elapsed_sec = Number(((Date.now() - started) / 1000).toFixed(1));
      summary.parts.push(base);
      summary.counts.errors += 1;
      writeJsonAtomic(summaryPath, summary);
      console.log(`${identity} ERROR ${base.reason}`);
      continue;
    }
    const elapsed = Number(((Date.now() - started) / 1000).toFixed(1));

    const asr = out.asr ?? { status: 'not_requested' };
    const asrSummary = asr.status === 'ok'
      ? {
        status: 'ok',
        audio_sha256: asr.audio_sha256,
        model_version: asr.model_version,
        segments: asr.segments,
        words: asr.words,
        duration_sec: asr.duration_sec,
        elapsed_sec: asr.elapsed_sec,
        words_file: `${safeName(identity)}.asr.json`,
      }
      : { status: asr.status, error: asr.error ?? null, detail: asr.detail ?? null, path: asr.path ?? null };

    const doc = {
      schema: 'ielts.alignment-run/1',
      identity,
      part: parsed.part,
      generated_at: new Date().toISOString(),
      elapsed_sec: elapsed,
      inputs: {
        audio: audioRecord,
        question_count: matcherQuestions.length,
        group_count: matcherGroups.length,
        questions: matcherQuestions.map((q) => ({
          number: q.number,
          group_id: q.group_id,
          answer_variants: q.answer_variants,
          answer_form: q.answer_form,
          answer_status: q.answer_status,
          excluded_variants: q.excluded_variants,
        })),
        transcript_source: site ? site.source : 'local_asr',
        transcript_page_sha256: site?.page_sha256 ?? null,
        gold_windows: goldWindows ? goldWindows.length : 0,
      },
      provider: {
        setup: out.setup,
        asr: asrSummary,
        alignment: out.alignment,
      },
    };
    writeJsonAtomic(outPath, doc);
    if (asr.status === 'ok') {
      const siteText = site ? site.segments.map((s) => s.text).join(' ') : null;
      const sm = siteText ? scriptMatch(siteText, asr.words_full) : null;
      writeJsonAtomic(asrPath, {
        schema: 'ielts.alignment-asr/1',
        identity,
        part: parsed.part,
        generated_at: new Date().toISOString(),
        audio_sha256: asr.audio_sha256,
        model_version: asr.model_version,
        duration_sec: asr.duration_sec,
        words: asr.words_full,
        segments: asr.segments_full,
        script_match: sm,
      });
    }

    base.status = 'ok';
    base.elapsed_sec = elapsed;
    base.question_count = matcherQuestions.length;
    if (noQuestions) base.note = 'no_questions_in_index';
    base.asr_status = asr.status;
    if (asr.reused) base.asr_reused = true;
    base.coverage = out.alignment?.coverage ?? null;
    base.method = out.alignment?.method ?? null;
    base.clock_valid = out.alignment?.clock?.valid ?? null;
    summary.parts.push(base);
    summary.counts.processed += 1;
    if (noQuestions) summary.counts.no_question_parts += 1;
    if (asr.status === 'ok') summary.counts.asr_ok += 1;
    else if (asr.status === 'not_requested') summary.counts.asr_not_requested += 1;
    else summary.counts.asr_failed += 1;
    writeJsonAtomic(summaryPath, summary);
    console.log(`${identity} ok ${elapsed}s asr=${asr.status} coverage=${JSON.stringify(out.alignment?.coverage ?? null)}`);
  }

  writeJsonAtomic(summaryPath, summary);
  console.log(JSON.stringify({ out_dir: outDir, counts: summary.counts }, null, 1));
}

main().catch((err) => {
  console.error(err?.stack ?? String(err));
  process.exit(1);
});
