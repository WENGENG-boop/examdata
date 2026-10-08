/**
 * ielts-audio-matcher.test.mjs — S10 音频—原文—逐题对齐算法单元测试（无网络）
 *
 * 覆盖计划验收 fixture：同答案多处出现、错误音频 hash、毫秒/秒混淆、
 * full-test offset、变速、末尾越界、非单调、无时间戳、诱饵选项、
 * 多选共享窗口、旧版非 10 题段；以及置信度组成、ASR 合并与 setup 检查。
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import {
  ALIGN_STATUS, AUTO_THRESHOLDS, THRESHOLD_VERSION,
  normalizeText, tokenize, phraseMatchScore, contiguousScore, answerEvidenceScore,
  numberWordVariants,
  stemKeywords, detectTimestampUnit, validateClock, estimateOffset, applyOffset,
  buildCandidates, selectWindowsDP, composeConfidence, gateNeedsReview,
  alignQuestions, coverageOf,
} from '../audio-matcher.mjs';

import {
  alignmentPaths, checkAlignmentSetup, wordsInWindow, windowWordStats,
  mergeAsrIntoAlignment, MODEL_LOCK_SCHEMA,
} from '../alignment-provider.mjs';

const AUDIO = (over = {}) => ({
  audio_id: 'audio:cambridge:21:shared:listening:1:P1',
  identity_status: 'verified',
  duration_sec: 300,
  content_sha256: 'aa'.repeat(32),
  ...over,
});

const Q = (number, over = {}) => ({
  number,
  group_id: `g${number}`,
  prompt: '',
  answer_variants: [],
  ...over,
});

// ---------------------------------------------------------------- 文本工具

test('normalize/tokenize handles punctuation and unicode quotes', () => {
  assert.equal(normalizeText("It's £1.50, isn't it?"), "it's 1 50 isn't it");
  assert.deepEqual(tokenize('Hello, Oyster Bay!'), ['hello', 'oyster', 'bay']);
});

test('normalizeText folds diacritics so cafe matches café', () => {
  assert.equal(normalizeText('caf\u00e9'), 'cafe');
  assert.equal(normalizeText('Caf\u00e9 Rouge'), 'cafe rouge');
  assert.equal(answerEvidenceScore(['cafe'], tokenize('meet me at the caf\u00e9 tomorrow')), 1);
});

test('phraseMatchScore rewards in-order coverage; contiguousScore rewards runs', () => {
  const phrase = tokenize('oyster bay sailing club');
  const win = tokenize('welcome to oyster bay sailing club today');
  assert.equal(phraseMatchScore(phrase, win), 1);
  assert.equal(contiguousScore(phrase, win), 1);
  const scattered = tokenize('oyster then later bay and sailing and club');
  assert.equal(phraseMatchScore(phrase, scattered), 1);
  assert.ok(contiguousScore(phrase, scattered) < 1);
  assert.equal(answerEvidenceScore(['not there'], win), 0);
});

test('numberWordVariants maps digit answers to spoken forms without inventing them', () => {
  assert.deepEqual(numberWordVariants('7'), ['seven']);
  assert.deepEqual(numberWordVariants('42'), ['forty-two', 'forty two']);
  assert.ok(numberWordVariants('115').includes('one hundred and fifteen'));
  assert.ok(numberWordVariants('1500').includes('one thousand five hundred'));
  assert.ok(numberWordVariants('100').includes('a hundred'));
  assert.deepEqual(numberWordVariants('£30'), ['thirty']);
  assert.deepEqual(numberWordVariants('1a'), []);
  assert.deepEqual(numberWordVariants(null), []);
  assert.deepEqual(numberWordVariants('abc'), []);
});

// ---------------------------------------------------------------- 时钟

test('detectTimestampUnit distinguishes sec vs ms vs ambiguous', () => {
  assert.equal(detectTimestampUnit([0, 100, 280], 300).unit, 'sec');
  assert.equal(detectTimestampUnit([0, 100000, 280000], 300).unit, 'ms');
  assert.equal(detectTimestampUnit([0, 1, 2], 300).unit, 'sec');
  assert.equal(detectTimestampUnit([0, 4000, 5000], null).unit, 'ambiguous');
  assert.equal(detectTimestampUnit([], 300).unit, null);
});

test('validateClock converts ms and rejects non-monotonic / out-of-bounds', () => {
  const ok = validateClock([{ t_sec: 0 }, { t_sec: 60000 }, { t_sec: 120000 }], { durationSec: 300 });
  assert.equal(ok.valid, true);
  assert.equal(ok.unit, 'ms');
  assert.equal(ok.entries[1].t_sec, 60);

  const bad = validateClock([{ t_sec: 0 }, { t_sec: 50 }, { t_sec: 40 }], { durationSec: 300 });
  assert.equal(bad.valid, false);
  assert.ok(bad.reasons.includes('non_monotonic'));

  const oob = validateClock([{ t_sec: 0 }, { t_sec: 900 }], { durationSec: 300 });
  assert.equal(oob.valid, false);
  assert.ok(oob.reasons.includes('out_of_bounds'));
});

// ---------------------------------------------------------------- offset

test('estimateOffset fits a~1 with 3+ anchors and rejects residual/insufficient', () => {
  const fit = estimateOffset([
    { source_sec: 10, target_sec: 310 },
    { source_sec: 100, target_sec: 400 },
    { source_sec: 200, target_sec: 500 },
  ]);
  assert.equal(fit.ok, true);
  assert.ok(Math.abs(fit.a - 1) < 1e-9);
  assert.ok(Math.abs(fit.b - 300) < 1e-9);
  assert.equal(applyOffset(fit, 150), 450);

  const tooFew = estimateOffset([{ source_sec: 10, target_sec: 310 }]);
  assert.equal(tooFew.ok, false);
  assert.equal(tooFew.reason, 'insufficient_anchors');

  const badResidual = estimateOffset([
    { source_sec: 10, target_sec: 310 },
    { source_sec: 100, target_sec: 430 },
    { source_sec: 200, target_sec: 500 },
  ]);
  assert.equal(badResidual.ok, false);
  assert.ok(badResidual.reason.includes('residual_exceeds_limit'));

  const nonMono = estimateOffset([
    { source_sec: 10, target_sec: 310 },
    { source_sec: 100, target_sec: 290 },
    { source_sec: 200, target_sec: 500 },
  ]);
  assert.equal(nonMono.ok, false);
});

test('estimateOffset handles variable speed (a != 1)', () => {
  const fit = estimateOffset([
    { source_sec: 0, target_sec: 5 },
    { source_sec: 100, target_sec: 105.2 },
    { source_sec: 200, target_sec: 205.4 },
  ]);
  assert.equal(fit.ok, true);
  assert.ok(Math.abs(fit.a - 1.002) < 0.005);
  assert.ok(Math.abs(fit.b - 5) < 0.3);
  assert.ok(fit.max_abs_residual < 0.05);
});

// ---------------------------------------------------------------- 候选构建

test('buildCandidates marks (Qn) markers and answer occurrences separately', () => {
  const transcript = {
    segments: [
      { t_sec: 10, text: 'First, the price is fifteen pounds.', q: [] },
      { t_sec: 20, text: 'And here is the answer: oyster bay.', q: [1] },
      { t_sec: 30, text: 'A decoy mention of oyster bay again.', q: [] },
    ],
  };
  const questions = [Q(1, { answer_variants: ['oyster bay'], prompt: 'club name' })];
  const cands = buildCandidates({ questions, transcript });
  const list = cands.get(1);
  assert.ok(list.length >= 2);
  const marker = list.find((c) => c.source === 'transcript_qn_marker');
  assert.ok(marker);
  assert.equal(marker.start_sec, 20);
  const ans = list.find((c) => c.source === 'answer_occurrence' || c.source === 'answer_in_marker_window');
  assert.ok(ans);
});

// ---------------------------------------------------------------- DP

test('selectWindowsDP prefers monotonic non-decreasing windows and reports margins', () => {
  const nodes = [
    { key: 'g1', numbers: [1], required: true, candidates: [
      { start_sec: 100, end_sec: 110, context_score: 0.9, evidence_refs: ['a'] },
      { start_sec: 10, end_sec: 20, context_score: 0.6, evidence_refs: ['b'] },
    ] },
    { key: 'g2', numbers: [2], required: true, candidates: [
      { start_sec: 120, end_sec: 130, context_score: 0.9, evidence_refs: ['c'] },
      { start_sec: 5, end_sec: 15, context_score: 0.95, evidence_refs: ['d'] },
    ] },
  ];
  const { picks } = selectWindowsDP(nodes);
  assert.equal(picks[0].chosen.start_sec, 100);
  assert.equal(picks[1].chosen.start_sec, 120);
  assert.ok(picks[0].margin >= 0);
});

test('selectWindowsDP keeps single candidate margin null and skip allowed', () => {
  const nodes = [
    { key: 'g1', numbers: [1], required: true, candidates: [{ start_sec: 50, end_sec: 60, context_score: 0.7, evidence_refs: [] }] },
    { key: 'g2', numbers: [2], required: true, candidates: [] },
  ];
  const { picks } = selectWindowsDP(nodes);
  assert.equal(picks[0].chosen.start_sec, 50);
  assert.equal(picks[0].margin, null);
  assert.equal(picks[1].chosen, null);
});

// ---------------------------------------------------------------- confidence

test('composeConfidence + gateNeedsReview follow documented thresholds', () => {
  const good = composeConfidence({
    identity_valid: true, clock_valid: true, text_anchor_score: 0.95,
    aligner_word_confidence: 0.9, ambiguity_margin: 0.3,
  });
  assert.ok(good.score > 0.6);
  assert.equal(gateNeedsReview(good, 'asr_forced_align').passes, true);

  const lowAnchor = composeConfidence({ identity_valid: true, clock_valid: true, text_anchor_score: 0.5 });
  assert.equal(gateNeedsReview(lowAnchor, 'official_transcript_candidates+dp').passes, false);

  const lowMargin = composeConfidence({ identity_valid: true, clock_valid: true, text_anchor_score: 0.95, ambiguity_margin: 0.05 });
  assert.equal(gateNeedsReview(lowMargin, 'official_transcript_candidates+dp').passes, false);

  const lowAsr = composeConfidence({ identity_valid: true, clock_valid: true, text_anchor_score: 0.95, aligner_word_confidence: 0.5 });
  assert.equal(gateNeedsReview(lowAsr, 'asr_forced_align').passes, false);
  assert.equal(gateNeedsReview(lowAsr, 'official_transcript_candidates+dp').passes, true);
});

// ---------------------------------------------------------------- alignQuestions

test('alignQuestions refuses unverified audio identity (wrong audio guard)', () => {
  const res = alignQuestions({
    identity: 'cambridge:21:shared:listening:1:P1',
    part: 'P1',
    questions: [Q(1)],
    audio: AUDIO({ identity_status: 'available' }),
    transcript: { segments: [{ t_sec: 10, text: 'hello', q: [1] }] },
  });
  assert.equal(res.questions[0].status, ALIGN_STATUS.UNVERIFIED);
  assert.ok(res.warnings.includes('audio_identity_not_verified'));
  assert.equal(res.questions[0].intervals.length, 0);
});

test('alignQuestions: no timestamps -> section_only/unverified, never fabricated windows', () => {
  const res = alignQuestions({
    identity: 'cambridge:1:shared:listening:1:P1',
    part: 'P1',
    questions: [Q(1), Q(2)],
    audio: AUDIO(),
    transcript: null,
    candidateTimestamps: null,
    config: { section_range: { start_sec: 0, end_sec: 120 } },
  });
  assert.equal(res.questions.length, 2);
  for (const q of res.questions) {
    assert.equal(q.intervals.length, 0);
    assert.ok([ALIGN_STATUS.SECTION_ONLY, ALIGN_STATUS.UNVERIFIED].includes(q.status));
  }
});

test('alignQuestions: multiple occurrences of the same answer pick marker context, decoys not verified', () => {
  const transcript = {
    segments: [
      { t_sec: 30, text: 'Someone mentions oyster bay as a decoy.', q: [] },
      { t_sec: 60, text: 'The club is called Oyster Bay Sailing Club.', q: [1] },
      { t_sec: 90, text: 'Other talk.', q: [] },
    ],
  };
  const res = alignQuestions({
    identity: 'cambridge:21:shared:listening:1:P1',
    part: 'P1',
    questions: [Q(1, { answer_variants: ['oyster bay'], prompt: 'What is the club called?' })],
    audio: AUDIO(),
    transcript,
    config: { method: 'official_transcript_candidates+dp' },
  });
  const q1 = res.questions[0];
  assert.equal(q1.status, ALIGN_STATUS.NEEDS_REVIEW);
  assert.ok(Math.abs(q1.intervals[0].start_sec - 60) < 6);
  assert.ok(!q1.evidence_refs.some((r) => String(r).includes('30')));
});

test('alignQuestions: multi-select group shares one window instead of splitting per letter', () => {
  const transcript = {
    segments: [
      { t_sec: 100, text: 'You need a tent, a torch and a map for the trip.', q: [11, 12, 13] },
      { t_sec: 130, text: 'Later they discuss other things.', q: [] },
    ],
  };
  const questions = [
    Q(11, { group_id: 'gA', answer_variants: ['tent'], prompt: 'equipment' }),
    Q(12, { group_id: 'gA', answer_variants: ['torch'], prompt: 'equipment' }),
    Q(13, { group_id: 'gA', answer_variants: ['map'], prompt: 'equipment' }),
  ];
  const groups = [{ id: 'gA', numbers: [11, 12, 13], type: 'multiple_choice_multi', instruction: 'Choose THREE letters' }];
  const res = alignQuestions({
    identity: 'cambridge:21:shared:listening:2:P2',
    part: 'P2',
    questions,
    groups,
    audio: AUDIO({ audio_id: 'audio:cambridge:21:shared:listening:2:P2' }),
    transcript,
    config: { method: 'official_transcript_candidates+dp' },
  });
  const q11 = res.questions.find((q) => q.number === 11);
  const q12 = res.questions.find((q) => q.number === 12);
  const q13 = res.questions.find((q) => q.number === 13);
  assert.equal(q11.intervals[0].start_sec, q12.intervals[0].start_sec);
  assert.equal(q12.intervals[0].start_sec, q13.intervals[0].start_sec);
  assert.ok(res.coverage.groups_shared_window >= 1);
});

test('alignQuestions: old-version numbering (Q41) works with no fixed Q1-10 assumption', () => {
  const transcript = {
    segments: [{ t_sec: 5, text: 'The forty-first answer is alpha.', q: [41] }],
  };
  const res = alignQuestions({
    identity: 'cambridge:1:shared:listening:2:P5',
    part: 'P5',
    questions: [Q(41, { answer_variants: ['alpha'], prompt: 'answer 41' })],
    audio: AUDIO({ audio_id: 'audio:cambridge:1:shared:listening:2:P5', duration_sec: 120 }),
    transcript,
    config: { method: 'official_transcript_candidates+dp' },
  });
  assert.equal(res.questions[0].number, 41);
  assert.ok(res.questions[0].intervals.length === 1);
});

test('alignQuestions: ms timestamps are normalized; out-of-range rejected (end overflow)', () => {
  const msTranscript = {
    segments: [
      { t_sec: 30000, text: 'alpha answer here.', q: [1] },
      { t_sec: 90000, text: 'more talk.', q: [] },
    ],
  };
  const ok = alignQuestions({
    identity: 'cambridge:21:shared:listening:1:P1',
    part: 'P1',
    questions: [Q(1, { answer_variants: ['alpha'], prompt: 'x' })],
    audio: AUDIO({ duration_sec: 300 }),
    transcript: msTranscript,
    config: { method: 'official_transcript_candidates+dp' },
  });
  assert.equal(ok.clock.unit, 'ms');
  assert.ok(ok.questions[0].intervals.length === 1);
  assert.ok(ok.questions[0].intervals[0].start_sec < 300);

  const overflow = alignQuestions({
    identity: 'cambridge:21:shared:listening:1:P1',
    part: 'P1',
    questions: [Q(1, { answer_variants: ['alpha'], prompt: 'x' })],
    audio: AUDIO({ duration_sec: 60 }),
    transcript: { segments: [{ t_sec: 600000, text: 'alpha', q: [1] }] },
    config: { method: 'official_transcript_candidates+dp' },
  });
  assert.equal(overflow.questions[0].intervals.length, 0);
  assert.ok(overflow.warnings.some((w) => w.startsWith('clock_invalid')));
});

test('alignQuestions: non-monotonic transcript invalidates clock and yields no windows', () => {
  const res = alignQuestions({
    identity: 'cambridge:21:shared:listening:1:P1',
    part: 'P1',
    questions: [Q(1, { answer_variants: ['alpha'], prompt: 'x' })],
    audio: AUDIO(),
    transcript: { segments: [{ t_sec: 100, text: 'alpha', q: [1] }, { t_sec: 40, text: 'beta', q: [] }] },
    config: { method: 'official_transcript_candidates+dp' },
  });
  assert.equal(res.questions[0].intervals.length, 0);
});

test('alignQuestions: verified only via independent gold windows', () => {
  const transcript = { segments: [{ t_sec: 60, text: 'The club is Oyster Bay.', q: [1] }] };
  const res = alignQuestions({
    identity: 'cambridge:21:shared:listening:1:P1',
    part: 'P1',
    questions: [Q(1, { answer_variants: ['oyster bay'], prompt: 'club' })],
    audio: AUDIO(),
    transcript,
    config: {
      method: 'official_transcript_candidates+dp',
      verified_windows: [{ number: 1, start_sec: 60, end_sec: 90, labeler: 'site-transcript', source: 'cam21-page' }],
    },
  });
  assert.equal(res.questions[0].status, ALIGN_STATUS.VERIFIED);
  assert.equal(res.questions[0].verified_by.labeler, 'site-transcript');

  const res2 = alignQuestions({
    identity: 'cambridge:21:shared:listening:1:P1',
    part: 'P1',
    questions: [Q(1, { answer_variants: ['oyster bay'], prompt: 'club' })],
    audio: AUDIO(),
    transcript,
    config: { method: 'official_transcript_candidates+dp', verified_windows: [{ number: 1, start_sec: 200, end_sec: 230 }] },
  });
  assert.notEqual(res2.questions[0].status, ALIGN_STATUS.VERIFIED);
});

test('alignQuestions: question verifies via its own candidate when the group pick diverges from gold', () => {
  const transcript = {
    segments: [
      { t_sec: 60, text: 'The club is Oyster Bay.', q: [] },
      { t_sec: 200, text: 'Harbor street.', q: [2] },
    ],
  };
  const res = alignQuestions({
    identity: 'cambridge:21:shared:listening:1:P1',
    part: 'P1',
    questions: [
      Q(1, { answer_variants: ['oyster bay'], prompt: 'club', group_id: 'g12' }),
      Q(2, { answer_variants: ['harbor'], prompt: 'street', group_id: 'g12' }),
    ],
    audio: AUDIO(),
    transcript,
    config: {
      method: 'official_transcript_candidates+dp',
      verified_windows: [{ number: 1, start_sec: 60, end_sec: 90, labeler: 'site-transcript', source: 'cam21-page' }],
    },
  });
  const q1 = res.questions.find((q) => q.number === 1);
  const q2 = res.questions.find((q) => q.number === 2);
  // The group pick landed on Q2's stronger marker window…
  assert.ok(q2.candidate_window.start_sec >= 190);
  assert.ok(q1.candidate_window.start_sec >= 190);
  // …yet Q1 still verifies because its own answer-occurrence candidate agrees
  // with the independent gold window, and the divergence is recorded.
  assert.equal(q1.status, ALIGN_STATUS.VERIFIED);
  assert.equal(q1.gold_match_source, 'answer_occurrence');
  assert.deepEqual(q1.intervals, [{ start_sec: 60, end_sec: 90, role: 'answer_evidence' }]);
  assert.equal(q1.gold_match_window.start_sec, 58);
  assert.equal(q1.gold_match_window.end_sec, 92);
});

// ---------------------------------------------------------------- ASR merge

test('windowWordStats / wordsInWindow compute mean confidence and text', () => {
  const words = [
    { word: 'the', start: 10, end: 10.3, confidence: 0.9 },
    { word: 'club', start: 10.4, end: 10.8, confidence: 0.8 },
    { word: 'later', start: 99, end: 99.5, confidence: 0.95 },
  ];
  const stats = windowWordStats(words, 9, 12);
  assert.equal(stats.count, 2);
  assert.ok(Math.abs(stats.mean_confidence - 0.85) < 1e-9);
  assert.equal(stats.text, 'the club');
  assert.equal(wordsInWindow(words, 98, 100).length, 1);
});

test('mergeAsrIntoAlignment upgrades unverified->needs_review only when gates pass', () => {
  const base = alignQuestions({
    identity: 'cambridge:21:shared:listening:1:P1',
    part: 'P1',
    questions: [Q(1, { answer_variants: ['alpha'], prompt: 'x' })],
    audio: AUDIO(),
    transcript: { segments: [{ t_sec: 60, text: 'alpha spoken here.', q: [] }] },
    config: { method: 'asr_forced_align' },
  });
  assert.equal(base.questions[0].status, ALIGN_STATUS.UNVERIFIED);

  const merged = mergeAsrIntoAlignment(base, {
    status: 'ok',
    words: [
      { word: 'alpha', start: 60.5, end: 60.9, confidence: 0.92 },
      { word: 'spoken', start: 61.0, end: 61.4, confidence: 0.88 },
    ],
    audio_sha256: 'aa'.repeat(32),
  });
  assert.equal(merged.questions[0].status, ALIGN_STATUS.NEEDS_REVIEW);
  assert.equal(merged.asr_merge.applied, true);

  const noWords = mergeAsrIntoAlignment(base, { status: 'ok', words: [], audio_sha256: 'aa'.repeat(32) });
  assert.equal(noWords.questions[0].status, ALIGN_STATUS.UNVERIFIED);
});

// ---------------------------------------------------------------- setup check

test('checkAlignmentSetup reports alignment_setup_blocked with empty dirs', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ielts-align-'));
  const setup = checkAlignmentSetup({ dataDir: tmp });
  assert.equal(setup.status, 'alignment_setup_blocked');
  assert.ok(setup.reason.includes('venv_python'));
  fs.rmSync(tmp, { recursive: true, force: true });
});

test('checkAlignmentSetup reports ready with fake venv + tool + model-lock', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ielts-align-'));
  // Sandbox the tool path too: `tool` is anchored to the module dir by
  // default, and a test must never write to the real tools/align-audio.py.
  const toolPath = path.join(tmp, 'tools', 'align-audio.py');
  const paths = alignmentPaths({ dataDir: tmp, toolPath });
  fs.mkdirSync(path.dirname(paths.python), { recursive: true });
  fs.writeFileSync(paths.python, '');
  fs.mkdirSync(path.dirname(paths.tool), { recursive: true });
  fs.writeFileSync(paths.tool, "print('ok')\n");
  const whisperDir = path.join(paths.modelsDir, 'whisper-small');
  const alignDir = path.join(paths.modelsDir, 'wav2vec2-base-960h');
  fs.mkdirSync(whisperDir, { recursive: true });
  fs.mkdirSync(alignDir, { recursive: true });
  fs.writeFileSync(path.join(whisperDir, 'model.bin'), 'x');
  fs.writeFileSync(path.join(alignDir, 'pytorch_model.bin'), 'x');
  fs.writeFileSync(paths.modelLock, JSON.stringify({
    schema: MODEL_LOCK_SCHEMA,
    models: {
      whisper: { dir: 'whisper-small', source: 'https://huggingface.co/Systran/faster-whisper-small', bytes: 1 },
      align: { dir: 'wav2vec2-base-960h', source: 'https://huggingface.co/facebook/wav2vec2-base-960h', bytes: 1 },
    },
  }));
  const setup = checkAlignmentSetup({ dataDir: tmp, toolPath });
  assert.equal(setup.status, 'ready');
  fs.rmSync(tmp, { recursive: true, force: true });
});

// ---------------------------------------------------------------- fixture

test('alignment gold fixture exists and documents its label status', () => {
  const fixturePath = path.join(process.cwd(), 'tests', 'fixtures', 'alignment-gold.json');
  const gold = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
  assert.equal(gold.schema, 'ielts.alignment-gold/1');
  assert.ok(Array.isArray(gold.parts));
  assert.ok(typeof gold.label_policy === 'string');
});

test('threshold version is recorded in matcher output', () => {
  const res = alignQuestions({
    identity: 'x', part: 'P1', questions: [Q(1)], audio: AUDIO(), transcript: null,
  });
  assert.equal(res.threshold_version, THRESHOLD_VERSION);
});
