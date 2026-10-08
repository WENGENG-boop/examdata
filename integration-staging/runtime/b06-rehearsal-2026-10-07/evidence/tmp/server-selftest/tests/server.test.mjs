// Candidate frontend server tests: the static allowlist and its exclusions,
// 405 handling, the /resources compatibility bridge (400 guards, single
// season, fan-out, cross-season url dedup, per-season warnings, all-failed
// 502, legacy season guards, syllabus snapshot shape), the /api/v2
// passthrough, the /gateway/ allowlist, and the protected-port refusal.
// Every upstream is a local stub or an intentionally closed port on
// 127.0.0.1; nothing touches the network or the original services.

import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createServer as createStub} from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createServer} from '../server.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(HERE, '..');

async function listen(handler) {
  const server = createStub(handler);
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return {server, url: `http://127.0.0.1:${server.address().port}`};
}

async function close(server) {
  await new Promise(resolve => server.close(resolve));
}

// The default upstream is an intentionally closed port, so no test can
// reach a real service by accident; tests that exercise upstream behaviour
// pass their own stub.
async function withServer(run, options = {}) {
  const server = createServer({upstream: 'http://127.0.0.1:1', ...options});
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const {port} = server.address();
  assert.notEqual(port, 5188);
  assert.notEqual(port, 8000);
  try {
    await run(`http://127.0.0.1:${port}`);
  } finally {
    await close(server);
  }
}

function envelope(items) {
  return JSON.stringify({schema_version: 'examdata.v2/1', request_id: 'stub',
                         data: {items}, meta: {}, error: null});
}

function cieItem(publicId, documentType) {
  return {
    public_id: publicId,
    content_available: true,
    content_link: `/api/v2/assets/${publicId}/content`,
    discovery: {board: 'cie', subject: '9999', subject_title: 'synthetic-subject',
                year: 2024, season: 'Jun', paper: '11', document_type: documentType},
  };
}

function edexcelItem(publicId, documentType) {
  return {
    public_id: publicId,
    content_available: true,
    content_link: `/api/v2/assets/${publicId}/content`,
    discovery: {board: 'edexcel', subject: 'wma11', subject_title: null,
                year: '2024', season: null, paper: 'wma11-01', document_type: documentType},
  };
}

test('the staged files and snapshots are served', async () => {
  await withServer(async base => {
    const page = await fetch(`${base}/`);
    assert.equal(page.status, 200);
    assert.match(page.headers.get('content-type'), /text\/html/);
    assert.match(await page.text(), /集成暂存副本/);
    for (const [route, type] of [['/index.html', /text\/html/], ['/app.js', /javascript/],
                                 ['/client.mjs', /javascript/], ['/search.mjs', /javascript/],
                                 ['/styles.css', /css/]]) {
      const res = await fetch(base + route);
      assert.equal(res.status, 200);
      assert.match(res.headers.get('content-type'), type);
    }
    for (const route of ['/catalog.json', '/syllabi.json']) {
      const res = await fetch(base + route);
      assert.equal(res.status, 200);
      assert.match(res.headers.get('content-type'), /application\/json/);
      await res.json();
    }
  });
});

test('test-and-fixture paths are not served', async () => {
  await withServer(async base => {
    for (const route of ['/tests/server.test.mjs', '/tests/flow.test.mjs',
                         '/fixtures/catalog.json', '/fixtures/resources.json',
                         '/fixture-server.mjs', '/README.md', '/PROVENANCE.json']) {
      const res = await fetch(base + route);
      assert.equal(res.status, 404, `${route} must be 404`);
    }
  });
});

test('non-GET requests are refused with Allow: GET', async () => {
  await withServer(async base => {
    const res = await fetch(`${base}/resources`, {method: 'POST'});
    assert.equal(res.status, 405);
    assert.equal(res.headers.get('allow'), 'GET');
  });
});

test('/resources keeps the legacy 400 guards', async () => {
  await withServer(async base => {
    const cases = [
      'year=2024&subject=9999',
      'board=foo&year=2024&subject=9999',
      'board=cie&year=1999&subject=9999',
      `board=cie&year=2024&subject=${'9'.repeat(81)}`,
      `board=cie&year=2024&subject=9999&paper=${'1'.repeat(21)}`,
    ];
    for (const qs of cases) {
      const res = await fetch(`${base}/resources?${qs}`);
      assert.equal(res.status, 400);
      assert.deepEqual(await res.json(), {detail: '请选择科目、年份与考季'});
    }
  });
});

test('/resources keeps the legacy per-season guards (single season)', async () => {
  await withServer(async base => {
    const bad = await fetch(`${base}/resources?board=cie&subject=9999&year=2024&season=Apr`);
    assert.equal(bad.status, 502);
    assert.deepEqual(await bad.json(), {detail: '请选择有效科目与考季'});
    const badSubject = await fetch(`${base}/resources?board=cie&subject=99&year=2024&season=Jun`);
    assert.equal(badSubject.status, 502);
    assert.deepEqual(await badSubject.json(), {detail: '请选择有效科目与考季'});
    const badEdexcel = await fetch(`${base}/resources?board=edexcel&subject=wma11&year=2024&season=May`);
    assert.equal(badEdexcel.status, 502);
    assert.deepEqual(await badEdexcel.json(), {detail: '请从科目列表选择 Edexcel 课程'});
  });
});

test('/resources asks a single season when one is named, without fan-out', async () => {
  const requests = [];
  const {server: stub, url: upstream} = await listen((req, res) => {
    const url = new URL(req.url, 'http://stub');
    requests.push(Object.fromEntries(url.searchParams));
    res.writeHead(200, {'content-type': 'application/json; charset=utf-8'});
    res.end(envelope([cieItem('asset_syn_qp', 'question_paper'),
                      cieItem('asset_syn_ms', 'mark_scheme')]));
  });
  try {
    await withServer(async base => {
      const res = await fetch(`${base}/resources?board=cie&subject=9999&year=2024&season=Jun`);
      assert.equal(res.status, 200);
      const body = await res.json();
      assert.equal(body.documents.length, 2);
      assert.equal(body.warning, '');
      assert.deepEqual(body.documents.map(d => d.type), ['question_paper', 'mark_scheme']);
      assert.ok(body.documents.every(d => d.season === 'Jun' && d.year === '2024'
        && d.origin === 'staged_fixture' && d.title === 'synthetic-subject'));
      assert.ok(body.documents.every(d => d.url.startsWith(base + '/api/v2/assets/')));
    }, {upstream});
  } finally {
    await close(stub);
  }
  assert.equal(requests.length, 1);
  assert.deepEqual(requests[0], {system: 'cie', query: '9999 2024 Jun'});
});

test('/resources fans out over the board seasons and reports per-season failures', async () => {
  const requests = [];
  const {server: stub, url: upstream} = await listen((req, res) => {
    const url = new URL(req.url, 'http://stub');
    const query = url.searchParams.get('query') || '';
    requests.push({system: url.searchParams.get('system'), query});
    if (query.includes('Mar')) {
      res.writeHead(503, {'content-type': 'application/json; charset=utf-8'});
      return res.end(JSON.stringify({error: {code: 'upstream_unavailable'}}));
    }
    res.writeHead(200, {'content-type': 'application/json; charset=utf-8'});
    res.end(envelope(query.includes('Jun')
      ? [cieItem('asset_syn_qp', 'question_paper'), cieItem('asset_syn_ms', 'mark_scheme')]
      : []));
  });
  try {
    await withServer(async base => {
      const res = await fetch(`${base}/resources?board=cie&subject=9999&year=2024`);
      assert.equal(res.status, 200);
      const body = await res.json();
      assert.equal(body.documents.length, 2);
      assert.match(body.warning, /^Mar 查询失败：来源查询失败（HTTP 503）$/);
      assert.equal(body.syllabus, null);
    }, {upstream});
  } finally {
    await close(stub);
  }
  assert.deepEqual(requests.map(r => r.query).sort(),
                   ['9999 2024 Jun', '9999 2024 Mar', '9999 2024 Nov']);
  assert.ok(requests.every(r => r.system === 'cie'));
});

test('/resources deduplicates cross-season duplicates by url (last wins)', async () => {
  const queries = [];
  const {server: stub, url: upstream} = await listen((req, res) => {
    const url = new URL(req.url, 'http://stub');
    queries.push(url.searchParams.get('query'));
    res.writeHead(200, {'content-type': 'application/json; charset=utf-8'});
    res.end(envelope([edexcelItem('asset_syn_edx_qp', 'question_paper'),
                      edexcelItem('asset_syn_edx_ms', 'mark_scheme')]));
  });
  try {
    await withServer(async base => {
      const res = await fetch(`${base}/resources?board=edexcel&subject=wma11&year=2024`);
      assert.equal(res.status, 200);
      const body = await res.json();
      // Four seasons answer with the same two fixtures; the url dedup keeps
      // two rows, with the Edexcel block's own null season and paper.
      assert.equal(body.documents.length, 2);
      assert.equal(body.warning, '');
      assert.ok(body.documents.every(d => d.season === null && d.paper === 'wma11-01'
        && d.title === null && d.board === 'edexcel'));
      assert.deepEqual(body.documents.map(d => d.type), ['question_paper', 'mark_scheme']);
    }, {upstream});
  } finally {
    await close(stub);
  }
  assert.deepEqual(queries.sort(), ['wma11 2024 January', 'wma11 2024 June',
                                    'wma11 2024 November', 'wma11 2024 October']);
});

test('/resources reports 502 when every season fails', async () => {
  const {server: stub, url: upstream} = await listen((req, res) => {
    res.writeHead(500, {'content-type': 'application/json; charset=utf-8'});
    res.end(JSON.stringify({error: {code: 'provider_failed'}}));
  });
  try {
    await withServer(async base => {
      const res = await fetch(`${base}/resources?board=cie&subject=9999&year=2024`);
      assert.equal(res.status, 502);
      const body = await res.json();
      assert.match(body.detail, /^Mar 查询失败：来源查询失败（HTTP 500）；Jun /);
      assert.match(body.detail, /；Nov 查询失败：来源查询失败（HTTP 500）$/);
    }, {upstream});
  } finally {
    await close(stub);
  }
});

test('/resources keeps the legacy syllabus snapshot shape', async () => {
  const {server: stub, url: upstream} = await listen((req, res) => {
    res.writeHead(200, {'content-type': 'application/json; charset=utf-8'});
    res.end(envelope([]));
  });
  try {
    await withServer(async base => {
      const res = await fetch(`${base}/resources?board=cie&subject=9709&year=2024`);
      assert.equal(res.status, 200);
      const body = await res.json();
      assert.equal(body.documents.length, 0);
      assert.equal(body.warning, '');
      assert.equal(body.syllabus.origin, 'snapshot');
      assert.equal(body.syllabus.subject, '9709');
      assert.equal(body.syllabus.title, 'Mathematics 9709');
    }, {upstream});
  } finally {
    await close(stub);
  }
});

test('the /api/v2 proxy passes the v2 envelope and status through', async () => {
  const seen = [];
  const {server: stub, url: upstream} = await listen((req, res) => {
    const url = new URL(req.url, 'http://stub');
    seen.push(url.pathname + url.search);
    res.writeHead(200, {'content-type': 'application/json; charset=utf-8'});
    res.end(envelope([cieItem('asset_syn_qp', 'question_paper')]));
  });
  try {
    await withServer(async base => {
      const res = await fetch(`${base}/api/v2/resources?system=cie&query=9999%202024%20Jun`);
      assert.equal(res.status, 200);
      assert.match(res.headers.get('content-type'), /application\/json/);
      const body = await res.json();
      assert.equal(body.schema_version, 'examdata.v2/1');
      assert.equal(body.data.items[0].public_id, 'asset_syn_qp');
      assert.equal(body.data.items[0].discovery.document_type, 'question_paper');
    }, {upstream});
  } finally {
    await close(stub);
  }
  assert.deepEqual(seen, ['/api/v2/resources?system=cie&query=9999%202024%20Jun']);
});

test('the /api/v2 proxy answers 502 when the upstream is unreachable', async () => {
  await withServer(async base => {
    const res = await fetch(`${base}/api/v2/resources?system=cie`);
    assert.equal(res.status, 502);
    assert.deepEqual(await res.json(),
                     {detail: '暂时无法连接数据服务，请检查前端的 EXAMDATA_URL 配置。'});
  });
});

test('the /gateway/ proxy keeps the legacy allowlist and vocabulary', async () => {
  const {server: stub, url: upstream} = await listen((req, res) => {
    res.writeHead(200, {'content-type': 'application/json; charset=utf-8'});
    res.end(JSON.stringify({ok: true}));
  });
  try {
    await withServer(async base => {
      const denied = await fetch(`${base}/gateway/secret`);
      assert.equal(denied.status, 404);
      const allowed = await fetch(`${base}/gateway/health`);
      assert.equal(allowed.status, 200);
      assert.deepEqual(await allowed.json(), {ok: true});
    }, {upstream});
  } finally {
    await close(stub);
  }
  await withServer(async base => {
    const res = await fetch(`${base}/gateway/health`);
    assert.equal(res.status, 502);
    assert.deepEqual(await res.json(),
                     {detail: '暂时无法连接数据服务，请检查前端的 EXAMDATA_URL 配置。'});
  });
});

test('the entry point refuses the protected original ports and invalid ports', async () => {
  const serverPath = path.join(ROOT, 'server.mjs');
  for (const [value, expected] of [['5188', /拒绝绑定受保护端口 5188/],
                                   ['8000', /拒绝绑定受保护端口 8000/],
                                   ['abc', /FRONTEND_PORT 不是有效端口/]]) {
    const child = spawn(process.execPath, [serverPath],
                        {env: {...process.env, FRONTEND_PORT: value}});
    let stderr = '';
    child.stderr.setEncoding('utf8');
    child.stderr.on('data', chunk => { stderr += chunk; });
    const code = await new Promise(resolve => child.on('close', resolve));
    assert.equal(code, 2, `FRONTEND_PORT=${value} must exit 2`);
    assert.match(stderr, expected);
  }
});
