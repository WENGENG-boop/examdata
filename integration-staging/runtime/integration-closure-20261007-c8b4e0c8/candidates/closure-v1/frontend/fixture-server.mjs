// Staged frontend fixture server (Phase A proposal).
//
// A private, offline stand-in for the pages' runtime dependencies:
//   * serves the staged copy (index.html/app.js/client.mjs/search.mjs/styles.css)
//     and the synthetic /catalog.json + /syllabi.json snapshots,
//   * answers /api/v2/resources* with the same examdata.v2/1 envelope the
//     staged v2 API emits, from private fixtures only,
//   * injects the fixture failure map (e.g. CIE March -> 503) so the client's
//     partial-failure path can be exercised,
//   * never touches the network, never reads the original project tree,
//   * binds 127.0.0.1 on any port except the protected original ports (5188,
//     8000); the default is an ephemeral port.
//
// It is intentionally a separate plain-Node implementation: it does not
// import the Python v2 API. The Phase B merge replaces it with the real
// /api/v2 backend (see README.md).

import {createServer as createHttpServer} from 'node:http';
import {createHash, randomUUID} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));

export const SCHEMA_VERSION = 'examdata.v2/1';
export const WARNING = 'staged_fixture_validation';
export const PROTECTED_PORTS = new Set([5188, 8000]);

const STATIC_FILES = new Map([
  ['/', 'index.html'],
  ['/index.html', 'index.html'],
  ['/app.js', 'app.js'],
  ['/client.mjs', 'client.mjs'],
  ['/search.mjs', 'search.mjs'],
  ['/styles.css', 'styles.css'],
]);

const FIXTURE_FILES = new Map([
  ['/catalog.json', 'catalog.json'],
  ['/syllabi.json', 'syllabi.json'],
]);

const CONTENT_TYPES = new Map([
  ['.html', 'text/html; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.mjs', 'text/javascript; charset=utf-8'],
  ['.css', 'text/css; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
]);

// Lowercase season token -> full English name (both spellings are accepted in
// query tokens and indexed in each item's haystack).
const SEASON_ENGLISH = new Map([
  ['jun', 'June'], ['nov', 'November'], ['mar', 'March'],
  ['january', 'January'], ['june', 'June'], ['october', 'October'],
  ['november', 'November'],
]);

function contentTypeFor(filename) {
  return CONTENT_TYPES.get(path.extname(filename).toLowerCase()) || 'application/octet-stream';
}

function sha256hex(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

export function placeholderBytes(publicId) {
  return Buffer.from(`%PDF-1.4\n% staged fixture placeholder ${publicId}\n%%EOF\n`, 'utf8');
}

function sendJson(res, status, body) {
  const bytes = Buffer.from(JSON.stringify(body), 'utf8');
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': bytes.length,
    'cache-control': 'no-store',
  });
  res.end(bytes);
}

function sendText(res, status, text) {
  const bytes = Buffer.from(String(text), 'utf8');
  res.writeHead(status, {
    'content-type': 'text/plain; charset=utf-8',
    'content-length': bytes.length,
    'cache-control': 'no-store',
  });
  res.end(bytes);
}

async function serveFile(res, filePath, filename) {
  const bytes = await readFile(filePath);
  res.writeHead(200, {
    'content-type': contentTypeFor(filename),
    'content-length': bytes.length,
    'cache-control': 'no-store',
  });
  res.end(bytes);
}

export function createServer({rootDir = HERE, fixturesDir = path.join(HERE, 'fixtures')} = {}) {
  const resources = JSON.parse(readFileSync(path.join(fixturesDir, 'resources.json'), 'utf8'));
  if (!Array.isArray(resources.items)) {
    throw new Error('fixtures/resources.json must carry an items array');
  }
  const revision = resources.revision || 'fixture-unversioned';
  const failures = resources.failures || {};
  const seasonLists = resources.seasons || {};
  const byId = new Map(resources.items.map(item => [item.public_id, item]));

  function okEnvelope(data, {completeness = 'complete', warnings = [WARNING]} = {}) {
    return {
      schema_version: SCHEMA_VERSION,
      request_id: randomUUID(),
      data,
      meta: {
        dataset_revision: revision,
        retrieved_at: new Date().toISOString(),
        pagination: {limit: null, next_cursor: null},
        completeness,
        warnings: [...warnings],
        providers: ['fixture'],
      },
      error: null,
    };
  }

  function errorEnvelope(code, message) {
    return {
      schema_version: SCHEMA_VERSION,
      request_id: randomUUID(),
      data: null,
      meta: {
        dataset_revision: revision,
        retrieved_at: new Date().toISOString(),
        pagination: {limit: null, next_cursor: null},
        completeness: 'unknown',
        warnings: [],
        providers: [],
      },
      error: {code, message, retryable: false, details: {}},
    };
  }

  function detectSeason(system, tokens) {
    const list = seasonLists[system] || [];
    const lookup = new Map();
    for (const season of list) {
      lookup.set(String(season).toLowerCase(), season);
      const english = SEASON_ENGLISH.get(String(season).toLowerCase());
      if (english && !lookup.has(english.toLowerCase())) lookup.set(english.toLowerCase(), season);
    }
    for (const token of tokens) {
      const hit = lookup.get(token);
      if (hit) return hit;
    }
    return null;
  }

  function haystack(item) {
    const parts = [item.system, item.media_type];
    const discovery = item.discovery && typeof item.discovery === 'object' ? item.discovery : {};
    for (const value of Object.values(discovery)) {
      if (value !== null && value !== undefined && value !== '') parts.push(String(value));
    }
    if (discovery.season) {
      const english = SEASON_ENGLISH.get(String(discovery.season).toLowerCase());
      if (english) parts.push(english);
    }
    return parts.join(' ').toLowerCase();
  }

  async function handle(req, res) {
    const url = new URL(req.url || '/', 'http://127.0.0.1');
    const {pathname} = url;
    const apiPath = pathname.startsWith('/api/');
    if (req.method !== 'GET') {
      if (apiPath) return sendJson(res, 405, errorEnvelope('method_not_allowed', '暂存夹具服务器仅支持 GET'));
      return sendText(res, 405, 'method not allowed');
    }
    const staticName = STATIC_FILES.get(pathname);
    if (staticName) return serveFile(res, path.join(rootDir, staticName), staticName);
    const fixtureName = FIXTURE_FILES.get(pathname);
    if (fixtureName) return serveFile(res, path.join(fixturesDir, fixtureName), fixtureName);

    if (pathname === '/api/v2/resources') {
      const system = url.searchParams.get('system');
      const query = url.searchParams.get('query') || '';
      const tokens = query.toLowerCase().split(/\s+/).filter(Boolean);
      const systemFailures = system ? failures[system] : null;
      if (systemFailures) {
        const season = detectSeason(system, tokens);
        const failure = season ? systemFailures[season] : null;
        if (failure) {
          return sendJson(res, failure.status || 503,
            errorEnvelope(failure.code || 'upstream_unavailable', failure.message || '暂存夹具：该考季不可用'));
        }
      }
      const items = resources.items.filter(item =>
        (!system || item.system === system) && tokens.every(token => haystack(item).includes(token)));
      return sendJson(res, 200, okEnvelope({items}, {completeness: items.length ? 'complete' : 'empty'}));
    }

    const match = pathname.match(/^\/api\/v2\/(?:resources|assets)\/([A-Za-z0-9_-]+)(\/content)?$/);
    if (match) {
      const item = byId.get(match[1]);
      if (!item) return sendJson(res, 404, errorEnvelope('not_found', `未知的资源标识：${match[1]}`));
      if (match[2]) {
        if (!item.content_available) {
          return sendJson(res, 404, errorEnvelope('content_not_available', `该资源暂未提供内容：${match[1]}`));
        }
        const bytes = placeholderBytes(match[1]);
        const sha = sha256hex(bytes);
        res.writeHead(200, {
          'content-type': item.media_type || 'application/pdf',
          'content-length': bytes.length,
          etag: `"${sha}"`,
          'x-content-sha256': sha,
          'x-evidence': 'synthetic_fixture',
          'cache-control': 'no-store',
        });
        return res.end(bytes);
      }
      return sendJson(res, 200, okEnvelope({item}));
    }

    if (apiPath) return sendJson(res, 404, errorEnvelope('route_not_found', '暂存夹具服务器没有该路由'));
    return sendText(res, 404, 'not found');
  }

  return createHttpServer((req, res) => {
    Promise.resolve(handle(req, res)).catch(() => {
      if (!res.headersSent) {
        if ((req.url || '').startsWith('/api/')) sendJson(res, 500, errorEnvelope('internal_error', '暂存夹具服务器内部错误'));
        else sendText(res, 500, 'staged fixture server error');
      } else {
        res.destroy();
      }
    });
  });
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url));
if (isMain) {
  const port = Number(process.env.STAGED_FRONTEND_PORT ?? 0);
  if (!Number.isInteger(port) || port < 0 || port > 65535) {
    console.error('STAGED_FRONTEND_PORT 不是有效端口');
    process.exit(2);
  }
  if (PROTECTED_PORTS.has(port)) {
    console.error(`拒绝绑定受保护端口 ${port}（原服务端口）；请使用其他端口（默认 0 = 临时端口）`);
    process.exit(2);
  }
  const server = createServer({});
  server.listen(port, '127.0.0.1', () => {
    const bound = server.address().port;
    console.log(`staged fixture frontend server: http://127.0.0.1:${bound}（集成暂存副本 · staged fixture validation · 仅 127.0.0.1）`);
  });
}
