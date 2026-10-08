#!/usr/bin/env node
/** toefl-cli.mjs — 托福聚合器命令行入口（零 npm 依赖，Node ≥18）。
 *
 *  用法（全部输出 stdout JSON；业务失败 = {ok:false,…} 且退出码 0；
 *  未知命令/参数错误 = stderr + 退出码 2）：
 *    node toefl-cli.mjs info
 *    node toefl-cli.mjs coverage
 *    node toefl-cli.mjs sets [--tpo=54] [--era=tpo-51-54] [--section=reading]
 *                            [--tpo-min=1] [--tpo-max=54] [--page=1] [--page-size=20]
 *    node toefl-cli.mjs get --set=tpo-30 [--section=reading] [--file=1-1.txt]
 *    node toefl-cli.mjs questions --set=tpo-30 --section=read|listen [--item=1]
 *                                 [--limit=3] [--refresh=1] [--url=…]
 *    node toefl-cli.mjs search --q="punctuated equilibrium" [--limit=20]
 *                              [--sources=ddy-ddy,find-similar-tpo,kmf-index,kmf-cache]
 *    node toefl-cli.mjs detail --url=<kmf 详情页> [--refresh=1]
 *    node toefl-cli.mjs jj [--section=read|listen|speak|write] [--batch=1..25] [--url=…]
 */
import fs from 'node:fs';
import {
  asInt,
  fail,
  ok,
  parseArgs,
} from './lib/util.mjs';
import {
  buildSet,
  coverageSummary,
  eras,
  hasAny,
  kmf,
  listSets,
  tpoRange,
} from './lib/catalog.mjs';
import { fetchKmfSet, KMF_BASE, KMF_PAGES_DIR } from './lib/kmf.mjs';
import {
  findSimilarIndex,
  loadFindSimilarFile,
} from './lib/sources.mjs';
import { search, SOURCE_IDS } from './lib/search.mjs';
import { fetchJjDetail, jjList, jjSummary } from './lib/jj.mjs';
import { fetchKmfDetail } from './lib/detail.mjs';

const args = parseArgs(process.argv.slice(3));
const cmd = process.argv[2];

function normTpo(v) {
  if (v === undefined || v === null || v === '') return undefined;
  const m = /(\d{1,2})/.exec(String(v));
  if (!m) return undefined;
  return Number(m[1]);
}

function normSet(v) {
  const n = normTpo(v);
  return n === undefined ? undefined : `tpo-${n}`;
}

function sectionArg() {
  const raw = args.section;
  if (raw === undefined) return undefined;
  const s = String(raw).toLowerCase();
  const map = {
    reading: 'reading', read: 'reading',
    listening: 'listening', listen: 'listening',
    speaking: 'speaking', speak: 'speaking',
    writing: 'writing', write: 'writing',
  };
  const out = map[s];
  if (!out) throw new Error(`未知 section：${raw}（可用 reading/listening/speaking/writing）`);
  return out;
}

function safeSection() {
  // 用户输入错误必须是 ok:false（退出码 0），不是异常（退出码 1/2）。
  try {
    return { ok: true, value: sectionArg() };
  } catch (e) {
    return { ok: false, error: String((e && e.message) || e) };
  }
}

function info() {
  const cov = coverageSummary();
  const range = tpoRange();
  return ok({
    name: 'TOEFL（托福 TPO / 公开第三方索引）',
    schema: 'toefl.v1',
    aggregator: 'toefl-api/toefl-cli.mjs（Node ≥18，零 npm 依赖）',
    exam_family: 'toefl',
    tpo_range: range,
    exam_forms: {
      sections: ['reading', 'listening', 'speaking', 'writing'],
      note: 'TPO 无官方逐年发布日；时间维度用编号分区（eras）表达；`questions` 支持 reading/listening 逐题内容（kmf 源有题有答案）；speaking/writing 索引见 kmf-index，内容用 `detail` 抓取（speak=题干+音频；write=材料/题干文本）。',
    },
    eras: [
      ...eras().map((e) => ({ ...e, note: '编号分区，非官方年份' })),
      { id: 'pre-2023-07', note: '旧版 TOEFL iBT（阅读/听力/口语/写作 4 科）', tpo_min: range.min, tpo_max: range.max },
      { id: 'post-2023-07', note: '2023-07 改版后（独立写作→学术讨论写作；TPO 编号仍连续）', tpo_min: range.min, tpo_max: range.max },
    ],
    commands: [
      { cmd: 'info', does: '本清单' },
      { cmd: 'coverage', does: '源覆盖自检（离线；逐 TPO 计数、缺口、重复）' },
      { cmd: 'sets', does: '按时间分区/编号与考试形式筛选套次（元数据）' },
      { cmd: 'get --set=<tpo-N> [--file=1-1.txt]', does: '单套元数据视图；--file 时返回该原文文件（网络+缓存）' },
      { cmd: 'questions --set=<tpo-N> --section=read|listen [--item=1] [--limit=3]', does: '抓取该套/该 Section 的真实题目（题干/选项/答案，kmf 源）' },
      { cmd: 'search --q=… [--sources=…]', does: '关键词检索（ddy 全文/FindSimilar 缓存/kmf 索引/kmf 缓存页）' },
      { cmd: 'detail --url=<kmf 详情页> [--refresh=1]', does: '抓取任意 kmf 详情页内容（read/listen 逐题；speak 题干+音频；write 材料/题干文本；TPO 与机经通用）' },
      { cmd: 'jj [--section=read|listen|speak|write] [--batch=1..25] [--free=1] [--locked=1] [--page=] [--page-size=]', does: '机经真题板块索引（325 条，含免费/锁定标记）；--url=<详情页> 抓取内容' },
    ],
    sources: [
      { id: 'kmf', name: '考满分 toefl.kmf.com', role: '索引 758 条（read/listen/speak/write）+ 逐题内容（题干/选项/答案）；robots 允许列表与详情页，1 req/s 限速', content: 'questions' },
      { id: 'kmf-jj', name: '考满分机经真题板块 /jj/order/27..30', role: '索引 325 条（read 50/listen 125/speak 100/write 50；免费 213/锁定 112）；免费条目详情并入 kmf 缓存供检索', content: 'index+questions' },
      { id: 'find-similar-tpo', name: 'SAOHPRWHG/FindSimilarTPO（GitHub）', role: 'TPO 阅读原文（156 篇）与听力原文（312 段），无题目答案', content: 'passages/transcripts' },
      { id: 'ddy-ddy', name: 'ddy-ddy/TOEFL-TPO（GitHub）', role: 'TPO 30–54 结构化阅读 72 篇（标题+段落，带 kmf 链接）', content: 'reading text' },
    ],
    coverage: cov.sources,
    per_official: cov.per_official,
    kmf_cache_dir: KMF_PAGES_DIR,
    env: {
      EXAMDATA_TOEFL_DIR: '聚合器目录（默认 <repo>/toefl-api）',
      EXAMDATA_NODE: 'node 可执行文件（默认从 PATH 找）',
      EXAMDATA_TOEFL_TIMEOUT: '所有托福路由的子进程超时（秒）',
    },
    notes: [
      '业务失败与正常响应一样是 {ok:true|false,…}；ok:false 表示该请求无法从源取到数据（不伪造 ok:true）。',
      '题目/答案来自第三方公开整理（考满分），仅供学习检索；受版权保护的原文不提交进 git，按需实时抓取并缓存到 .data/。',
    ],
  });
}

async function cmdSets() {
  const tpo = normTpo(args.tpo);
  const era = args.era === undefined ? undefined : String(args.era);
  const secRes = safeSection();
  if (!secRes.ok) return fail(secRes.error);
  const section = secRes.value;
  const tpoMin = normTpo(args['tpo-min'] ?? args.tpoMin);
  const tpoMax = normTpo(args['tpo-max'] ?? args.tpoMax);
  const page = asInt(args.page, 1);
  const pageSize = asInt(args['page-size'] ?? args.pageSize, 20);
  if (page !== undefined && (page < 1 || page > 1000)) return fail('page 需在 1–1000');
  if (pageSize !== undefined && (pageSize < 1 || pageSize > 100)) return fail('page-size 需在 1–100');
  const data = listSets({ tpo, era, section, tpoMin, tpoMax, page, pageSize });
  return ok({
    filters: { tpo: tpo ?? null, era: era ?? null, section: section ?? null, tpo_min: tpoMin ?? null, tpo_max: tpoMax ?? null },
    ...data,
    note: 'TPO 无官方发布年份，时间维度为编号分区（见 info.eras）。',
  });
}

async function cmdGet() {
  const set = normSet(args.set ?? args._[0]);
  if (!set) return fail('缺少 --set=tpo-N（例：--set=tpo-30）');
  const tpo = Number(set.split('-')[1]);
  if (args.file) {
    const r = await loadFindSimilarFile(String(args.file), { refresh: !!(args.refresh && args.refresh !== '0') });
    if (!r.ok) return fail(`读取原文失败：${r.error}`);
    return ok({ set_id: set, file: r.file, url: r.url, meta: r.meta, cached: r.cached, parsed: r.parsed });
  }
  if (!hasAny(tpo)) return fail(`未收录 TPO ${tpo}：该套在所有源中都没有条目（可用 sets 查看可用套次）`);
  const s = buildSet(tpo);
  const secRes = safeSection();
  if (!secRes.ok) return fail(secRes.error);
  const section = secRes.value;
  if (section) {
    if (!s.sections[section]) return fail(`未知 section：${section}`);
    s.sections = { [section]: s.sections[section] };
  }
  return ok({ set: s });
}

async function cmdQuestions() {
  const set = normSet(args.set ?? args._[0]);
  const secRes = safeSection();
  if (!secRes.ok) return fail(secRes.error);
  const section = secRes.value;
  if (!set) return fail('缺少 --set=tpo-N');
  if (!section || (section !== 'reading' && section !== 'listening')) {
    return fail('--section 需为 read 或 listen（speaking/writing 目前只有索引指针）');
  }
  const tpo = Number(set.split('-')[1]);
  const item = asInt(args.item, 1);
  const limit = asInt(args.limit, 0);
  const refresh = !!(args.refresh && args.refresh !== '0');

  let url = args.url ? String(args.url) : null;
  let label = null;
  if (!url) {
    const want = section === 'reading'
      ? `Official ${tpo} Passage ${item}`
      : `Official ${tpo} Set ${item}`;
    const kmfSection = section === 'reading' ? 'read' : 'listen';
    const hit = kmf().items.find(
      (x) => x.section === kmfSection && x.official === tpo && x.label === want,
    );
    if (!hit) {
      return fail(`kmf 索引中没有 ${want}；可用 get --set=${set} 查看该套可用条目`);
    }
    url = hit.url;
    label = hit.label;
  }
  const r = await fetchKmfSet({ url, section: section === 'reading' ? 'read' : 'listen', refresh, limit });
  if (!r.ok) return fail(`抓题失败：${r.error}`, { url });
  return ok({
    set_id: set,
    item,
    label: label || r.set.label,
    kmf_url: url,
    cached_pages_dir: KMF_PAGES_DIR,
    set: r.set,
  });
}

async function cmdSearch() {
  const q = args.q ?? args._[0];
  const limit = asInt(args.limit, 20);
  let sources = null;
  if (args.sources) {
    sources = String(args.sources).split(',').map((s) => s.trim()).filter(Boolean);
  }
  if (limit !== undefined && (limit < 1 || limit > 200)) return fail('limit 需在 1–200');
  const r = await search(q, { sources, limit });
  if (r.ok !== true) return fail(r.error);
  return ok(r);
}

async function cmdJj() {
  if (args.url) {
    const r = await fetchJjDetail({
      url: String(args.url),
      refresh: !!(args.refresh && args.refresh !== '0'),
    });
    if (!r.ok) return fail(`抓取机经详情失败：${r.error}`, { url: String(args.url) });
    return ok(r);
  }
  const raw = args.section;
  let section;
  if (raw !== undefined) {
    const map = {
      read: 'read', reading: 'read',
      listen: 'listen', listening: 'listen',
      speak: 'speak', speaking: 'speak',
      write: 'write', writing: 'write',
    };
    section = map[String(raw).toLowerCase()];
    if (!section) return fail(`未知 section：${raw}（可用 read/listen/speak/write）`);
  }
  const batch = asInt(args.batch, undefined);
  if (batch !== undefined && (batch < 1 || batch > 99)) return fail('batch 需在 1–99');
  const page = asInt(args.page, 1);
  const pageSize = asInt(args['page-size'] ?? args.pageSize, 50);
  if (page !== undefined && (page < 1 || page > 1000)) return fail('page 需在 1–1000');
  if (pageSize !== undefined && (pageSize < 1 || pageSize > 200)) return fail('page-size 需在 1–200');
  const free = !!(args.free && args.free !== '0');
  const locked = !!(args.locked && args.locked !== '0');
  const listMode = args.list !== undefined || section !== undefined || batch !== undefined || free || locked;
  if (!listMode) {
    return ok({
      summary: jjSummary(),
      note: '用 --section/--batch/--free/--locked 列出条目；--url=<详情页> 抓取内容（read/listen 逐题，speak/write 整页文本）。',
    });
  }
  const list = jjList({ section, batch, free, locked, page, pageSize });
  return ok({
    filters: { section: section ?? null, batch: batch ?? null, free, locked },
    ...list,
    counts: jjSummary().counts,
  });
}

async function cmdDetail() {
  const url = args.url ? String(args.url) : null;
  if (!url) return fail('缺少 --url=<kmf 详情页>（/detail/{read|listen|speak|write}/{hash}.html）');
  const r = await fetchKmfDetail({
    url,
    refresh: !!(args.refresh && args.refresh !== '0'),
  });
  if (!r.ok) return fail(`抓取详情失败：${r.error}`, { url });
  return ok(r);
}

async function cmdCoverage() {
  const cov = coverageSummary();
  const range = tpoRange();
  return ok({
    tpo_range: range,
    ...cov,
    find_similar_files: findSimilarIndex().length,
    kmf_cache_pages: (() => {
      try {
        return fs.readdirSync(KMF_PAGES_DIR).filter((f) => f.endsWith('.html')).length;
      } catch {
        return 0;
      }
    })(),
    jj_index: (() => {
      try {
        return jjSummary();
      } catch {
        return null;
      }
    })(),
  });
}

async function main() {
  switch (cmd) {
    case 'info':
      return info();
    case 'coverage':
      return cmdCoverage();
    case 'sets':
      return cmdSets();
    case 'get':
      return cmdGet();
    case 'questions':
      return cmdQuestions();
    case 'search':
      return cmdSearch();
    case 'detail':
      return cmdDetail();
    case 'jj':
      return cmdJj();
    default:
      console.error(
        `usage: node toefl-cli.mjs <info|coverage|sets|get|questions|search|detail|jj> [--key=value …]\n` +
        `  sources: ${SOURCE_IDS.join(', ')}\n  kmf base: ${KMF_BASE}`,
      );
      process.exit(2);
  }
}

main()
  .then((out) => {
    const s = JSON.stringify(out, null, 1);
    const truncated = process.stdout.isTTY && s.length > 6000;
    console.log(truncated ? s.slice(0, 6000) + `\n... [truncated, ${s.length} bytes total]` : s);
  })
  .catch((err) => {
    console.error(String((err && err.stack) || err));
    process.exit(1);
  });
