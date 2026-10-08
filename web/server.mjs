// Examdata Web — standalone frontend server. Read-only: never writes data or touches the backend process.
import http from 'node:http';
import { readFile, readdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { join, normalize, extname } from 'node:path';
import { Readable } from 'node:stream';
import { timingSafeEqual } from 'node:crypto';
import { resources } from './lib/resources.mjs';

const root = fileURLToPath(new URL('.', import.meta.url));
const upstream = new URL(process.env.EXAMDATA_URL || 'http://127.0.0.1:8000');
const port = Number(process.env.WEB_PORT || 5190);
const timetableDir = process.env.EXAMDATA_TIMETABLE_DIR || join(root, '..', 'src', 'examdata', 'timetable', 'data');
const apiKey = process.env.EXAMDATA_API_KEY;
const classic = new URL(process.env.EXAMDATA_CLASSIC_URL || 'http://127.0.0.1:8002');

const types = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml' };
// Static roots: public/ for the app, plus the shared search helpers and catalogue snapshots.
const mounts = [['/lib/search.mjs', join(root, 'lib', 'search.mjs')], ['/data/catalog.json', join(root, 'data', 'catalog.json')], ['/data/syllabi.json', join(root, 'data', 'syllabi.json')]];
const gatewayAllowed = /^\/(?:health|assets\/\d+|api\/v1\/(?:boards|search|paper|question\/\d+))$/;

const json = (res, status, body) => { res.writeHead(status, { 'Content-Type': types['.json'], 'Cache-Control': 'no-store' }); res.end(JSON.stringify(body)); };
const readJson = async path => JSON.parse(await readFile(path, 'utf8'));
const cached = new Map();
const once = (key, load) => { if (!cached.has(key)) cached.set(key, load().catch(e => { cached.delete(key); throw e; })); return cached.get(key); };

async function upstreamFetch(path, search = '', timeout = 15000) {
  const target = new URL(upstream);
  target.pathname = upstream.pathname.replace(/\/$/, '') + path;
  target.search = search;
  return fetch(target, { signal: AbortSignal.timeout(timeout), redirect: 'error', headers: apiKey ? { 'X-API-Key': apiKey } : {} });
}
async function upstreamJson(path, search) {
  try { const r = await upstreamFetch(path, search, 6000); return r.ok ? await r.json() : null; } catch { return null; }
}

// ---- Timetable: every snapshot (CIE Zone 5 + Edexcel IAL) merged into one date-ordered list.
// The running backend has no date-range route, and its timetable data is these same snapshot files.
const monthOf = { cie: { Mar: '03', Jun: '06', Nov: '11' }, edexcel: { Jan: '01', Jun: '06', Oct: '10', Nov: '11' } };
const snapshotDir = board => board === 'edexcel' ? join(timetableDir, 'edexcel', 'ial') : join(timetableDir, 'zone5');
async function timetableSeasons(board) {
  const names = await readdir(snapshotDir(board)).catch(() => []);
  const back = Object.fromEntries(Object.entries(monthOf[board]).map(([k, v]) => [v, k]));
  return names.map(n => n.match(/^(\d{4})-(\d{2})\.json$/)).filter(m => m && back[m[2]]).map(m => ({ year: Number(m[1]), season: back[m[2]], file: `${m[1]}-${m[2]}.json` })).sort((a, b) => b.year - a.year || monthOf[board][b.season] - monthOf[board][a.season]);
}
function allEvents() {
  return once('timetable', async () => {
    const events = [], series = [];
    for (const board of ['cie', 'edexcel']) {
      for (const s of await timetableSeasons(board)) {
        const data = await readJson(join(snapshotDir(board), s.file)).catch(() => null);
        if (!data?.events) continue;
        const key = `${s.year}-${s.season}`;
        series.push({ board, key, year: s.year, season: s.season, count: data.events.length, url: data.source?.url || '', sha256: data.source?.sha256 || '' });
        for (const e of data.events) if (/^\d{4}-\d{2}-\d{2}$/.test(e.date)) events.push({ board, series: key, date: e.date, session: e.session || '', level: e.level || '', subject_code: e.subject_code, paper_code: e.paper_code, subject_title: e.subject_title || '', duration_raw: e.duration_raw || '', duration_minutes: e.duration_minutes || 0 });
      }
    }
    events.sort((a, b) => a.date.localeCompare(b.date) || a.session.localeCompare(b.session) || a.subject_code.localeCompare(b.subject_code));
    return { events, series };
  });
}
async function timetableRange(q) {
  const day = /^\d{4}-\d{2}-\d{2}$/;
  if (!day.test(q.from || '') || !day.test(q.to || '') || q.from > q.to) return [400, { detail: 'from / to 须为 YYYY-MM-DD' }];
  if ((new Date(q.to) - new Date(q.from)) / 864e5 > 400) return [400, { detail: '日期范围不能超过 400 天' }];
  const boards = q.board === 'cie' || q.board === 'edexcel' ? [q.board] : ['cie', 'edexcel'];
  const subject = String(q.subject || '').trim().toUpperCase().slice(0, 16);
  const { events, series } = await allEvents();
  const match = e => boards.includes(e.board) && (!subject || e.subject_code.toUpperCase().startsWith(subject));
  const pool = events.filter(match);
  const hit = pool.filter(e => e.date >= q.from && e.date <= q.to);
  const keys = new Set(hit.map(e => e.board + '|' + e.series));
  // Nearest exam dates outside the window let the UI jump straight to a month that has exams.
  const prev = pool.filter(e => e.date < q.from).at(-1)?.date || null;
  const next = pool.find(e => e.date > q.to)?.date || null;
  return [200, { from: q.from, to: q.to, count: hit.length, events: hit, series: series.filter(s => keys.has(s.board + '|' + s.key)), prev, next, bounds: { first: pool[0]?.date || null, last: pool.at(-1)?.date || null } }];
}

// ---- Overview numbers, each source independent so one failure never blanks the page.
async function stats() {
  const [catalog, syllabi, health, search, cieSeasons, edxSeasons] = await Promise.all([
    once('catalog', () => readJson(join(root, 'data', 'catalog.json'))),
    once('syllabi', () => readJson(join(root, 'data', 'syllabi.json'))),
    upstreamJson('/health'),
    upstreamJson('/api/v1/search', '?limit=1'),
    timetableSeasons('cie'),
    timetableSeasons('edexcel'),
  ]);
  const byType = {};
  for (const item of catalog.items) byType[item.type] = (byType[item.type] || 0) + 1;
  return {
    backend: !!health,
    papers: health?.papers ?? null,
    questions: search ? { total: search.total, byBoard: search.by_board } : null,
    catalog: { snapshot: catalog.snapshot_date, files: catalog.items.length, subjects: new Set(catalog.items.map(i => i.code)).size, byType, edexcelSubjects: catalog.edexcelSubjects.length },
    syllabi: { cie: Object.keys(syllabi.cie || {}).length, edexcel: Object.keys(syllabi.edexcel || {}).length },
    timetable: { cie: cieSeasons.length, edexcel: edxSeasons.length, latest: cieSeasons[0] || null },
  };
}

async function serveFile(res, path) {
  const data = await readFile(path);
  res.writeHead(200, { 'Content-Type': types[extname(path)] || 'application/octet-stream', 'Cache-Control': 'no-cache', 'X-Content-Type-Options': 'nosniff' });
  res.end(data);
}

http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://localhost');
    if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405, { Allow: 'GET, HEAD' }); return res.end(); }
    const p = url.pathname, q = Object.fromEntries(url.searchParams);

    // Fixed upstream targets: the caller cannot select an arbitrary proxy host.
    const directApi = /^\/(?:api\/v[12](?:\/|$)|health$|docs(?:\/|$)|redoc$|openapi\.json$|paper-qa\/|questions(?:\/|$)|papers(?:\/|$)|assets\/|taxonomy(?:\/|$)|monitor(?:\/|$))/.test(p);
    if (directApi || p === '/classic' || p.startsWith('/classic/')) {
      const isClassic = !directApi;
      if (directApi && apiKey && !['/health', '/docs', '/redoc', '/openapi.json'].includes(p)) {
        const supplied = Buffer.from(String(req.headers['x-api-key'] || ''));
        const expected = Buffer.from(apiKey);
        if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected)) return json(res, 401, { detail: 'Invalid or missing API key' });
      }
      if (p === '/classic') { res.writeHead(307, { Location: '/classic/' }); return res.end(); }
      const target = new URL(isClassic ? classic : upstream);
      target.pathname = isClassic ? (p.slice('/classic'.length) || '/') : p;
      target.search = url.search;
      const requestHeaders = directApi && apiKey ? { 'X-API-Key': apiKey } : {};
      for (const key of ['range', 'if-none-match', 'if-range']) if (req.headers[key]) requestHeaders[key] = req.headers[key];
      const response = await fetch(target, { method: req.method, redirect: 'manual', signal: AbortSignal.timeout(180000), headers: requestHeaders });
      const headers = { 'Cache-Control': 'no-store' };
      for (const key of ['content-type', 'content-disposition', 'content-length', 'etag', 'location']) if (response.headers.has(key)) headers[key] = response.headers.get(key);
      res.writeHead(response.status, headers);
      if (!response.body || req.method === 'HEAD') return res.end();
      Readable.fromWeb(response.body).on('error', () => res.destroy()).pipe(res);
      return;
    }

    if (p === '/api/stats') return json(res, 200, await stats());
    if (p === '/api/timetable/events') { const [status, body] = await timetableRange(q); return json(res, status, body); }
    if (p === '/api/resources') {
      const query = Object.fromEntries(['board', 'subject', 'year', 'season', 'paper'].map(k => [k, q[k] || '']));
      if (!['cie', 'edexcel'].includes(query.board) || !/^20\d{2}$/.test(query.year) || query.subject.length > 80 || query.paper.length > 20) return json(res, 400, { detail: '请选择科目与年份' });
      const catalog = await once('catalog', () => readJson(join(root, 'data', 'catalog.json')));
      const syllabi = await once('syllabi', () => readJson(join(root, 'data', 'syllabi.json'))).catch(() => null);
      try { return json(res, 200, await resources(query, catalog.edexcelSubjects, syllabi)); }
      catch (error) { return json(res, 502, { detail: error.message }); }
    }
    if (p.startsWith('/gateway/')) {
      const path = p.slice('/gateway'.length);
      if (!gatewayAllowed.test(path)) return json(res, 404, { detail: 'Not found' });
      const response = await upstreamFetch(path, url.search, path === '/api/v1/paper' ? 180000 : 20000);
      const headers = { 'Cache-Control': 'no-store' };
      for (const key of ['content-type', 'content-disposition', 'content-length']) if (response.headers.has(key)) headers[key] = response.headers.get(key);
      res.writeHead(response.status, headers);
      if (!response.body) return res.end();
      Readable.fromWeb(response.body).on('error', () => res.destroy()).pipe(res);
      return;
    }
    const mount = mounts.find(([m]) => m === p);
    if (mount) return await serveFile(res, mount[1]);
    const rel = p === '/' ? 'index.html' : normalize(p).replace(/^[\\/]+/, '');
    if (rel.includes('..') || !/^[\w./-]+$/.test(rel)) { res.writeHead(404); return res.end('Not found'); }
    return await serveFile(res, join(root, 'public', rel)).catch(() => { res.writeHead(404); res.end('Not found'); });
  } catch (error) {
    if (res.headersSent) return res.destroy();
    json(res, 502, { detail: error.name === 'TimeoutError' ? '请求超时，请稍后重试。' : '暂时无法连接数据服务，请检查 EXAMDATA_URL。' });
  }
}).listen(port, process.env.WEB_HOST || '127.0.0.1', () => console.log(`Examdata Web: http://${process.env.WEB_HOST || '127.0.0.1'}:${port}`));
