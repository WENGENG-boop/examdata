// B07 cross-stack rehearsal script (private; run by b07_route_probe.py section H).
//
// Drives the *candidate's own* staged client (frontend/client.mjs) and raw HTTP
// against the candidate's frontend server (frontend/server.mjs) whose upstream
// is a private uvicorn instance of the candidate read API. Everything is
// 127.0.0.1, synthetic fixtures only, no credentials, no original tree.
//
// Usage: node b07_cross_stack.mjs <candidateFrontendDir> <frontendBase> <upstreamBase>
// Output: one JSON object on stdout. Exit 0 when every check passed.

import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const [clientDir, frontendBase, upstreamBase] = process.argv.slice(2);
if (!clientDir || !frontendBase || !upstreamBase) {
  console.error('usage: node b07_cross_stack.mjs <clientDir> <frontendBase> <upstreamBase>');
  process.exit(2);
}

const checks = [];
function check(name, ok, detail) {
  checks.push({name, ok: Boolean(ok), detail});
}
function sha256(buffer) {
  return createHash('sha256').update(buffer).digest('hex');
}
function sorted(values) {
  return [...values].sort();
}

const CIE = {
  ms: 'asset_nz3uic3wquirttazjeo4fnsi3g7esn3k',
  qp: 'asset_umsge7vuubq3ncsz3zfe7b3golwybrmn',
};
const EDX = {
  ms: 'asset_6xyrzhw4g5dy56xaxmhzk52da6zem5vu',
  qp: 'asset_jkw4xdasfrjtknr6ewnvus2rflr2r56n',
};
const OBS = {};

const client = await import(pathToFileURL(path.join(clientDir, 'client.mjs')).href);

async function get(pathname) {
  const response = await fetch(frontendBase + pathname, {redirect: 'error'});
  return {status: response.status, headers: response.headers,
          bytes: Buffer.from(await response.arrayBuffer())};
}

// -- static surface --------------------------------------------------------- #
{
  const index = await get('/');
  const indexFile = await readFile(path.join(clientDir, 'index.html'));
  check('static_index_bytes_equal',
        index.status === 200 && index.bytes.equals(indexFile)
        && (index.headers.get('content-type') || '').startsWith('text/html'),
        {status: index.status, ctype: index.headers.get('content-type')});

  const alias = await get('/index.html');
  check('static_root_alias_serves_index', alias.status === 200 && alias.bytes.equals(indexFile),
        {status: alias.status});

  const missing = await get('/definitely-missing');
  check('static_missing_404', missing.status === 404 && missing.bytes.toString('utf8') === 'Not found',
        {status: missing.status, body: missing.bytes.toString('utf8')});

  const post = await fetch(frontendBase + '/', {method: 'POST'});
  check('method_405_allow_get', post.status === 405 && post.headers.get('allow') === 'GET',
        {status: post.status, allow: post.headers.get('allow')});
}

// -- snapshot fixtures served by the server --------------------------------- #
{
  const catalog = await get('/catalog.json');
  const catalogFile = await readFile(path.join(clientDir, 'fixtures', 'catalog.json'));
  check('catalog_json_bytes_equal',
        catalog.status === 200 && catalog.bytes.equals(catalogFile),
        {status: catalog.status, bytes: catalog.bytes.length});

  const syllabi = await get('/syllabi.json');
  const syllabiFile = await readFile(path.join(clientDir, 'fixtures', 'syllabi.json'));
  let parsed = null;
  try { parsed = JSON.parse(syllabi.bytes.toString('utf8')); } catch { parsed = null; }
  check('syllabi_json_bytes_equal',
        syllabi.status === 200 && syllabi.bytes.equals(syllabiFile)
        && parsed && parsed.fixture_kind === 'synthetic',
        {status: syllabi.status, fixture_kind: parsed && parsed.fixture_kind});
}

// -- the staged client over the full stack ---------------------------------- #
{
  const single = await client.searchDocuments(
    {board: 'cie', subject: '9999', year: '2024', season: 'Jun'}, {baseUrl: frontendBase});
  const ids = sorted(single.documents.map(d => d.public_id));
  const fields = single.documents.map(d => ({
    public_id: d.public_id, type: d.type, board: d.board, code: d.code, year: d.year,
    season: d.season, paper: d.paper, title: d.title,
    url: d.url, quality: d.quality,
  }));
  OBS.client_cie_single = {ids, warning: single.warning, origin: single.origin,
                           queried: single.seasons.queried, fields};
  check('client_cie_single_season',
        single.documents.length === 2 && ids.join(',') === sorted([CIE.ms, CIE.qp]).join(',')
        && single.seasons.queried.join(',') === 'Jun' && single.seasons.failed.length === 0
        && single.warning === null
        && single.documents.every(d => d.board === 'cie' && d.code === '9999'
            && d.year === '2024' && d.season === 'Jun' && d.paper === '11'
            && d.title === 'synthetic-subject' && d.availability === 'fixture'
            && [CIE.ms, CIE.qp].includes(d.public_id)
            && d.url === `${frontendBase}/api/v2/assets/${d.public_id}/content`),
        fields);

  const fanout = await client.searchDocuments(
    {board: 'cie', subject: '9999', year: '2024'}, {baseUrl: frontendBase});
  OBS.client_cie_fanout = {queried: fanout.seasons.queried, failed: fanout.seasons.failed,
                           warning: fanout.warning, n: fanout.documents.length};
  check('client_cie_fanout',
        fanout.seasons.queried.join(',') === 'Jun,Nov,Mar' && fanout.seasons.failed.length === 0
        && fanout.warning === null && fanout.documents.length === 2,
        OBS.client_cie_fanout);

  const june = await client.searchDocuments(
    {board: 'edexcel', subject: 'wma11', year: '2024', season: 'June'}, {baseUrl: frontendBase});
  OBS.client_edexcel_june = june.documents.map(d => ({public_id: d.public_id, type: d.type,
    season: d.season, paper: d.paper, title: d.title, code: d.code}));
  check('client_edexcel_single_june',
        june.documents.length === 2
        && sorted(june.documents.map(d => d.public_id)).join(',') === sorted([EDX.ms, EDX.qp]).join(',')
        && june.documents.every(d => d.board === 'edexcel' && d.code === 'wma11'
            && d.season === null && d.paper === 'wma11-01' && d.title === null),
        OBS.client_edexcel_june);

  const edxFan = await client.searchDocuments(
    {board: 'edexcel', subject: 'wma11', year: '2024'}, {baseUrl: frontendBase});
  const urls = edxFan.documents.map(d => d.url);
  const counts = new Map();
  for (const url of urls) counts.set(url, (counts.get(url) || 0) + 1);
  OBS.client_edexcel_fanout = {queried: edxFan.seasons.queried, failed: edxFan.seasons.failed,
                               warning: edxFan.warning, n: edxFan.documents.length,
                               distinct_urls: counts.size,
                               url_counts: [...counts.values()]};
  check('client_edexcel_fanout_cross_season_duplicates',
        edxFan.seasons.queried.join(',') === 'January,June,October,November'
        && edxFan.seasons.failed.length === 0 && edxFan.warning === null
        && edxFan.documents.length === 4 && counts.size === 2
        && [...counts.values()].every(c => c === 2),
        OBS.client_edexcel_fanout);
}

// -- the legacy /resources bridge ------------------------------------------- #
{
  const single = await get('/resources?board=cie&subject=9999&year=2024&season=Jun');
  const body = JSON.parse(single.bytes.toString('utf8'));
  OBS.bridge_cie_single = body;
  const rows = body.documents || [];
  const byType = Object.fromEntries(rows.map(row => [row.type, row]));
  check('bridge_cie_single_rows',
        single.status === 200 && rows.length === 2 && body.warning === '' && body.syllabus === null
        && rows.every(row => row.board === 'cie' && row.subject === '9999' && row.year === '2024'
            && row.season === 'Jun' && row.paper === '11' && row.origin === 'staged_fixture'
            && row.title === 'synthetic-subject'
            && row.url === `${frontendBase}/api/v2/assets/asset_${
              row.type === 'mark_scheme' ? 'nz3uic3wquirttazjeo4fnsi3g7esn3k'
                                         : 'umsge7vuubq3ncsz3zfe7b3golwybrmn'}/content`)
        && byType.question_paper && byType.mark_scheme,
        rows);

  const cieFan = await get('/resources?board=cie&subject=9999&year=2024');
  const cieFanBody = JSON.parse(cieFan.bytes.toString('utf8'));
  OBS.bridge_cie_fanout = {n: (cieFanBody.documents || []).length,
                           warning: cieFanBody.warning};
  check('bridge_cie_fanout_empty_seasons_ok',
        cieFan.status === 200 && (cieFanBody.documents || []).length === 2
        && cieFanBody.warning === '',
        OBS.bridge_cie_fanout);

  const edxFan = await get('/resources?board=edexcel&subject=wma11&year=2024');
  const edxFanBody = JSON.parse(edxFan.bytes.toString('utf8'));
  OBS.bridge_edexcel_fanout = {n: (edxFanBody.documents || []).length,
                               warning: edxFanBody.warning,
                               rows: edxFanBody.documents};
  check('bridge_edexcel_fanout_deduped',
        edxFan.status === 200 && (edxFanBody.documents || []).length === 2
        && edxFanBody.warning === ''
        && new Set((edxFanBody.documents || []).map(r => r.url)).size === 2
        && (edxFanBody.documents || []).every(row => row.board === 'edexcel'
            && row.season === null && row.paper === 'wma11-01' && row.title === null),
        OBS.bridge_edexcel_fanout);

  const bad = await get('/resources?board=excel&subject=9999&year=2024&season=Jun');
  const badBody = JSON.parse(bad.bytes.toString('utf8'));
  check('bridge_guard_400', bad.status === 400 && badBody.detail === '请选择科目、年份与考季',
        {status: bad.status, detail: badBody.detail});
}

// -- content bytes through the /api/v2 proxy -------------------------------- #
{
  const content = await get(`/api/v2/assets/${CIE.qp}/content`);
  OBS.content_via_proxy = {status: content.status,
                           ctype: content.headers.get('content-type'),
                           bytes: content.bytes.length,
                           sha256: sha256(content.bytes)};
  check('content_bytes_via_proxy',
        content.status === 200
        && (content.headers.get('content-type') || '').startsWith('application/pdf')
        && content.bytes.length === 817
        && sha256(content.bytes) === '6596e686e26208b79bef32ecb04561d8813da7b15419ceeb32728dd0c0420790',
        OBS.content_via_proxy);

  const info = await get('/api/v2/info');
  let infoBody = null;
  try { infoBody = JSON.parse(info.bytes.toString('utf8')); } catch { infoBody = null; }
  check('v2_info_via_proxy',
        info.status === 200 && infoBody && infoBody.schema_version === 'examdata.v2/1',
        {status: info.status, schema_version: infoBody && infoBody.schema_version});
}

// -- /gateway/ allowlist, still legacy -------------------------------------- #
{
  const denied = await get('/gateway/definitely-not-allowed');
  check('gateway_denied_404',
        denied.status === 404 && denied.bytes.length === 0,
        {status: denied.status, bytes: denied.bytes.length});

  const allowed = await get('/gateway/health');
  let body = null;
  try { body = JSON.parse(allowed.bytes.toString('utf8')); } catch { body = null; }
  OBS.gateway_allowed = {status: allowed.status,
                         ctype: allowed.headers.get('content-type'),
                         code: body && body.error && body.error.code};
  check('gateway_allowed_forwarded_to_upstream',
        allowed.status === 404 && body && body.error && body.error.code === 'route_not_found',
        OBS.gateway_allowed);
}

const failed = checks.filter(c => !c.ok).map(c => c.name);
console.log(JSON.stringify({ok: failed.length === 0, checks, observations: OBS,
                            counts: {checks: checks.length, failed: failed.length}},
                           null, 2));
process.exit(failed.length === 0 ? 0 : 1);
