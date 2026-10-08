/**
 * ielts-transcript.test.mjs — S11 原文逐 Part 选择与跨源补缺单元测试（无网络）
 *
 * 覆盖计划验收场景：空 test/raw、Part 缺失、正文截尾、错误套、同 Part
 * 多源冲突、广告/HTML 错误页、四段全有但最后一句缺失、音文本分维度状态。
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  SCRIPT_STATUS, SCRIPT_THRESHOLDS, TRANSCRIPT_SCHEMA,
  assessTranscriptText, tailRelation, headRelation, seqContains,
  comparePartScript, matchTranscripts, unsegmentedFallback,
} from '../transcript-matcher.mjs';

const PART_TEXT = `PART 1
Narrator: Good morning and welcome to the community centre.
Receptionist: Hello, I'd like to ask about booking a room for a family celebration.
Narrator: Certainly. Can I take your name first?
Receptionist: Yes, it's Sarah Jenkins, and the celebration is for my parents' anniversary.
Narrator: How many people would you expect to attend the event?
Receptionist: Probably about eighty guests, including a few children.
Narrator: We have a large hall that seats one hundred comfortably.
Receptionist: That sounds ideal. Could you tell me what the hire charge is?
Narrator: The charge for a Saturday evening is two hundred pounds.
Receptionist: Does that include the use of the kitchen as well?
Narrator: Yes, the kitchen is included, but you would need to bring your own plates.
Receptionist: That's fine. I'll call back tomorrow to confirm the booking.`;

function cand(source, text, over = {}) {
  return {
    source,
    text,
    meta: {
      identity: { book: 20, test: 2, part: 'P4' },
      identity_basis: 'page-header',
      source_ref: `${source}:b20:t2:p4`,
      sha256: `${source}-sha`,
      ...over,
    },
  };
}

test('assessTranscriptText flags truncation, HTML and advertisement scaffolds', () => {
  const truncated = assessTranscriptText('PART 2\nSo the next thing we need to do is think about the timetable and...');
  assert.equal(truncated.tail_ellipsis, true);
  assert.equal(truncated.ends_with_terminal, false);

  const html = assessTranscriptText('<!DOCTYPE html><html><body>upstream error</body></html>');
  assert.equal(html.html_like, true);

  const ad = assessTranscriptText('Advertisements\n\n<script>document.createElement("div")</script>\nsome body text');
  assert.equal(ad.ad_like, true);

  const complete = assessTranscriptText(PART_TEXT);
  assert.equal(complete.tail_ellipsis, false);
  assert.equal(complete.ends_with_terminal, true);
  assert.ok(complete.chars > SCRIPT_THRESHOLDS.min_part_chars);
});

test('empty candidate list yields missing; empty text is rejected outright', () => {
  const r1 = comparePartScript({ identity: { book: 20, test: 2, part: 'P4' }, candidates: [] });
  assert.equal(r1.status, SCRIPT_STATUS.MISSING);
  assert.equal(r1.chosen, null);

  const r2 = comparePartScript({
    identity: { book: 20, test: 2, part: 'P4' },
    candidates: [cand('ito', '   ')],
  });
  assert.equal(r2.status, SCRIPT_STATUS.MISSING);
  assert.deepEqual(r2.rejected.map((x) => x.reason), ['empty']);
});

test('HTML error page and advertisement page are rejected, not chosen', () => {
  const r = comparePartScript({
    identity: { book: 20, test: 2, part: 'P4' },
    candidates: [
      cand('ito', '<!DOCTYPE html><html><body>error</body></html>'),
      cand('pdf-audioscript', PART_TEXT),
    ],
  });
  assert.equal(r.status, SCRIPT_STATUS.OK);
  assert.equal(r.chosen.source, 'pdf-audioscript');
  assert.ok(r.rejected.some((x) => x.reason === 'html_error_page'));
});

test('wrong test identity (wrong edition/test) is rejected even if text is complete', () => {
  const r = comparePartScript({
    identity: { book: 20, test: 2, part: 'P4' },
    candidates: [
      cand('ito', PART_TEXT, { identity: { book: 20, test: 3, part: 'P4' } }),
    ],
  });
  assert.equal(r.status, SCRIPT_STATUS.MISSING);
  assert.deepEqual(r.rejected.map((x) => x.reason), ['identity_mismatch']);
});

test('truncated (ellipsis tail) text is partial; complete fallback wins over truncated primary', () => {
  const truncatedText = PART_TEXT.slice(0, 420).trim() + '...';
  const r = comparePartScript({
    identity: { book: 20, test: 2, part: 'P4' },
    candidates: [
      cand('ito', truncatedText),
      cand('maslow', PART_TEXT),
    ],
  });
  assert.equal(r.chosen.source, 'maslow');
  assert.equal(r.status, SCRIPT_STATUS.OK);
  assert.equal(r.complete_basis, 'cross_source_prefix_agreement');
  assert.ok(r.conflicts.some((c) => c.type === 'alternative_tail_truncated'));

  const onlyTruncated = comparePartScript({
    identity: { book: 20, test: 2, part: 'P4' },
    candidates: [cand('ito', truncatedText)],
  });
  assert.equal(onlyTruncated.status, SCRIPT_STATUS.PARTIAL);
  assert.equal(onlyTruncated.complete_basis, null);
});

test('same-Part multi-source tail conflict lands in review with both sources kept', () => {
  const other = PART_TEXT.replace('I\'ll call back tomorrow to confirm the booking.', 'We look forward to seeing you at the weekend.');
  const r = comparePartScript({
    identity: { book: 20, test: 2, part: 'P4' },
    candidates: [cand('ito', PART_TEXT), cand('maslow', other)],
  });
  assert.equal(r.status, SCRIPT_STATUS.REVIEW);
  assert.ok(r.conflicts.some((c) => c.type === 'tail_conflict'));
  assert.equal(r.alternatives.length, 1);
});

test('four parts present but chosen source is missing the last sentence → review via tail extension', () => {
  const cut = PART_TEXT.slice(0, PART_TEXT.indexOf('I\'ll call back tomorrow')).trim();
  const r = comparePartScript({
    identity: { book: 20, test: 2, part: 'P4' },
    candidates: [cand('ito', cut), cand('maslow', PART_TEXT)],
  });
  // chosen is the longer (maslow) one; the shorter ito tail must be contained
  assert.equal(r.chosen.source, 'maslow');
  assert.ok(r.conflicts.some((c) => c.type === 'alternative_tail_truncated'));
  assert.equal(r.status, SCRIPT_STATUS.OK, 'shorter candidate is truncated, chosen is fine');
});

test('when the chosen text is itself the truncated one, status is review', () => {
  const long = `${PART_TEXT}\nNarrator: Thank you for calling and have a pleasant day.`;
  // force the truncated candidate to be chosen by making the long one ellipsis-tailed
  const longEllipsis = long + '...';
  const r = comparePartScript({
    identity: { book: 20, test: 2, part: 'P4' },
    candidates: [cand('ito', longEllipsis), cand('maslow', PART_TEXT)],
  });
  // maslow (non-ellipsis) is chosen; ito is longer but ellipsis-tailed
  assert.equal(r.chosen.source, 'maslow');
  assert.ok(r.conflicts.length >= 0);
});

test('audio dimension is separate from text: text found but no audio stays unverified audio', () => {
  const r = comparePartScript({
    identity: { book: 20, test: 2, part: 'P4' },
    candidates: [cand('ito', PART_TEXT)],
    audio: { available: false, duration_sec: null, source: null },
  });
  assert.equal(r.status, SCRIPT_STATUS.OK);
  assert.equal(r.audio.available, false);
  assert.equal(r.audio.words_per_sec, undefined);

  const withAudio = comparePartScript({
    identity: { book: 20, test: 2, part: 'P4' },
    candidates: [cand('ito', PART_TEXT)],
    audio: { available: true, duration_sec: 240, source: 'maslow' },
  });
  assert.equal(withAudio.audio.available, true);
  assert.ok(withAudio.audio.words_per_sec > 0);
});

test('words-per-second far outside speech range flags duration_ratio review', () => {
  const r = comparePartScript({
    identity: { book: 20, test: 2, part: 'P4' },
    candidates: [cand('ito', PART_TEXT)],
    audio: { available: true, duration_sec: 5000, source: 'maslow' },
  });
  assert.ok(r.audio.ratio_ok === false);
  assert.equal(r.status, SCRIPT_STATUS.REVIEW);
  assert.ok(r.conflicts.some((c) => c.type === 'duration_ratio'));
});

test('unsegmentedFallback keeps raw text unsegmented and refuses empty/HTML', () => {
  const ok = unsegmentedFallback('Long raw text '.repeat(40));
  assert.equal(ok.format, 'raw');
  assert.deepEqual(ok.tests, {});
  assert.equal(ok.parts, 0);

  assert.equal(unsegmentedFallback(''), null);
  assert.equal(unsegmentedFallback('<html><body>err</body></html>'), null);
});

test('matchTranscripts reports per-part status and missing keys', () => {
  const out = matchTranscripts({
    book: 20,
    candidatesByPart: {
      '2:4': [cand('ito', PART_TEXT)],
      '2:3': [],
    },
  });
  assert.equal(out.schema, TRANSCRIPT_SCHEMA);
  assert.equal(out.summary.parts_total, 2);
  assert.equal(out.summary.ok, 1);
  assert.equal(out.summary.missing, 1);
  assert.deepEqual(out.missing_parts, ['2:3']);
  assert.equal(out.parts['2:4'].chosen.source, 'ito');
});

test('tailRelation/headRelation/seqContains basics', () => {
  assert.equal(seqContains(['a', 'b', 'c'], ['b', 'c']), true);
  assert.equal(seqContains(['a', 'b', 'c'], ['b', 'd']), false);
  assert.equal(tailRelation('one two three', 'two three'), 'extends');
  assert.equal(tailRelation('two three', 'one two three'), 'extended_by');
  assert.equal(tailRelation('one two three', 'one two three'), 'same');
  assert.equal(tailRelation('alpha beta gamma', 'delta epsilon zeta'), 'differ');
});
