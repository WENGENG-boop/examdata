// Examdata v2 staged client (Phase A proposal).
//
// Replaces the legacy browser calls that went straight to /resources and the
// dead /gateway proxy: every request now goes through the staged v2 envelope
// (/api/v2) and the browser never carries credentials.
//
// This module is a proposal. It is exercised only against the private offline
// fixture server in this directory and is not connected to any real source.
// It runs unchanged in the browser and under `node --test`.

export const API_PREFIX = '/api/v2';
export const SCHEMA_VERSION = 'examdata.v2/1';
export const FLAG_NAME = 'examdata.v2-client';

export const SEASONS = {
  cie: ['Jun', 'Nov', 'Mar'],
  edexcel: ['January', 'June', 'October', 'November'],
};

export class ApiClientError extends Error {
  constructor(message, {code = 'client_error', status = 0, requestId = null, causes = []} = {}) {
    super(message);
    this.name = 'ApiClientError';
    this.code = code;
    this.status = status;
    this.requestId = requestId;
    this.causes = causes;
  }
}

function defaultStorage(explicit) {
  if (explicit !== undefined) return explicit;
  try {
    return typeof localStorage === 'undefined' ? null : localStorage;
  } catch {
    return null;
  }
}

// The v2 client is on by default. It can be switched off reversibly by
// storing FLAG_NAME='off' (e.g. localStorage.setItem('examdata.v2-client','off'));
// removing the marker switches it back on.
export function clientEnabled({storage} = {}) {
  const store = defaultStorage(storage);
  if (!store) return true;
  try {
    return store.getItem(FLAG_NAME) !== 'off';
  } catch {
    return true;
  }
}

export function setClientEnabled(enabled, {storage} = {}) {
  const store = defaultStorage(storage);
  const next = Boolean(enabled);
  if (!store) return next;
  try {
    if (next) store.removeItem(FLAG_NAME);
    else store.setItem(FLAG_NAME, 'off');
  } catch {
    // A blocked storage must not break the page; the flag simply stays put.
  }
  return next;
}

function resolveUrl(value, baseUrl, {strict = false} = {}) {
  if (value === null || value === undefined || value === '') return '';
  const text = String(value);
  if (/^https?:\/\//i.test(text)) return text;
  let base = baseUrl;
  if (!base && typeof location !== 'undefined') base = location.href;
  if (!base) {
    if (strict) {
      throw new ApiClientError(`相对路径 ${text} 需要 baseUrl 或浏览器 location`, {code: 'no_base_url'});
    }
    return '';
  }
  try {
    return new URL(text, base).href;
  } catch {
    if (strict) {
      throw new ApiClientError(`无法解析的请求地址：${text}`, {code: 'invalid_url'});
    }
    return '';
  }
}

// One v2 request, one parsed envelope. A non-2xx response, a populated
// `error` object, invalid JSON and an unknown schema_version all raise
// ApiClientError, so callers never branch on raw HTTP shapes.
export async function fetchEnvelope(path, {fetchImpl, baseUrl, headers} = {}) {
  const doFetch = fetchImpl ?? globalThis.fetch;
  if (typeof doFetch !== 'function') {
    throw new ApiClientError('没有任何 fetch 实现可用', {code: 'no_fetch'});
  }
  const url = resolveUrl(path, baseUrl, {strict: true});
  let response;
  try {
    response = await doFetch(url, {headers: {accept: 'application/json', ...headers}});
  } catch (cause) {
    throw new ApiClientError(`网络请求失败：${url}`, {code: 'network_error', causes: [String(cause)]});
  }
  let body = null;
  try {
    body = await response.json();
  } catch {
    throw new ApiClientError(`响应不是有效 JSON（HTTP ${response.status}）`, {code: 'invalid_json', status: response.status});
  }
  const error = body && body.error;
  if (!response.ok || error) {
    const message = (error && (error.message || error.code)) || `查询失败（HTTP ${response.status}）`;
    throw new ApiClientError(message, {
      code: (error && error.code) || 'http_error',
      status: response.status,
      requestId: body && body.request_id != null ? body.request_id : null,
    });
  }
  if (!body || body.schema_version !== SCHEMA_VERSION) {
    throw new ApiClientError(`未知的响应信封版本：${body && body.schema_version}`, {
      code: 'unsupported_envelope',
      status: response.status,
    });
  }
  return {data: body.data, meta: body.meta || {}, requestId: body.request_id ?? null};
}

const ROLE_ALIASES = {
  question_paper: 'question_paper',
  qp: 'question_paper',
  paper: 'question_paper',
  mark_scheme: 'mark_scheme',
  markscheme: 'mark_scheme',
  ms: 'mark_scheme',
  examiner_report: 'examiner_report',
  er: 'examiner_report',
  grade_threshold: 'grade_threshold',
  grade_thresholds: 'grade_threshold',
  gt: 'grade_threshold',
};

// Map one /api/v2/resources item onto the document shape app.js already
// groups and renders. The source-discovery fields come from the proposed
// `discovery` block (board/subject/year/season/paper/document_type); until
// that block exists upstream, items without it simply produce null.
export function documentFromResource(item, {baseUrl} = {}) {
  if (!item || typeof item !== 'object') return null;
  const discovery = item.discovery && typeof item.discovery === 'object' ? item.discovery : {};
  const rawRole = String(discovery.document_type ?? item.role ?? '').trim().toLowerCase().replace(/[\s-]+/g, '_');
  const type = ROLE_ALIASES[rawRole];
  if (!type) return null;
  const evidence = Array.isArray(item.evidence) ? item.evidence.map(String) : item.evidence ? [String(item.evidence)] : [];
  const quality = evidence.some(label => /synthetic[_-]?fixture/i.test(label)) ? 'synthetic_fixture' : null;
  // content_available === false means the content can not be fetched; never offer a link.
  const link = item.content_available === false ? null : (item.content_link ?? (item.links && item.links.content) ?? null);
  return {
    public_id: item.public_id ?? null,
    type,
    role: rawRole,
    board: discovery.board ?? item.system ?? null,
    code: discovery.subject != null ? String(discovery.subject) : null,
    title: discovery.subject_title ?? null,
    year: discovery.year != null ? String(discovery.year) : null,
    season: discovery.season ?? null,
    paper: discovery.paper != null && discovery.paper !== '' ? String(discovery.paper) : null,
    url: resolveUrl(link, baseUrl),
    availability: item.availability ?? 'unknown',
    quality,
    evidence,
  };
}

// Query every season of the selected board (or the one season the user
// picked), merging documents. A partial failure keeps the other seasons and
// reports a warning; only an all-failed fan-out rejects.
export async function searchDocuments(query, {fetchImpl, baseUrl, seasons = SEASONS} = {}) {
  const board = query && query.board === 'edexcel' ? 'edexcel' : 'cie';
  const configured = seasons[board] || [];
  const wanted = query && query.season ? [query.season] : configured;
  const tokens = [];
  if (query && query.subject) tokens.push(String(query.subject));
  if (query && query.year) tokens.push(String(query.year));
  if (query && query.paper) tokens.push(String(query.paper));
  const outcomes = await Promise.allSettled(wanted.map(season => {
    const text = [...tokens, season].join(' ');
    const path = `${API_PREFIX}/resources?system=${encodeURIComponent(board)}&query=${encodeURIComponent(text)}`;
    return fetchEnvelope(path, {fetchImpl, baseUrl});
  }));
  const documents = [];
  const failed = [];
  const causes = [];
  outcomes.forEach((outcome, index) => {
    const season = wanted[index];
    if (outcome.status !== 'fulfilled') {
      failed.push(season);
      causes.push(outcome.reason && outcome.reason.message ? String(outcome.reason.message) : String(outcome.reason));
      return;
    }
    const payload = outcome.value && outcome.value.data;
    const items = payload && Array.isArray(payload.items) ? payload.items : null;
    if (!items) {
      failed.push(season);
      causes.push('响应缺少资料列表');
      return;
    }
    for (const item of items) {
      const document = documentFromResource(item, {baseUrl});
      if (document) documents.push(document);
    }
  });
  if (wanted.length && failed.length === wanted.length) {
    throw new ApiClientError(`来源查询失败（${failed.join('、')}）`, {code: 'all_seasons_failed', causes});
  }
  const warning = failed.length ? `部分考季查询失败（${failed.join('、')}）` : null;
  const origin = documents.some(document => document.quality === 'synthetic_fixture') ? 'staged_fixture' : 'source';
  return {documents, seasons: {queried: [...wanted], failed: [...failed]}, warning, origin, syllabus: null};
}
