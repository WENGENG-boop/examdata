// Contract tests for the staged v2 client. Everything runs offline against
// fake fetch implementations; no request leaves this process.

import test from 'node:test';
import assert from 'node:assert/strict';
import {
  ApiClientError, FLAG_NAME, clientEnabled, documentFromResource,
  fetchEnvelope, searchDocuments, setClientEnabled,
} from '../client.mjs';

const BASE = 'http://staged.test';

function envelope(items, {completeness = 'complete'} = {}) {
  return {
    schema_version: 'examdata.v2/1',
    request_id: 'fixture-request',
    data: {items},
    meta: {
      dataset_revision: 'fixture-2026-10-06',
      retrieved_at: '2026-10-06T00:00:00Z',
      pagination: {limit: null, next_cursor: null},
      completeness,
      warnings: ['staged_fixture_validation'],
      providers: ['fixture'],
    },
    error: null,
  };
}

function errorBody(code, message) {
  return {
    schema_version: 'examdata.v2/1',
    request_id: 'fixture-request',
    data: null,
    meta: {
      dataset_revision: 'fixture-2026-10-06',
      retrieved_at: '2026-10-06T00:00:00Z',
      pagination: {limit: null, next_cursor: null},
      completeness: 'unknown',
      warnings: [],
      providers: [],
    },
    error: {code, message, retryable: false, details: {}},
  };
}

function response(body, status = 200) {
  return {ok: status >= 200 && status < 300, status, json: async () => body};
}

function item(overrides = {}) {
  return {
    public_id: 'asset_test',
    system: 'cie',
    media_type: 'application/pdf',
    availability: 'fixture',
    content_available: true,
    content_link: '/api/v2/assets/asset_test/content',
    evidence: ['synthetic_fixture'],
    links: {self: '/api/v2/assets/asset_test', content: '/api/v2/assets/asset_test/content'},
    discovery: {board: 'cie', subject: '9709', subject_title: 'Mathematics 9709', year: '2026', season: 'Jun', paper: '21', document_type: 'question_paper'},
    ...overrides,
  };
}

function fakeStorage() {
  const map = new Map();
  return {
    getItem: key => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
    removeItem: key => map.delete(key),
  };
}

test('fetchEnvelope parses the staged envelope and absolutises the path', async () => {
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({url, options});
    return response(envelope([item()]));
  };
  const result = await fetchEnvelope('/api/v2/resources', {fetchImpl, baseUrl: BASE});
  assert.equal(calls[0].url, `${BASE}/api/v2/resources`);
  assert.equal(calls[0].options.headers.accept, 'application/json');
  assert.equal(result.data.items.length, 1);
  assert.equal(result.meta.dataset_revision, 'fixture-2026-10-06');
  assert.equal(result.requestId, 'fixture-request');
});

test('fetchEnvelope raises typed errors for failures, bad JSON and unknown envelopes', async () => {
  await assert.rejects(
    fetchEnvelope('/api/v2/resources', {
      fetchImpl: async () => response(errorBody('upstream_unavailable', '考季不可用'), 503),
      baseUrl: BASE,
    }),
    error => error instanceof ApiClientError && error.code === 'upstream_unavailable' && error.status === 503);
  await assert.rejects(
    fetchEnvelope('/api/v2/resources', {
      fetchImpl: async () => ({ok: true, status: 200, json: async () => { throw new Error('bad body'); }}),
      baseUrl: BASE,
    }),
    error => error instanceof ApiClientError && error.code === 'invalid_json');
  await assert.rejects(
    fetchEnvelope('/api/v2/resources', {
      fetchImpl: async () => response({schema_version: 'examdata.v1/9', data: {}, meta: {}, error: null}),
      baseUrl: BASE,
    }),
    error => error instanceof ApiClientError && error.code === 'unsupported_envelope');
  await assert.rejects(
    fetchEnvelope('/api/v2/resources', {fetchImpl: async () => { throw new Error('refused'); }, baseUrl: BASE}),
    error => error instanceof ApiClientError && error.code === 'network_error');
});

test('documentFromResource maps discovery fields to the legacy document shape', () => {
  const doc = documentFromResource(item(), {baseUrl: BASE});
  assert.equal(doc.type, 'question_paper');
  assert.equal(doc.board, 'cie');
  assert.equal(doc.code, '9709');
  assert.equal(doc.year, '2026');
  assert.equal(doc.season, 'Jun');
  assert.equal(doc.paper, '21');
  assert.equal(doc.url, `${BASE}/api/v2/assets/asset_test/content`);
  assert.equal(doc.quality, 'synthetic_fixture');
  assert.equal(doc.availability, 'fixture');
});

test('documentFromResource marks unavailable items and drops unknown roles', () => {
  const unavailable = documentFromResource(
    item({availability: 'unknown', content_available: false, content_link: null}),
    {baseUrl: BASE});
  assert.equal(unavailable.availability, 'unknown');
  assert.equal(unavailable.url, '');
  const report = documentFromResource(
    item({discovery: {...item().discovery, document_type: 'examiner_report', paper: null}}),
    {baseUrl: BASE});
  assert.equal(report.type, 'examiner_report');
  assert.equal(report.paper, null);
  assert.equal(documentFromResource(
    item({discovery: {...item().discovery, document_type: 'syllabus'}}),
    {baseUrl: BASE}), null);
});

test('searchDocuments fans out over every board season and merges documents', async () => {
  const calls = [];
  const fetchImpl = async url => {
    calls.push(url);
    return response(envelope([item()]));
  };
  const result = await searchDocuments({board: 'cie', subject: '9709', year: '2026'}, {fetchImpl, baseUrl: BASE});
  assert.equal(calls.length, 3);
  assert.deepEqual(calls.map(url => new URL(url).searchParams.get('system')), ['cie', 'cie', 'cie']);
  assert.deepEqual(calls.map(url => new URL(url).searchParams.get('query')),
    ['9709 2026 Jun', '9709 2026 Nov', '9709 2026 Mar']);
  assert.equal(result.documents.length, 3);
  assert.equal(result.warning, null);
  assert.equal(result.origin, 'staged_fixture');
  assert.deepEqual(result.seasons, {queried: ['Jun', 'Nov', 'Mar'], failed: []});
});

test('a failed season is reported without discarding the others', async () => {
  const fetchImpl = async url => {
    if (url.includes('Mar')) return response(errorBody('upstream_unavailable', '考季不可用'), 503);
    return response(envelope([item()]));
  };
  const result = await searchDocuments({board: 'cie', subject: '9709', year: '2026'}, {fetchImpl, baseUrl: BASE});
  assert.equal(result.documents.length, 2);
  assert.deepEqual(result.seasons.failed, ['Mar']);
  assert.match(result.warning, /部分考季查询失败（Mar）/);
  assert.equal(result.origin, 'staged_fixture');
});

test('an all-failed fan-out rejects instead of claiming no matches', async () => {
  const fetchImpl = async () => { throw new Error('offline'); };
  await assert.rejects(
    searchDocuments({board: 'edexcel', subject: 'wec11', year: '2026'}, {fetchImpl, baseUrl: BASE}),
    error => error instanceof ApiClientError
      && error.code === 'all_seasons_failed'
      && /January/.test(error.message)
      && /November/.test(error.message));
});

test('a chosen season queries only that season with the edexcel selector set', async () => {
  const calls = [];
  const fetchImpl = async url => {
    calls.push(url);
    return response(envelope([]));
  };
  const result = await searchDocuments(
    {board: 'edexcel', subject: 'wec11', year: '2026', season: 'June'},
    {fetchImpl, baseUrl: BASE});
  assert.equal(calls.length, 1);
  assert.equal(new URL(calls[0]).searchParams.get('system'), 'edexcel');
  assert.equal(new URL(calls[0]).searchParams.get('query'), 'wec11 2026 June');
  assert.deepEqual(result.seasons, {queried: ['June'], failed: []});
  assert.equal(result.origin, 'source');
});

test('a paper number joins the per-season query token list', async () => {
  const calls = [];
  const fetchImpl = async url => {
    calls.push(url);
    return response(envelope([]));
  };
  await searchDocuments({board: 'cie', subject: '9709', year: '2026', paper: '21', season: 'Jun'}, {fetchImpl, baseUrl: BASE});
  assert.equal(new URL(calls[0]).searchParams.get('query'), '9709 2026 21 Jun');
});

test('the v2 client flag is on by default and reversible', () => {
  const storage = fakeStorage();
  assert.equal(clientEnabled({storage}), true);
  setClientEnabled(false, {storage});
  assert.equal(storage.getItem(FLAG_NAME), 'off');
  assert.equal(clientEnabled({storage}), false);
  setClientEnabled(true, {storage});
  assert.equal(storage.getItem(FLAG_NAME), null);
  assert.equal(clientEnabled({storage}), true);
});
