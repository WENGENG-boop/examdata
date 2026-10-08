#!/usr/bin/env node
/** verify_live_evidence.mjs — 校验 live_evidence.sh 采集到的真实 HTTP 响应。
 *
 *  用法：node tools/verify_live_evidence.mjs [evidence_dir]
 *  逐条断言结构与关键计数，输出 _validation.json（passed/failed 全量清单），
 *  任一断言失败时退出码 1。校验对象是「实跑服务」落盘的真实响应，不是探活。
 */
import fs from 'node:fs';
import path from 'node:path';

const dir = process.argv[2] || path.join(path.dirname(new URL(import.meta.url).pathname), '..', 'probe', 'live_evidence');
const results = [];
function check(name, fn) {
  try {
    const detail = fn();
    results.push({ name, pass: true, detail: detail ?? null });
  } catch (e) {
    results.push({ name, pass: false, error: String((e && e.message) || e) });
  }
}
function load(name) {
  const meta = fs.readFileSync(path.join(dir, `${name}.meta.txt`), 'utf8').trim().split(/\s+/);
  const body = JSON.parse(fs.readFileSync(path.join(dir, `${name}.body.json`), 'utf8'));
  return { http: Number(meta[1]), time: Number(meta[2]), body };
}
function must(cond, msg) {
  if (!cond) throw new Error(msg);
}
function nonzero(list, msg) {
  must(Array.isArray(list) && list.length > 0, `${msg}: empty`);
}

const info = load('info');
check('info: 200 + board/schema + 6 routes', () => {
  must(info.http === 200, `http=${info.http}`);
  must(info.body.board === 'toefl', 'board');
  must(info.body.schema === 'toefl.v1', 'schema');
  must(info.body.routes.length === 6, `routes=${info.body.routes.length}`);
  return { http: info.http, time: info.time, routes: info.body.routes.length, eras: info.body.eras.length };
});

const coverage = load('coverage');
check('coverage: ok + 486 files + range 1-54', () => {
  must(coverage.http === 200, `http=${coverage.http}`);
  must(coverage.body.ok === true, 'ok');
  must(coverage.body.find_similar_files === 486, `files=${coverage.body.find_similar_files}`);
  must(coverage.body.tpo_range.min === 1 && coverage.body.tpo_range.max === 54, 'range');
  return { http: coverage.http, time: coverage.time, files: coverage.body.find_similar_files, kmf_cache_pages: coverage.body.kmf_cache_pages };
});

const setsEra = load('sets_era');
check('sets 按时间分区筛选: era=tpo-51-54 → 4 套', () => {
  must(setsEra.http === 200 && setsEra.body.ok === true, 'ok');
  const tpos = setsEra.body.sets.map((s) => s.tpo);
  must(JSON.stringify(tpos) === JSON.stringify([54, 53, 52, 51]), `tpos=${tpos}`);
  return { http: setsEra.http, time: setsEra.time, total: setsEra.body.total, tpos };
});

const setsSingle = load('sets_single');
check('sets 按编号筛选: tpo=54 → 1 套 + 4 sections', () => {
  must(setsSingle.http === 200 && setsSingle.body.ok === true, 'ok');
  must(setsSingle.body.sets.length === 1, 'len');
  const s = setsSingle.body.sets[0];
  must(s.set_id === 'tpo-54' && s.era === 'tpo-51-54', 'set_id/era');
  must(JSON.stringify(Object.keys(s.sections).sort()) === JSON.stringify(['listening', 'reading', 'speaking', 'writing']), 'sections');
  return { http: setsSingle.http, time: setsSingle.time, era: s.era };
});

const getSet = load('get_tpo30');
check('get 单套: tpo-30 reading>=3 / listening>=6 / sources 含 find-similar-tpo', () => {
  must(getSet.http === 200 && getSet.body.ok === true, 'ok');
  const s = getSet.body.set;
  must(s.set_id === 'tpo-30', 'set_id');
  must(s.sections.reading.items.length >= 3, `reading.items=${s.sections.reading.items.length}`);
  must(s.sections.listening.items.length >= 6, `listening.items=${s.sections.listening.items.length}`);
  must(s.sources.includes('find-similar-tpo'), 'sources');
  return { http: getSet.http, time: getSet.time, reading: s.sections.reading.items.length, listening: s.sections.listening.items.length, sources: s.sources };
});

const qRead = load('questions_reading');
check('questions 阅读: tpo-30 P1 → complete + >=10 题 + 答案/题型结构', () => {
  must(qRead.http === 200 && qRead.body.ok === true, 'ok');
  const s = qRead.body.set;
  must(s.complete === true, 'complete');
  must(s.fetched >= 10, `fetched=${s.fetched}`);
  must(s.questions.length === s.fetched, 'len==fetched');
  must(s.passage.length > 2000, `passage=${s.passage.length}`);
  for (const q of s.questions) {
    must(q.stem && Array.isArray(q.answer) && q.answer.length > 0, `q#${q.number} answer`);
  }
  must(s.questions.some((q) => q.type === 'insert_sentence'), 'insert_sentence');
  must(s.questions.filter((q) => (q.options || []).length >= 4).length >= 8, 'options>=4 count');
  return { http: qRead.http, time: qRead.time, fetched: s.fetched, complete: s.complete, passage_chars: s.passage.length, q1_answer: s.questions[0].answer };
});

const qList = load('questions_listening');
check('questions 听力: tpo-54 S1 → complete + >=4 题 + mp3 + 答案', () => {
  must(qList.http === 200 && qList.body.ok === true, 'ok');
  const s = qList.body.set;
  must(s.complete === true, 'complete');
  must(s.fetched >= 4, `fetched=${s.fetched}`);
  must(s.questions.some((q) => q.audio_url && q.audio_url.includes('.mp3')), 'mp3');
  for (const q of s.questions) must(q.answer, `q#${q.number} answer`);
  return { http: qList.http, time: qList.time, fetched: s.fetched, complete: s.complete, audio: s.questions.find((q) => q.audio_url)?.audio_url };
});

const search = load('search_punctuated');
check('search 检索: q=punctuated → hits>=1 + 字段完整', () => {
  must(search.http === 200 && search.body.ok === true, 'ok');
  must(search.body.total_matches >= 1, 'total_matches');
  must(search.body.returned === search.body.hits.length && search.body.hits.length >= 1, 'returned');
  for (const h of search.body.hits) must(h.source && h.url && h.snippet, 'hit fields');
  return { http: search.http, time: search.time, total_matches: search.body.total_matches, returned: search.body.returned, sources: search.body.sources_searched };
});

const health = load('ctrl_health');
check('对照组 /health: 200 + status=ok', () => {
  must(health.http === 200 && health.body.status === 'ok', 'status');
  return { http: health.http, time: health.time, papers: health.body.papers };
});
const papers = load('ctrl_papers');
check('对照组 /papers?limit=1: 200 + total>0 + items=1', () => {
  must(papers.http === 200 && papers.body.total > 0 && papers.body.items.length === 1, 'papers');
  return { http: papers.http, time: papers.time, total: papers.body.total };
});
const tax = load('ctrl_taxonomy');
check('对照组 /taxonomy: 200 结构不变', () => {
  must(tax.http === 200, `http=${tax.http}`);
  return { http: tax.http, time: tax.time };
});
const ielts = load('ctrl_ielts_info');
check('对照组 /api/v1/ielts/info: 200 + board=ielts', () => {
  must(ielts.http === 200 && ielts.body.board === 'ielts', 'board');
  return { http: ielts.http, time: ielts.time };
});

const passed = results.filter((r) => r.pass).length;
const summary = { dir, at: new Date().toISOString(), total: results.length, passed, failed: results.length - passed, results };
fs.writeFileSync(path.join(dir, '_validation.json'), JSON.stringify(summary, null, 1));
console.log(JSON.stringify({ total: summary.total, passed, failed: summary.failed, failed_names: results.filter((r) => !r.pass).map((r) => r.name) }, null, 1));
process.exit(summary.failed === 0 ? 0 : 1);
