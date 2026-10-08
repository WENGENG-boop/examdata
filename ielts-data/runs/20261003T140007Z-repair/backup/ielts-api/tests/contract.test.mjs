import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as api from '../ielts-api.mjs';
import { parseArgs, verifyPdfs } from '../verify-pdfs.mjs';

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const STUB = path.join(ROOT, 'tests', 'stub-fetch.cjs');
const CLI = path.join(ROOT, 'ielts-cli.mjs');
const STANDALONE = path.join(ROOT, 'verify-pdfs.mjs');

const INVALID_VERIFY_ARGS = [['99'], ['0'], ['1', '99'], ['1.5'], ['abc'], ['--unknown'], ['--jobs'], ['--jobs', 'abc'], ['--jobs', '0'], ['--jobs', '-1'], ['--jobs', '1.5'], ['--jobs', '65'], ['--jobs', '2', '--jobs', '5']];

function runVerify(script, args, { mode = 'throw', log } = {}) {
  const r = spawnSync(process.execPath, [script, ...args], {
    env: { ...process.env, NODE_OPTIONS: '--require=' + STUB, STUB_FETCH_MODE: mode, STUB_FETCH_LOG: log },
    encoding: 'utf8', timeout: 60000,
  });
  let stubLog = null;
  try { stubLog = JSON.parse(fs.readFileSync(log, 'utf8')); } catch {}
  return { status: r.status, stdout: r.stdout, stderr: r.stderr, stubLog };
}

test('invalid audio identities fail rather than returning invented successful URLs', async () => {
  const bad = [0, -1, 999, null, undefined, NaN, Infinity, 1.5, 'abc', [], {}, Symbol('x')];
  for (const value of bad) {
    assert.equal(api.listeningAudio(value, 1, 1).ok, false);
    assert.equal(api.listeningAudio(19, value, 1).ok, false);
    assert.equal(api.listeningAudio(19, 1, value).ok, false);
    assert.equal((await api.cam21Audio(value, 1)).ok, false);
    if (value !== undefined) assert.equal((await api.cam21Audio(1, value)).ok, false);
  }
  assert.equal(api.listeningAudio(20, 4, 4).ok, true);
  assert.equal((await api.cam21Audio(4, 4)).ok, true);
  assert.equal((await api.cam21Audio(1)).section, 1);
});

test('bad JSON and HTML error pages do not become successful transcripts', async () => {
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    return new Response('<html><body>upstream error</body></html>', {
      status: 200, headers: { 'content-type': 'text/html' },
    });
  };
  try {
    const reading = await api.reading(19, 1, 1);
    assert.equal(reading.ok, false);
    const transcript = await api.listeningScript(5);
    assert.equal(transcript.ok, false);
    assert.ok(calls > 0 && calls < 20, `unexpected retry explosion: ${calls}`);
    const before = calls;
    assert.equal((await api.listeningScript(999)).ok, false);
    assert.equal(calls, before, 'out of range identity must not fetch');
  } finally { globalThis.fetch = original; }
});

test('verify-pdfs CLI treats --jobs value as concurrency, not as a book filter', () => {
  assert.deepEqual(parseArgs(['--jobs', '13']), { jsonOut: false, jobs: 13, books: [], bad: [] });
  assert.deepEqual(parseArgs(['1', '20']), { jsonOut: false, jobs: 3, books: [1, 20], bad: [] });
  assert.deepEqual(parseArgs(['--jobs', '2', '5']), { jsonOut: false, jobs: 2, books: [5], bad: [] });
  assert.deepEqual(parseArgs(['1', '20', '--jobs', '3', '--json']), { jsonOut: true, jobs: 3, books: [1, 20], bad: [] });
  assert.deepEqual(parseArgs(['abc']).bad, ['abc']);
  assert.deepEqual(parseArgs([]), { jsonOut: false, jobs: 3, books: [], bad: [] });
});

test('verify-pdfs rejects invalid books passed to verifyPdfs without any fetch', async () => {
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => { calls++; throw new Error('network disabled in unit test'); };
  try {
    await assert.rejects(verifyPdfs({ books: [99] }), /非法册号/);
    await assert.rejects(verifyPdfs({ books: [0] }), /非法册号/);
    await assert.rejects(verifyPdfs({ books: [1, 99] }), /非法册号/);
    await assert.rejects(verifyPdfs({ books: [1.5] }), /非法册号/);
    await assert.rejects(verifyPdfs({ books: ['1'] }), /非法册号/);
    assert.equal(calls, 0, 'invalid books must be rejected before any fetch');
  } finally { globalThis.fetch = original; }
});

test('verify-pdfs parseArgs accepts only valid books and --jobs 1..64', () => {
  assert.deepEqual(parseArgs(['--jobs', '1']), { jsonOut: false, jobs: 1, books: [], bad: [] });
  assert.deepEqual(parseArgs(['--jobs', '64']), { jsonOut: false, jobs: 64, books: [], bad: [] });
  assert.deepEqual(parseArgs(['99']), { jsonOut: false, jobs: 3, books: [], bad: ['99'] });
  assert.deepEqual(parseArgs(['1', '99']), { jsonOut: false, jobs: 3, books: [1], bad: ['99'] });
  for (const args of INVALID_VERIFY_ARGS) {
    assert.ok(parseArgs(args).bad.length > 0, 'should be invalid: ' + JSON.stringify(args));
  }
});

test('both verify-pdfs CLI entrances exit 2 before any fetch on invalid args', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'verify-stub-'));
  try {
    for (const script of [STANDALONE, CLI]) {
      const viaCli = script === CLI;
      for (let i = 0; i < INVALID_VERIFY_ARGS.length; i++) {
        const log = path.join(tmp, (viaCli ? 'cli-' : 'standalone-') + i + '.json');
        const args = viaCli ? ['verify-pdfs', ...INVALID_VERIFY_ARGS[i]] : INVALID_VERIFY_ARGS[i];
        const r = runVerify(script, args, { mode: 'throw', log });
        assert.equal(r.status, 2, script + ' ' + JSON.stringify(args) + ' -> status ' + r.status + '\n' + r.stderr);
        assert.ok(r.stubLog, 'stub log missing for ' + JSON.stringify(args));
        assert.equal(r.stubLog.count, 0, 'fetch called with invalid args ' + JSON.stringify(args) + ': ' + JSON.stringify(r.stubLog.urls));
      }
    }
  } finally { fs.rmSync(tmp, { recursive: true, force: true }); }
});

test('verify-pdfs checks only the specified books; no args means full set', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'verify-serve-'));
  try {
    const oneLog = path.join(tmp, 'one.json');
    const one = runVerify(STANDALONE, ['1', '--json'], { mode: 'serve', log: oneLog });
    assert.equal(one.status, 0, one.stderr);
    const summary = JSON.parse(one.stdout);
    assert.equal(summary.checked, 1);
    assert.deepEqual(Object.keys(summary.books), ['1']);
    assert.ok(one.stubLog.urls.length > 0);
    for (const u of one.stubLog.urls) {
      assert.ok(decodeURIComponent(u).includes('【1】剑桥雅思真题1.pdf'), 'unexpected URL: ' + u);
    }
    const allLog = path.join(tmp, 'all.json');
    const all = runVerify(CLI, ['verify-pdfs', '--json'], { mode: 'serve', log: allLog });
    assert.equal(all.status, 0, all.stderr);
    assert.equal(JSON.parse(all.stdout).checked, 20);
  } finally { fs.rmSync(tmp, { recursive: true, force: true }); }
});

test('answer corrections: only the 7 verified source errors are replaced, keyed by exact from-value', () => {
  const mk = (book, test, values) => ({
    ok: true, source: 'practicepteonline.com', book, test,
    questions: values.map((v, i) => ({ number: i + 1, prompt: 'q' + (i + 1), answer: v, explanation: null })),
    answer_key: values.slice(),
  });
  const zeros = new Array(40).fill('x');

  const pairs = [
    [5, 1, 4, 'palisades', 'Pallisades'],
    [5, 2, 9, 'grantigham', 'Grantingham'],
    [5, 4, 19, 'end newsletter', 'send (out/the) newsletter(s)'],
    [6, 4, 6, 'conference park', 'conference pack'],
    [7, 2, 2, '730453', '(a) dentist'],
    [7, 2, 12, 'newton', 'Newtown'],
    [17, 4, 38, 'Stream', 'steam'],
  ];
  let total = 0;
  for (const [b, t, q, from, to] of pairs) {
    const values = zeros.slice();
    values[q - 1] = from;
    const r = api.applyAnswerCorrections(b, t, mk(b, t, values));
    assert.equal(r.answer_key[q - 1], to, `${b}-${t} Q${q} answer_key`);
    assert.equal(r.questions[q - 1].answer, to, `${b}-${t} Q${q} questions[].answer`);
    assert.ok(r.answer_corrections.some((c) => c.question === q && c.from === from && c.to === to && c.basis), `${b}-${t} Q${q} traceability`);
    total += r.answer_corrections.length;
  }
  assert.equal(total, pairs.length, 'each of the 7 corrections applies exactly once');

  const v72 = zeros.slice();
  v72[1] = '730453'; v72[11] = 'newton'; v72[37] = 'vision';
  const r72 = api.applyAnswerCorrections(7, 2, mk(7, 2, v72));
  assert.equal(r72.answer_key[1], '(a) dentist');
  assert.equal(r72.answer_key[11], 'Newtown');
  assert.equal(r72.answer_key[37], 'vision', 'unlisted question must stay untouched');
  assert.equal(r72.answer_corrections.length, 2);
});

test('answer corrections guards: mismatch, unknown identity, non-ok, and immutability', () => {
  const mk = (book, test, values) => ({
    ok: true, source: 'practicepteonline.com', book, test,
    questions: values.map((v, i) => ({ number: i + 1, answer: v })),
    answer_key: values.slice(),
  });
  const zeros = new Array(40).fill('x');

  const changed = zeros.slice(); changed[1] = '730453x';
  const r1 = api.applyAnswerCorrections(7, 2, mk(7, 2, changed));
  assert.equal(r1.answer_key[1], '730453x', 'value changed upstream -> no replacement');
  assert.equal(r1.answer_corrections, undefined);

  const r2 = api.applyAnswerCorrections(9, 3, mk(9, 3, zeros));
  assert.equal(r2.answer_corrections, undefined, 'unknown book/test -> untouched');

  assert.equal(api.applyAnswerCorrections(7, 2, { ok: false, error: 'x' }).ok, false);
  assert.equal(api.applyAnswerCorrections(7, 2, null), null);
  assert.equal(api.applyAnswerCorrections(7, 2, { ok: true, answer_key: 'nope' }).answer_key, 'nope');

  const values = zeros.slice(); values[1] = '730453';
  const orig = mk(7, 2, values);
  const r4 = api.applyAnswerCorrections(7, 2, orig);
  assert.equal(orig.answer_key[1], '730453', 'original result object must not be mutated');
  assert.equal(orig.answer_corrections, undefined);
  assert.equal(r4.answer_key[1], '(a) dentist');
  assert.equal(r4.questions[1].answer, '(a) dentist');
});
