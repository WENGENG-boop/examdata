// Staged v2 frontend server (B06 candidate).
//
// The B06 replacement for the legacy frontend server: no source-discovery
// business logic runs in the frontend process, and the staged page never
// fetches a live provider directly.
//   * serves the staged pages/modules plus the synthetic /catalog.json and
//     /syllabi.json snapshots (read from fixturesDir),
//   * proxies /api/v2/* to the examdata read service (EXAMDATA_URL), so the
//     staged v2 client is answered by the Python read API from private
//     fixtures,
//   * keeps the legacy /resources shape as a compatibility bridge during the
//     validation window by projecting the v2 items back onto legacy document
//     rows; the row urls point back at this server's own /api/v2 content
//     routes,
//   * keeps the legacy /gateway/ proxy for the still-legacy paths only (the
//     exact paths the original server allowed; the optional X-API-Key comes
//     from the environment and is never inlined),
//   * binds 127.0.0.1 only, defaults to an ephemeral port and refuses the
//     protected original ports (5188, 8000).
//
// It reads no original tree, no database and no live provider network.

import {createServer as createHttpServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {Readable} from 'node:stream';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));

export const PROTECTED_PORTS = new Set([5188, 8000]);
export const SEASONS = Object.freeze({
  cie: Object.freeze(['Mar', 'Jun', 'Nov']),
  edexcel: Object.freeze(['January', 'June', 'October', 'November']),
});

//: v2 discovery document_type -> legacy document row type; unknown values are
//: skipped rather than guessed.
export const ROLE_ALIASES = new Map([
  ['question_paper', 'question_paper'],
  ['mark_scheme', 'mark_scheme'],
  ['examiner_report', 'examiner_report'],
  ['grade_threshold', 'grade_threshold'],
]);

const STATIC_FILES = new Map([
  ['/', ['index.html', 'text/html; charset=utf-8']],
  ['/index.html', ['index.html', 'text/html; charset=utf-8']],
  ['/app.js', ['app.js', 'text/javascript; charset=utf-8']],
  ['/client.mjs', ['client.mjs', 'text/javascript; charset=utf-8']],
  ['/search.mjs', ['search.mjs', 'text/javascript; charset=utf-8']],
  ['/styles.css', ['styles.css', 'text/css; charset=utf-8']],
]);

const FIXTURE_FILES = new Map([
  ['/catalog.json', ['catalog.json', 'application/json; charset=utf-8']],
  ['/syllabi.json', ['syllabi.json', 'application/json; charset=utf-8']],
]);

const GATEWAY_ALLOWED = /^\/(?:health|papers|papers\/\d+\/tree|api\/v1\/(?:boards|search|question\/\d+|paper|ielts\/(?:reading\/\d+\/\d+|listening\/\d+\/\d+)))$/;

const UPSTREAM_TIMEOUT_MS = 180000;

function sendJson(res, status, body) {
  const bytes = Buffer.from(JSON.stringify(body), 'utf8');
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': bytes.length,
    'cache-control': 'no-store',
  });
  res.end(bytes);
}

function upstreamBase(upstream) {
  const base = new URL(upstream);
  if (base.protocol !== 'http:' && base.protocol !== 'https:') {
    throw new Error('EXAMDATA_URL 必须是 http(s) 地址');
  }
  return base;
}

function upstreamUrl(base, pathname) {
  const target = new URL(base);
  target.pathname = base.pathname.replace(/\/$/, '') + pathname;
  target.search = '';
  return target;
}

export function createServer({rootDir = HERE, fixturesDir = path.join(HERE, 'fixtures'),
                              upstream = process.env.EXAMDATA_URL || 'http://127.0.0.1:8000'} = {}) {
  const base = upstreamBase(upstream);

  async function readSyllabi() {
    try {
      return JSON.parse(await readFile(path.join(fixturesDir, 'syllabi.json'), 'utf8'));
    } catch {
      return null;
    }
  }

  function syllabusFor(syllabi, query) {
    const table = syllabi && (query.board === 'edexcel' ? syllabi.edexcel : syllabi.cie);
    const entry = table && query.subject ? table[query.subject] : null;
    if (!entry) return null;
    return {board: query.board, subject: query.subject, title: entry.title || query.subject,
            page: entry.page || '', syllabuses: entry.syllabuses || [], origin: 'snapshot'};
  }

  // One season request against the v2 read API. The inner guards keep the
  // legacy per-season error vocabulary; the tokens mirror what the staged
  // client sends (subject, year, optional paper, season).
  async function loadSeason(query, season) {
    if (query.board === 'cie') {
      if (!/^\d{4}$/.test(query.subject) || !SEASONS.cie.includes(season)) {
        throw new Error('请选择有效科目与考季');
      }
    } else if (!SEASONS.edexcel.includes(season)) {
      throw new Error('请从科目列表选择 Edexcel 课程');
    }
    const tokens = [query.subject, query.year];
    if (query.paper) tokens.push(query.paper);
    tokens.push(season);
    const target = upstreamUrl(base, '/api/v2/resources');
    target.search = new URLSearchParams({system: query.board, query: tokens.join(' ')}).toString();
    const response = await fetch(target, {
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS), redirect: 'error'});
    if (!response.ok) throw new Error(`来源查询失败（HTTP ${response.status}）`);
    const body = await response.json().catch(() => null);
    if (!body || !body.data || !Array.isArray(body.data.items)) {
      throw new Error('来源查询响应格式错误');
    }
    return body.data.items;
  }

  // v2 item -> legacy document row: only items the backend reports as
  // available with a content link become rows, and only known document types.
  function documentRows(query, items, origin) {
    const rows = [];
    for (const item of items) {
      if (!item || item.content_available !== true || !item.content_link) continue;
      const discovery = item.discovery && typeof item.discovery === 'object' ? item.discovery : {};
      const type = ROLE_ALIASES.get(String(discovery.document_type));
      if (!type) continue;
      rows.push({
        board: query.board,
        subject: query.subject,
        year: query.year,
        season: discovery.season ?? null,
        paper: discovery.paper ?? '',
        type,
        url: new URL(item.content_link, origin).toString(),
        title: discovery.subject_title ?? null,
        origin: 'staged_fixture',
      });
    }
    return rows;
  }

  function dedupe(documents) {
    return [...new Map(documents.map(row => [row.url, row])).values()];
  }

  // The legacy /resources semantics: an explicit season asks that season
  // only; otherwise every season of the board is asked and settled
  // independently, and only a total failure is an error.
  async function legacyResources(query, origin) {
    const syllabi = await readSyllabi();
    if (query.season) {
      const items = await loadSeason(query, query.season);
      return {documents: dedupe(documentRows(query, items, origin)), warning: '',
              syllabus: syllabusFor(syllabi, query)};
    }
    const seasons = SEASONS[query.board];
    const results = await Promise.allSettled(seasons.map(season => loadSeason(query, season)));
    const documents = [];
    const warnings = [];
    results.forEach((result, i) => {
      if (result.status === 'fulfilled') {
        documents.push(...documentRows(query, result.value, origin));
      } else {
        warnings.push(`${seasons[i]} 查询失败：${result.reason?.message || '来源暂不可用'}`);
      }
    });
    if (results.every(result => result.status === 'rejected')) throw new Error(warnings.join('；'));
    return {documents: dedupe(documents), warning: warnings.join('；'),
            syllabus: syllabusFor(syllabi, query)};
  }

  async function serveFile(res, filePath, contentType) {
    const bytes = await readFile(filePath);
    res.writeHead(200, {
      'content-type': contentType,
      'content-length': bytes.length,
      'cache-control': 'no-cache',
      'x-content-type-options': 'nosniff',
    });
    res.end(bytes);
  }

  async function proxy(res, target, headers) {
    const response = await fetch(target, {
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      redirect: 'error',
      headers,
    });
    const outHeaders = {'cache-control': 'no-store'};
    for (const key of ['content-type', 'content-disposition']) {
      if (response.headers.has(key)) outHeaders[key] = response.headers.get(key);
    }
    res.writeHead(response.status, outHeaders);
    if (!response.body) return res.end();
    Readable.fromWeb(response.body).on('error', () => res.destroy()).pipe(res);
  }

  async function handle(req, res) {
    const url = new URL(req.url || '/', 'http://localhost');
    if (req.method !== 'GET') {
      res.writeHead(405, {allow: 'GET'});
      return res.end();
    }
    if (url.pathname === '/resources') {
      const query = Object.fromEntries(
        ['board', 'subject', 'year', 'season', 'paper'].map(k => [k, url.searchParams.get(k) || '']));
      if (!['cie', 'edexcel'].includes(query.board) || !/^20\d{2}$/.test(query.year)
          || query.subject.length > 80 || query.paper.length > 20) {
        return sendJson(res, 400, {detail: '请选择科目、年份与考季'});
      }
      try {
        const origin = `http://${req.headers.host || '127.0.0.1'}`;
        return sendJson(res, 200, await legacyResources(query, origin));
      } catch (error) {
        return sendJson(res, 502, {detail: error.message});
      }
    }
    if (url.pathname.startsWith('/gateway/')) {
      const path = url.pathname.slice('/gateway'.length);
      if (!GATEWAY_ALLOWED.test(path)) {
        res.writeHead(404);
        return res.end();
      }
      const target = upstreamUrl(base, path);
      target.search = url.search;
      const headers = process.env.EXAMDATA_API_KEY
        ? {'X-API-Key': process.env.EXAMDATA_API_KEY} : {};
      return proxy(res, target, headers);
    }
    if (url.pathname.startsWith('/api/v2/')) {
      const target = upstreamUrl(base, url.pathname);
      target.search = url.search;
      return proxy(res, target, {});
    }
    const file = STATIC_FILES.get(url.pathname);
    if (file) return serveFile(res, path.join(rootDir, file[0]), file[1]);
    const fixture = FIXTURE_FILES.get(url.pathname);
    if (fixture) return serveFile(res, path.join(fixturesDir, fixture[0]), fixture[1]);
    res.writeHead(404);
    return res.end('Not found');
  }

  return createHttpServer((req, res) => {
    Promise.resolve(handle(req, res)).catch(error => {
      if (res.headersSent) return res.destroy();
      sendJson(res, 502, {
        detail: error.name === 'TimeoutError'
          ? '请求超时，请稍后手动重试。'
          : '暂时无法连接数据服务，请检查前端的 EXAMDATA_URL 配置。',
      });
    });
  });
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url));
if (isMain) {
  const port = Number(process.env.FRONTEND_PORT ?? 0);
  if (!Number.isInteger(port) || port < 0 || port > 65535) {
    console.error('FRONTEND_PORT 不是有效端口');
    process.exit(2);
  }
  if (PROTECTED_PORTS.has(port)) {
    console.error(`拒绝绑定受保护端口 ${port}（原服务端口）；请使用其他端口（默认 0 = 临时端口）`);
    process.exit(2);
  }
  const server = createServer({});
  server.listen(port, '127.0.0.1', () => {
    const bound = server.address().port;
    console.log(`staged v2 frontend server: http://127.0.0.1:${bound}`
      + `（EXAMDATA_URL=${process.env.EXAMDATA_URL || 'http://127.0.0.1:8000'} · 仅 127.0.0.1）`);
  });
}
