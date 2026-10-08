import { resolveSubject, subjectMatches, normalizePaper, groupPapers, subjectLabel } from '/lib/search.mjs';

/* ============ language ============ */
let lang = document.documentElement.dataset.lang === 'en' ? 'en' : 'zh';
const L = (zh, en) => (lang === 'zh' ? zh : en);
function setLang(next) {
  if (next === lang) return;
  lang = next;
  document.documentElement.dataset.lang = next;
  document.documentElement.lang = next === 'zh' ? 'zh-CN' : 'en';
  try { localStorage.setItem('xd-lang', next); } catch {}
  renderChrome();
  route();
}

/* ============ utilities ============ */
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const safeUrl = v => { try { const u = new URL(v, location.origin); return ['http:', 'https:'].includes(u.protocol) ? u.href : ''; } catch { return ''; } };
const fmt = n => n == null ? '—' : Number(n).toLocaleString(lang === 'zh' ? 'zh-CN' : 'en-US');
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const seasonName = s => ({ jun: 'June', june: 'June', nov: 'November', november: 'November', mar: 'March', march: 'March', jan: 'January', january: 'January', oct: 'October', october: 'October' }[String(s || '').toLowerCase()] || s || '—');
const seasonZh = s => ({ June: '夏季', November: '冬季', March: '春季', January: '一月', October: '十月' }[seasonName(s)] || '');
const seasonLabel = s => L(`${seasonName(s)} · ${seasonZh(s)}`, seasonName(s));
const boardName = b => (b === 'edexcel' ? 'Edexcel' : 'Cambridge');
const subjName = s => (lang === 'zh' ? subjectLabel(s) : s.title);
const docMeta = () => ({
  question_paper: ['qp', 'QP', L('试卷', 'Question paper')], mark_scheme: ['ms', 'MS', L('评分标准', 'Mark scheme')],
  examiner_report: ['er', 'ER', L('考官报告', 'Examiner report')], grade_threshold: ['gt', 'GT', L('分数线', 'Grade thresholds')],
});
async function getJson(url) {
  const r = await fetch(url);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = body.detail;
    const err = new Error(typeof d === 'string' ? d : d?.message || L(`请求失败（HTTP ${r.status}）`, `Request failed (HTTP ${r.status})`));
    err.status = r.status; err.detail = d; throw err;
  }
  return body;
}
const icon = {
  doc: '<svg viewBox="0 0 24 24"><path d="M6 3h8l4 4v14H6zM14 3v4h4M9 12h6M9 16h4"/></svg>',
  q: '<svg viewBox="0 0 24 24"><path d="M5 5h14v10H9l-4 4z"/><path d="M9 9h6M9 12h3"/></svg>',
  cal: '<svg viewBox="0 0 24 24"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/></svg>',
  home: '<svg viewBox="0 0 24 24"><path d="M4 11 12 4l8 7v9h-5v-6H9v6H4z"/></svg>',
  book: '<svg viewBox="0 0 24 24"><path d="M5 4h9a4 4 0 0 1 4 4v12H9a4 4 0 0 1-4-4z"/><path d="M5 16a4 4 0 0 1 4-4h9"/></svg>',
  arrow: '<svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
  ext: '<svg viewBox="0 0 24 24"><path d="M7 17 17 7M9 7h8v8"/></svg>',
  info: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>',
  search: '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/></svg>',
  hash: '<svg viewBox="0 0 24 24"><path d="M5 9h14M5 15h14M10 4 8 20M16 4l-2 16"/></svg>',
  board: '<svg viewBox="0 0 24 24"><path d="M4 20h16M6 20V10M10 20V10M14 20V10M18 20V10M3 10l9-6 9 6z"/></svg>',
  layers: '<svg viewBox="0 0 24 24"><path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/></svg>',
  clock: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>',
  dl: '<svg viewBox="0 0 24 24"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg>',
  tag: '<svg viewBox="0 0 24 24"><path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.5" cy="8.5" r="1.2"/></svg>',
  chev: '<svg viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg>',
  sun: '<svg class="sun" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
  moon: '<svg class="moon" viewBox="0 0 24 24"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>',
};
const glyphEmpty = (title, text, extra = '', ic = icon.search) => `<div class="empty"><div class="glyph">${ic}</div><h3>${esc(title)}</h3><p>${esc(text)}</p>${extra}</div>`;
const skeleton = (n = 6) => `<div class="skeleton">${'<i></i>'.repeat(n)}</div>`;
const pageHead = (n, kicker, title, lede, meta = '') => `<header class="page-head"><div><p class="kicker"><i></i><span class="n">${n}</span> — ${kicker}</p><h1 class="title">${title}</h1><p class="lede">${lede}</p></div>${meta ? `<div class="head-meta">${meta}</div>` : ''}</header>`;

/* ============ shared data ============ */
const store = { catalog: [], cieSubjects: [], edexcelSubjects: [], syllabi: null, stats: null, seasons: null };
const ready = (async () => {
  const [catalog, syllabi] = await Promise.all([getJson('/data/catalog.json'), getJson('/data/syllabi.json').catch(() => null)]);
  store.catalog = catalog.items;
  store.snapshot = catalog.snapshot_date;
  store.edexcelSubjects = catalog.edexcelSubjects || [];
  store.cieSubjects = [...new Map(catalog.items.map(r => [r.code, { code: r.code, title: r.title, qualification: r.qualification || '' }])).values()].sort((a, b) => a.title.localeCompare(b.title));
  store.syllabi = syllabi;
})();
const subjectsFor = board => (board === 'edexcel' ? store.edexcelSubjects : board === 'all' ? store.cieSubjects.concat(store.edexcelSubjects) : store.cieSubjects);
const subjectByCode = (board, code) => subjectsFor(board).find(s => s.code === code);
function syllabusFor(board, code) {
  const table = store.syllabi && (board === 'edexcel' ? store.syllabi.edexcel : store.syllabi.cie);
  const e = table && table[code];
  return e ? { title: e.title || code, page: e.page || '', syllabuses: e.syllabuses || [] } : null;
}
function paintStatus() {
  const el = $('#backend-status'); if (!el) return;
  const s = store.stats;
  el.className = 'status ' + (s ? (s.backend ? 'ok' : 'down') : '');
  el.lastElementChild.textContent = !s ? L('连接中', 'Connecting') : s.backend ? L('数据服务在线', 'Service online') : L('数据服务离线', 'Service offline');
}
function loadStats() {
  return getJson('/api/stats').then(s => { store.stats = s; paintStatus(); return s; })
    .catch(() => { store.stats = { backend: false }; paintStatus(); return null; });
}

/* ============ chrome ============ */
const NAV = () => [['home', '#/', icon.home, L('概览', 'Overview')], ['papers', '#/papers', icon.doc, L('试卷', 'Papers')], ['questions', '#/questions', icon.q, L('题库', 'Questions')], ['timetable', '#/timetable', icon.cal, L('时间表', 'Timetable')]];
const langSwitch = () => `<button type="button" data-lang="zh" aria-pressed="${lang === 'zh'}">中</button><button type="button" data-lang="en" aria-pressed="${lang === 'en'}">EN</button>`;
function renderChrome() {
  $('#sidebar').innerHTML = `
    <a class="workspace" href="#/"><span class="logo"><svg viewBox="0 0 24 24"><path d="M7 5h10M7 12h7M7 19h10M7 5v14"/></svg></span><span class="workspace-name">Examdata</span><span class="workspace-ver">v2</span></a>
    <button class="side-search" type="button" data-palette>${icon.search}<span>${L('搜索', 'Search')}</span><kbd>Ctrl K</kbd></button>
    <p class="side-label">${L('页面', 'Pages')}</p>
    <nav class="side-nav">${NAV().map(([r, h, ic, t], i) => `<a href="${h}" data-route="${r}"><span class="idx">0${i + 1}</span>${t}</a>`).join('')}</nav>
    <div class="side-group"><p class="side-label">${L('数据源', 'Sources')}</p>
      <a class="side-source" href="#/papers?board=cie"><b>CIE</b>Cambridge International</a>
      <a class="side-source" href="#/papers?board=edexcel"><b>EDX</b>Pearson Edexcel IAL</a></div>
    <div class="side-foot">
      <div class="side-row"><div class="lang-switch" data-lang-switch>${langSwitch()}</div><button class="icon-btn" id="theme-toggle" type="button" aria-label="${L('切换主题', 'Toggle theme')}">${icon.sun}${icon.moon}</button></div>
      <span class="status" id="backend-status"><i></i><span></span></span>
    </div>`;
  $$('[data-lang-switch]').forEach(el => { el.innerHTML = langSwitch(); });
  $('#palette-input').placeholder = L('搜索科目、题目关键词，或输入题目编号…', 'Search subjects, question text, or a question ID…');
  $('#palette-foot').innerHTML = `<span><kbd>↑</kbd><kbd>↓</kbd> ${L('选择', 'Navigate')}</span><span><kbd>Enter</kbd> ${L('打开', 'Open')}</span><span><kbd>Esc</kbd> ${L('关闭', 'Close')}</span>`;
  $('#theme-toggle').addEventListener('click', toggleTheme);
  paintStatus();
  const r = parseHash();
  $$('.side-nav a').forEach(a => a.classList.toggle('active', a.dataset.route === r.name));
}
document.addEventListener('click', e => {
  const l = e.target.closest('[data-lang]'); if (l && l.closest('[data-lang-switch]')) setLang(l.dataset.lang);
  if (e.target.closest('[data-palette]')) paletteOpen();
  if (e.target.closest('[data-replay]')) playIntro(true);
});
function toggleTheme() {
  const dark = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  const next = dark ? 'light' : 'dark';
  const apply = () => { document.documentElement.dataset.theme = next; try { localStorage.setItem('xd-theme', next); } catch {} };
  document.startViewTransition && !reduced() ? document.startViewTransition(apply) : apply();
}

/* ============ router ============ */
const routes = { home: viewHome, papers: viewPapers, questions: viewQuestions, timetable: viewTimetable };
const titleOf = name => ({ home: L('概览', 'Overview'), papers: L('试卷', 'Papers'), questions: L('题库', 'Questions'), timetable: L('时间表', 'Timetable') }[name]);
function parseHash() {
  const raw = location.hash.replace(/^#\/?/, '');
  const [path, query = ''] = raw.split('?');
  const [name, arg] = path.split('/');
  return { name: routes[name] ? name : (name === 'q' ? 'questions' : 'home'), arg: name === 'q' ? arg : null, params: Object.fromEntries(new URLSearchParams(query)) };
}
// push=true records an explicit search so the back button steps through searches.
function setQuery(name, params, push = false) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v != null && v !== false)).toString();
  const url = `#/${name}${qs ? '?' + qs : ''}`;
  if (url === location.hash) return;
  history[push ? 'pushState' : 'replaceState'](null, '', url);
}
const seasonParam = (board, s) => { const n = seasonName(s); return board === 'edexcel' ? n : ({ June: 'Jun', November: 'Nov', March: 'Mar' }[n] || ''); };
function crumbs(parts) {
  $('#crumbs').innerHTML = [`<a href="#/">Examdata</a>`, ...parts.map((p, i) => i === parts.length - 1 ? `<span class="current">${esc(p.label)}</span>` : `<a href="${p.href}">${esc(p.label)}</a>`)].join('<span class="sep">/</span>');
}
let cleanup = null;
async function route() {
  const r = parseHash();
  $$('.side-nav a').forEach(a => a.classList.toggle('active', a.dataset.route === r.name));
  if ($('#sidebar').classList.contains('open')) toggleDrawer(false);
  if (cleanup) { cleanup(); cleanup = null; }
  const page = $('#page');
  page.className = 'page';
  void page.offsetWidth;
  page.classList.add('view-enter');
  crumbs(r.name === 'home' ? [] : [{ label: titleOf(r.name) }]);
  document.title = r.name === 'home' ? 'Examdata' : `${titleOf(r.name)} · Examdata`;
  scrollTo({ top: 0 });
  await ready.catch(() => {});
  cleanup = await routes[r.name](page, r.params, r.arg) || null;
  if (r.arg) openQuestion(r.arg);
  else if (lastPeek && $('#peek').classList.contains('open')) openQuestion(lastPeek);
}
addEventListener('hashchange', route);
addEventListener('scroll', () => $('.topbar').classList.toggle('scrolled', scrollY > 8), { passive: true });

/* ============ home ============ */
async function viewHome(page) {
  page.classList.add('home');
  const lines = L(['每一份试卷，', '每一道题，', '<em>一个安静的索引</em><span class="dot">。</span>'], ['Every paper,', 'every question,', '<em>one quiet index</em><span class="dot">.</span>']);
  const cieTick = store.cieSubjects.filter(s => /^9\d{3}$/.test(s.code)).slice(0, 24);
  const edxTick = store.edexcelSubjects.filter(s => !/ial27|ial26/.test(s.code));
  const ticker = cieTick.flatMap((s, i) => [['cie', s], ...(edxTick[i] ? [['edexcel', edxTick[i]]] : [])]);
  const tickerHtml = ticker.map(([b, s]) => `<a href="#/papers?board=${b}&subject=${encodeURIComponent(s.code)}"><b>${esc(s.code)}</b>${esc(subjName(s))}</a>`).join('');
  page.innerHTML = `
  <section class="hero">
    <canvas aria-hidden="true"></canvas>
    <div class="hero-guides" aria-hidden="true"><i></i><i></i></div>
    <div class="hero-grid">
      <div>
        <p class="kicker"><i></i>Examdata — ${L('统一考试数据索引', 'A unified exam data index')}</p>
        <h1 class="display">${lines.map(l => `<span class="line"><span>${l}</span></span>`).join('')}</h1>
        <p class="hero-sub">${L('Cambridge 与 Pearson Edexcel 的原始试卷、评分标准、考官报告与分数线；四万余道已解析题目；逐场次的官方考试时间表。', 'Original papers, mark schemes, examiner reports and grade thresholds from Cambridge and Pearson Edexcel — forty-thousand parsed questions and every official exam session, in one place.')}</p>
        <div class="actions">
          <a class="btn primary" href="#/papers">${L('查找试卷', 'Find papers')}<span class="arrow">${icon.arrow}</span></a>
          <a class="btn" href="#/questions">${L('搜索题目', 'Search questions')}</a>
          <span class="hint"><kbd>Ctrl</kbd><kbd>K</kbd>${L('随处搜索', 'anywhere')}</span>
        </div>
      </div>
      <div class="console" id="console">
        <div class="console-bar"><i></i><i></i><i></i><span>examdata — /api/v1/search</span><b id="console-state">LIVE</b></div>
        <div class="console-body" id="console-body"></div>
      </div>
    </div>
  </section>
  <div class="marquee" aria-label="${L('科目', 'Subjects')}"><div class="marquee-track">${tickerHtml}${tickerHtml.replace(/<a /g, '<a tabindex="-1" aria-hidden="true" ')}</div></div>
  <section class="home-section">
    <div class="section-head"><h2>${L('数据规模', 'By the numbers')}</h2><span class="db-meta" id="fig-meta">${L('实时读取', 'Live')}</span></div>
    <div class="figures" id="figures">
      ${[[L('题目', 'Questions'), '01'], [L('已解析试卷', 'Parsed papers'), '02'], [L('目录文件', 'Catalogue files'), '03'], [L('官方考纲', 'Syllabi'), '04']].map(([k, n]) => `<div class="figure"><div class="k"><span>${k}</span><span>${n}</span></div><div class="v">—</div><div class="s">&nbsp;</div></div>`).join('')}
    </div>
    <div class="section-head"><h2>${L('目录', 'Index')}</h2><span class="db-meta">04 ${L('个模块', 'modules')}</span></div>
    <div class="index-list">
      ${indexRow('01', '#/papers', L('试卷', 'Papers'), L('按科目、年份与考季取得 QP / MS / ER / GT 原件，附官方考纲。', 'Original QP / MS / ER / GT by subject, year and series — with the official syllabus.'), 'CIE · EDEXCEL')}
      ${indexRow('02', '#/questions', L('题库', 'Questions'), L('跨考试局检索题干，查看评分要点、知识点与所属原卷。', 'Search question text across boards; see mark schemes, topics and the source paper.'), 'FULL-TEXT')}
      ${indexRow('03', '#/timetable', L('时间表', 'Timetable'), L('CIE Zone 5 与 Edexcel IAL 逐日考试安排，日历热力一览。', 'Day-by-day sessions for CIE Zone 5 and Edexcel IAL, at a glance.'), 'ZONE 5 · IAL')}
      ${indexRow('04', '#/papers?board=cie&subject=9709', L('考纲', 'Syllabi'), L('每个科目的官方 Syllabus / Specification，查询科目时自动附上。', 'Official syllabus or specification for every subject, attached to each lookup.'), 'SYLLABUS')}
    </div>
    <div class="footnote"><span class="mono">NOTE</span><p>${L('目录收录不代表全卷已解析；答案关联率与标签覆盖率不等于逐题人工核验。来源未提供的文件会如实标注，不生成替代链接。', 'A catalogue entry does not mean the paper is fully parsed; answer-link and tag coverage are not per-question human verification. Files the source does not provide are labelled as such — never substituted.')}</p></div>
    <div class="colophon"><span>EXAMDATA WEB v2</span><span>CAMBRIDGE INTERNATIONAL · PEARSON EDEXCEL</span><button class="replay" type="button" data-replay>${L('重播开场 ↺', 'Replay intro ↺')}</button></div>
  </section>`;
  const stopDots = dotField($('.hero canvas', page), $('.hero', page));
  const stopConsole = liveConsole($('#console-body', page));
  (async () => {
    const s = (store.stats && store.stats.catalog) ? store.stats : await loadStats();
    if (!s || !page.isConnected || !s.catalog) return;
    const cells = $$('#figures .figure', page);
    const cam = s.questions?.byBoard?.cambridge || 0, edx = s.questions?.byBoard?.edexcel || 0;
    fillFigure(cells[0], s.questions?.total, s.questions ? '' : L('数据服务离线', 'Service offline'), s.questions ? [cam, edx] : null);
    fillFigure(cells[1], s.papers, s.backend ? L('后端数据库收录的试卷', 'Papers in the backend database') : L('数据服务离线', 'Service offline'));
    fillFigure(cells[2], s.catalog.files, L(`CIE ${s.catalog.subjects} 科 · 快照 ${s.catalog.snapshot}`, `${s.catalog.subjects} CIE subjects · snapshot ${s.catalog.snapshot}`));
    fillFigure(cells[3], s.syllabi.cie + s.syllabi.edexcel, L(`另有 ${s.timetable.cie + s.timetable.edexcel} 个考季的时间表`, `plus ${s.timetable.cie + s.timetable.edexcel} timetable series`));
  })();
  return () => { stopDots(); stopConsole(); };
}
function indexRow(n, href, title, text, meta) {
  return `<a class="index-row" href="${href}"><span class="n">${n}</span><h3>${title}</h3><p>${text}</p><span class="meta">${meta}</span><span class="go">${icon.arrow}</span></a>`;
}
function fillFigure(cell, value, sub, split) {
  const v = $('.v', cell);
  $('.s', cell).textContent = sub || ' ';
  if (split) {
    const sum = split[0] + split[1] || 1;
    $('.s', cell).insertAdjacentHTML('afterend', `<div class="bar"><i></i><i></i></div><div class="legend"><span>CIE ${fmt(split[0])}</span><span>EDX ${fmt(split[1])}</span></div>`);
    requestAnimationFrame(() => requestAnimationFrame(() => { const [a, b] = $$('.bar i', cell); a.style.width = `${Math.max(split[0] / sum * 100, 1.5)}%`; b.style.width = `${split[1] / sum * 100}%`; }));
  }
  if (value == null) { v.textContent = '—'; return; }
  if (reduced()) { v.textContent = fmt(value); return; }
  const start = performance.now(), dur = 1400;
  const tick = now => { const t = Math.min((now - start) / dur, 1), e = 1 - Math.pow(1 - t, 5); v.textContent = fmt(Math.round(value * e)); if (t < 1 && cell.isConnected) requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
}

/* Cursor-reactive dot matrix behind the hero. */
function dotField(canvas, host) {
  const ctx = canvas.getContext('2d');
  let w = 0, h = 0, raf = 0, mx = -1e4, my = -1e4, tx = -1e4, ty = -1e4, visible = true, alive = true;
  const gap = 22;
  const resize = () => { const r = host.getBoundingClientRect(), d = Math.min(devicePixelRatio || 1, 2); w = r.width; h = r.height; canvas.width = w * d; canvas.height = h * d; ctx.setTransform(d, 0, 0, d, 0, 0); };
  const move = e => { const r = canvas.getBoundingClientRect(); tx = e.clientX - r.left; ty = e.clientY - r.top; };
  const leave = () => { tx = -1e4; ty = -1e4; };
  const draw = t => {
    if (!alive) return;
    const css = getComputedStyle(document.documentElement);
    const dot = css.getPropertyValue('--dot').trim(), sig = css.getPropertyValue('--signal').trim();
    mx += (tx - mx) * .12; my += (ty - my) * .12;
    ctx.clearRect(0, 0, w, h);
    for (let y = gap / 2; y < h; y += gap) for (let x = gap / 2; x < w; x += gap) {
      const d = Math.hypot(x - mx, y - my), k = Math.max(0, 1 - d / 170);
      const wave = Math.sin(x * .018 + y * .012 + t * .0011) * .5 + .5;
      const s = 1 + wave * .7 + k * k * 3.2;
      const ox = k ? (x - mx) / (d || 1) * k * 7 : 0, oy = k ? (y - my) / (d || 1) * k * 7 : 0;
      ctx.fillStyle = k > .72 ? sig : dot;
      ctx.globalAlpha = .55 + k * .45;
      ctx.fillRect(x + ox - s / 2, y + oy - s / 2, s, s);
    }
    ctx.globalAlpha = 1;
    if (!reduced() && visible) raf = requestAnimationFrame(draw);
  };
  const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible && alive) { cancelAnimationFrame(raf); raf = requestAnimationFrame(draw); } });
  resize(); io.observe(host);
  addEventListener('resize', resize); host.addEventListener('pointermove', move); host.addEventListener('pointerleave', leave);
  raf = requestAnimationFrame(draw);
  return () => { alive = false; cancelAnimationFrame(raf); io.disconnect(); removeEventListener('resize', resize); };
}

/* Typed, real queries against the search API. */
function liveConsole(body) {
  let alive = true;
  const words = ['probability', 'triangle', 'elasticity', 'titration', 'gradient', 'enzyme', 'velocity', 'equilibrium'];
  (async () => {
    for (let i = 0; alive; i++) {
      const kw = words[i % words.length];
      // Alternate boards so both Cambridge and Edexcel questions surface.
      const board = i % 2 ? 'cie' : 'edexcel';
      const path = `/api/v1/search?board=${board}&keyword=${kw}&leaves_only=true&limit=3`;
      body.innerHTML = `<div class="c-line"><span class="c-prompt">❯</span> <span class="c-method">GET</span> <span class="c-path" id="c-typed"></span><span class="c-caret"></span></div>`;
      const typed = $('#c-typed', body);
      const html = `/api/v1/search?board=${board}&amp;keyword=<span class="c-kw">${kw}</span>&amp;leaves_only=true&amp;limit=3`;
      for (let c = 1; c <= path.length && alive; c++) {
        const shown = path.slice(0, c), at = shown.indexOf(kw);
        typed.innerHTML = at < 0 ? esc(shown) : esc(shown.slice(0, at)) + `<span class="c-kw">${esc(shown.slice(at, at + kw.length))}</span>` + esc(shown.slice(at + kw.length));
        await sleep(reduced() ? 0 : 18 + Math.random() * 22);
      }
      if (!alive) return;
      typed.innerHTML = html;
      $('.c-caret', body)?.remove();
      const t0 = performance.now();
      let data = null;
      try { data = await getJson('/gateway' + path); } catch {}
      if (!alive) return;
      const ms = Math.round(performance.now() - t0);
      const state = $('#console-state');
      if (!data) {
        state?.classList.add('off');
        body.insertAdjacentHTML('beforeend', `<div class="c-line"><span class="c-err">✕ ${L('数据服务离线', 'service offline')}</span> <span class="c-dim">· EXAMDATA_URL</span></div>`);
        await sleep(6000); continue;
      }
      state?.classList.remove('off');
      body.insertAdjacentHTML('beforeend', `<div class="c-line"><span class="c-ok">200</span> <span class="c-dim">·</span> ${fmt(data.total)} ${L('条匹配', 'matches')} <span class="c-dim">· ${ms}ms · cie ${fmt(data.by_board?.cambridge)} / edx ${fmt(data.by_board?.edexcel)}</span></div>`);
      const re = new RegExp(kw, 'gi');
      data.items.forEach((q, j) => {
        const stem = (q.stem_text || '').replace(/\.{4,}/g, '…').replace(/\s+/g, ' ').trim();
        body.insertAdjacentHTML('beforeend', `<button class="c-result" style="animation-delay:${.12 + j * .14}s" data-open="${q.question_id}"><span class="c-id"><b>${esc(q.subject_code)}</b>${esc(q.year || '')} · ${esc(q.paper_code || '')} · Q${esc(q.number_path)}</span><span class="c-stem">${esc(stem).replace(re, m => `<mark>${m}</mark>`)}</span></button>`);
      });
      await sleep(5200);
    }
  })();
  body.addEventListener('click', e => { const b = e.target.closest('[data-open]'); if (b) openQuestion(b.dataset.open); });
  return () => { alive = false; };
}

/* ============ subject combobox ============ */
function combobox(input, list, getBoard, onPick) {
  let active = -1;
  const render = () => {
    const items = subjectMatches(subjectsFor(getBoard()), input.value).slice(0, 60);
    list.innerHTML = items.map((s, i) => `<button type="button" class="combo-item" role="option" aria-selected="false" data-code="${esc(s.code)}" id="${list.id}-${i}"><span>${esc(subjName(s))}</span><small>${esc(s.qualification || '')}</small><code>${esc(s.code)}</code></button>`).join('') || `<div class="combo-empty">${L('没有匹配的科目，可直接输入四位代码。', 'No match — you can type a 4-digit code directly.')}</div>`;
    list.hidden = false; active = -1; input.setAttribute('aria-expanded', 'true');
  };
  const close = () => { list.hidden = true; input.setAttribute('aria-expanded', 'false'); };
  const label = code => { const s = subjectByCode(getBoard(), code); return s ? `${subjName(s)} · ${s.code}` : (code || ''); };
  const pick = code => { input.value = label(code); close(); onPick?.(code); };
  input.addEventListener('focus', render);
  input.addEventListener('input', render);
  input.addEventListener('blur', () => setTimeout(close, 120));
  list.addEventListener('pointerdown', e => e.preventDefault());
  list.addEventListener('click', e => { const b = e.target.closest('[data-code]'); if (b) pick(b.dataset.code); });
  input.addEventListener('keydown', e => {
    const opts = $$('[role=option]', list);
    if (e.key === 'Escape') return close();
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault(); if (list.hidden) render(); const o = $$('[role=option]', list); if (!o.length) return;
      active = (active + (e.key === 'ArrowDown' ? 1 : -1) + o.length) % o.length;
      o.forEach((x, i) => x.setAttribute('aria-selected', String(i === active)));
      o[active].scrollIntoView({ block: 'nearest' });
    }
    if (e.key === 'Enter' && !list.hidden && opts[active]) { e.preventDefault(); pick(opts[active].dataset.code); }
  });
  return { set: code => { input.value = label(code); } };
}

/* ============ papers ============ */
const SEASONS = { cie: ['Jun', 'Nov', 'Mar'], edexcel: ['January', 'June', 'October', 'November'] };
const DEFAULT_YEAR = String(new Date().getFullYear() - 1);
async function viewPapers(page, params) {
  page.classList.add('wide');
  const st = { board: params.board === 'edexcel' ? 'edexcel' : 'cie', subject: params.subject || '', year: params.year || '', season: params.season || '', paper: params.paper || '' };
  const years = Array.from({ length: 27 }, (_, i) => String(2026 - i));
  page.innerHTML = `
    ${pageHead('02', L('试卷检索', 'Paper lookup'), L('试卷', 'Papers'), L('选择科目与年份，直接取得官方原件。卷号与考季可留空——留空时汇总全年各考季。', 'Pick a subject and year to get the original files. Leave series and paper blank to gather the whole year.'), `<b>QP</b> · <b>MS</b> · <b>ER</b> · <b>GT</b><br>${L('官方来源 · 实时', 'Official sources · live')}`)}
    <form class="props" id="pf" autocomplete="off">
      <div class="prop-key">${icon.board}${L('考试局', 'Board')}</div>
      <div class="prop-val"><div class="seg" id="board-seg"><button type="button" data-v="cie">Cambridge</button><button type="button" data-v="edexcel">Edexcel IAL</button></div></div>
      <div class="prop-key">${icon.book}${L('科目', 'Subject')}</div>
      <div class="prop-val"><div class="field"><input class="input wide" id="subject" placeholder="${L('中文、英文或代码，如 数学 / 9709', 'Name or code, e.g. Mathematics / 9709')}" role="combobox" aria-expanded="false" aria-controls="subject-list"><div class="combo-list" id="subject-list" role="listbox" hidden></div></div></div>
      <div class="prop-key">${icon.cal}${L('年份 / 考季', 'Year / Series')}</div>
      <div class="prop-val"><select class="select" id="year"><option value="">${L('选择年份', 'Year')}</option>${years.map(y => `<option>${y}</option>`).join('')}</select><select class="select" id="season"></select></div>
      <div class="prop-key">${icon.hash}${L('卷号', 'Paper')}</div>
      <div class="prop-val"><input class="input" id="paper" placeholder="${L('选填，如 11 / wec11-01', 'Optional, e.g. 11 / wec11-01')}" style="width:220px"></div>
      <div class="bare"></div>
      <div class="prop-val bare" style="padding-top:16px"><button class="btn primary" id="go" type="submit">${L('查询', 'Search')}<span class="arrow">${icon.arrow}</span></button><button class="btn" type="button" id="reset">${L('重置', 'Reset')}</button></div>
    </form>
    <div id="out"></div>`;
  const f = { subject: $('#subject', page), year: $('#year', page), season: $('#season', page), paper: $('#paper', page), go: $('#go', page) };
  const combo = combobox(f.subject, $('#subject-list', page), () => st.board);
  const setBoard = b => {
    st.board = b;
    $$('#board-seg button', page).forEach(x => x.setAttribute('aria-pressed', String(x.dataset.v === b)));
    f.season.innerHTML = `<option value="">${L('所有考季', 'All series')}</option>` + SEASONS[b].map(s => `<option value="${s}">${seasonLabel(s)}</option>`).join('');
  };
  setBoard(st.board);
  combo.set(st.subject); f.year.value = st.year; f.season.value = SEASONS[st.board].includes(st.season) ? st.season : ''; f.paper.value = st.paper;
  $('#board-seg', page).addEventListener('click', e => { const b = e.target.closest('button'); if (!b || b.dataset.v === st.board) return; setBoard(b.dataset.v); f.subject.value = ''; f.paper.value = ''; run(true); });
  $('#reset', page).addEventListener('click', () => { f.subject.value = ''; f.year.value = ''; f.season.value = ''; f.paper.value = ''; run(true); });
  $('#pf', page).addEventListener('submit', e => { e.preventDefault(); run(true); });
  const out = $('#out', page);
  let req = 0;

  function run(push = false) {
    const id = ++req;
    const raw = f.subject.value.trim();
    const resolved = raw ? resolveSubject(subjectsFor(st.board), raw, st.board) : { code: null, matches: [] };
    Object.assign(st, { subject: resolved.code || '', year: f.year.value, season: f.season.value, paper: normalizePaper(f.paper.value, st.board) });
    if (st.subject && !st.year) { st.year = DEFAULT_YEAR; f.year.value = DEFAULT_YEAR; }
    setQuery('papers', { board: st.board, subject: st.subject, year: st.year, season: st.season, paper: st.paper }, push);
    crumbs([{ label: L('试卷', 'Papers'), href: '#/papers' }, ...(st.subject ? [{ label: st.subject }] : [])]);
    if (raw && !resolved.code) return renderChoices(raw, resolved.matches);
    if (st.subject && st.year) return live(id);
    if (st.board === 'edexcel') return edexcelDirectory();
    cieDirectory();
  }
  const pickSubject = code => { combo.set(code); if (!f.year.value) f.year.value = DEFAULT_YEAR; run(true); scrollTo({ top: 0, behavior: reduced() ? 'auto' : 'smooth' }); };
  function cieDirectory() {
    // A subject without a year searches the latest complete year (see run()).
    const levels = [['A Level', L('AS 与 A Level', 'AS & A Level')], ['IGCSE', 'IGCSE'], ['O Level', 'O Level']];
    const subs = store.cieSubjects;
    out.innerHTML = `
      <div class="db-head"><div class="db-title">${L('Cambridge 科目', 'Cambridge subjects')}<span class="mono">${subs.length} ${L('门课程', 'COURSES')}</span></div>
        <div class="actions"><input class="input dir-filter" id="dir-filter" placeholder="${L('筛选科目…', 'Filter subjects…')}"><button class="btn small" id="browse-catalog" type="button">${L(`目录快照 · ${fmt(store.catalog.length)} 份`, `Catalogue · ${fmt(store.catalog.length)} files`)}</button></div></div>
      ${levels.map(([q, name], gi) => { const list = subs.filter(s => s.qualification === q); return list.length ? `<section class="dir-level"><h3 class="dir-h"><span>0${gi + 1}</span>${name}<small>${list.length}</small></h3><div class="dir-compact">${list.map(s => `<button class="dir-row" data-cie="${esc(s.code)}" data-q="${esc((s.code + ' ' + subjectLabel(s)).toLowerCase())}"><code>${esc(s.code)}</code><span>${esc(subjName(s))}</span></button>`).join('')}</div></section>` : ''; }).join('')}
      <p class="notice">${L(`选择科目后实时查询 ${DEFAULT_YEAR} 年全部考季（March / June / November）。列表来自 ${store.snapshot} 官方目录快照，可直接输入其他四位科目代码。`, `Pick a subject to query every ${DEFAULT_YEAR} series live (March / June / November). The list comes from the ${store.snapshot} catalogue snapshot — any other 4-digit code also works.`)}</p>`;
    $$('[data-cie]', out).forEach(b => b.addEventListener('click', () => pickSubject(b.dataset.cie)));
    $('#browse-catalog', out).addEventListener('click', browseCatalog);
    $('#dir-filter', out).addEventListener('input', e => {
      const t = e.target.value.trim().toLowerCase();
      $$('.dir-row', out).forEach(r => { r.hidden = !!t && !r.dataset.q.includes(t); });
      $$('.dir-level', out).forEach(sec => { sec.hidden = !$$('.dir-row', sec).some(r => !r.hidden); });
    });
  }
  function edexcelDirectory() {
    const groups = [
      [L('数学与科学', 'Maths & sciences'), /math|biology|chemistry|physics|computer|-it$/],
      [L('商科与社会科学', 'Business & social sciences'), /economics|business|accounting|psychology|law|geography|history/],
      [L('语言与文学', 'Languages & literature'), /eng|german|greek|french|spanish|arabic/],
    ];
    const subs = store.edexcelSubjects;
    const spec = s => (s.title.match(/\((\d{4})\)/) || [])[1] || '';
    const item = s => {
      const y = spec(s), fresh = Number(y) >= 2026;
      return `<button class="dir-item" data-edx="${esc(s.code)}"><span class="dir-name">${esc(subjName(s).replace(/\s*\(\d{4}\)/, ''))}</span><span class="dir-meta">${y ? `${L('规格', 'Spec')} ${y}` : L('旧版', 'Legacy')}${fresh ? ` · <em>${L('新课程', 'New')}</em>` : ''}</span><span class="dir-code">${esc(s.code)}</span><span class="dir-go">${icon.arrow}</span></button>`;
    };
    out.innerHTML = `
      <div class="db-head"><div class="db-title">${L('Edexcel IAL 科目', 'Edexcel IAL subjects')}<span class="mono">${subs.length} ${L('门课程', 'COURSES')}</span></div><div class="db-meta">${L(`选择课程，实时查询 ${DEFAULT_YEAR} 年全部考季`, `Pick a course to query every ${DEFAULT_YEAR} series live`)}</div></div>
      <div class="dir">${groups.map(([name, re], gi) => `<section class="dir-col"><h3 class="dir-h"><span>0${gi + 1}</span>${name}</h3>${subs.filter(s => re.test(s.code)).sort((a, b) => spec(b) - spec(a) || a.title.localeCompare(b.title)).map(item).join('')}</section>`).join('')}</div>
      <p class="notice">${L('文件实时取自 Pearson 官方目录（January / June / October / November）。2026、2027 新规格课程可能尚无历史试卷。', 'Files come live from Pearson’s official listing (January / June / October / November). Courses on the 2026/2027 specs may not have past papers yet.')}</p>`;
    $$('[data-edx]', out).forEach(b => b.addEventListener('click', () => pickSubject(b.dataset.edx)));
  }
  function renderChoices(raw, matches) {
    out.innerHTML = glyphEmpty(matches.length ? L('选择具体课程', 'Pick a course') : L('没有找到这个科目', 'Subject not found'), matches.length ? L(`“${raw}” 对应多门课程，选一门即可。`, `“${raw}” matches several courses.`) : L('试试中文名、英文名或四位代码。', 'Try an English name or a 4-digit code.'),
      matches.length ? `<div class="choices">${matches.slice(0, 24).map(s => `<button class="btn small" data-pick="${esc(s.code)}">${esc(subjName(s))} <code class="k">${esc(s.code)}</code></button>`).join('')}</div>` : '');
    $$('[data-pick]', out).forEach(b => b.addEventListener('click', () => { combo.set(b.dataset.pick); run(true); }));
  }
  function browseCatalog() {
    const rows = store.catalog.filter(r => (!st.year || String(r.year) === st.year) && (!st.season || seasonName(r.season) === seasonName(st.season)) && (!st.paper || r.type === 'examiner_report' || normalizePaper(r.paper) === st.paper));
    const popular = ['9709', '0580', '9702', '9701', '9700', '0455', '9708', '0625'];
    const rank = c => { const i = popular.indexOf(c); return i < 0 ? 99 : i; };
    rows.sort((a, b) => rank(a.code) - rank(b.code) || a.code.localeCompare(b.code) || b.year - a.year);
    table(rows, { title: L('官方目录快照', 'Official catalogue'), tag: store.snapshot, meta: L('选择科目与年份可实时查询最新文件', 'choose a subject + year for live results'), source: 'catalog' });
  }
  async function live(id) {
    f.go.disabled = true;
    out.innerHTML = syllabusCallout(st.board, st.subject) + `<div class="db-head"><div class="db-title">${L('正在检索原始来源…', 'Querying sources…')}</div></div>` + skeleton(7);
    try {
      const q = { board: st.board, subject: st.subject, year: st.year, season: st.season, paper: st.paper };
      // How many parsed questions the bank holds for this subject/year decides whether rows link to them.
      const bankReq = getJson('/gateway/api/v1/search?' + new URLSearchParams({ subject: st.subject, year: st.year, limit: '1' })).then(r => r.total).catch(() => 0);
      const data = await getJson('/api/resources?' + new URLSearchParams(Object.entries(q).filter(([, v]) => v)));
      const bank = await bankReq;
      if (id !== req) return;
      const docs = (data.documents || []).map(d => ({ ...d, code: st.subject, url: safeUrl(d.url) }));
      // Same-season examiner reports from the official catalogue snapshot fill gaps in the live listing.
      for (const extra of store.catalog.filter(r => r.type === 'examiner_report' && r.board === st.board && r.code === st.subject && String(r.year) === st.year && (!st.season || seasonName(r.season) === seasonName(st.season))))
        if (!docs.some(d => d.type === 'examiner_report' && seasonName(d.season) === seasonName(extra.season))) docs.push(extra);
      const s = subjectByCode(st.board, st.subject);
      table(docs, { title: s ? subjName(s) : st.subject, tag: `${st.subject} · ${st.year}${st.season ? ' · ' + seasonName(st.season) : ''}${st.paper ? ' · P' + st.paper : ''}`, meta: L('原始来源 · 实时', 'original source · live'), source: 'live', warning: data.warning, coverage: true, bank, bankPapers: new Set() });
    } catch (e) {
      if (id !== req) return;
      out.innerHTML = syllabusCallout(st.board, st.subject) + glyphEmpty(L('暂时无法获取', 'Could not fetch'), e.message, `<div class="choices"><button class="btn" id="retry">${L('重试', 'Retry')}</button></div>`);
      $('#retry', out)?.addEventListener('click', () => run());
    } finally { if (id === req) f.go.disabled = false; }
  }
  function table(docs, opt) {
    const groups = groupPapers(docs).sort((a, b) => (b.year || 0) - (a.year || 0) || String(a.season).localeCompare(String(b.season)) || String(a.paper).localeCompare(String(b.paper), undefined, { numeric: true }));
    const has = t => docs.some(d => d.type === t);
    const meta = docMeta();
    const cov = opt.coverage ? `<div class="coverage-row">${Object.entries(meta).map(([t, [, short, name]]) => `<div class="cov ${has(t) ? 'ok' : ''}"><b><i style="background:var(--${short.toLowerCase()})"></i>${short}</b><span>${esc(name)} · ${has(t) ? L('已找到', 'found') : L('来源未提供', 'not provided')}</span></div>`).join('')}</div>` : '';
    if (!groups.length) { out.innerHTML = syllabusCallout(st.board, st.subject) + glyphEmpty(L('没有找到对应文件', 'No files found'), L('检查年份、考季与卷号；新课程可能尚无历史试卷。', 'Check the year, series and paper; new courses may have no past papers yet.'), '', icon.doc); return; }
    let shown = 30;
    const draw = () => {
      out.innerHTML = `${syllabusCallout(st.board, st.subject)}
      <div class="db-head"><div class="db-title">${esc(opt.title)}<span class="mono">${esc(opt.tag || '')}</span></div><div class="db-meta">${groups.length} ${L('组', 'groups')} · ${docs.length} ${L('份文件', 'files')} · ${esc(opt.meta)}</div></div>
      ${opt.bank ? `<div class="callout bank">${icon.q}<div>${opt.bankPapers.size ? L(`题库中有该科目 ${st.year} 年已解析的 <strong>${fmt(opt.bank)}</strong> 道题，点击行内「题目」查看对应试卷的题目与评分要点。`, `The question bank holds <strong>${fmt(opt.bank)}</strong> parsed questions for this subject in ${st.year} — use “Qs” on a row to open that paper’s questions.`) : L(`题库中有该科目 ${st.year} 年已解析的 <strong>${fmt(opt.bank)}</strong> 道题（可能来自样卷，未与下列考季试卷对应）。`, `The question bank holds <strong>${fmt(opt.bank)}</strong> parsed questions for this subject in ${st.year} (possibly specimen papers, not matched to the series below).`)}</div><a class="btn small" href="#/questions?subject=${encodeURIComponent(st.subject)}&year=${st.year}">${L('全部题目', 'All questions')}<span class="arrow">${icon.arrow}</span></a></div>` : ''}
      ${cov}${opt.warning ? `<p class="notice warn">${esc(lang === 'zh' ? opt.warning : opt.warning.replace(/GT 分数线来源暂时无法读取；其他文件已显示。/g, 'grade thresholds temporarily unreachable; other files shown.').replace(/查询失败/g, 'lookup failed').replace(/来源暂不可用/g, 'source unavailable').replace(/；/g, '; ').replace(/：/g, ': '))}</p>` : ''}
      <div class="table-wrap"><table class="db"><thead><tr><th>${L('科目', 'Subject')}</th><th>${L('考季', 'Series')}</th><th>${L('卷号', 'Paper')}</th><th>${L('文件', 'Files')}</th></tr></thead><tbody>
      ${groups.slice(0, shown).map((g, i) => {
        const s = subjectByCode(g.board, g.code);
        const name = s ? subjName(s) : (g.title || g.code);
        return `<tr style="--i:${Math.min(i, 30)}"><td><div class="cell-title">${opt.source === 'catalog' ? `<span class="code">${esc(g.code)}</span>` : ''}<span>${esc(name)}<span class="cell-sub">${esc(g.qualification || s?.qualification || boardName(g.board))}</span></span></div></td>
        <td style="white-space:nowrap">${esc(g.year || '—')}<span class="cell-sub">${esc(seasonName(g.season))}</span></td>
        <td><span class="tag mono">${esc(g.paper || (g.board === 'edexcel' && g.type === 'grade_threshold' ? L('全科', 'all') : L('整季', 'series')))}</span></td>
        <td><div class="pills">${g.documents.map(d => { const [cls, short, nm] = meta[d.type] || ['', 'FILE', '']; const u = safeUrl(d.url); return u ? `<a class="doc-pill ${cls}" href="${esc(u)}" target="_blank" rel="noopener noreferrer" title="${esc(nm)} · ${esc(d.title || d.label || '')}"><i></i>${short}${icon.ext}</a>` : ''; }).join('')}${opt.bankPapers?.has(g.paper) ? `<a class="doc-pill qb" href="#/questions?subject=${encodeURIComponent(g.code)}&year=${esc(g.year)}&paper=${encodeURIComponent(g.paper)}" title="${L('题库中该卷的题目', 'Parsed questions from this paper')}">${icon.q}${L('题目', 'Qs')}</a>` : ''}</div></td></tr>`;
      }).join('')}</tbody></table></div>
      ${groups.length > shown ? `<button class="more" id="more">+ ${L(`再显示 ${Math.min(30, groups.length - shown)} 组 · 剩余 ${groups.length - shown}`, `Show ${Math.min(30, groups.length - shown)} more · ${groups.length - shown} left`)}</button>` : ''}
      ${opt.source === 'catalog' ? `<p class="notice">${L('目录快照只包含部分科目与年份；选择科目与年份后会实时检索来源站点。', 'The catalogue snapshot covers only some subjects and years; pick a subject and year to query the source live.')}</p>` : ''}`;
      $('#more', out)?.addEventListener('click', () => { shown += 30; draw(); });
    };
    draw();
    // Only link rows whose exact paper is in the question bank (the bank may hold specimens rather than series papers).
    if (opt.bank) {
      const papers = [...new Set(groups.filter(g => g.paper && g.documents.some(d => d.type === 'question_paper')).map(g => g.paper))];
      const myReq = req;
      Promise.all(papers.map(p => getJson('/gateway/api/v1/search?' + new URLSearchParams({ subject: st.subject, year: st.year, paper: p, limit: '1' })).then(r => r.total ? p : null).catch(() => null)))
        .then(found => { if (myReq !== req) return; found.filter(Boolean).forEach(p => opt.bankPapers.add(p)); if (opt.bankPapers.size) draw(); });
    }
  }
  run();
}
function syllabusCallout(board, code) {
  if (!code) return '';
  const s = syllabusFor(board, code);
  if (!s) return '';
  const links = s.syllabuses.map(x => safeUrl(x.url) ? `<a class="doc-pill" href="${esc(safeUrl(x.url))}" target="_blank" rel="noopener noreferrer">${esc(x.title || 'Syllabus')}${icon.ext}</a>` : '').join('')
    || (safeUrl(s.page) ? `<a class="doc-pill" href="${esc(safeUrl(s.page))}" target="_blank" rel="noopener noreferrer">${L('科目页', 'Subject page')}${icon.ext}</a>` : '');
  return links ? `<div class="callout mark" style="margin-top:34px">${icon.book}<div><strong>${L('考纲', 'Syllabus')}</strong>　${esc(s.title)}<div class="links">${links}</div></div></div>` : '';
}

/* ============ questions ============ */
async function viewQuestions(page, params) {
  const st = { keyword: params.keyword || '', board: params.board || '', subject: params.subject || '', year: params.year || '', paper: params.paper || '', leaves: params.leaves === '1', answer: params.answer === '1', offset: 0 };
  page.innerHTML = `
    ${pageHead('03', L('题目检索', 'Question search'), L('题库', 'Questions'), L('在已解析的题目中按题干关键词检索。点开任一题，在侧栏查看评分要点、知识点与原卷。', 'Search parsed questions by their wording. Open any question to see the mark scheme, topics and the original paper.'))}
    <div class="searchbar" id="sb">${icon.search}<input id="kw" placeholder="${L('输入关键词，如 probability…', 'Try probability, titration, elasticity…')}" value="${esc(st.keyword)}"><span class="spin"></span></div>
    <div class="filters">
      <div class="seg" id="qboard"><button data-v="">${L('全部', 'All')}</button><button data-v="cie">Cambridge</button><button data-v="edexcel">Edexcel</button></div>
      <div class="field"><input class="input" id="qsubject" placeholder="${L('科目：名称或代码', 'Subject: name or code')}" role="combobox" aria-expanded="false" aria-controls="qsubject-list" style="width:230px"><div class="combo-list" id="qsubject-list" role="listbox" hidden></div></div>
      <input class="input" id="qpaper" placeholder="${L('卷号', 'Paper')}" value="${esc(st.paper)}" style="width:110px">
      <select class="select" id="qyear"><option value="">${L('任意年份', 'Any year')}</option>${Array.from({ length: 17 }, (_, i) => 2026 - i).map(y => `<option ${String(y) === st.year ? 'selected' : ''}>${y}</option>`).join('')}</select>
      <button class="toggle" id="qleaves" aria-pressed="${st.leaves}">${L('仅可作答小题', 'Answerable parts only')}</button>
      <button class="toggle" id="qanswer" aria-pressed="${st.answer}">${L('有官方答案', 'Has mark scheme')}</button>
    </div>
    <div class="result-bar"><div class="result-count" id="qcount">&nbsp;</div><div class="board-split" id="qsplit"></div></div>
    <div class="qlist" id="qlist"></div>`;
  const list = $('#qlist', page), sb = $('#sb', page);
  const setSeg = () => $$('#qboard button', page).forEach(b => b.setAttribute('aria-pressed', String(b.dataset.v === st.board)));
  setSeg();
  let req = 0, items = [], total = 0;
  const highlight = text => {
    const t = esc(text);
    if (!st.keyword) return t;
    const k = esc(st.keyword).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return t.replace(new RegExp(k, 'gi'), m => `<mark>${m}</mark>`);
  };
  const rowHtml = (q, i) => `<button class="qrow" style="--i:${i % 20}" data-qid="${q.question_id}">
      <span class="qnum">${esc(q.number_path || '—')}</span>
      <span><span class="qstem ${q.stem_text?.trim() ? '' : 'empty-stem'}">${q.stem_text?.trim() ? highlight(q.stem_text.replace(/\.{6,}/g, '……').replace(/\s*\n\s*/g, ' ')) : L('（题干在子题中）', '(stem is in the sub-parts)')}</span>
      <span class="qmeta"><span class="tag ${q.board === 'edexcel' ? 'edexcel' : 'cie'}">${boardName(q.board)}</span><span class="tag mono">${esc(q.subject_code)}</span>${q.year ? `<span class="tag">${q.year}</span>` : ''}${q.paper_code ? `<span class="tag mono">${esc(q.paper_code)}</span>` : ''}${q.marks != null ? `<span class="tag orange">${q.marks} ${L('分', q.marks === 1 ? 'mark' : 'marks')}</span>` : ''}</span></span>
      <span class="chev">${icon.chev}</span></button>`;
  async function search(append = false) {
    const id = ++req;
    if (!append) st.offset = 0;
    setQuery('questions', { keyword: st.keyword, board: st.board, subject: st.subject, year: st.year, paper: st.paper, leaves: st.leaves ? '1' : '', answer: st.answer ? '1' : '' });
    sb.classList.add('loading');
    if (!append) list.innerHTML = skeleton(8);
    const q = { keyword: st.keyword, board: st.board, subject: st.subject.trim(), year: st.year, paper: st.paper, leaves_only: st.leaves ? 'true' : '', has_answer: st.answer ? 'true' : '', limit: '30', offset: String(st.offset) };
    try {
      const data = await getJson('/gateway/api/v1/search?' + new URLSearchParams(Object.entries(q).filter(([, v]) => v)));
      if (id !== req) return;
      total = data.total; items = append ? items.concat(data.items) : data.items;
      const cam = data.by_board?.cambridge || 0, edx = data.by_board?.edexcel || 0, sum = cam + edx || 1;
      $('#qcount', page).innerHTML = `${fmt(total)}<span>${L('道题', 'QUESTIONS')}${st.keyword ? ` · “${esc(st.keyword)}”` : ''}</span>`;
      $('#qsplit', page).innerHTML = `<span>CIE ${fmt(cam)}</span><div class="bar"><i style="width:${Math.max(cam / sum * 100, cam ? 1.5 : 0)}%"></i><i style="width:${edx / sum * 100}%"></i></div><span>EDX ${fmt(edx)}</span>`;
      if (!items.length) { list.innerHTML = glyphEmpty(L('没有匹配的题目', 'No matching questions'), L('换个关键词，或放宽考试局、科目与年份筛选。', 'Try another keyword or loosen the filters.'), '', icon.q); return; }
      list.innerHTML = items.map(rowHtml).join('') + (items.length < total ? `<button class="more" id="qmore">+ ${L(`加载更多 · ${items.length} / ${fmt(total)}`, `Load more · ${items.length} of ${fmt(total)}`)}</button>` : '');
      $('#qmore', list)?.addEventListener('click', () => { st.offset = items.length; search(true); });
    } catch (e) {
      if (id !== req) return;
      $('#qcount', page).innerHTML = '&nbsp;'; $('#qsplit', page).innerHTML = '';
      list.innerHTML = glyphEmpty(L('题库暂不可用', 'Question bank unavailable'), e.status === 502 || e.status == null ? L('无法连接数据服务，请确认后端已在 EXAMDATA_URL 运行。', 'Cannot reach the data service — check that the backend is running at EXAMDATA_URL.') : e.message, '', icon.q);
    } finally { if (id === req) sb.classList.remove('loading'); }
  }
  const later = debounce(() => search(), 320);
  $('#kw', page).addEventListener('input', e => { st.keyword = e.target.value.trim(); later(); });
  // Subject filter: pick from the board-aware list, or type a raw code (e.g. 0580, ial18-economics).
  const qcombo = combobox($('#qsubject', page), $('#qsubject-list', page), () => st.board || 'all', code => { st.subject = code; search(); });
  qcombo.set(st.subject);
  $('#qsubject', page).addEventListener('input', e => {
    const v = e.target.value.trim(), code = v.includes('·') ? v.split('·').pop().trim() : v;
    const next = !v ? '' : /^[a-z0-9-]+$/i.test(code) ? code : st.subject;
    if (next !== st.subject) { st.subject = next; later(); }
  });
  $('#qpaper', page).addEventListener('input', e => { st.paper = e.target.value.trim().toLowerCase(); later(); });
  $('#qyear', page).addEventListener('change', e => { st.year = e.target.value; search(); });
  $('#qboard', page).addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; st.board = b.dataset.v; setSeg(); search(); });
  $('#qleaves', page).addEventListener('click', e => { st.leaves = !st.leaves; e.currentTarget.setAttribute('aria-pressed', String(st.leaves)); search(); });
  $('#qanswer', page).addEventListener('click', e => { st.answer = !st.answer; e.currentTarget.setAttribute('aria-pressed', String(st.answer)); search(); });
  list.addEventListener('click', e => { const r = e.target.closest('[data-qid]'); if (!r) return; $$('.qrow.active', list).forEach(x => x.classList.remove('active')); r.classList.add('active'); openQuestion(r.dataset.qid); });
  if (!params.keyword) setTimeout(() => $('#kw', page)?.focus({ preventScroll: true }), 60);
  search();
}

/* ============ peek: question detail ============ */
let peekReq = 0, lastPeek = null;
let peekReturn = null;
function openPeek(title, html) {
  $('#peek-title').textContent = title; $('#peek-body').innerHTML = html;
  const wasOpen = $('#peek').classList.contains('open');
  $('#peek').classList.add('open'); $('#peek').setAttribute('aria-hidden', 'false'); $('#scrim').classList.add('on');
  // Move focus into the panel and remember where to return it.
  if (!wasOpen) { peekReturn = document.activeElement; $('#peek-close').focus({ preventScroll: true }); }
}
function closePeek() {
  lastPeek = null; $('#peek').classList.remove('open'); $('#peek').setAttribute('aria-hidden', 'true'); $('#scrim').classList.remove('on'); $$('.qrow.active').forEach(x => x.classList.remove('active'));
  if (peekReturn instanceof HTMLElement && peekReturn.isConnected) peekReturn.focus({ preventScroll: true });
  peekReturn = null;
}
$('#peek-close').addEventListener('click', closePeek);
$('#scrim').addEventListener('click', () => { if ($('#sidebar').classList.contains('open')) toggleDrawer(false); else closePeek(); });
async function openQuestion(id) {
  if (!/^\d+$/.test(String(id))) return;
  const my = ++peekReq; lastPeek = id;
  openPeek(`QUESTION #${id}`, skeleton(9));
  try {
    const d = await getJson(`/gateway/api/v1/question/${id}`);
    if (my !== peekReq) return;
    const { question: q = {}, children = [], assets = [], official_answers = [], mark_scheme_entries = [], taxonomy = [], difficulty = [] } = d.bundle || {};
    const s = d.source || {};
    const board = s.board_canonical || (d.board === 'edexcel' ? 'edexcel' : 'cie');
    const answers = mark_scheme_entries.length ? mark_scheme_entries.map(m => m.answer_text).filter(Boolean) : official_answers.map(a => a.content).filter(Boolean);
    const paperUrl = s.paper_endpoint ? '/gateway' + s.paper_endpoint : '';
    const cropUrl = board === 'edexcel' && s.paper_endpoint && q.number_path ? '/gateway' + s.paper_endpoint.replace(/mode=paper/, 'mode=question') + '&question=' + encodeURIComponent(q.number_path) : '';
    const conf = q.parse_confidence, diff = difficulty[0];
    const subj = subjectByCode(board, s.subject_code);
    const kind = { sub: L('小题', 'Part'), question: L('大题', 'Question') }[q.kind] || q.kind;
    $('#peek-body').innerHTML = `
      <div class="qmeta" style="margin:0"><span class="tag ${board === 'edexcel' ? 'edexcel' : 'cie'}">${boardName(board)}</span>${kind ? `<span class="tag">${esc(kind)}</span>` : ''}${q.has_override ? `<span class="tag orange">${L('人工修订', 'Edited')}</span>` : ''}</div>
      <h2>${L(`第 ${esc(q.number_path || q.number_label || id)} 题`, `Question ${esc(q.number_path || q.number_label || id)}`)}</h2>
      <div class="props">
        <div class="prop-key">${icon.book}${L('科目', 'Subject')}</div><div class="prop-val">${esc(s.subject_code || '—')}${subj ? ` <span class="db-meta">${esc(subjName(subj))}</span>` : ''}</div>
        <div class="prop-key">${icon.cal}${L('考季', 'Series')}</div><div class="prop-val">${esc(s.year || '—')} ${esc(s.session ? seasonName(s.session) : (s.doc_type === 'specimen_paper' ? L('样卷', 'Specimen') : ''))}</div>
        <div class="prop-key">${icon.hash}${L('卷号 / 页码', 'Paper / page')}</div><div class="prop-val"><span class="tag mono">${esc(s.paper_code || '—')}</span><span class="db-meta">${L('第', 'p.')} ${esc(q.page_from ?? '—')}${q.page_to && q.page_to !== q.page_from ? '–' + esc(q.page_to) : ''} ${L('页', '')}</span></div>
        <div class="prop-key">${icon.tag}${L('分值', 'Marks')}</div><div class="prop-val">${q.marks != null ? `<span class="tag orange">${q.marks} ${L('分', q.marks === 1 ? 'mark' : 'marks')}</span>` : `<span class="db-meta">${L('未标注', 'not stated')}</span>`}</div>
        ${conf != null ? `<div class="prop-key">${icon.layers}${L('解析置信度', 'Parse confidence')}</div><div class="prop-val"><span class="meter"><span><i style="width:${Math.round(conf * 100)}%"></i></span>${Math.round(conf * 100)}%</span></div>` : ''}
        ${diff ? `<div class="prop-key">${icon.clock}${L('难度估计', 'Difficulty')}</div><div class="prop-val"><span class="meter"><span><i style="width:${Math.round((diff.value || 0) * 100)}%"></i></span>${(diff.value ?? 0).toFixed(2)}</span><span class="db-meta">${esc(diff.source || '')}</span></div>` : ''}
      </div>
      <div class="actions">${paperUrl ? `<a class="btn primary" href="${esc(paperUrl)}">${icon.dl}${L('下载原卷', 'Download paper')}</a>` : ''}${cropUrl ? `<a class="btn" href="${esc(cropUrl)}">${icon.dl}${L('仅本题', 'This question only')}</a>` : ''}${s.subject_code && s.year ? `<a class="btn" href="#/papers?${new URLSearchParams(Object.entries({ board, subject: s.subject_code, year: s.year, season: s.session ? seasonParam(board, s.session) : '', paper: s.paper_code || '' }).filter(([, v]) => v))}">${icon.doc}${L('该卷全部文件', 'All files for this paper')}</a>` : ''}${!paperUrl ? `<span class="db-meta">${L('样卷或缺少定位信息，暂无取卷链接。', 'Specimen or incomplete locator — no download link.')}</span>` : ''}</div>
      <div class="block-label">${L('题干', 'Question')}</div>
      <div class="stem-block">${q.stem_text?.trim() ? esc(q.stem_text.replace(/\.{12,}/g, '…………').replace(/[ \t]*\n(?:[ \t]*\n)+/g, '\n\n')) : `<span class="db-meta">${L('本题题干位于子题中。', 'The stem lives in the sub-parts.')}</span>`}</div>
      ${assets.filter(a => a.id != null).map(a => `<img class="asset-img" loading="lazy" src="/gateway/assets/${encodeURIComponent(a.id)}" alt="">`).join('')}
      ${children.length ? `<div class="block-label">${L('子题', 'Parts')} · ${children.length}</div><div class="child-list">${children.map(c => `<button data-child="${c.id}"><span>${esc(c.number_path)}</span><span class="db-meta">${c.marks != null ? c.marks + ' ' + L('分', 'm') : ''} →</span></button>`).join('')}</div>` : ''}
      <div class="block-label">${L('评分要点', 'Mark scheme')}</div>
      ${answers.length ? answers.map(a => `<div class="answer">${esc(a.replace(/[ \t]*\n[ \t]*\n+/g, '\n').trim())}</div>`).join('') : `<div class="callout">${icon.info}<div>${L('暂无关联的官方评分标准。', 'No linked official mark scheme yet.')}</div></div>`}
      ${taxonomy.length ? `<div class="block-label">${L('知识点', 'Topics')}</div><div class="pills">${taxonomy.map(t => `<span class="tag green" title="${esc(t.code)}">${esc(t.name || t.code)}</span>`).join('')}</div>` : ''}
      <p class="notice">#${esc(id)} · DOC ${esc(s.document_id ?? '—')} · ${esc(s.doc_type || '')}</p>`;
    $$('[data-child]', $('#peek-body')).forEach(b => b.addEventListener('click', () => openQuestion(b.dataset.child)));
    $('#peek-body').scrollTop = 0;
  } catch (e) {
    if (my === peekReq) $('#peek-body').innerHTML = glyphEmpty(L('无法加载题目', 'Could not load question'), e.message, '', icon.q);
  }
}

/* ============ timetable ============ */
const WEEK_ZH = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
const WEEK_EN = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTH_EN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTH_FULL_EN = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
// Dates are handled as UTC midnights of YYYY-MM-DD strings; "today" is the viewer's local calendar date.
const localISO = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const utc = iso => new Date(iso + 'T00:00:00Z');
const isoOf = d => d.toISOString().slice(0, 10);
const addDays = (iso, n) => { const d = utc(iso); d.setUTCDate(d.getUTCDate() + n); return isoOf(d); };
const addMonths = (ym, n) => { const [y, m] = ym.split('-').map(Number), d = new Date(Date.UTC(y, m - 1 + n, 1)); return isoOf(d).slice(0, 7); };
const monthTitle = ym => { const [y, m] = ym.split('-').map(Number); return L(`${y} 年 ${m} 月`, `${MONTH_FULL_EN[m - 1]} ${y}`); };
const dayTitle = iso => { const d = utc(iso); return L(`${d.getUTCMonth() + 1} 月 ${d.getUTCDate()} 日 · ${WEEK_ZH[d.getUTCDay()]}`, `${WEEK_EN[d.getUTCDay()]} ${d.getUTCDate()} ${MONTH_FULL_EN[d.getUTCMonth()]}`); };
const boardShort = b => (b === 'edexcel' ? 'EDX' : 'CIE');
const seriesLabel = e => `${boardShort(e.board)} ${seasonName(e.series.split('-')[1])} ${e.series.split('-')[0]}`;

async function viewTimetable(page, params) {
  const today = localISO();
  const st = {
    view: params.view === 'list' || params.view === 'month' ? params.view : (innerWidth < 820 ? 'list' : 'month'),
    month: /^\d{4}-\d{2}$/.test(params.month || '') ? params.month : today.slice(0, 7),
    board: ['cie', 'edexcel'].includes(params.board) ? params.board : 'all',
    subject: params.subject || '', session: '', level: '',
  };
  page.classList.add('wide');
  page.innerHTML = `
    ${pageHead('04', L('考试日程', 'Exam schedule'), L('时间表', 'Timetable'), L('Cambridge Zone 5 与 Edexcel IAL 的官方时间表合并在同一本日历里。默认显示全部考试局，可按月查看或按日滚动。', 'Official Cambridge Zone 5 and Edexcel IAL timetables merged into one calendar — every board by default, by month or day by day.'))}
    <div class="props">
      <div class="prop-key">${icon.board}${L('考试局', 'Board')}</div>
      <div class="prop-val"><div class="seg" id="tboard"><button data-v="all">${L('全部', 'All')}</button><button data-v="cie">Cambridge</button><button data-v="edexcel">Edexcel IAL</button></div></div>
      <div class="prop-key">${icon.hash}${L('科目', 'Subject')}</div>
      <div class="prop-val"><input class="input" id="tsubject" placeholder="${L('代码前缀，如 9709 / WMA', 'Code prefix, e.g. 9709 / WMA')}" style="width:240px"></div>
      <div class="prop-key">${icon.layers}${L('筛选', 'Filter')}</div>
      <div class="prop-val" id="tfilters"><span class="db-meta">—</span></div>
    </div>
    <div class="tt-bar">
      <div class="tt-nav"><button class="icon-btn" data-nav="-1" aria-label="${L('上一月', 'Previous month')}">${icon.chev.replace('m9 6 6 6-6 6', 'm15 6-6 6 6 6')}</button><span class="tt-bar-title" id="tt-title"></span><button class="icon-btn" data-nav="1" aria-label="${L('下一月', 'Next month')}">${icon.chev}</button></div>
      <button class="btn small" data-today>${L('今天', 'Today')}</button>
      <span class="db-meta tt-sum" id="tt-sum"></span>
      <span class="tt-bar-actions"><div class="seg" id="tview"><button data-v="month">${L('月', 'Month')}</button><button data-v="list">${L('列表', 'List')}</button></div><button class="btn small" data-ics type="button" title="${L('导出本月日历', 'Export this month')}">${icon.dl}.ics</button></span>
    </div>
    <div id="tout">${skeleton(6)}</div>`;
  const out = $('#tout', page);
  $('#tsubject', page).value = st.subject;
  let data = null, req = 0;
  const paintControls = () => {
    $$('#tboard button', page).forEach(b => b.setAttribute('aria-pressed', String(b.dataset.v === st.board)));
    $$('#tview button', page).forEach(b => b.setAttribute('aria-pressed', String(b.dataset.v === st.view)));
    $('#tt-title', page).textContent = monthTitle(st.month);
  };
  // The month grid runs Monday → Sunday, so it spills into neighbouring months.
  const gridRange = () => {
    const first = st.month + '-01', last = addDays(addMonths(st.month, 1) + '-01', -1);
    const lead = (utc(first).getUTCDay() + 6) % 7, trail = (7 - ((utc(last).getUTCDay() + 6) % 7) - 1);
    return { first, last, from: addDays(first, -lead), to: addDays(last, trail) };
  };
  async function load(anchor = true) {
    const id = ++req;
    paintControls();
    setQuery('timetable', { view: st.view, month: st.month, board: st.board === 'all' ? '' : st.board, subject: st.subject });
    const r = gridRange();
    if (!data) out.innerHTML = skeleton(8);
    try {
      const d = await getJson('/api/timetable/events?' + new URLSearchParams({ from: r.from, to: r.to, board: st.board, subject: st.subject }));
      if (id !== req) return;
      data = d; draw(anchor);
    } catch (e) { if (id === req) out.innerHTML = glyphEmpty(L('时间表暂不可用', 'Timetable unavailable'), e.message, '', icon.cal); }
  }
  const visible = () => data.events.filter(e => (!st.session || e.session === st.session) && (!st.level || e.level === st.level));
  function draw(anchor = false) {
    const r = gridRange();
    const all = visible(), inMonth = all.filter(e => e.date >= r.first && e.date <= r.last);
    const sessions = [...new Set(data.events.map(e => e.session).filter(Boolean))].sort();
    const levels = [...new Set(data.events.map(e => e.level).filter(Boolean))];
    $('#tfilters', page).innerHTML = [...sessions.map(s => `<button class="toggle" data-session="${s}" aria-pressed="${st.session === s}">${s}</button>`), ...levels.map(l => `<button class="toggle" data-level="${l}" aria-pressed="${st.level === l}">${{ IG: 'IGCSE', OL: 'O Level', AS: 'AS', AL: 'A Level', PR: 'Pre-U' }[l] || l}</button>`)].join('') || `<span class="db-meta">${L('本月无可筛选项', 'Nothing to filter this month')}</span>`;
    const cie = inMonth.filter(e => e.board === 'cie').length, edx = inMonth.length - cie;
    $('#tt-sum', page).innerHTML = inMonth.length ? `${inMonth.length} ${L('场', 'sessions')} · <span class="bd cie"></span>CIE ${cie} · <span class="bd edexcel"></span>EDX ${edx}` : L('本月无考试', 'No exams this month');
    if (st.view === 'month') drawMonth(all, r); else drawList(inMonth, r, anchor);
  }
  function emptyMonth() {
    const jump = (iso, label) => iso ? `<button class="btn small" data-goto="${iso.slice(0, 7)}">${label} · ${monthTitle(iso.slice(0, 7))}</button>` : '';
    return glyphEmpty(L('本月没有考试', 'No exams this month'), st.subject ? L(`没有 ${st.subject} 开头的科目在本月考试。`, `No ${st.subject}… papers are sat this month.`) : L('换个月份，或直接跳到最近有考试的月份。', 'Try another month, or jump to the nearest month with exams.'), `<div class="choices">${jump(data.prev, L('上一个有考试的月份', 'Previous'))}${jump(data.next, L('下一个有考试的月份', 'Next'))}</div>`, icon.cal);
  }
  const chip = e => `<span class="chip ${e.board}" title="${esc(`${boardShort(e.board)} ${e.subject_code}/${e.paper_code} ${e.subject_title} · ${e.session} ${e.duration_raw}`)}"><i></i><code>${esc(e.subject_code)}/${esc(e.paper_code)}</code><em>${esc(e.session)}</em></span>`;
  // Cells show three chips; take them round-robin across boards so a busy CIE day never hides Edexcel.
  const preview = list => {
    const queues = ['cie', 'edexcel'].map(bd => list.filter(e => e.board === bd)).filter(q => q.length), picked = [];
    for (let i = 0; picked.length < 3 && queues.some(q => q.length); i++) { const q = queues[i % queues.length]; if (q.length) picked.push(q.shift()); }
    return picked;
  };
  function drawMonth(all, r) {
    const byDate = new Map();
    for (const e of all) { if (!byDate.has(e.date)) byDate.set(e.date, []); byDate.get(e.date).push(e); }
    const monthEvents = all.filter(e => e.date >= r.first && e.date <= r.last);
    const cieN = monthEvents.filter(e => e.board === 'cie').length, edxN = monthEvents.length - cieN;
    const days = [...byDate.entries()].filter(([k]) => k >= r.first && k <= r.last);
    const busiest = days.sort((a, b) => b[1].length - a[1].length)[0];
    const cells = [];
    for (let d = r.from; d <= r.to; d = addDays(d, 1)) {
      const outside = d < r.first || d > r.last, list = outside ? [] : byDate.get(d) || [], n = list.length;
      const c = list.filter(e => e.board === 'cie').length, x = n - c;
      const wd = (utc(d).getUTCDay() + 6) % 7;
      cells.push(`<button class="cal-cell${outside ? ' out' : ''}${wd > 4 ? ' we' : ''}${d === today ? ' today' : ''}${d < today ? ' past' : ''}${n ? ' has' : ''}" data-day="${d}" ${n ? '' : 'tabindex="-1"'} aria-label="${esc(dayTitle(d))} · ${n}">
        <span class="cal-top"><span class="cal-date">${utc(d).getUTCDate()}</span>${n ? `<span class="cal-count">${n}<small>${L('场', '')}</small></span>` : ''}</span>
        ${n ? `<span class="cal-split" aria-hidden="true">${c ? `<i class="cie" style="flex:${c}"></i>` : ''}${x ? `<i class="edexcel" style="flex:${x}"></i>` : ''}</span>` : ''}
        <span class="cal-chips">${preview(list).map(chip).join('')}${n > 3 ? `<span class="cal-more">+${n - 3} ${L('场', 'more')}</span>` : ''}</span>
        <span class="cal-dots">${c ? '<i class="cie"></i>' : ''}${x ? '<i class="edexcel"></i>' : ''}</span></button>`);
    }
    const heads = (lang === 'zh' ? ['一', '二', '三', '四', '五', '六', '日'] : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']).map((w, i) => `<span class="${i > 4 ? 'we' : ''}">${w}</span>`).join('');
    const total = monthEvents.length || 1;
    const stat = (cls, label, value, sub, share) => `<div class="cal-stat ${cls}"><span class="k">${label}</span><b>${value}</b><span class="s">${sub}</span>${share != null ? `<span class="share"><i style="width:${share}%"></i></span>` : ''}</div>`;
    out.innerHTML = `
      ${monthEvents.length ? `<div class="cal-stats">
        ${stat('all', L('本月场次', 'Sessions'), fmt(monthEvents.length), `${days.length} ${L('个考试日', 'exam days')}`)}
        ${stat('cie', 'Cambridge', fmt(cieN), `${Math.round(cieN / total * 100)}%`, cieN / total * 100)}
        ${stat('edexcel', 'Edexcel IAL', fmt(edxN), `${Math.round(edxN / total * 100)}%`, edxN / total * 100)}
        ${busiest ? stat('peak', L('最忙的一天', 'Busiest day'), `${utc(busiest[0]).getUTCMonth() + 1}/${utc(busiest[0]).getUTCDate()}`, `${busiest[1].length} ${L('场', 'sessions')}`) : ''}
      </div>` : ''}
      <div class="cal">
        <div class="cal-head">${heads}</div>
        <div class="cal-grid">${cells.join('')}</div>
      </div>
      <div class="cal-legend"><span><i class="bd cie"></i>Cambridge (CIE)</span><span><i class="bd edexcel"></i>Edexcel IAL (EDX)</span><span><i class="bd now"></i>${L('今天', 'Today')}</span><span class="db-meta">${L('点击日期查看当天全部场次', 'Click a day for every session')}</span></div>
      ${monthEvents.length ? '' : emptyMonth()}
      ${sourceNote()}`;
  }
  function drawList(inMonth, r, anchor) {
    if (!inMonth.length) { out.innerHTML = emptyMonth() + sourceNote(); return; }
    const byDate = new Map();
    for (const e of inMonth) { if (!byDate.has(e.date)) byDate.set(e.date, []); byDate.get(e.date).push(e); }
    const dates = [...byDate.keys()].sort();
    const upcoming = dates.find(d => d >= today);
    const maxMin = Math.max(...inMonth.map(e => e.duration_minutes || 0), 60);
    // The "today" line splits finished sessions (above) from upcoming ones (below) when today falls in this month.
    const showNow = today >= r.first && today <= r.last;
    const daysTo = upcoming ? Math.round((utc(upcoming) - utc(today)) / 864e5) : 0;
    const nowText = !upcoming ? L('本月考试已全部结束', 'All of this month’s sessions are done')
      : upcoming === today ? L('今天有考试 · 上方为已结束，下方为即将进行', 'Exams today · finished above, upcoming below')
      : L(`下一场在 ${daysTo} 天后`, `Next session in ${daysTo} day${daysTo === 1 ? '' : 's'}`);
    const nowLine = showNow ? `<div class="now-line" id="now"><b>${L('今天', 'TODAY')} · ${esc(dayTitle(today))}</b><span>${nowText}</span></div>` : '';
    const nowAt = showNow ? (upcoming || '') : null;
    out.innerHTML = `<div class="days">${dates.map(k => {
      const d = utc(k), list = byDate.get(k);
      const big = lang === 'zh' ? `${d.getUTCMonth() + 1}/${d.getUTCDate()}` : `${d.getUTCDate()}<small>${MONTH_EN[d.getUTCMonth()]}</small>`;
      const boards = [...new Set(list.map(e => e.board))];
      return `${k === nowAt ? nowLine : ''}<section class="day ${k < today ? 'past' : ''}" id="d-${k}"><div class="day-head"><strong>${big}</strong><span>${(lang === 'zh' ? WEEK_ZH : WEEK_EN)[d.getUTCDay()]} · ${list.length} ${L('场', list.length === 1 ? 'session' : 'sessions')}</span><span class="day-boards">${boards.map(b => `<i class="bd ${b}"></i>${boardShort(b)}`).join(' ')}</span>${k === today ? `<span class="tag green">${L('今天', 'Today')}</span>` : k === upcoming ? `<span class="tag orange">${L('下一个', 'Next')}</span>` : ''}</div>
        <div class="events">${list.map(e => eventRow(e, maxMin)).join('')}</div></section>`;
    }).join('')}${nowAt === '' ? nowLine : ''}</div>
    <div class="list-foot"><button class="btn small" data-nav="-1">← ${monthTitle(addMonths(st.month, -1))}</button><button class="btn small" data-nav="1">${monthTitle(addMonths(st.month, 1))} →</button></div>
    ${sourceNote()}`;
    if (anchor && showNow && upcoming && upcoming !== dates[0]) anchorNow();
  }
  function eventRow(e, maxMin = 180) {
    const inner = `<span class="ev-board ${e.board}" title="${esc(seriesLabel(e))}">${boardShort(e.board)}</span><span class="sess ${esc(e.session)}">${esc(e.session || '—')}</span><code>${esc(e.subject_code)}/${esc(e.paper_code)}</code><span class="ev-title">${esc(e.subject_title)}${e.level ? ` <span class="tag">${esc(e.level)}</span>` : ''}</span><span class="dur"><span style="width:${Math.round((e.duration_minutes || 0) / maxMin * 60)}px"></span>${esc(e.duration_raw)}</span>`;
    // CIE sessions link to the most recent sitting of the same paper that has already happened.
    if (e.board !== 'cie' || !/^\d{4}$/.test(e.subject_code)) return `<div class="event">${inner}</div>`;
    const [y, s] = e.series.split('-'), py = e.date < today ? y : String(Number(y) - 1);
    return `<a class="event link" href="#/papers?board=cie&subject=${e.subject_code}&year=${py}&season=${s}&paper=${encodeURIComponent(e.paper_code)}" title="${L(`查看 ${py} ${seasonName(s)} 的试卷`, `Papers from ${seasonName(s)} ${py}`)}">${inner}</a>`;
  }
  function sourceNote() {
    const links = (data.series || []).map(s => safeUrl(s.url) ? `<a href="${esc(safeUrl(s.url))}" target="_blank" rel="noopener noreferrer">${boardShort(s.board)} ${esc(seasonName(s.season))} ${s.year}</a>` : `${boardShort(s.board)} ${esc(seasonName(s.season))} ${s.year}`).join(' · ');
    return `<p class="notice">${links ? L('官方时间表：', 'Official timetables: ') + links + ' · ' : ''}${L('CIE 场次可点击查看该卷最近一次已考的试卷。Edexcel 为 International A Level。时间表来自本地快照（只读），以考试局最终发布为准。', 'Click a CIE session for the latest past sitting of that paper. Edexcel covers International A Level. Read-only local snapshots — the board’s final publication prevails.')}</p>`;
  }
  function openDay(iso) {
    const list = visible().filter(e => e.date === iso);
    if (!list.length) return;
    const maxMin = Math.max(...list.map(e => e.duration_minutes || 0), 60);
    const groups = ['AM', 'PM', 'EV', ''].map(s => [s, list.filter(e => (e.session || '') === s)]).filter(([, v]) => v.length);
    const cie = list.filter(e => e.board === 'cie').length;
    openPeek(dayTitle(iso).toUpperCase(), `
      <div class="qmeta" style="margin:0">${iso === today ? `<span class="tag green">${L('今天', 'Today')}</span>` : ''}${cie ? `<span class="tag cie">CIE ${cie}</span>` : ''}${list.length - cie ? `<span class="tag edexcel">EDX ${list.length - cie}</span>` : ''}</div>
      <h2>${esc(dayTitle(iso))}</h2>
      <p class="lede" style="margin-top:8px">${list.length} ${L('场考试', list.length === 1 ? 'session' : 'sessions')} · ${[...new Set(list.map(seriesLabel))].join(' · ')}</p>
      ${groups.map(([s, v]) => `<div class="block-label">${s ? { AM: L('上午 · AM', 'Morning · AM'), PM: L('下午 · PM', 'Afternoon · PM'), EV: L('晚间 · EV', 'Evening · EV') }[s] || s : L('未标注场次', 'Unspecified')} · ${v.length}</div><div class="events">${v.map(e => eventRow(e, maxMin)).join('')}</div>`).join('')}
      <div class="actions" style="margin-top:24px"><button class="btn" data-day-list="${iso}">${icon.cal}${L('在列表中查看这一天', 'Show this day in the list')}</button></div>`);
    $('[data-day-list]', $('#peek-body'))?.addEventListener('click', () => { closePeek(); st.view = 'list'; paintControls(); draw(false); requestAnimationFrame(() => jumpTo(iso)); setQuery('timetable', { view: st.view, month: st.month, board: st.board === 'all' ? '' : st.board, subject: st.subject }); });
  }
  // Page-level scroll so the target sits just below the sticky top bar and session bar.
  function jumpTo(id, smooth = true) {
    const el = id === 'now' ? $('#now', out) : $('#d-' + id, out);
    if (!el) return;
    const offset = $('.topbar').offsetHeight + ($('.tt-bar', page)?.offsetHeight || 0) + 6;
    scrollTo({ top: Math.max(0, el.getBoundingClientRect().top + scrollY - offset), behavior: smooth && !reduced() ? 'smooth' : 'auto' });
  }
  // Web fonts and late layout can shift the list after the first jump; re-anchor until the user scrolls.
  function anchorNow() {
    jumpTo('now', false);
    let expected = scrollY;
    const again = () => { if (Math.abs(scrollY - expected) > 2 || !out.isConnected) return; jumpTo('now', false); expected = scrollY; };
    requestAnimationFrame(() => requestAnimationFrame(again));
    document.fonts?.ready.then(again);
    const ro = new ResizeObserver(again);
    ro.observe(page);
    setTimeout(() => ro.disconnect(), 3000);
  }
  const go = month => { st.month = month; st.session = ''; st.level = ''; load(); };
  page.addEventListener('click', e => {
    const t = e.target;
    const nav = t.closest('[data-nav]'); if (nav) { go(addMonths(st.month, Number(nav.dataset.nav))); return; }
    const g = t.closest('[data-goto]'); if (g) { go(g.dataset.goto); return; }
    if (t.closest('[data-today]')) { if (st.month !== today.slice(0, 7)) go(today.slice(0, 7)); else if (st.view === 'list') jumpTo('now'); else $('.cal-cell.today', out)?.focus(); return; }
    const cell = t.closest('[data-day]'); if (cell) { if (cell.classList.contains('has')) openDay(cell.dataset.day); return; }
    const b = t.closest('#tboard button'); if (b) { if (b.dataset.v !== st.board) { st.board = b.dataset.v; st.level = ''; st.session = ''; load(); } return; }
    const v = t.closest('#tview button'); if (v) { if (v.dataset.v !== st.view) { st.view = v.dataset.v; paintControls(); setQuery('timetable', { view: st.view, month: st.month, board: st.board === 'all' ? '' : st.board, subject: st.subject }); if (data) draw(true); } return; }
    if (t.closest('[data-ics]') && data) { const r = gridRange(); downloadIcs(visible().filter(x => x.date >= r.first && x.date <= r.last), `${st.board}-${st.month}${st.subject ? '-' + st.subject : ''}`); return; }
    const s = t.closest('[data-session]'); if (s) { st.session = st.session === s.dataset.session ? '' : s.dataset.session; draw(); return; }
    const l = t.closest('[data-level]'); if (l) { st.level = st.level === l.dataset.level ? '' : l.dataset.level; draw(); }
  });
  $('#tsubject', page).addEventListener('input', debounce(e => { st.subject = e.target.value.trim(); load(false); }, 300));
  // ← / → page through months when focus is not in a text field.
  const onKey = e => { if (palette.open || $('#peek').classList.contains('open') || /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) return; if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); go(addMonths(st.month, e.key === 'ArrowLeft' ? -1 : 1)); } };
  document.addEventListener('keydown', onKey);
  load();
  return () => document.removeEventListener('keydown', onKey);
}

// All-day calendar entries: the timetables give AM/PM sessions, not start times.
function downloadIcs(events, name) {
  const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+/, '');
  const fold = t => t.replace(/[\\;,]/g, m => '\\' + m);
  const day = d => d.replace(/-/g, '');
  const next = d => { const x = new Date(d + 'T00:00:00Z'); x.setUTCDate(x.getUTCDate() + 1); return x.toISOString().slice(0, 10).replace(/-/g, ''); };
  const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Examdata//Timetable//EN', 'CALSCALE:GREGORIAN', ...events.flatMap(e => [
    'BEGIN:VEVENT', `UID:${e.date}-${e.subject_code}-${e.paper_code}-${e.session}@examdata.local`, `DTSTAMP:${stamp}`,
    `DTSTART;VALUE=DATE:${day(e.date)}`, `DTEND;VALUE=DATE:${next(e.date)}`,
    `SUMMARY:${fold(`${e.subject_code}/${e.paper_code} ${e.subject_title || ''} (${e.session || ''}${e.duration_raw ? ', ' + e.duration_raw : ''})`)}`,
    `DESCRIPTION:${fold(e.raw || '')}`, 'END:VEVENT']), 'END:VCALENDAR'];
  const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(new Blob([lines.join('\r\n')],{ type: 'text/calendar' })), download: `examdata-${name}.ics` });
  a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

/* ============ intro ============ */
let statsPromise = null;
// Cinematic opener: grid draws in, data streams, wordmark rises, then the screen splits open.
async function playIntro(force = false) {
  if (reduced() || $('#intro')) return;
  if (!force) { try { if (sessionStorage.getItem('xd-intro')) return; sessionStorage.setItem('xd-intro', '1'); } catch {} }
  const word = 'Examdata';
  const el = document.createElement('div');
  el.className = 'intro'; el.id = 'intro';
  el.setAttribute('role', 'dialog'); el.setAttribute('aria-modal', 'true'); el.setAttribute('aria-label', L('开场动画', 'Intro'));
  const labels = [L('题目', 'Questions'), L('已解析试卷', 'Parsed papers'), L('时间表考季', 'Timetable series')];
  el.innerHTML = `
    <div class="intro-half top"></div><div class="intro-half bottom"></div>
    <div class="intro-stage">
      <div class="intro-grid">${[12.5, 25, 37.5, 50, 62.5, 75, 87.5].map((x, i) => `<i class="v" style="left:${x}%;--d:${i}"></i>`).join('')}${[20, 40, 60, 80].map((y, i) => `<i class="h" style="top:${y}%;--d:${i}"></i>`).join('')}</div>
      <div class="intro-scan"></div>
      <div class="intro-corner tl"><b></b>Examdata <span style="opacity:.5">/ v2</span></div>
      <div class="intro-corner tr"><button class="intro-skip" type="button">${L('跳过', 'Skip')}<kbd>Esc</kbd></button></div>
      <div class="intro-stream" aria-hidden="true"></div>
      <div class="intro-center"><div class="intro-word" aria-label="Examdata">${[...word].map((c, i) => `<span class="ch"><i style="--d:${i}">${c}</i></span>`).join('')}<span class="dot" style="--d:${word.length}">.</span></div><div class="intro-tag" aria-hidden="true"></div></div>
      <div class="intro-counters">${labels.map(l => `<div><span>${l}</span><b>000</b></div>`).join('')}</div>
      <div class="intro-progress"><span>${L('正在载入索引', 'Indexing')} <b>000</b>%</span><div><i></i></div></div>
    </div>
    <div class="intro-seam"></div>`;
  document.body.append(el);
  document.documentElement.classList.remove('intro-pending');
  const shell = $('.shell'); shell.inert = true;
  const timers = []; const at = (ms, fn) => timers.push(setTimeout(fn, ms));
  let done = false, raf = 0, stream = 0;
  const cleanup = () => { el.remove(); shell.inert = false; document.removeEventListener('keydown', onKey, true); };
  const finish = fast => {
    if (done) return; done = true;
    timers.forEach(clearTimeout); clearInterval(stream); cancelAnimationFrame(raf);
    el.classList.add('leaving', 'seam');
    setTimeout(() => { el.classList.add('split'); shell.classList.remove('revealing'); void shell.offsetWidth; shell.classList.add('revealing'); }, fast ? 140 : 360);
    setTimeout(() => { cleanup(); shell.classList.remove('revealing'); }, fast ? 1000 : 1250);
  };
  const onKey = e => { if (['Escape', 'Enter', ' '].includes(e.key)) { e.preventDefault(); finish(true); } };
  document.addEventListener('keydown', onKey, true);
  el.addEventListener('click', () => finish(true));
  $('.intro-skip', el).focus({ preventScroll: true });
  requestAnimationFrame(() => el.classList.add('go'));
  at(3400, () => finish(false)); // hard cap if the font never arrives

  // Wordmark waits briefly for the serif so letters don't swap fonts mid-rise.
  // Exit is timed from the wordmark so it always finishes rising first.
  Promise.race([document.fonts?.load('400 120px "Instrument Serif"') || Promise.resolve(), sleep(1000)]).then(() => { if (done) return; el.classList.add('word'); at(1500, () => finish(false)); });

  // Subject stream on the left.
  await ready.catch(() => {});
  const pool = [...store.cieSubjects.map(s => [s.code, s.title]), ...store.edexcelSubjects.map(s => [s.code, s.title])];
  const box = $('.intro-stream', el); let k = 0;
  if (pool.length) stream = setInterval(() => {
    const [code, title] = pool[(k++ * 7) % pool.length];
    box.insertAdjacentHTML('beforeend', `<div><b>${esc(code)}</b>${esc(title.toUpperCase())}<i>✓</i></div>`);
    while (box.children.length > 16) box.firstElementChild.remove();
  }, 45);

  // Real counts, scrambling up to their value.
  const s = store.stats?.catalog ? store.stats : await Promise.race([statsPromise || loadStats(), sleep(500)]);
  const targets = [s?.questions?.total, s?.papers, s?.timetable ? s.timetable.cie + s.timetable.edexcel : null];
  const nums = $$('.intro-counters b', el), pct = $('.intro-progress b', el), bar = $('.intro-progress i', el);
  const t0 = performance.now(), dur = 1250;
  const tick = now => {
    const t = Math.min((now - t0) / dur, 1), e = 1 - Math.pow(1 - t, 3);
    targets.forEach((v, i) => {
      if (v == null) { nums[i].textContent = '—'; return; }
      const shown = String(Math.round(v * e)).padStart(String(v).length, '0');
      // Not-yet-settled digits flicker.
      nums[i].textContent = t < 1 ? [...shown].map((d, j) => (j >= shown.length - 2 && Math.random() < .6 ? Math.floor(Math.random() * 10) : d)).join('') : fmt(v);
    });
    pct.textContent = String(Math.round(e * 100)).padStart(3, '0');
    bar.style.transform = `scaleX(${e})`;
    if (t < 1 && !done) raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);

  // Tagline decodes from noise.
  const tag = $('.intro-tag', el), text = L('每一份试卷 · 每一道题 · 一个索引', 'Every paper · every question · one index');
  const glyphs = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#%&/+';
  at(250, () => {
    const start = performance.now(), span = 650;
    const dec = now => {
      const p = Math.min((now - start) / span, 1), n = Math.floor(p * text.length);
      tag.innerHTML = esc(text.slice(0, n)) + `<span class="hot">${[...text.slice(n, n + 6)].map(c => (c === ' ' ? ' ' : glyphs[Math.floor(Math.random() * glyphs.length)])).join('')}</span>`;
      if (p < 1 && !done) requestAnimationFrame(dec); else if (p >= 1) tag.textContent = text;
    };
    requestAnimationFrame(dec);
  });
}

/* ============ command palette ============ */
const palette = $('#palette'), pInput = $('#palette-input'), pList = $('#palette-list');
let pItems = [], pActive = 0;
function paletteRender() {
  const term = pInput.value.trim();
  const groups = [];
  const pages = NAV().filter(([, , , n]) => !term || n.toLowerCase().includes(term.toLowerCase())).map(([, href, ic, label]) => ({ label, href, ic, hint: L('页面', 'PAGE') }));
  if (/^\d{1,7}$/.test(term) && term.length !== 4) groups.push([L('题目', 'Question'), [{ label: L(`打开题目 #${term}`, `Open question #${term}`), href: `#/q/${term}`, ic: icon.hash, hint: 'ID' }]]);
  if (term) {
    const subj = ['cie', 'edexcel'].flatMap(b => subjectMatches(subjectsFor(b), term).slice(0, 6).map(s => ({ label: subjName(s), href: `#/papers?board=${b}&subject=${encodeURIComponent(s.code)}`, ic: icon.doc, hint: `${b === 'cie' ? 'CIE' : 'EDX'} ${s.code}` })));
    if (subj.length) groups.push([L('科目试卷', 'Subject papers'), subj.slice(0, 8)]);
    groups.push([L('题库', 'Questions'), [{ label: L(`搜索题目：“${term}”`, `Search questions for “${term}”`), href: `#/questions?keyword=${encodeURIComponent(term)}`, ic: icon.search, hint: L('全文', 'TEXT') }]]);
    if (/^\d{4}$/.test(term) || /^w[a-z]{2}\d/i.test(term)) groups.push([L('时间表', 'Timetable'), [{ label: L(`${term.toUpperCase()} 的考试安排`, `${term.toUpperCase()} exam sessions`), href: `#/timetable?board=${/^\d/.test(term) ? 'cie' : 'edexcel'}&subject=${encodeURIComponent(term.toUpperCase())}`, ic: icon.cal, hint: L('日程', 'DATES') }]]);
  }
  if (!term || /intro|replay|开场|动画|重播/i.test(term)) groups.push([L('操作', 'Actions'), [{ label: L('重播开场动画', 'Replay intro'), run: () => playIntro(true), ic: icon.clock, hint: 'INTRO' }]]);
  if (pages.length) groups.unshift([L('页面', 'Pages'), pages]);
  pItems = groups.flatMap(([, items]) => items);
  pActive = Math.min(pActive, Math.max(0, pItems.length - 1));
  let i = 0;
  pList.innerHTML = groups.map(([name, items]) => `<div class="palette-group">${name}</div>` + items.map(it => `<button class="palette-item" role="option" data-i="${i}" aria-selected="${i++ === pActive}">${it.ic}<span>${esc(it.label)}</span><small>${esc(it.hint)}</small></button>`).join('')).join('') || `<div class="combo-empty">${L('没有结果', 'No results')}</div>`;
}
function paletteOpen() { if (palette.open) return; pInput.value = ''; pActive = 0; paletteRender(); palette.showModal(); pInput.focus(); }
function paletteGo(i) { const it = pItems[i]; if (!it) return; palette.close(); if (it.run) return it.run(); if (location.hash === it.href) route(); else location.hash = it.href; }
pInput.addEventListener('input', () => { pActive = 0; paletteRender(); });
pInput.addEventListener('keydown', e => {
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); pActive = (pActive + (e.key === 'ArrowDown' ? 1 : -1) + pItems.length) % (pItems.length || 1); $$('.palette-item', pList).forEach((b, i) => b.setAttribute('aria-selected', String(i === pActive))); $(`.palette-item[data-i="${pActive}"]`, pList)?.scrollIntoView({ block: 'nearest' }); }
  if (e.key === 'Enter') { e.preventDefault(); paletteGo(pActive); }
});
pList.addEventListener('click', e => { const b = e.target.closest('[data-i]'); if (b) paletteGo(Number(b.dataset.i)); });
palette.addEventListener('click', e => { if (e.target === palette) palette.close(); });
$('#open-palette-top').addEventListener('click', paletteOpen);
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); paletteOpen(); }
  else if (e.key === '/' && !/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName) && !palette.open) { e.preventDefault(); paletteOpen(); }
  else if (e.key === 'Escape' && !palette.open) { if ($('#sidebar').classList.contains('open')) toggleDrawer(false); else if ($('#peek').classList.contains('open')) closePeek(); }
});

/* ============ boot ============ */
function toggleDrawer(open = !$('#sidebar').classList.contains('open')) {
  $('#sidebar').classList.toggle('open', open);
  $('#scrim').classList.toggle('on', open || $('#peek').classList.contains('open'));
}
$('#menu').addEventListener('click', () => toggleDrawer());
renderChrome();
statsPromise = loadStats();
playIntro();
if (!$('#intro')) document.documentElement.classList.remove('intro-pending');
route();
