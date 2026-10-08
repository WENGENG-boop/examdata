/**
 * ielts-audio-catalog.test.mjs — S09 音频目录状态机单元测试（无网络）
 *
 * 覆盖：候选 URL 模式、同 hash 合并/异 hash 变体、跨 Part 重复检测、
 * verified 守卫、sniff/Content-Range 校验、full-test 区间派生不冒充 verified。
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  AUDIO_STATUS, AUDIO_SCOPE, VERIFICATION_KINDS, MASLOW, CAM21,
  partIdentity, fullTestIdentity, audioIdFor, pad2,
  maslowPartCandidates, maslowFullCandidates, cam21Candidates,
  buildAudioCatalog, applyProbe, markVerified, setFullTestIntervals,
  sniffAudio, parseContentRange, validateRangeProbe, summarizeAudioCatalog,
  gitBlobSha1Buffer, parseCam21ListeningPage, transcriptQNums, transcriptPlainText,
} from '../audio-catalog.mjs';

const P = (b, t, p) => audioIdFor(partIdentity(b, t, p), AUDIO_SCOPE.PART);

// ---------------------------------------------------------------- URL 模式

test('candidate URL patterns are deterministic', () => {
  const mp = maslowPartCandidates(3, 2, 4);
  assert.equal(mp.length, 2);
  assert.equal(mp[0].url, MASLOW.raw + 'ielts_listening/book_03/test_2_part_4.mp3');
  assert.equal(mp[1].url, MASLOW.cdn + 'ielts_listening/book_03/test_2_part_4.mp3');
  const mf = maslowFullCandidates(20, 4);
  assert.equal(mf[0].url, MASLOW.raw + 'ielts_listening/book_20/test_4.mp3');
  const c = cam21Candidates(1, 2);
  assert.equal(c[0].url, CAM21.raw + 'audio/C21T1_Section_2.mp3');
  assert.equal(c[1].url, CAM21.cdn + 'audio/C21T1_Section_2.mp3');
  assert.equal(pad2(7), '07');
  assert.equal(partIdentity(21, 1, 1), 'cambridge:21:shared:listening:1:P1');
  assert.equal(fullTestIdentity(4, 3), 'cambridge:4:shared:listening:3');
  assert.equal(audioIdFor(partIdentity(1, 1, 1), AUDIO_SCOPE.PART), 'audio:cambridge:1:shared:listening:1:P1');
  assert.equal(audioIdFor(fullTestIdentity(1, 1), AUDIO_SCOPE.FULL_TEST), 'audio:cambridge:1:shared:listening:1:full');
});

// ---------------------------------------------------------------- build

test('buildAudioCatalog starts everything as candidate and dedupes', () => {
  const cat = buildAudioCatalog({
    maslowParts: [{ book: 1, test: 1, part: 1 }, { book: 1, test: 1, part: 1 }, { book: 1, test: 1, part: 2 }],
    maslowFull: [{ book: 1, test: 1 }],
    cam21: [{ test: 1, section: 1 }],
  });
  assert.equal(cat.records.length, 4);
  assert.ok(cat.records.every((r) => r.status === AUDIO_STATUS.CANDIDATE));
  const r = cat.records.find((x) => x.audio_id === P(1, 1, 1));
  assert.equal(r.source, 'maslow');
  assert.equal(r.urls.length, 2);
  const c = cat.records.find((x) => x.audio_id === P(21, 1, 1));
  assert.equal(c.source, 'cam21');
  assert.equal(c.urls[0].url, CAM21.raw + 'audio/C21T1_Section_1.mp3');
  const f = cat.records.find((x) => x.scope === AUDIO_SCOPE.FULL_TEST);
  assert.equal(f.part, null);
});

// ---------------------------------------------------------------- applyProbe

test('applyProbe merges same hash from two URLs into one available record', () => {
  const cat = buildAudioCatalog({ maslowParts: [{ book: 2, test: 3, part: 1 }] });
  const id = P(2, 3, 1);
  const raw = MASLOW.raw + 'ielts_listening/book_02/test_3_part_1.mp3';
  const cdn = MASLOW.cdn + 'ielts_listening/book_02/test_3_part_1.mp3';
  const sha = 'a'.repeat(64);

  // raw 先失败一次（记录错误链）
  applyProbe(cat, { url: raw, error: { kind: 'network', message: 'reset' } });
  let rec = cat.records.find((r) => r.audio_id === id);
  assert.equal(rec.status, AUDIO_STATUS.CANDIDATE);
  assert.equal(rec.urls[0].tried, true);
  assert.equal(rec.urls[0].last_error.kind, 'network');

  // cdn 成功 → 同 hash 合并；raw 错误保留
  const { record } = applyProbe(cat, {
    url: cdn, sha256: sha, bytes: 123456, container: 'mp3', codec: 'mp3',
    sample_rate: 44100, channels: 2, duration_sec: 500.5, file_path: 'audio/x.mp3',
    fetched_at: '2026-10-04T00:00:00Z', decode_ok: true, magic_ok: true,
  });
  assert.equal(record.audio_id, id);
  assert.equal(record.status, AUDIO_STATUS.AVAILABLE);
  assert.equal(record.content_sha256, sha);
  assert.equal(record.duration_sec, 500.5);
  const urls = record.urls.map((u) => u.url);
  assert.ok(urls.includes(raw) && urls.includes(cdn));
  assert.equal(cat.records.filter((r) => r.identity === partIdentity(2, 3, 1)).length, 1);

  // 再探测 raw 成功同 hash → 仍是同一记录，无变体
  applyProbe(cat, {
    url: raw, sha256: sha, bytes: 123456, container: 'mp3', codec: 'mp3',
    duration_sec: 500.5, file_path: 'audio/x.mp3', decode_ok: true, magic_ok: true,
  });
  assert.equal(cat.records.filter((r) => r.identity === partIdentity(2, 3, 1)).length, 1);
  rec = cat.records.find((r) => r.audio_id === id);
  assert.equal(rec.urls.find((u) => u.url === raw).last_error, null);
  assert.equal(rec.status, AUDIO_STATUS.AVAILABLE);
});

test('applyProbe with different hash creates a separate variant and issue', () => {
  const cat = buildAudioCatalog({ cam21: [{ test: 1, section: 1 }] });
  const id = P(21, 1, 1);
  applyProbe(cat, { url: CAM21.raw + 'audio/C21T1_Section_1.mp3', sha256: '1'.repeat(64), bytes: 10, decode_ok: true, magic_ok: true, container: 'mp3', duration_sec: 300 });
  const { record, issues } = applyProbe(cat, { url: CAM21.cdn + 'audio/C21T1_Section_1.mp3', sha256: '2'.repeat(64), bytes: 20, decode_ok: true, magic_ok: true, container: 'mp3', duration_sec: 400 });
  assert.equal(record.audio_id, id + ':v2');
  assert.equal(record.content_sha256, '2'.repeat(64));
  assert.ok(issues.some((i) => i.kind === 'content_variant'));
  assert.equal(cat.records.filter((r) => r.identity === partIdentity(21, 1, 1)).length, 2);
  const base = cat.records.find((r) => r.audio_id === id);
  assert.equal(base.content_sha256, '1'.repeat(64));
});

test('all urls failed marks record failed with error chain', () => {
  const cat = buildAudioCatalog({ maslowParts: [{ book: 9, test: 1, part: 1 }] });
  const id = P(9, 1, 1);
  const rec = cat.records.find((r) => r.audio_id === id);
  applyProbe(cat, { url: rec.urls[0].url, error: { kind: 'resource_missing', status: 404 } });
  assert.equal(rec.status, AUDIO_STATUS.CANDIDATE);
  applyProbe(cat, { url: rec.urls[1].url, error: { kind: 'resource_missing', status: 404 } });
  assert.equal(rec.status, AUDIO_STATUS.FAILED);
  assert.equal(rec.error.kind, 'all_urls_failed');
  assert.equal(rec.error.attempts.length, 2);
});

test('probe failure (html/zero magic) marks failed, not available', () => {
  const cat = buildAudioCatalog({ maslowParts: [{ book: 9, test: 2, part: 1 }] });
  const rec = cat.records.find((r) => r.audio_id === P(9, 2, 1));
  applyProbe(cat, { url: rec.urls[0].url, sha256: 'c'.repeat(64), bytes: 700, decode_ok: false, decode_error: 'html_body', magic_ok: false, html: true, reason: 'html_body' });
  assert.equal(rec.status, AUDIO_STATUS.FAILED);
  assert.equal(rec.error.kind, 'probe_failed');
});

test('decode failure marks failed with decode_failed', () => {
  const cat = buildAudioCatalog({ maslowParts: [{ book: 9, test: 3, part: 1 }] });
  const rec = cat.records.find((r) => r.audio_id === P(9, 3, 1));
  applyProbe(cat, { url: rec.urls[0].url, sha256: 'd'.repeat(64), bytes: 4096, decode_ok: false, decode_error: 'Invalid data found', magic_ok: true, container: 'mp3' });
  assert.equal(rec.status, AUDIO_STATUS.FAILED);
  assert.equal(rec.error.kind, 'decode_failed');
});

test('duplicate content across parts raises high severity issue', () => {
  const cat = buildAudioCatalog({ maslowParts: [{ book: 5, test: 1, part: 1 }, { book: 5, test: 1, part: 2 }] });
  const sha = 'e'.repeat(64);
  for (const p of [1, 2]) {
    const rec = cat.records.find((r) => r.audio_id === P(5, 1, p));
    applyProbe(cat, { url: rec.urls[0].url, sha256: sha, bytes: 999, decode_ok: true, magic_ok: true, container: 'mp3', duration_sec: 300 });
  }
  assert.ok(cat.issues.some((i) => i.kind === 'duplicate_content_across_parts' && i.severity === 'high' && i.audio_ids.length === 2));
});

// ---------------------------------------------------------------- verified 守卫

test('markVerified requires available status and valid refs', () => {
  const cat = buildAudioCatalog({ maslowParts: [{ book: 6, test: 1, part: 1 }] });
  const id = P(6, 1, 1);
  // candidate 状态不能 verified
  let r = markVerified(cat, id, { refs: [{ kind: 'official_binding', ref: 'x' }] });
  assert.equal(r.ok, false);
  assert.equal(r.error, 'not_available');

  const rec = cat.records.find((x) => x.audio_id === id);
  applyProbe(cat, { url: rec.urls[0].url, sha256: 'f'.repeat(64), bytes: 1000, decode_ok: true, magic_ok: true, container: 'mp3', duration_sec: 301 });

  // 无 refs / 非法 kind 均拒绝
  assert.equal(markVerified(cat, id, { refs: [] }).error, 'no_verification_refs');
  assert.equal(markVerified(cat, id, { refs: [{ kind: 'vibes', ref: 'x' }] }).error, 'no_verification_refs');
  assert.equal(markVerified(cat, id, { refs: [{ kind: 'asr_match', ref: '' }] }).error, 'no_verification_refs');

  const ok = markVerified(cat, id, { refs: [{ kind: 'asr_match', ref: 'audio/align/b6t1p1.json', note: '3 anchors' }] });
  assert.equal(ok.ok, true);
  assert.equal(rec.status, AUDIO_STATUS.VERIFIED);
  assert.equal(rec.identity_status, 'verified');
  assert.equal(rec.verification_refs.length, 1);
  // 重复 ref 不重复追加
  markVerified(cat, id, { refs: [{ kind: 'asr_match', ref: 'audio/align/b6t1p1.json' }] });
  assert.equal(rec.verification_refs.length, 1);
  assert.ok(VERIFICATION_KINDS.includes('official_binding'));
});

// ---------------------------------------------------------------- sniff

test('sniffAudio detects containers and rejects html/zero', () => {
  const id3 = Buffer.concat([Buffer.from('ID3'), Buffer.alloc(60)]);
  assert.equal(sniffAudio(id3).container, 'mp3');
  const frame = Buffer.alloc(64); frame[0] = 0xff; frame[1] = 0xfb;
  assert.equal(sniffAudio(frame).container, 'mp3');
  const m4a = Buffer.alloc(64); m4a.write('....ftypM4A ', 0, 'latin1');
  assert.equal(sniffAudio(m4a).container, 'm4a');
  const ogg = Buffer.concat([Buffer.from('OggS'), Buffer.alloc(60)]);
  assert.equal(sniffAudio(ogg).container, 'ogg');
  const flac = Buffer.concat([Buffer.from('fLaC'), Buffer.alloc(60)]);
  assert.equal(sniffAudio(flac).container, 'flac');
  const wav = Buffer.alloc(64); wav.write('RIFF....WAVE', 0, 'latin1');
  assert.equal(sniffAudio(wav).container, 'wav');

  const html = Buffer.from('<!DOCTYPE html><html><head><title>404: Not Found</title></head>');
  const h = sniffAudio(html);
  assert.equal(h.ok, false);
  assert.equal(h.html, true);
  assert.equal(h.reason, 'html_body');
  assert.equal(sniffAudio(Buffer.alloc(0)).reason, 'zero_length');
  assert.equal(sniffAudio(Buffer.alloc(4)).reason, 'too_short');
  const junk = Buffer.alloc(64, 0x42);
  assert.equal(sniffAudio(junk).reason, 'unknown_magic');
});

// ---------------------------------------------------------------- Range

test('parseContentRange and validateRangeProbe', () => {
  assert.deepEqual(parseContentRange('bytes 0-299/3731165'), { start: 0, end: 299, total: 3731165 });
  assert.deepEqual(parseContentRange('bytes 100-299/3731165'), { start: 100, end: 299, total: 3731165 });
  assert.equal(parseContentRange('garbage'), null);
  assert.equal(parseContentRange('bytes 5-4/100'), null);

  assert.equal(validateRangeProbe({ status: 206, content_range: 'bytes 0-299/1000', bytes_len: 300 }).ok, true);
  assert.equal(validateRangeProbe({ status: 206, content_range: 'bytes 10-309/1000', bytes_len: 300 }).reason, 'range_start_not_zero');
  assert.equal(validateRangeProbe({ status: 206, content_range: 'bytes 0-299/1000', bytes_len: 200 }).reason, 'range_length_mismatch');
  assert.equal(validateRangeProbe({ status: 206, content_range: null, bytes_len: 300 }).reason, 'bad_content_range');
  assert.equal(validateRangeProbe({ status: 200, content_range: null, bytes_len: 11216604 }).reason, 'range_ignored_full_body');
  assert.equal(validateRangeProbe({ status: 404 }).reason, 'http_404');
});

// ---------------------------------------------------------------- full-test intervals

test('full-test intervals derive parts but never count as verified', () => {
  const cat = buildAudioCatalog({ maslowFull: [{ book: 2, test: 1 }] });
  const fid = audioIdFor(fullTestIdentity(2, 1), AUDIO_SCOPE.FULL_TEST);
  const rec = cat.records.find((r) => r.audio_id === fid);
  applyProbe(cat, { url: rec.urls[0].url, sha256: '9'.repeat(64), bytes: 2975616, decode_ok: true, magic_ok: true, container: 'mp3', duration_sec: 2000 });

  const bad = setFullTestIntervals(cat, fid, [{ part: 1, start_sec: 0, end_sec: 100 }, { part: 1, start_sec: 100, end_sec: 200 }]);
  assert.equal(bad.ok, false);

  const ok = setFullTestIntervals(cat, fid, [
    { part: 1, start_sec: 0, end_sec: 480 },
    { part: 2, start_sec: 480, end_sec: 990 },
    { part: 3, start_sec: 990, end_sec: 1500 },
    { part: 4, start_sec: 1500, end_sec: 2000 },
  ]);
  assert.equal(ok.ok, true);
  assert.equal(cat.derived_parts.length, 4);
  assert.ok(cat.derived_parts.every((d) => d.status === 'derived' && d.derived_from === fid));

  const overlap = setFullTestIntervals(cat, fid, [
    { part: 1, start_sec: 0, end_sec: 500 },
    { part: 2, start_sec: 400, end_sec: 990 },
    { part: 3, start_sec: 990, end_sec: 1500 },
    { part: 4, start_sec: 1500, end_sec: 2000 },
  ]);
  assert.equal(overlap.ok, false);
  assert.ok(overlap.errors.includes('intervals_overlap'));

  const beyond = setFullTestIntervals(cat, fid, [
    { part: 1, start_sec: 0, end_sec: 480 },
    { part: 2, start_sec: 480, end_sec: 990 },
    { part: 3, start_sec: 990, end_sec: 1500 },
    { part: 4, start_sec: 1500, end_sec: 2500 },
  ]);
  assert.equal(beyond.ok, false);
  assert.ok(beyond.errors.includes('interval_exceeds_duration'));
});

// ---------------------------------------------------------------- summary

test('summarize audio_complete requires four truly verified parts', () => {
  const cat = buildAudioCatalog({ maslowParts: [1, 2, 3, 4].map((p) => ({ book: 7, test: 2, part: p })) });
  for (const p of [1, 2, 3]) {
    const rec = cat.records.find((r) => r.audio_id === P(7, 2, p));
    applyProbe(cat, { url: rec.urls[0].url, sha256: String(p).repeat(64), bytes: 1000 * p, decode_ok: true, magic_ok: true, container: 'mp3', duration_sec: 300 + p });
    markVerified(cat, rec.audio_id, { refs: [{ kind: 'asr_match', ref: `align/b7t2p${p}.json` }] });
  }
  const p4 = cat.records.find((r) => r.audio_id === P(7, 2, 4));
  applyProbe(cat, { url: p4.urls[0].url, sha256: '4'.repeat(64), bytes: 4000, decode_ok: true, magic_ok: true, container: 'mp3', duration_sec: 304 });

  let s = summarizeAudioCatalog(cat);
  assert.equal(s.books[7].tests[2].audio_complete, false);
  const missing = s.books[7].tests[2].incomplete_parts;
  assert.equal(missing.length, 1);
  assert.equal(missing[0].part, 4);
  assert.equal(missing[0].status, 'available');

  markVerified(cat, p4.audio_id, { refs: [{ kind: 'official_binding', ref: 'listening-page:b7t2' }] });
  s = summarizeAudioCatalog(cat);
  assert.equal(s.books[7].tests[2].audio_complete, true);
  assert.equal(s.by_status[AUDIO_STATUS.VERIFIED], 4);
});

test('derived full-test parts alone never make audio_complete true', () => {
  const cat = buildAudioCatalog({ maslowFull: [{ book: 3, test: 1 }] });
  const fid = audioIdFor(fullTestIdentity(3, 1), AUDIO_SCOPE.FULL_TEST);
  const rec = cat.records.find((r) => r.audio_id === fid);
  applyProbe(cat, { url: rec.urls[0].url, sha256: '8'.repeat(64), bytes: 5000, decode_ok: true, magic_ok: true, container: 'mp3', duration_sec: 2000 });
  markVerified(cat, fid, { refs: [{ kind: 'official_binding', ref: 'x' }] });
  setFullTestIntervals(cat, fid, [
    { part: 1, start_sec: 0, end_sec: 480 },
    { part: 2, start_sec: 480, end_sec: 990 },
    { part: 3, start_sec: 990, end_sec: 1500 },
    { part: 4, start_sec: 1500, end_sec: 2000 },
  ]);
  const s = summarizeAudioCatalog(cat);
  assert.equal(s.books[3].tests[1].audio_complete, false);
  assert.ok(s.books[3].tests[1].incomplete_parts.every((x) => x.status === 'derived_only'));
  assert.equal(s.derived_parts, 4);
});

// ---------------------------------------------------------------- git blob sha1

test('gitBlobSha1Buffer matches git hash-object golden values', () => {
  // golden 值由 `git hash-object` 实测（见 S09 证据）
  assert.equal(gitBlobSha1Buffer(Buffer.from('hello\n')), 'ce013625030ba8dba906f756967f9e9ca394464a');
  assert.equal(gitBlobSha1Buffer(Buffer.from('')), 'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391');
  // 与直接 sha1("blob <n>\0"+content) 一致，且长度参与前缀
  const a = gitBlobSha1Buffer(Buffer.from('abc'));
  const b = gitBlobSha1Buffer(Buffer.from('abcd'));
  assert.notEqual(a, b);
});

// ---------------------------------------------------------------- cam21 页面解析

const PAGE_SAMPLE = `<!doctype html><html><body>
<script>
const audioTracks = {"1": "audio/C21T1_Section_1.mp3", "2": "audio/C21T1_Section_2.mp3"};
const TRANSCRIPTS = {"1": [{"sp": "WOMAN", "h": "no more than <span class=\\"tr-ans\\">ten<sup class=\\"tr-q\\">Q1</sup></span> \\u2013 and friendly.", "t": 161.64}, {"sp": "MAN", "h": "See <span class=\\"tr-ans\\">this<sup class=\\"tr-q\\">Q2</sup></span> and <span class=\\"tr-ans\\">that<sup class=\\"tr-q\\">Q3/4</sup></span>", "t": 175.0}], "2": [{"sp": "", "h": "plain", "t": 10.5}]};
const PARTS = [1,2];
</script></body></html>`;

test('parseCam21ListeningPage extracts audioTracks and transcripts with q numbers', () => {
  const parsed = parseCam21ListeningPage(PAGE_SAMPLE);
  assert.deepEqual(parsed.warnings, []);
  assert.equal(parsed.audio_tracks['1'], 'audio/C21T1_Section_1.mp3');
  assert.equal(parsed.audio_tracks['2'], 'audio/C21T1_Section_2.mp3');
  assert.equal(parsed.transcripts['1'].length, 2);
  const s1 = parsed.sections['1'];
  assert.equal(s1.lines, 2);
  assert.equal(s1.first_t, 161.64);
  assert.equal(s1.last_t, 175.0);
  assert.deepEqual(s1.q_numbers, [1, 2, 3, 4]);
  const s2 = parsed.sections['2'];
  assert.deepEqual(s2.q_numbers, []);
});

test('parseCam21ListeningPage reports warnings instead of throwing on broken input', () => {
  const noTracks = parseCam21ListeningPage('const TRANSCRIPTS = {"1": []};');
  assert.equal(noTracks.audio_tracks, null);
  assert.ok(noTracks.warnings.includes('audioTracks_not_found'));
  const broken = parseCam21ListeningPage('const audioTracks = {"1": "x"}; const TRANSCRIPTS = {"1": [}');
  assert.ok(broken.warnings.includes('TRANSCRIPTS_json_invalid') || broken.warnings.includes('TRANSCRIPTS_unbalanced'));
});

test('transcriptQNums handles Q21/22 compound markers and ignores plain Q text', () => {
  assert.deepEqual(transcriptQNums('<sup class="tr-q">Q21/22</sup>'), [21, 22]);
  assert.deepEqual(transcriptQNums('<sup class="tr-q">Q7</sup> and <sup class="tr-q">Q9</sup>'), [7, 9]);
  assert.deepEqual(transcriptQNums('Q7 without sup tag'), []);
});

test('transcriptPlainText separates inline Q markers so words do not glue together', () => {
  assert.equal(transcriptPlainText('I need ten<sup class="tr-q">Q1</sup> pounds'), 'I need ten pounds');
  assert.equal(transcriptPlainText('weather<sup class="tr-q">Q2</sup>'), 'weather');
  assert.equal(transcriptPlainText('caf\u00e9<sup class="tr-q">Q8</sup> is open'), 'caf\u00e9 is open');
  assert.equal(transcriptPlainText('<b>bold</b> and <i>italic</i>'), 'bold and italic');
  assert.equal(transcriptPlainText('<sup class="tr-q">Q21/22</sup>'), '');
  assert.equal(transcriptPlainText(null), '');
  assert.equal(transcriptPlainText('  multiple   spaces\n\tand tabs  '), 'multiple spaces and tabs');
  assert.equal(transcriptPlainText('I don&#x27;t know &quot;exactly&quot;'), 'I don\'t know "exactly"');
  assert.equal(transcriptPlainText('fish &amp; chips'), 'fish & chips');
  assert.equal(transcriptPlainText('a&nbsp;b'), 'a b');
});

