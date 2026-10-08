import {resolveSubject,subjectMatches,normalizePaper,groupPapers,subjectLabel} from './search.mjs';
import {searchDocuments,clientEnabled,fetchEnvelope,ApiClientError} from './client.mjs';
const $ = id => document.getElementById(id);
setupOpening();
const esc = v => String(v ?? '').replace(/[&<>"']/g,c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeUrl = value => {try {const u = new URL(value);return ['http:','https:'].includes(u.protocol) ? u.href : '';} catch {return '';}};
const seasonName = s => ({jun:'June',june:'June',nov:'November',november:'November',mar:'March',march:'March',jan:'January',january:'January',oct:'October',october:'October'}[String(s || '').toLowerCase()] || s || '—');
let catalog = [], cieSubjects = [], edexcelSubjects = [], subjects = [], rows = [], filtered = [], grouped = [], page = 0, requestId = 0, syllabi = null, liveSyllabus = null;
const pageSize = 10;
const documentLabel = type => ({question_paper:'QP 试卷',mark_scheme:'MS 评分标准',examiner_report:'ER 考官报告',grade_threshold:'GT 分数线'}[type] || '资料');
function sessionExtras() {return catalog.filter(r=>r.type==='examiner_report' && r.board===submitted.board && r.code===subjectCode(submitted.subject) && String(r.year)===submitted.year && (!submitted.season || seasonName(r.season)===seasonName(submitted.season)));}
let submitted = {board:'cie',subject:'',year:'',season:'',paper:''};
function syllabusEntry(board,code) {const table = syllabi && (board === 'edexcel' ? syllabi.edexcel : syllabi.cie);const entry = table && code ? table[code] : null;return entry ? {board,subject:code,title:entry.title || code,page:entry.page || '',syllabuses:entry.syllabuses || []} : null;}
function submittedSyllabus() {if (liveSyllabus) return liveSyllabus;if (!submitted.subject) return null;const list = submitted.board === 'edexcel' ? edexcelSubjects : cieSubjects;const code = resolveSubject(list,submitted.subject,submitted.board).code;return code ? syllabusEntry(submitted.board,code) : null;}
function syllabusStrip(info) {if (!info) return '';const links = (info.syllabuses || []).map(s => {const url = safeUrl(s.url);return url ? `<a class="document-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(s.title || 'Syllabus')} <span>↗</span></a>` : '';}).join('');const page = safeUrl(info.page || '');const body = links || (page ? `<a class="document-link" href="${esc(page)}" target="_blank" rel="noopener noreferrer">${esc(info.title || '科目页')} · 科目页 <span>↗</span></a>` : '');return body ? `<div class="syllabus-strip"><span class="syllabus-label">考纲</span><div class="document-actions">${body}</div></div>` : '';}
function formValues() {const values=Object.fromEntries(['board','subject','year','season','paper'].map(k => [k,$(k).value.trim()]));values.paper=normalizePaper(values.paper,values.board);return values;}
function empty(title,message,extra = '') {$('results').innerHTML = `<div class="empty"><h3>${esc(title)}</h3><p>${esc(message)}</p>${extra}</div>`;}
function subjectCode(value) {return resolveSubject(subjects,value,$('board').value).code;}
function render() {
  grouped=groupPapers(filtered);rows = grouped.slice(page * pageSize,(page + 1) * pageSize);$('result-count').textContent = `${grouped.length} 组资料 · ${filtered.length} 份文件`;
  const canLive = submitted.subject && submitted.year;
  if (!rows.length) return empty('没有找到符合条件的资料','可以调整查询条件。如果已填写科目和年份，也可以直接查找来源中的试卷。',(canLive ? '<button class="primary" id="live-search">查找原始试卷 ↗</button>' : '') + syllabusStrip(submittedSyllabus()));
  $('results').innerHTML = `${canLive?'<div class="resource-summary">'+['question_paper','mark_scheme','examiner_report','grade_threshold'].map(type=>'<span class="'+(filtered.some(d=>d.type===type)?'available':'')+'">'+documentLabel(type)+' · '+(filtered.some(d=>d.type===type)?'已找到':'来源未提供')+'</span>').join('')+'</div>':''}${syllabusStrip(submittedSyllabus())}<div class="table-wrap"><table><thead><tr><th>科目 / 试卷</th><th>考季</th><th>卷号</th><th>QP / MS / ER / GT</th></tr></thead><tbody>${rows.map((r,i) => `<tr style="--row:${i}" data-detail="${i}"><td class="subject-column"><button class="title-button" data-detail="${i}"><span class="file-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3h9l5 5v16H5zM14 3v6h5M9 13h6M9 17h4"/></svg></span><span><strong>${esc(r.origin==='live' ? (subjects.find(s=>s.code===r.code) ? subjectLabel(subjects.find(s=>s.code===r.code)) : r.code) : r.title)}</strong><span class="meta">${esc(r.code)} · ${esc(r.qualification || (r.board === 'cie' ? 'Cambridge' : 'Edexcel'))}</span></span></button></td><td><span class="year-label">${esc(r.year || '—')}</span><span class="meta">${esc(seasonName(r.season))}</span></td><td><span class="paper-tag">${esc(r.paper || (r.type==='grade_threshold' && r.board==='edexcel'?'全科分数线':'整季资料'))}</span></td><td><div class="document-actions">${r.documents.map(d=>safeUrl(d.url) ? `<a class="document-link ${d.type==='mark_scheme'?'answer-link':''}" href="${esc(safeUrl(d.url))}" target="_blank" rel="noopener noreferrer">${esc(documentLabel(d.type))} <span>↗</span></a>` : '').join('')}</div></td></tr>`).join('')}</tbody></table></div><div class="pager"><span>显示 ${page * pageSize + 1}–${Math.min((page + 1) * pageSize,grouped.length)}，共 ${grouped.length} 组</span><div><button data-page="-1" ${page === 0 ? 'disabled' : ''}>← 上一页</button><span>${page + 1} / ${Math.ceil(grouped.length / pageSize)}</span><button data-page="1" ${(page + 1) * pageSize >= grouped.length ? 'disabled' : ''}>下一页 →</button></div></div>${canLive && submitted.board === 'cie' && filtered[0]?.origin === 'catalog' ? '<p class="lookup-note">这是一份目录快照。<button id="live-search">查询来源中的最新文件 ↗</button></p>' : ''}`;
  animateResults();
}
function queryCatalog() {
  if (subjects !== ($('board').value === 'edexcel' ? edexcelSubjects : cieSubjects)) configureBoard(true);
  requestId++;page = 0;liveSyllabus = null;submitted = formValues();$('submit').disabled = false;$('results').setAttribute('aria-busy','false');
  closeSuggestions();
  if (submitted.subject && submitted.year) {
    const resolution=resolveSubject(subjects,submitted.subject,submitted.board);
    if (!resolution.code) {
      $('results-title').textContent='选择具体科目';$('results-note').textContent='从下方选择课程即可，无需记忆代码。';$('result-count').textContent='';
      empty(resolution.matches.length?'选择你要查的课程':'请选择科目',resolution.matches.length?'请选择对应课程。':'点击科目输入框可浏览课程，也可以输入中文或英文名称。',resolution.matches.map(s=>`<button class="subject-choice" data-subject="${esc(s.code)}">${esc(subjectLabel(s))} <span>${esc(s.qualification)} · ${esc(s.code)}</span> ↗</button>`).join(''));
      return;
    }
    liveSearch();return;
  }
  if (submitted.board === 'edexcel') {
    if (!submitted.subject || !submitted.year) {$('results-title').textContent = '查询 Edexcel 试卷';$('results-note').textContent = '选择科目，查询 QP / MS / ER / GT';$('result-count').textContent = '';empty('选好条件，即可查找','点击科目框选择中文课程，再选择年份。所有考季会汇总该年资料，卷号选填。');return;}
    liveSearch();return;
  }
  const resolved=resolveSubject(subjects,submitted.subject,'cie');const matchingCodes=new Set(resolved.code?[resolved.code]:subjectMatches(subjects,submitted.subject).map(s=>s.code));
  filtered = catalog.filter(r => (!submitted.subject || matchingCodes.has(r.code)) && (!submitted.year || String(r.year) === submitted.year) && (!submitted.season || seasonName(r.season) === seasonName(submitted.season)) && (!submitted.paper || r.type==='examiner_report' || normalizePaper(r.paper) === submitted.paper));
  $('results-title').textContent = ['subject','year','season','paper'].some(k => submitted[k]) ? '查询结果' : '浏览试卷';$('results-note').textContent = 'CIE 官方目录 · 2026.10.01 快照；目录收录不表示题目已解析。';render();
}
async function liveSearch() {
  const id = ++requestId;const query = {...submitted,subject:subjectCode(submitted.subject)};
  if (!query.subject || !query.year) return;
  $('submit').disabled = true;$('results').setAttribute('aria-busy','true');$('result-count').textContent = '';$('results-title').textContent = '查询结果';$('results-note').textContent = '正在查找 QP / MS / ER / GT…';$('results').innerHTML = '<div class="loading">正在查找来源中的试卷…</div>';
  try {
    if (!clientEnabled()) {if (id !== requestId) return;filtered = sessionExtras();if (filtered.length) {render();$('results-note').textContent = '在线查询已关闭（examdata.v2-client=off） · 下方仅显示目录快照中的 ER';} else empty('在线查询已关闭','在线查询已关闭（examdata.v2-client=off）。移除浏览器标记后可重试。');return;}
    const result = await searchDocuments(query);if (id !== requestId) return;liveSyllabus = result.syllabus || null;
    filtered = (result.documents || []).map(d=>({...d,code:query.subject,url:safeUrl(d.url)}));
    for(const extra of sessionExtras()) {if(!filtered.some(d=>d.type==='examiner_report' && seasonName(d.season)===seasonName(extra.season))) filtered.push(extra);}
    page = 0;$('results-note').textContent = `${query.subject} · ${query.year} · ${query.season?seasonName(query.season):'所有考季'}${query.paper?' · Paper '+query.paper:''} / ${result.origin === 'staged_fixture' ? '暂存夹具验证（staged fixture validation）· 合成夹具数据' : '原始来源文件'} · ER/GT 按文件适用范围显示${result.warning?' · '+result.warning:''}`;
    if (!filtered.length) {$('result-count').textContent = '0 份资料';empty('没有找到对应试卷','请检查科目、年份、考季与卷号。');} else render();
  } catch (e) {if (id === requestId) {$('results-note').textContent = '本次在线查询未完成';filtered=sessionExtras();if(filtered.length) {render();$('results-note').textContent=e.message+' · 下方仅显示目录快照中的 ER';}else empty('暂时无法获取试卷',e.message,syllabusStrip(submittedSyllabus()));}}
  finally {if (id === requestId) {$('results').setAttribute('aria-busy','false');$('submit').disabled = false;}}
}
function detail(row) {
  $('detail-body').innerHTML = `<span class="source-text">${row.origin === 'catalog' ? 'OFFICIAL CATALOG' : row.quality === 'synthetic_fixture' ? 'STAGED FIXTURE · 合成夹具' : 'ORIGINAL SOURCE'}</span><h2>${esc(row.origin==='live'?row.code:row.title)}</h2><dl><dt>考试局</dt><dd>${row.board === 'cie' ? 'Cambridge International' : 'Pearson Edexcel'}</dd><dt>科目代码</dt><dd>${esc(row.code)}</dd><dt>年份 / 考季</dt><dd>${esc(row.year || '—')} / ${esc(seasonName(row.season))}</dd><dt>卷号</dt><dd>${esc(row.paper || '—')}</dd></dl><p class="detail-note">${row.origin === 'catalog' ? '来自 2026 年 10 月 1 日的官方资源目录快照。文件可用性以来源站点为准。' : '来自本次查询返回的原始文件清单。'}</p><div class="document-actions">${row.documents.map(d=>safeUrl(d.url)?`<a class="primary" href="${esc(safeUrl(d.url))}" target="_blank" rel="noopener noreferrer">${esc(documentLabel(d.type))} ↗</a>`:'').join('')}</div>${syllabusStrip(syllabusEntry(row.board,row.code) || submittedSyllabus())}`;$('detail').showModal();
}
$('query-form').onsubmit = e => {e.preventDefault();queryCatalog();};
function configureBoard(keepValues = false) {const edx = $('board').value === 'edexcel';const season = keepValues ? $('season').value : '';subjects=edx?edexcelSubjects:cieSubjects;$('subject-hint').textContent=edx?'点击选择 IAL 科目 · 中文名自动匹配 · 卷号选填':'点击选择课程 · 数学默认 A Level 9709 · 可切换 IGCSE';const seasons = edx ? ['January','June','October','November'] : ['Jun','Nov','Mar'];$('season').innerHTML = '<option value="">所有考季</option>' + seasons.map(s => `<option value="${s}">${seasonName(s)}</option>`).join('');if (season && [...$('season').options].some(o => o.value === season)) $('season').value = season;if (!keepValues) {$('subject').value='';$('paper').value='';}$('subject').placeholder = edx ? '点击选择科目，如数学 / 经济' : '输入科目、中文名或代码';$('paper').placeholder = edx ? '如 wec11-01' : '如 11 / Paper 11';closeSuggestions();}
$('reset').onclick = () => {$('query-form').reset();configureBoard();queryCatalog();};$('board').onchange = ()=>{configureBoard();queryCatalog();};
$('close-detail').onclick = () => $('detail').close();
$('detail').onclick = e => {if (e.target === $('detail')) {const r = e.target.getBoundingClientRect();if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) e.target.close();}};
document.addEventListener('click',e => {if (e.target.closest('a')) return;const row = e.target.closest('tr[data-detail]');if (row) {const selection = window.getSelection();if (!(selection && !selection.isCollapsed && selection.containsNode(row,true))) detail(rows[Number(row.dataset.detail)]);return;}const el = e.target.closest('button');if (!el) return;if (el.dataset.page) {page += Number(el.dataset.page);render();}if (el.id === 'live-search') liveSearch();if (el.dataset.subject) {chooseSubject(el.dataset.subject);if (el.classList.contains('subject-choice')) queryCatalog();}});
for (let year = 2026;year >= 2000;year--) $('year').add(new Option(String(year),String(year)));
function animateResults() {if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;$('results').animate([{opacity:0,transform:'translateY(8px)'},{opacity:1,transform:'translateY(0)'}],{duration:280,easing:'ease-out'});}
function closeSuggestions() {$('subject-options').hidden=true;$('subject').setAttribute('aria-expanded','false');$('subject').removeAttribute('aria-activedescendant');}
function chooseSubject(code) {const s=subjects.find(s=>s.code===code);$('subject').value=s?`${subjectLabel(s)} · ${s.qualification} · ${s.code}`:code;$('subject').focus();closeSuggestions();}
function suggestions() {
  const choices=subjectMatches(subjects,$('subject').value);
  $('subject-options').innerHTML=choices.map((s,i)=>`<button type="button" role="option" aria-selected="false" tabindex="-1" id="subject-option-${i}" data-subject="${esc(s.code)}"><span>${esc(subjectLabel(s))}</span><small>${esc(s.qualification)} <b>${esc(s.code)}</b></small></button>`).join('') || '<p class="suggestion-note">可直接输入四位科目代码查询。</p>';
  $('subject-options').hidden=false;$('subject').setAttribute('aria-expanded','true');activeOption=-1;
}
let activeOption=-1;
$('subject').oninput=suggestions;$('subject').onfocus=suggestions;
$('subject').onblur=closeSuggestions;
$('subject-options').onpointerdown=e=>e.preventDefault();
$('subject').onkeydown=e=>{
  const options=[...$('subject-options').querySelectorAll('[role="option"]')];
  if (e.key==='Escape') return closeSuggestions();
  if (e.key==='ArrowDown'||e.key==='ArrowUp') {e.preventDefault();if ($('subject-options').hidden) suggestions();const items=[...$('subject-options').querySelectorAll('[role="option"]')];if (!items.length) return;activeOption=(activeOption+(e.key==='ArrowDown'?1:-1)+items.length)%items.length;items.forEach((el,i)=>el.setAttribute('aria-selected',String(i===activeOption)));$('subject').setAttribute('aria-activedescendant',items[activeOption].id);items[activeOption].scrollIntoView({block:'nearest'});}
  if (e.key==='Enter'&&!$('subject-options').hidden&&activeOption>=0&&options[activeOption]) {e.preventDefault();chooseSubject(options[activeOption].dataset.subject);}
};
document.addEventListener('pointerdown',e=>{if (!e.target.closest('.subject-field')) closeSuggestions();});
try {const response = await fetch('/syllabi.json');if (response.ok) syllabi = await response.json();} catch {}
try {const response = await fetch('/catalog.json');if (!response.ok) throw new Error('目录快照加载失败');const data=await response.json();catalog=data.items;edexcelSubjects=data.edexcelSubjects || [];cieSubjects=[...new Map(catalog.map(r=>[r.code,{code:r.code,title:r.title,qualification:r.qualification || ''}])).values()].sort((a,b)=>a.title.localeCompare(b.title));subjects=cieSubjects;const popular=['9709','0580','9702','9701','9700','0455'];catalog.sort((a,b)=>{const ai=popular.indexOf(a.code),bi=popular.indexOf(b.code);return (ai<0?100:ai)-(bi<0?100:bi);});configureBoard(true);queryCatalog();} catch(e) {$('results').setAttribute('aria-busy','false');empty('暂时无法加载目录',e.message);}

function setupOpening() {
  const overlay=$('opening'),canvas=$('opening-canvas'),skip=$('skip-opening'),replay=$('replay-opening');
  const motion=matchMedia('(prefers-reduced-motion: reduce)');
  const ctx=canvas.getContext('2d');
  const content=[document.querySelector('.site-header'),document.querySelector('main')];
  const duration=2450;
  let frame=0,timer=0,finishTimer=0,failsafe=0,startTime=0,active=false,returnFocus=null,width=0,height=0,particles=[];
  const colors={ink:'#111827',blue:'#2563eb',gray:'#f4f6f8'};
  const ease=t=>1-Math.pow(1-Math.max(0,Math.min(1,t)),4);
  function resize() {
    width=innerWidth;height=innerHeight;
    const ratio=Math.min(devicePixelRatio || 1,2);
    canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);ctx.setTransform(ratio,0,0,ratio,0,0);
    const scale=width<540?.76:1;
    const centerX=width/2,centerY=height/2-69*scale;
    const segments=[[-32,-45,34,-45],[-32,0,20,0],[-32,45,34,45],[-32,-45,-32,45]];
    particles=[];
    segments.forEach(([x1,y1,x2,y2],line)=>{
      const count=Math.ceil(Math.hypot(x2-x1,y2-y1)/3.1);
      for(let j=0;j<=count;j++) {
        const index=particles.length,angle=index*2.39996323,radius=Math.min(width,height)*(.18+(index%17)/52);
        particles.push({x:centerX+(x1+(x2-x1)*j/count)*scale,y:centerY+(y1+(y2-y1)*j/count)*scale,sx:centerX+Math.cos(angle)*radius,sy:centerY+Math.sin(angle)*radius,delay:(index%9)*.012,blue:index%13===0,size:index%7===0?2.2:1.45});
      }
    });
  }
  function draw(now) {
    if(!active) return;
    const elapsed=now-startTime,t=Math.min(elapsed/duration,1);
    const phase=elapsed<1500?'assembling':elapsed<2100?'identity':'reveal';
    if(overlay.dataset.phase!==phase) overlay.dataset.phase=phase;
    ctx.clearRect(0,0,width,height);
    const gather=ease((elapsed-160)/1150),scatter=ease((elapsed-2040)/400);
    particles.forEach((p,index)=>{
      const g=ease(Math.max(0,gather-p.delay)/(1-p.delay));
      const swirl=(1-g)*.48,dx=p.sx-width/2,dy=p.sy-(height/2-(width<540?52.44:69));
      const x=p.sx+(p.x-p.sx)*g+Math.sin(index+elapsed*.0014)*(1-g)*16+(Math.cos(swirl)*dx-Math.sin(swirl)*dy-dx)*(1-g);
      const y=p.sy+(p.y-p.sy)*g+Math.cos(index+elapsed*.0012)*(1-g)*16+(Math.sin(swirl)*dx+Math.cos(swirl)*dy-dy)*(1-g);
      ctx.globalAlpha=Math.min(elapsed/350,1)*(1-scatter)*(.5+.5*g);
      ctx.fillStyle=p.blue?colors.blue:colors.ink;
      ctx.fillRect(x-p.size/2,y-p.size/2,p.size,p.size);
      if(g<.85 && index%6===0) {
        ctx.globalAlpha*=.16;ctx.strokeStyle=colors.ink;ctx.lineWidth=.5;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(p.x,p.y);ctx.stroke();
      }
    });
    ctx.globalAlpha=1;
    $('opening-progress').style.transform=`scaleX(${t})`;
    $('opening-counter').textContent=String(Math.round(t*100)).padStart(3,'0');
    if(t<1) frame=requestAnimationFrame(draw);else finish();
  }
  function unlock() {
    content.forEach(el=>{if(el) el.inert=false;});
    document.body.classList.remove('opening-active');
  }
  function release() {
    clearTimeout(finishTimer);clearTimeout(failsafe);overlay.hidden=true;overlay.dataset.phase='complete';overlay.classList.remove('is-running','is-leaving');
    unlock();
    if(returnFocus instanceof HTMLElement && returnFocus.isConnected) returnFocus.focus({preventScroll:true});
    returnFocus=null;
  }
  function finish(immediate=false) {
    if(!active && overlay.hidden) return;
    active=false;cancelAnimationFrame(frame);clearTimeout(timer);
    unlock();
    if(immediate || motion.matches) return release();
    overlay.classList.add('is-leaving');document.body.classList.remove('opening-active');
    finishTimer=setTimeout(release,460);
  }
  function play() {
    if(active) return;
    clearTimeout(finishTimer);clearTimeout(failsafe);returnFocus=document.activeElement===replay?replay:null;
    if(motion.matches || !ctx) {release();return;}
    active=true;content.forEach(el=>{if(el) el.inert=true;});document.body.classList.remove('opening-complete');document.body.classList.add('opening-active');
    overlay.hidden=false;overlay.dataset.phase='assembling';overlay.classList.remove('is-running','is-leaving');
    // Recreate CSS animations for replay without altering the search form or results.
    void overlay.offsetWidth;overlay.classList.add('is-running');resize();startTime=performance.now();skip.focus({preventScroll:true});
    frame=requestAnimationFrame(draw);timer=setTimeout(()=>finish(),duration+350);
    failsafe=setTimeout(()=>{if(active) finish(true);else if(!overlay.hidden) release();else unlock();},duration+1200);
  }
  skip.onclick=()=>finish();replay.onclick=play;
  document.addEventListener('keydown',e=>{if(!overlay.hidden && e.key==='Escape') {e.preventDefault();finish();}else if(!overlay.hidden && e.key==='Tab') {e.preventDefault();skip.focus();}});
  addEventListener('resize',()=>{if(active) resize();});
  addEventListener('pagehide',()=>finish(true));
  document.addEventListener('pointerdown',()=>{if(overlay.hidden || overlay.classList.contains('is-leaving')) unlock();},true);
  document.addEventListener('visibilitychange',()=>{if(!overlay.hidden && (document.hidden || performance.now()-startTime>duration+400)) finish(true);else if(overlay.hidden) unlock();});
  motion.addEventListener('change',()=>{if(motion.matches) finish(true);});
  play();
}

// ---- Staged integration journeys (private closure build, Part B) ----
// Five read-only journeys walk the staged /api/v2 surface through this same
// origin and render what the staged fixture declares, including the steps it
// declares unavailable. Nothing is inferred from similarity, stop details and
// internal source fields are deliberately not rendered, and the browser never
// contacts an upstream source.

const JOURNEY_RUN = {id: 0};
const JOURNEY_NAMES = ['sources', 'ielts', 'toefl', 'library', 'diagnostics'];
const jblobs = {};
let journeyName = null;
let jseq = 0;

const jbadge = (state, label) => `<span class="jbadge ${state}"><i></i>${esc(label)}</span>`;
const jnull = () => '<span class="jnull">—</span>';
const jval = v => v === null || v === undefined || v === '' ? jnull() : esc(String(v));
const jcode = code => `<code class="jcode">${esc(String(code ?? ''))}</code>`;
const jshort = value => {const text = String(value ?? '');return esc(text.length > 18 ? `${text.slice(0, 18)}…` : text);};
const jtrue = () => '<span class="jcheck ok">✓ 一致</span>';
const jfalse = () => '<span class="jcheck no">✗ 不一致</span>';

function jtable(head, cells) {
  return `<div class="jtable-wrap"><table class="jtable"><thead><tr>${head.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${cells.map(row => `<tr>${row.map(cell => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}

function jgaps(list) {
  if (!Array.isArray(list) || !list.length) return '';
  return `<ul class="jgaps">${list.map(gap => `<li>${jcode(gap.code || 'gap')} ${esc(gap.detail || '')} <span class="jmeta">${[
    gap.scope ? `scope=${esc(gap.scope)}` : '',
    gap.source ? `source=${esc(gap.source)}` : '',
    gap.ref ? `ref=${jshort(gap.ref)}` : '',
    gap.system ? `system=${esc(gap.system)}` : ''
  ].filter(Boolean).join(' · ')}</span></li>`).join('')}</ul>`;
}

function jmetaline(meta) {
  const warnings = meta && Array.isArray(meta.warnings) ? meta.warnings.map(String) : [];
  const completeness = meta && meta.completeness ? meta.completeness : '—';
  return `<p class="jmeta">completeness=${esc(completeness)} · warnings: ${warnings.length ? warnings.map(warning => esc(warning)).join(' / ') : '（空）'}</p>`;
}

function jsummary(value) {
  if (value === null || value === undefined) return jnull();
  if (Array.isArray(value)) return esc(`${value.length} 项`);
  if (typeof value === 'object') {
    const parts = Object.entries(value).filter(([, entry]) => entry !== undefined).map(([key, entry]) => `${esc(key)}=${Array.isArray(entry) ? `${entry.length} 项` : entry === null ? '—' : esc(String(entry))}`);
    return parts.length ? parts.join(' · ') : jnull();
  }
  return esc(String(value));
}

function jlist(heading, items) {
  if (!items || !items.length) return '';
  return `<h4>${esc(heading)}</h4><ul class="jgaps">${items.map(item => `<li>${item}</li>`).join('')}</ul>`;
}

function jreason(text) {return `<p class="jreason">${esc(text)}</p>`;}

async function jcontent(path) {
  const response = await fetch(new URL(path, location.href));
  const buffer = await response.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let sha = null;
  try {sha = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(byte => byte.toString(16).padStart(2, '0')).join('');} catch {}
  let error = null;
  if (!response.ok) {try {const body = JSON.parse(new TextDecoder().decode(bytes)); if (body && body.error) error = {code: body.error.code || '', message: body.error.message || ''};} catch {}}
  return {ok: response.ok, status: response.status, type: response.headers.get('content-type') || '', size: bytes.length, sha, page: response.headers.get('x-page'), declared: (response.headers.get('x-content-sha256') || '').replace(/"/g, ''), buffer, error};
}

async function jattempt(path) {
  try {return {ok: true, result: await fetchEnvelope(path)};}
  catch (error) {if (error instanceof ApiClientError) return {ok: false, error};throw error;}
}

function jdeclaredError(error) {
  return `${jfalse()} <span class="jmeta">HTTP ${error.status || '—'} · ${jcode(error.code || 'unknown')} ${esc(error.message || '')}</span>`;
}

function jline(content) {
  const bits = [`HTTP ${content.status}`, esc(content.type || '无 content-type'), `${content.size} B`];
  if (content.page) bits.push(`page ${esc(String(content.page))}`);
  if (content.ok) {
    if (content.sha) bits.push(`实测 sha256 ${jshort(content.sha)}`);
    if (content.declared) bits.push(`声明 ${jshort(content.declared)} ${content.declared === content.sha ? jtrue() : jfalse()}`);
    else bits.push('响应头无 x-content-sha256');
  } else if (content.error) {
    bits.push(`${jcode(content.error.code)} ${esc(content.error.message)}`);
  }
  return `<span class="jmeta">${bits.join(' · ')}</span>`;
}

function jcropimage(content, journey, alt) {
  let src = '';
  try {
    src = URL.createObjectURL(new Blob([content.buffer], {type: content.type || 'image/png'}));
    (jblobs[journey] = jblobs[journey] || []).push(src);
  } catch {
    return `<p class="jreason">crop 字节已到达（${content.size} B）但无法生成对象 URL，未渲染图像。</p>${jline(content)}`;
  }
  return `<figure class="jcrop"><img src="${esc(src)}" alt="${esc(alt)}"><figcaption>${jline(content)}</figcaption></figure>`;
}

function janswers(envelope) {
  const data = envelope && envelope.data ? envelope.data : {};
  const items = Array.isArray(data.items) ? data.items : [];
  const gaps = Array.isArray(data.gaps) ? data.gaps : [];
  let html = `<p class="jmeta">answers items: ${items.length} 条</p>`;
  if (items.length) html += jtable(['question_ref', 'original_value', 'matching_method', 'verification', 'alternatives', 'conflicts'], items.map(item => [
    jval(item.question_ref), jval(item.original_value), jval(item.matching_method), jval(item.verification),
    Array.isArray(item.alternatives) && item.alternatives.length ? esc(item.alternatives.map(String).join(' / ')) : jnull(),
    Array.isArray(item.conflicts) && item.conflicts.length ? esc(item.conflicts.map(conflict => `${conflict.source}=${conflict.value}`).join(' / ')) : jnull()
  ]));
  return html + jgaps(gaps);
}

function jregions(envelope) {
  const data = envelope && envelope.data ? envelope.data : {};
  const items = Array.isArray(data.items) ? data.items : [];
  const gaps = Array.isArray(data.gaps) ? data.gaps : [];
  let html = `<p class="jmeta">regions items: ${items.length} 条</p>`;
  if (items.length) html += jtable(['page', 'bbox', 'coordinate_system', 'document_role', 'document_sha256', 'evidence_status'], items.map(item => [
    jval(item.page),
    Array.isArray(item.bbox) && item.bbox.length ? esc(item.bbox.join(', ')) : `${jnull()}（bbox 缺失）`,
    jval(item.coordinate_system), jval(item.document_role), jshort(item.document_sha256 || ''), jval(item.evidence_status)
  ]));
  return html + jgaps(gaps);
}

function jaudio(envelope) {
  const data = envelope && envelope.data ? envelope.data : {};
  const items = Array.isArray(data.items) ? data.items : [];
  const warnings = envelope && envelope.meta && Array.isArray(envelope.meta.warnings) ? envelope.meta.warnings.map(String) : [];
  return `<p class="jmeta">audio items: ${items.length} 条 · alignment=${data.alignment === null || data.alignment === undefined ? 'null' : jsummary(data.alignment)} · association=${data.association === null || data.association === undefined ? 'null' : jsummary(data.association)}</p>`
    + (warnings.length ? `<p class="jreason">${esc(warnings.join(' / '))}</p>` : '');
}

async function jresourceChecks(data) {
  const items = Array.isArray(data.items) ? data.items : [];
  let ok = 0, declared = 0, checked = 0, failed = 0, headerMissing = 0;
  const cells = [];
  for (const item of items) {
    const content = item.content && typeof item.content === 'object' ? item.content : {};
    const link = item.content_link || (item.links && item.links.content) || '';
    let verdict = jnull();
    let detail = '';
    if (item.content_available === false || !link) {
      verdict = '<span class="jmeta">声明无内容链接</span>';
      declared += 1;
    } else {
      const fetched = await jcontent(link);
      checked += 1;
      const bytesMatch = Boolean(fetched.sha && content.sha256 && fetched.sha === content.sha256);
      if (!fetched.ok) {verdict = jfalse();failed += 1;detail = jline(fetched);}
      else if (!fetched.sha) {verdict = '<span class="jmeta">已取字节（本环境无法计算 SHA-256）</span>';detail = jline(fetched);}
      else if (!fetched.declared) {
        headerMissing += 1;
        if (bytesMatch) {verdict = '<span class="jmeta">字节一致 · 响应头不可观察</span>';ok += 1;}
        else {verdict = jfalse();failed += 1;}
        detail = jline(fetched) + '<span class="jmeta"> · 响应头 x-content-sha256 不经暂存前端代理透传（server.mjs 仅透传 content-type / content-disposition），头级校验不可观察，未做推断</span>';
      }
      else if (bytesMatch && fetched.declared === fetched.sha) {verdict = jtrue();ok += 1;detail = jline(fetched);}
      else {verdict = jfalse();failed += 1;detail = jline(fetched);}
    }
    cells.push([jval(item.role), jval(item.public_id), jshort(item.sha256 || ''), jshort(content.sha256 || ''), content.byte_size != null ? String(content.byte_size) : jnull(), verdict, detail]);
  }
  const html = jtable(['role', 'public_id', '夹具声明 sha256', 'content.sha256', '声明字节数', '校验', '响应'], cells)
    + jgaps(data.gaps)
    + '<p class="jmeta">校验口径：实测字节 SHA-256 与 content.sha256 一致，并尽可能与响应头 x-content-sha256 一致；响应头不经暂存前端代理（server.mjs）透传时按声明标注"不可观察"，不推断头值。resources[].sha256 是夹具合成占位值（如 2222…），与真实字节不应等同。</p>';
  return {html, ok, declared, checked, failed, headerMissing, count: items.length};
}

async function jquestionChain(question, journey) {
  const id = question.public_id;
  const links = question.links || {};
  const counts = {detailOk: 0, answersOk: 0, regionsOk: 0, audioOk: 0, cropOk: 0, cropDeclared: 0, failures: 0};
  const parts = [`<header><strong>${esc(question.native_id || '')}</strong> <span class="jmeta">${esc(question.question_type || '')} · ${jshort(id)}</span></header>`];
  parts.push(question.stem ? `<p>${esc(question.stem)}</p>` : '<p class="jmeta">stem 缺失（null）——原样保留，不补写。</p>');
  const detailOutcome = await jattempt(links.self || `/api/v2/questions/${encodeURIComponent(id)}`);
  if (detailOutcome.ok) {
    counts.detailOk += 1;
    const data = detailOutcome.result.data || {};
    const item = data.item || null;
    parts.push(`<p>detail：${item ? `${jcode(item.system || '')} ${esc(item.question_type || '')} · parent=${jval(item.parent_native_id)} · container=${jshort(item.container_ref || '')}` : '响应没有 data.item'}</p>` + jgaps(data.gaps));
  } else {counts.failures += 1;parts.push(`<p class="jreason">detail 声明响应：${jdeclaredError(detailOutcome.error)}</p>`);}
  const answers = await jattempt(links.answers || `/api/v2/questions/${encodeURIComponent(id)}/answers`);
  if (answers.ok) {counts.answersOk += 1;parts.push('<h4>answers</h4>' + janswers(answers.result));}
  else {counts.failures += 1;parts.push(`<p class="jreason">answers 声明响应：${jdeclaredError(answers.error)}</p>`);}
  const regions = await jattempt(links.regions || `/api/v2/questions/${encodeURIComponent(id)}/regions`);
  if (regions.ok) {counts.regionsOk += 1;parts.push('<h4>regions</h4>' + jregions(regions.result));}
  else {counts.failures += 1;parts.push(`<p class="jreason">regions 声明响应：${jdeclaredError(regions.error)}</p>`);}
  const audio = await jattempt(links.audio || `/api/v2/questions/${encodeURIComponent(id)}/audio`);
  if (audio.ok) {counts.audioOk += 1;parts.push('<h4>audio</h4>' + jaudio(audio.result));}
  else {counts.failures += 1;parts.push(`<p class="jreason">audio 声明响应：${jdeclaredError(audio.error)}</p>`);}
  const cropPath = links.crop || `/api/v2/questions/${encodeURIComponent(id)}/crop`;
  const crop = await jcontent(cropPath);
  if (crop.ok && crop.type.startsWith('image/') && crop.size > 0) {counts.cropOk += 1;parts.push(jcropimage(crop, journey, `crop ${id}`));}
  else {
    counts.cropDeclared += 1;
    parts.push(`<p class="jreason">crop 声明响应：HTTP ${crop.status}${crop.error ? ` · ${jcode(crop.error.code)} ${esc(crop.error.message)}` : ` · ${esc(crop.type || '无 content-type')}`}${links.crop ? '' : '（该题未声明 crop 链接，仍按约定路径请求）'}</p>`);
  }
  return {html: `<article class="jqcard">${parts.join('')}</article>`, counts};
}

function jjobcard(envelope) {
  const data = envelope && envelope.data ? envelope.data : {};
  const item = data.item;
  if (!item) return '<p class="jreason">响应没有 data.item 成员。</p>';
  const rows = [];
  const put = (key, value) => {if (value !== null && value !== undefined && value !== '') rows.push([key, esc(String(value))]);};
  put('public_id', item.public_id);
  put('system', item.system);
  put('scope', item.scope);
  put('scope_kind', item.scope_kind);
  put('scope_id', item.scope_id);
  put('stage', item.stage);
  put('state', item.state);
  put('freshness', item.freshness);
  put('stop_reason', item.stop_reason);
  if (item.resume_required !== undefined) put('resume_required', String(Boolean(item.resume_required)));
  if (item.resume && typeof item.resume === 'object') put('resume', `needs_user_resume=${Boolean(item.resume.needs_user_resume)}${item.resume.resume_policy ? ` · policy=${item.resume.resume_policy}` : ''}`);
  if (item.progress && typeof item.progress === 'object') put('progress', `done=${item.progress.done ?? '—'} / total=${item.progress.total ?? '—'}`);
  if (item.counters && typeof item.counters === 'object') put('counters', Object.entries(item.counters).map(([key, value]) => `${key}=${value}`).join(' / '));
  put('started_at', item.started_at);
  put('finished_at', item.finished_at);
  put('input_revision', item.input_revision);
  put('native_updated_at', item.native_updated_at);
  put('observed_at', item.observed_at);
  put('integration_status', item.integration_status);
  if (item.stop) put('stop', `${item.stop.reason || ''}${item.stop.stopped_at ? ` @ ${item.stop.stopped_at}` : ''}`);
  if (item.result && item.result.note) put('result.note', item.result.note);
  let html = jtable(['字段', '值'], rows);
  const superseded = Array.isArray(data.superseded) ? data.superseded : [];
  if (superseded.length) {
    html += '<h4>被取代的尝试（superseded）</h4>' + jtable(['stage', 'state', 'freshness', 'stop_reason', 'stop', 'resume', 'native_updated_at'], superseded.map(entry => [
      jval(entry.stage), jval(entry.state), jval(entry.freshness), jval(entry.stop_reason),
      entry.stop ? esc(`${entry.stop.reason || ''}${entry.stop.stopped_at ? ` @ ${entry.stop.stopped_at}` : ''}`) : jnull(),
      entry.resume ? esc(`needs_user_resume=${Boolean(entry.resume.needs_user_resume)}`) : jnull(),
      jval(entry.native_updated_at)
    ]));
  }
  const conflicts = Array.isArray(data.conflicts) ? data.conflicts.length : 0;
  html += `<p class="jmeta">conflicts: ${conflicts} · 只读观察：不恢复、不重试、不写入；stop 明细与内部来源字段刻意不渲染。</p>`;
  html += jmetaline(envelope.meta);
  return html;
}

async function jloadJob(button) {
  const target = document.getElementById(button.dataset.jtarget || '');
  if (!target) return;
  const original = button.textContent;
  button.disabled = true;
  button.textContent = '读取中…';
  target.innerHTML = '<p class="jmeta">正在读取声明的作业记录…</p>';
  const outcome = await jattempt('/api/v2/jobs/' + encodeURIComponent(button.dataset.jjob || ''));
  if (outcome.ok) target.innerHTML = jjobcard(outcome.result);
  else target.innerHTML = `<p class="jreason">声明响应：${jdeclaredError(outcome.error)}</p>`;
  button.disabled = false;
  button.textContent = original;
}

function journeySources() {
  const sc = {};
  return [
    {title: 'CIE 课程列表（/api/v2/courses?system=cie）', run: async () => {
      const env = await fetchEnvelope('/api/v2/courses?system=cie');
      const items = Array.isArray(env.data.items) ? env.data.items : [];
      sc.course = items[0] || null;
      const html = jtable(['public_id', 'system', 'native_code', 'names', 'qualification', 'specification_version', 'aliases', 'availability'], items.map(item => [
        jval(item.public_id), jval(item.system), jval(item.native_code), esc((item.names || []).join(' / ')), jval(item.qualification), jval(item.specification_version), esc((item.aliases || []).join(' / ')), jval(item.availability)
      ])) + jmetaline(env.meta);
      return {state: items.length ? 'available' : 'empty', label: `${items.length} 条课程`, html, note: ''};
    }},
    {title: 'CIE 大纲与内容字节（/api/v2/syllabuses?system=cie）', run: async () => {
      const env = await fetchEnvelope('/api/v2/syllabuses?system=cie');
      const items = Array.isArray(env.data.items) ? env.data.items : [];
      let html = jtable(['public_id', 'version', 'title', 'course_native_code', 'applicable_years', 'integration_status'], items.map(item => [
        jval(item.public_id), jval(item.version), jval(item.title), jval(item.course_native_code),
        Array.isArray(item.applicable_years) && item.applicable_years.length ? esc(item.applicable_years.join(', ')) : jnull(),
        jval(item.integration_status)
      ]));
      let okCount = 0;
      for (const item of items) {
        const content = await jcontent(`/api/v2/syllabuses/${encodeURIComponent(item.public_id)}/content`);
        if (content.ok) okCount += 1;
        html += `<p>${jcode(item.public_id)} content：${jline(content)}</p>`;
      }
      html += jmetaline(env.meta);
      return {state: items.length && okCount === items.length ? 'available' : 'partial', label: `大纲 ${items.length} 条 · 内容 ${okCount}/${items.length}`, html, note: ''};
    }},
    {title: 'CIE 容器（/api/v2/containers?system=cie）', run: async () => {
      const env = await fetchEnvelope('/api/v2/containers?system=cie');
      const items = Array.isArray(env.data.items) ? env.data.items : [];
      sc.container = items[0] || null;
      const html = jtable(['public_id', 'system', 'native_identity', 'question_refs', 'resources', 'sections'], items.map(item => [
        jval(item.public_id), jval(item.system), jsummary(item.native_identity),
        Array.isArray(item.question_refs) ? `${item.question_refs.length} 项` : jnull(),
        Array.isArray(item.resources) ? item.resources.map(entry => `${esc(entry.role)}=${jshort(entry.sha256 || '')}`).join(' · ') : jnull(),
        jsummary(item.sections)
      ])) + jmetaline(env.meta);
      return {state: items.length ? 'available' : 'empty', label: `${items.length} 个容器`, html, note: sc.container ? `后续步骤使用容器 ${sc.container.public_id}。` : ''};
    }},
    {title: '容器资源与字节校验（/containers/{id}/resources + 内容下载）', run: async () => {
      if (!sc.container) throw new Error('没有可用的 CIE 容器');
      const path = (sc.container.links && sc.container.links.resources) || `/api/v2/containers/${encodeURIComponent(sc.container.public_id)}/resources`;
      const env = await fetchEnvelope(path);
      const outcome = await jresourceChecks(env.data);
      const html = outcome.html + jmetaline(env.meta);
      return {state: outcome.failed || outcome.headerMissing ? 'partial' : 'available', label: `资源 ${outcome.count} 项 · 校验 ${outcome.ok}/${outcome.checked} 字节一致${outcome.headerMissing ? ' · 响应头不可观察' : ''}`, html,
        note: '夹具 resources[].sha256 与 content.declared_sha256 是合成占位值，不是真实文档哈希；校验以 content.sha256 与实测字节一致为准；响应头 x-content-sha256 在暂存前端代理上不可观察（server.mjs 仅透传 content-type/content-disposition），按声明原样标注，不推断。'};
    }},
    {title: '容器题目列表（/containers/{id}/questions）', run: async () => {
      const path = (sc.container && sc.container.links && sc.container.links.questions) || `/api/v2/containers/${encodeURIComponent(sc.container ? sc.container.public_id : '')}/questions`;
      const env = await fetchEnvelope(path);
      const items = Array.isArray(env.data.items) ? env.data.items : [];
      sc.questions = items;
      const html = jtable(['public_id', 'native_id', 'parent', 'question_type', 'stem', 'crop 链接'], items.map(item => [
        jval(item.public_id), jval(item.native_id),
        item.parent_native_id && item.parent_native_id !== '__unknown__' ? jval(item.parent_native_id) : jnull(),
        jval(item.question_type), item.stem ? esc(item.stem) : `${jnull()}（stem 缺失）`,
        item.links && item.links.crop ? '<span class="jcheck ok">已声明</span>' : '<span class="jmeta">未声明</span>'
      ])) + jmetaline(env.meta);
      return {state: items.length ? 'available' : 'empty', label: `${items.length} 道题`, html, note: ''};
    }},
    {title: '题目详情链 detail / answers / regions / audio / crop', run: async () => {
      const questions = sc.questions || [];
      const cards = [];
      const totals = {detailOk: 0, answersOk: 0, regionsOk: 0, audioOk: 0, cropOk: 0, cropDeclared: 0, failures: 0};
      for (const question of questions) {
        const outcome = await jquestionChain(question, 'sources');
        cards.push(outcome.html);
        for (const key of Object.keys(totals)) totals[key] += outcome.counts[key];
      }
      const noCropLink = questions.filter(question => !(question.links && question.links.crop)).length;
      const state = totals.failures || totals.cropDeclared || totals.cropOk < questions.length ? 'partial' : 'available';
      return {state, label: `${questions.length} 题 · detail ${totals.detailOk}/${questions.length} · regions ${totals.regionsOk}/${questions.length} · crop ${totals.cropOk}/${questions.length}`, html: cards.join(''),
        note: `${noCropLink} 道题未声明 crop 链接，仍按约定路径请求并得到声明的不可用响应；crop 不可用一律显示声明原因，不编造图像。regions 的空 bbox 与缺口按声明原样显示。`};
    }},
    {title: 'Edexcel 课程与大纲空态（courses / syllabuses?system=edexcel）', run: async () => {
      const courses = await fetchEnvelope('/api/v2/courses?system=edexcel');
      const courseItems = Array.isArray(courses.data.items) ? courses.data.items : [];
      const syllabuses = await fetchEnvelope('/api/v2/syllabuses?system=edexcel');
      const syllabusItems = Array.isArray(syllabuses.data.items) ? syllabuses.data.items : [];
      const warnings = syllabuses.meta && Array.isArray(syllabuses.meta.warnings) ? syllabuses.meta.warnings.map(String) : [];
      let html = '<h4>courses?system=edexcel</h4>' + jtable(['public_id', 'native_code', 'names', 'qualification', 'specification_version', 'aliases'], courseItems.map(item => [
        jval(item.public_id), jval(item.native_code), esc((item.names || []).join(' / ')), jval(item.qualification), jval(item.specification_version), esc((item.aliases || []).join(' / '))
      ]));
      html += '<h4>syllabuses?system=edexcel</h4>';
      if (syllabusItems.length) html += jtable(['public_id', 'version', 'title'], syllabusItems.map(item => [jval(item.public_id), jval(item.version), jval(item.title)]));
      else html += jreason('items: 0 条（声明空态）') + (warnings.length ? `<p class="jreason">${esc(warnings.join(' / '))}</p>` : '');
      html += jmetaline(syllabuses.meta);
      return {state: 'empty', label: `课程 ${courseItems.length} · 大纲 0（声明）`, html, note: '大纲空态由数据集自身声明（该家族的正式来源尚未接入），未做任何推断。'};
    }},
    {title: 'Edexcel 容器、资源、题目空态与 provider 限制（providers）', run: async () => {
      const env = await fetchEnvelope('/api/v2/containers?system=edexcel');
      const items = Array.isArray(env.data.items) ? env.data.items : [];
      let html = jtable(['public_id', 'native_identity', 'question_refs', 'resources', 'sections'], items.map(item => [
        jval(item.public_id), jsummary(item.native_identity),
        Array.isArray(item.question_refs) ? `${item.question_refs.length} 项` : jnull(),
        Array.isArray(item.resources) ? item.resources.map(entry => `${esc(entry.role)}=${jshort(entry.sha256 || '')}`).join(' · ') : jnull(),
        jsummary(item.sections)
      ]));
      const container = items[0] || null;
      let resourceOk = 0, resourceCount = 0, questionCount = 0;
      if (container) {
        const resources = await fetchEnvelope((container.links && container.links.resources) || `/api/v2/containers/${encodeURIComponent(container.public_id)}/resources`);
        const outcome = await jresourceChecks(resources.data);
        resourceOk = outcome.ok;
        resourceCount = outcome.count;
        html += '<h4>容器资源与字节校验</h4>' + outcome.html;
        const questions = await fetchEnvelope((container.links && container.links.questions) || `/api/v2/containers/${encodeURIComponent(container.public_id)}/questions`);
        const questionItems = Array.isArray(questions.data.items) ? questions.data.items : [];
        questionCount = questionItems.length;
        html += '<h4>容器题目</h4>' + (questionItems.length
          ? jtable(['public_id', 'native_id', 'question_type'], questionItems.map(item => [jval(item.public_id), jval(item.native_id), jval(item.question_type)]))
          : jreason('items: 0 条（声明空态）')) + jmetaline(questions.meta);
      }
      const providers = await fetchEnvelope('/api/v2/providers');
      const providerItems = Array.isArray(providers.data.items) ? providers.data.items : [];
      html += '<h4>providers（限制声明原文）</h4>' + jtable(['provider_id', 'capabilities', 'limitations'], providerItems.map(item => [
        jval(item.provider_id),
        Array.isArray(item.capabilities) ? esc(item.capabilities.join(', ')) : jnull(),
        Array.isArray(item.limitations) && item.limitations.length ? esc(item.limitations.join(' | ')) : jnull()
      ])) + jmetaline(providers.meta);
      return {state: 'partial', label: `容器 ${items.length} · 资源校验 ${resourceOk}/${resourceCount} · 题目 ${questionCount}（声明）`, html,
        note: 'Edexcel 的题目、答案与区域数据由 provider 自身声明为无；声明的空列表原样显示，没有任何占位数据。'};
    }},
  ];
}

function journeyIelts() {
  const sc = {};
  return [
    {title: 'IELTS 课程（/api/v2/courses?system=ielts）', run: async () => {
      const env = await fetchEnvelope('/api/v2/courses?system=ielts');
      const items = Array.isArray(env.data.items) ? env.data.items : [];
      const html = jtable(['public_id', 'native_code', 'names', 'aliases', 'qualification'], items.map(item => [
        jval(item.public_id), jval(item.native_code), esc((item.names || []).join(' / ')), esc((item.aliases || []).join(' / ')), jval(item.qualification)
      ])) + jmetaline(env.meta);
      return {state: items.length ? 'available' : 'empty', label: `${items.length} 条课程`, html, note: ''};
    }},
    {title: 'IELTS 容器与资源（/containers?system=ielts）', run: async () => {
      const env = await fetchEnvelope('/api/v2/containers?system=ielts');
      const items = Array.isArray(env.data.items) ? env.data.items : [];
      sc.container = items[0] || null;
      let html = jtable(['public_id', 'native_identity', 'question_refs', 'resources', 'sections'], items.map(item => [
        jval(item.public_id), jsummary(item.native_identity),
        Array.isArray(item.question_refs) ? `${item.question_refs.length} 项` : jnull(),
        Array.isArray(item.resources) ? item.resources.map(entry => `${esc(entry.role)}=${jshort(entry.sha256 || '')}`).join(' · ') : jnull(),
        jsummary(item.sections)
      ]));
      let gapsCount = 0;
      if (sc.container) {
        const resources = await fetchEnvelope((sc.container.links && sc.container.links.resources) || `/api/v2/containers/${encodeURIComponent(sc.container.public_id)}/resources`);
        const resourceItems = Array.isArray(resources.data.items) ? resources.data.items : [];
        const gaps = Array.isArray(resources.data.gaps) ? resources.data.gaps : [];
        gapsCount = gaps.length;
        html += '<h4>容器资源</h4>' + (resourceItems.length
          ? jtable(['role', 'public_id', 'sha256'], resourceItems.map(item => [jval(item.role), jval(item.public_id), jshort(item.sha256 || '')]))
          : jreason('资源 items: 0 条（该资源仅被哈希引用，未配套目录资产）')) + jgaps(gaps) + jmetaline(resources.meta);
      }
      return {state: gapsCount ? 'partial' : 'available', label: `容器 ${items.length} · 资源缺口 ${gapsCount}`, html,
        note: '资源以哈希被容器引用但没有对应目录资产，属于数据集自身声明的缺口，原样显示。'};
    }},
    {title: 'IELTS 题目列表（/containers/{id}/questions）', run: async () => {
      if (!sc.container) throw new Error('没有可用的 IELTS 容器');
      const env = await fetchEnvelope((sc.container.links && sc.container.links.questions) || `/api/v2/containers/${encodeURIComponent(sc.container.public_id)}/questions`);
      const items = Array.isArray(env.data.items) ? env.data.items : [];
      sc.questions = items;
      const html = jtable(['public_id', 'native_id', 'parent', 'question_type', 'stem'], items.map(item => [
        jval(item.public_id), jval(item.native_id),
        item.parent_native_id && item.parent_native_id !== '__unknown__' ? jval(item.parent_native_id) : jnull(),
        jval(item.question_type), item.stem ? esc(item.stem) : `${jnull()}（stem 缺失）`
      ])) + jmetaline(env.meta);
      return {state: items.length ? 'available' : 'empty', label: `${items.length} 道题`, html, note: ''};
    }},
    {title: 'IELTS 题目详情链（regions / crop 声明不支持）', run: async () => {
      const questions = sc.questions || [];
      const cards = [];
      const totals = {detailOk: 0, answersOk: 0, regionsOk: 0, audioOk: 0, cropOk: 0, cropDeclared: 0, failures: 0};
      for (const question of questions) {
        const outcome = await jquestionChain(question, 'ielts');
        cards.push(outcome.html);
        for (const key of Object.keys(totals)) totals[key] += outcome.counts[key];
      }
      const unsupported = questions.length > 0 && totals.regionsOk === 0;
      const html = (unsupported ? '<p class="jreason">provider 声明不支持：IELTS 题目链的 regions 与 crop 返回 422 unsupported_capability，原文逐题显示。</p>' : '') + cards.join('');
      const state = totals.failures || totals.cropOk < questions.length ? 'partial' : 'available';
      return {state, label: `${questions.length} 题 · detail ${totals.detailOk}/${questions.length} · answers ${totals.answersOk}/${questions.length} · regions ${totals.regionsOk}/${questions.length} · audio ${totals.audioOk}/${questions.length} · crop ${totals.cropOk}/${questions.length}`, html,
        note: 'IELTS provider（ielts_questions_fixture）未注册 regions 能力，regions 与 crop 的 422 响应按声明原样展示；answers 中的缺失槽位与冲突答案按声明原样显示，未做任何补写。'};
    }},
  ];
}

function journeyToefl() {
  const sc = {};
  return [
    {title: '考试系统声明（/api/v2/exam-systems + /api/v2/providers）', run: async () => {
      const env = await fetchEnvelope('/api/v2/exam-systems');
      const items = Array.isArray(env.data.items) ? env.data.items : [];
      const toefl = items.find(item => item.system === 'toefl') || null;
      sc.toefl = toefl;
      let html = jtable(['system', 'availability', 'providers', 'reason'], items.map(item => [
        jval(item.system), jval(item.availability),
        Array.isArray(item.providers) && item.providers.length ? esc(item.providers.join(' / ')) : jnull(),
        item.reason ? esc(item.reason) : jnull()
      ]));
      const providers = await fetchEnvelope('/api/v2/providers');
      const providerItems = Array.isArray(providers.data.items) ? providers.data.items : [];
      const toeflProvider = providerItems.filter(item => String(item.provider_id || '').toLowerCase().includes('toefl'));
      html += `<p class="jmeta">providers 列表：${providerItems.length} 条${toeflProvider.length ? '' : '，其中没有任何 TOEFL provider 记录'}（${providerItems.map(item => esc(String(item.provider_id || ''))).join(' · ')}）。</p>`;
      const reason = toefl && toefl.reason ? toefl.reason : '';
      return {state: toefl && toefl.availability === 'unavailable' ? 'unavailable' : 'partial', label: toefl ? `toefl ${toefl.availability}` : 'toefl 未列出', html,
        note: reason ? `数据集声明原文：${reason}。本旅程不请求任何 TOEFL 上游，也不装载适配器。` : '本旅程不请求任何 TOEFL 上游。'};
    }},
    {title: 'TOEFL 课程（courses?system=toefl）', run: async () => {
      const outcome = await jattempt('/api/v2/courses?system=toefl');
      if (!outcome.ok) return {state: 'unavailable', label: '声明不可用', html: `<p class="jreason">声明响应：${jdeclaredError(outcome.error)}</p>`, note: ''};
      const items = Array.isArray(outcome.result.data.items) ? outcome.result.data.items : [];
      const html = (items.length ? jtable(['public_id', 'native_code', 'names'], items.map(item => [jval(item.public_id), jval(item.native_code), esc((item.names || []).join(' / '))])) : jreason('items: 0 条（声明空态）')) + jmetaline(outcome.result.meta);
      return {state: items.length ? 'available' : 'empty', label: `${items.length} 条课程`, html, note: ''};
    }},
    {title: 'TOEFL 题目（questions?system=toefl）', run: async () => {
      const outcome = await jattempt('/api/v2/questions?system=toefl');
      if (!outcome.ok) return {state: 'unavailable', label: '声明不可用', html: `<p class="jreason">声明响应：${jdeclaredError(outcome.error)}</p>`, note: ''};
      const items = Array.isArray(outcome.result.data.items) ? outcome.result.data.items : [];
      const html = (items.length ? jtable(['public_id', 'native_id', 'question_type'], items.map(item => [jval(item.public_id), jval(item.native_id), jval(item.question_type)])) : jreason('items: 0 条（声明空态）')) + jmetaline(outcome.result.meta);
      return {state: items.length ? 'available' : 'empty', label: `${items.length} 道题`, html, note: ''};
    }},
    {title: 'TOEFL 覆盖行（/api/v2/coverage 的 published 视图）', run: async () => {
      const env = await fetchEnvelope('/api/v2/coverage');
      const operations = env.data && env.data.operations ? env.data.operations : null;
      if (!operations) return {state: 'unavailable', label: '未配置 operations 视图', html: jreason('本次运行的 coverage 响应没有 operations 成员：published 视图未配置，无法读取 TOEFL 覆盖行。') + jmetaline(env.meta), note: ''};
      const rows = operations.published && Array.isArray(operations.published.rows) ? operations.published.rows : [];
      const row = rows.find(entry => String(entry.scope || '').includes('toefl')) || null;
      if (!row) return {state: 'unavailable', label: 'published 无 TOEFL 行', html: jreason('published.rows 中没有 scope 含 toefl 的行。') + jmetaline(env.meta), note: ''};
      const html = jtable(['public_id', 'scope', 'derived_status', 'denominator_known', 'denominator', 'expected', 'observed', 'percentage', 'unmet'], [[
        jval(row.public_id), jval(row.scope), jval(row.derived_status), String(Boolean(row.denominator_known)), jval(row.denominator), jval(row.expected), jval(row.observed),
        row.percentage === null || row.percentage === undefined ? jnull() : esc(String(row.percentage)), jval(row.unmet)
      ]]) + jlist('evidence 原文', (Array.isArray(row.evidence) ? row.evidence : []).map(text => esc(String(text))));
      return {state: 'empty', label: '分母未声明 · 无百分比', html, note: '该行声明 denominator=null：没有分母，百分比永远无法计算，也不会被推断。'};
    }},
  ];
}

function journeyLibrary() {
  const sc = {};
  return [
    {title: '材料列表（/api/v2/materials）', run: async () => {
      const env = await fetchEnvelope('/api/v2/materials');
      const items = Array.isArray(env.data.items) ? env.data.items : [];
      sc.materials = items;
      let html = jtable(['public_id', 'system', 'kind', 'native_id', 'versions', 'access_mode', 'integration_status'], items.map(item => [
        jval(item.public_id), jval(item.system), jval(item.kind), jval(item.native_id),
        Array.isArray(item.versions) ? esc(item.versions.join(', ')) : jnull(), jval(item.access_mode), jval(item.integration_status)
      ]));
      const ieltsFilter = await jattempt('/api/v2/materials?system=ielts');
      html += '<h4>?system=ielts</h4>';
      if (ieltsFilter.ok) {
        const filtered = Array.isArray(ieltsFilter.result.data.items) ? ieltsFilter.result.data.items : [];
        html += `<p class="jmeta">IELTS 过滤：items ${filtered.length} 条（声明空态）。</p>` + jmetaline(ieltsFilter.result.meta);
      } else html += `<p class="jreason">声明响应：${jdeclaredError(ieltsFilter.error)}</p>`;
      return {state: items.length ? 'available' : 'empty', label: `${items.length} 份材料 · IELTS 空态`, html, note: ''};
    }},
    {title: '材料内容字节（/materials/{id}/content）', run: async () => {
      const items = sc.materials || [];
      let html = '', okCount = 0;
      for (const item of items) {
        const content = await jcontent(`/api/v2/materials/${encodeURIComponent(item.public_id)}/content`);
        if (content.ok) okCount += 1;
        html += `<p>${jcode(item.public_id)} content：${jline(content)}</p>`;
      }
      return {state: items.length && okCount === items.length ? 'available' : 'partial', label: `${okCount}/${items.length} 份内容可用`, html,
        note: '不可用的内容返回声明的 404（例如没有暂存内容样本），原样显示；不做替代或补写。'};
    }},
    {title: '大纲全量列表与内容字节（/api/v2/syllabuses）', run: async () => {
      const env = await fetchEnvelope('/api/v2/syllabuses');
      const items = Array.isArray(env.data.items) ? env.data.items : [];
      let html = jtable(['public_id', 'system', 'version', 'title', 'course_native_code', 'applicable_years', 'integration_status'], items.map(item => [
        jval(item.public_id), jval(item.system), jval(item.version), jval(item.title), jval(item.course_native_code),
        Array.isArray(item.applicable_years) && item.applicable_years.length ? esc(item.applicable_years.join(', ')) : jnull(),
        jval(item.integration_status)
      ]));
      let okCount = 0;
      for (const item of items) {
        const content = await jcontent(`/api/v2/syllabuses/${encodeURIComponent(item.public_id)}/content`);
        if (content.ok) okCount += 1;
        html += `<p>${jcode(item.public_id)} content：${jline(content)}</p>`;
      }
      html += jmetaline(env.meta);
      return {state: items.length && okCount === items.length ? 'available' : 'partial', label: `大纲 ${items.length} 条 · 内容 ${okCount}/${items.length}`, html,
        note: '应用的年份列表为空表示按声明"未知"，不读作任何日期；内容不可用项按声明原样显示。'};
    }},
    {title: '时间表可用性（/api/v2/timetables）', run: async () => {
      const env = await fetchEnvelope('/api/v2/timetables');
      const data = env.data || {};
      const seasons = Array.isArray(data.seasons) ? data.seasons : [];
      let html = `<p class="jmeta">availability：${esc(String(data.availability || '—'))}（整族声明）</p>`;
      html += jtable(['system', 'season', 'year', 'qualification', 'availability', 'reason'], seasons.map(item => [
        jval(item.system), jval(item.season), jval(item.year), jval(item.qualification), jval(item.availability), item.reason ? esc(item.reason) : jnull()
      ])) + jmetaline(env.meta);
      return {state: data.availability === 'unavailable' ? 'unavailable' : 'partial', label: `声明不可用 · ${seasons.length} 个考季`, html,
        note: '时间表在 Phase A 没有来源，日期与考季边界保持 null，不做推断。'};
    }},
    {title: '时间事件、窗口与过滤行为（events / windows / ?system=）', run: async () => {
      const events = await fetchEnvelope('/api/v2/timetables/events');
      const eventItems = Array.isArray(events.data.items) ? events.data.items : [];
      let html = '<h4>events</h4>' + jtable(['system', 'date', 'session', 'component', 'course_native_code', 'raw_text', 'note'], eventItems.map(item => [
        jval(item.system), jval(item.date), jval(item.session), jval(item.component), jval(item.course_native_code), jval(item.raw_text), item.note ? esc(item.note) : jnull()
      ]));
      const windows = await fetchEnvelope('/api/v2/timetables/windows');
      const windowItems = Array.isArray(windows.data.items) ? windows.data.items : [];
      html += '<h4>windows</h4>' + jtable(['system', 'parsed.start', 'parsed.end', 'unknown_boundaries', 'original_text'], windowItems.map(item => [
        jval(item.system), jval(item.parsed && item.parsed.start), jval(item.parsed && item.parsed.end),
        Array.isArray(item.unknown_boundaries) && item.unknown_boundaries.length ? esc(item.unknown_boundaries.join(', ')) : jnull(),
        jval(item.original_text)
      ]));
      html += '<h4>过滤探测</h4>';
      const eventsFilter = await jattempt('/api/v2/timetables/events?system=cie');
      if (eventsFilter.ok) html += `<p class="jmeta">events?system=cie：items ${(Array.isArray(eventsFilter.result.data.items) ? eventsFilter.result.data.items : []).length} 条（接受该过滤）。</p>`;
      else html += `<p class="jreason">events 过滤声明响应：${jdeclaredError(eventsFilter.error)}</p>`;
      const probe = await jattempt('/api/v2/timetables?system=cie');
      if (probe.ok) html += '<p class="jmeta">timetables?system=cie：接受该过滤。</p>';
      else html += `<p class="jreason">timetables?system=cie 声明响应：${jdeclaredError(probe.error)}</p>`;
      return {state: 'partial', label: '过滤行为 422 声明', html,
        note: '同一参数在 events 端点被接受、在 timetables 主端点被拒绝（422 unsupported_filter）——按声明原样显示，不做统一化处理。'};
    }},
  ];
}

function journeyDiagnostics() {
  const sc = {};
  return [
    {title: '覆盖率条目（/api/v2/coverage）', run: async () => {
      const env = await fetchEnvelope('/api/v2/coverage');
      sc.coverage = env;
      const data = env.data || {};
      const items = Array.isArray(data.items) ? data.items : [];
      const cells = items.map(item => [
        jval(item.public_id), jval(item.scope), jval(item.derived_status), jval(item.denominator), String(Boolean(item.denominator_known)),
        item.percentage === null || item.percentage === undefined ? jnull() : esc(String(item.percentage)),
        jval(item.observed), jval(item.verified), jval(item.unknown), jval(item.partial), jval(item.missing), jval(item.excluded)
      ]);
      const evidence = items.flatMap(item => (Array.isArray(item.evidence) ? item.evidence : []).map(text => `${jcode(item.scope || '')} ${esc(String(text))}`));
      const html = jtable(['public_id', 'scope', 'derived_status', 'denominator', 'denominator_known', 'percentage', 'observed', 'verified', 'unknown', 'partial', 'missing', 'excluded'], cells)
        + jgaps(data.gaps) + jlist('evidence 原文', evidence) + jmetaline(env.meta);
      return {state: items.length ? 'available' : 'empty', label: `${items.length} 条覆盖条目`, html, note: '分母未知或缺失时不计算百分比（null 原样保留）。'};
    }},
    {title: 'operations 只读观察（checkpoints / scan / jobs / published）', run: async () => {
      const env = sc.coverage || await fetchEnvelope('/api/v2/coverage');
      const data = env.data || {};
      const operations = data.operations || null;
      if (!operations) {
        return {state: 'unavailable', label: '未配置 operations 视图', html: jreason('本次运行的 coverage 响应没有 operations 成员：只读作业视图未配置。') + jmetaline(env.meta),
          note: '未配置即未配置：不从缺失去推断原因，也不合成任何作业数据。'};
      }
      const warnings = env.meta && Array.isArray(env.meta.warnings) ? env.meta.warnings.map(String) : [];
      const observation = operations.checkpoints && operations.checkpoints.observation ? operations.checkpoints.observation : null;
      const checkpointRows = operations.checkpoints && Array.isArray(operations.checkpoints.rows) ? operations.checkpoints.rows : [];
      const checkpointProblems = operations.checkpoints && Array.isArray(operations.checkpoints.problems) ? operations.checkpoints.problems : [];
      const scan = operations.checkpoints && operations.checkpoints.scan ? operations.checkpoints.scan : null;
      const jobRows = Array.isArray(operations.jobs) ? operations.jobs : [];
      const published = operations.published || null;
      let html = '';
      if (warnings.length) html += `<p class="jreason">${esc(warnings.join(' / '))}</p>`;
      if (observation) html += `<p class="jmeta">observation：revision=${esc(String(observation.observation_revision ?? '—'))} · staleness=${esc(String(observation.staleness ?? '—'))} · age=${esc(String(observation.age_seconds ?? '—'))}s · ttl=${esc(String(observation.ttl_seconds ?? '—'))}s · problems=${Array.isArray(observation.problems) && observation.problems.length ? esc(observation.problems.join(', ')) : '空'}</p>`;
      if (operations.root) html += `<p class="jmeta">root：configured=${String(Boolean(operations.root.configured))} · kind=${esc(String(operations.root.kind ?? '—'))} · scanned_files=${esc(String(operations.root.scanned_files ?? '—'))} · skipped=${Array.isArray(operations.root.skipped) ? operations.root.skipped.length : '—'} · truncated=${String(Boolean(operations.root.truncated))}</p>`;
      if (scan) html += `<p class="jmeta">scan：attempted=${esc(String(scan.attempted))} · entries_seen=${esc(String(scan.entries_seen))} · entries_consumed=${esc(String(scan.entries_consumed))} · retained_paths=${esc(String(scan.retained_paths))} · bytes_read=${esc(String(scan.bytes_read))} · snapshot_complete=${String(Boolean(scan.snapshot_complete))} · truncated=${String(Boolean(scan.truncated))}${Array.isArray(scan.exhausted) && scan.exhausted.length ? ` · exhausted=${esc(scan.exhausted.join(', '))}` : ''}</p>`;
      html += '<h4>checkpoints.rows（只读观察）</h4>' + jtable(['system', 'scope_id', 'state', 'freshness', 'resume', 'stop_reason', 'stopped_at', 'native_updated_at', 'problems'], checkpointRows.map(row => [
        jval(row.system), jval(row.scope_id), jval(row.state), jval(row.freshness),
        row.resume ? esc(`needs_user_resume=${Boolean(row.resume.needs_user_resume)}`) : jnull(),
        row.stop ? jval(row.stop.reason) : jnull(),
        row.stop ? jval(row.stop.stopped_at) : jnull(),
        jval(row.native_updated_at),
        Array.isArray(row.problems) && row.problems.length ? esc(row.problems.join(', ')) : jnull()
      ]));
      if (checkpointProblems.length) html += jlist('checkpoint 问题', checkpointProblems.map(problem => `${jcode(Array.isArray(problem.problems) ? problem.problems.join(', ') : problem.problems || '')} <span class="jmeta">source=${esc(String(problem.source || ''))}</span>`));
      html += '<h4>jobs（只读作业列表 · 点击「读取」查看详情）</h4>';
      html += jtable(['public_id', 'system', 'scope_kind', 'stage', 'freshness', 'stop_reason', 'resume', 'native_updated_at', '详情'], jobRows.map(row => {
        const slot = `jslot-${++jseq}`;
        return [
          jval(row.public_id), jval(row.system), jval(row.scope_kind), jval(row.stage), jval(row.freshness), jval(row.stop_reason),
          row.resume_required === undefined ? jnull() : String(Boolean(row.resume_required)), jval(row.native_updated_at),
          `<button class="jbutton jslim" type="button" data-jjob="${esc(String(row.public_id || ''))}" data-jtarget="${slot}">读取</button><div class="jdetail" id="${slot}"></div>`
        ];
      }));
      if (published) {
        html += `<h4>published（manifest=${esc(String(published.manifest || '—'))} · read_only=${String(Boolean(published.read_only))}）</h4>`;
        const rows = Array.isArray(published.rows) ? published.rows : [];
        html += jtable(['public_id', 'scope', 'derived_status', 'denominator_known', 'denominator', 'expected', 'observed', 'verified', 'unknown', 'partial', 'missing', 'unmet', 'excluded', 'percentage'], rows.map(row => [
          jval(row.public_id), jval(row.scope), jval(row.derived_status), String(Boolean(row.denominator_known)), jval(row.denominator), jval(row.expected), jval(row.observed), jval(row.verified), jval(row.unknown), jval(row.partial), jval(row.missing), jval(row.unmet), jval(row.excluded),
          row.percentage === null || row.percentage === undefined ? jnull() : esc(String(row.percentage))
        ]));
        for (const row of rows) {
          const exclusions = Array.isArray(row.exclusions) ? row.exclusions : [];
          if (exclusions.length) html += jlist(`${row.public_id} exclusions`, exclusions.map(entry => `${jcode(entry.public_id || '')} <span class="jmeta">${esc(String(entry.reason || ''))}</span>`));
          const evidence = Array.isArray(row.evidence) ? row.evidence : [];
          if (evidence.length) html += jlist(`${row.public_id} evidence`, evidence.map(text => esc(String(text))));
        }
      }
      return {state: 'available', label: '只读观察', html,
        note: 'checkpoints 为只读观察；stop 明细与内部来源字段刻意不渲染；不恢复、不重试、不写入任何作业。'};
    }},
    {title: '作业详情读取（含刻意不存在的 id）', run: async () => {
      const candidates = ['job_synthetic_coverage', 'job:cie:cie-batch:8888', 'job:ielts:synthetic-run-ok', 'does-not-exist'];
      const cards = [];
      let okCount = 0;
      for (const id of candidates) {
        const outcome = await jattempt('/api/v2/jobs/' + encodeURIComponent(id));
        if (outcome.ok) {okCount += 1;cards.push(`<h4>${esc(id)}</h4>` + jjobcard(outcome.result));}
        else cards.push(`<h4>${esc(id)}</h4><p class="jreason">声明响应：${jdeclaredError(outcome.error)}</p>`);
      }
      const state = okCount === candidates.length ? 'available' : okCount ? 'partial' : 'unavailable';
      return {state, label: `${okCount}/${candidates.length} 个作业可读取`, html: cards.join(''),
        note: '其中一个 id 刻意不存在（does-not-exist），用于展示声明的 404 not_found；其余 id 在无 operations 配置的运行中同样返回声明的 404。作业详情只读，不恢复、不写入。'};
    }},
    {title: '缺口清单（/api/v2/gaps）', run: async () => {
      const env = await fetchEnvelope('/api/v2/gaps');
      const items = Array.isArray(env.data.items) ? env.data.items : [];
      const counts = {};
      for (const gap of items) counts[gap.code || 'unknown'] = (counts[gap.code || 'unknown'] || 0) + 1;
      const html = jtable(['code', 'scope', 'source', 'system', 'detail', 'ref'], items.map(gap => [
        jcode(gap.code || ''), jval(gap.scope), jval(gap.source), jval(gap.system), esc(gap.detail || ''), gap.ref ? jshort(gap.ref) : jnull()
      ])) + `<p class="jmeta">按 code 计数：${Object.entries(counts).map(([code, count]) => `${esc(code)}=${count}`).join(' · ')}</p>` + jmetaline(env.meta);
      return {state: items.length ? 'available' : 'empty', label: `${items.length} 条缺口`, html, note: '缺口清单原样显示，不合并、不推断、不折叠。'};
    }},
  ];
}

const JOURNEYS = {
  sources: {intro: '走 CIE 与 Edexcel 两条资源线路：课程、大纲内容、容器、资源字节校验、题目详情链（detail / answers / regions / audio / crop）。设计上不可用的步骤会原样展示声明的不可用原因。', boot: journeySources},
  ielts: {intro: 'IELTS 书籍暂存夹具：课程、容器、8 道题目与详情链。该 provider 未注册 regions 能力，因此 regions 与 crop 在本旅程中声明为 422 不支持，原样显示。', boot: journeyIelts},
  toefl: {intro: 'TOEFL 在 Phase A 没有注册任何 provider（数据集自身声明为不可用）。本旅程只读取暂存数据集自身的声明（exam-systems、空列表、published 覆盖行），不请求任何上游。', boot: journeyToefl},
  library: {intro: '材料、大纲与时间表：内容字节、声明的空态与不可用的时间表边界（null 保留、不推断）。', boot: journeyLibrary},
  diagnostics: {intro: '覆盖率与只读作业诊断：静态覆盖条目、operations 只读观察（如有配置）、作业详情读取与缺口清单。全程只读、不恢复、不写入。', boot: journeyDiagnostics},
};

function journeyFromHash() {
  const match = /^#\/(sources|ielts|toefl|library|diagnostics)$/.exec(location.hash || '');
  return match ? match[1] : 'sources';
}

async function runJourney(name) {
  const journey = JOURNEYS[name];
  if (!journey) return;
  const runId = ++JOURNEY_RUN.id;
  (jblobs[name] || []).forEach(url => {try {URL.revokeObjectURL(url);} catch {}});
  jblobs[name] = [];
  const panel = document.getElementById(`journey-${name}`);
  if (!panel) return;
  panel.setAttribute('aria-busy', 'true');
  panel.innerHTML = `<p class="jintro">${esc(journey.intro)}</p><div class="jrow-actions"><button class="jbutton" type="button" data-jretry="${name}">重跑整条旅程 ↺</button><span class="jmeta" data-jstatus="${name}" role="status">正在运行…</span></div><div class="jblocks"></div>`;
  const status = panel.querySelector('[data-jstatus]');
  const blocks = panel.querySelector('.jblocks');
  const steps = journey.boot();
  const total = steps.length;
  for (let index = 0; index < total; index++) {
    if (runId !== JOURNEY_RUN.id) return;
    const spec = steps[index];
    const article = document.createElement('article');
    article.className = 'jblock';
    article.innerHTML = `<header><span class="jstep">${String(index + 1).padStart(2, '0')} /</span><h3>${esc(spec.title)}</h3>${jbadge('loading', '加载中')}</header><div class="jbody"><p class="jmeta">等待中…</p></div>`;
    blocks.append(article);
    const badge = article.querySelector('header .jbadge');
    const body = article.querySelector('.jbody');
    let outcome;
    try {
      outcome = await spec.run();
    } catch (error) {
      if (runId !== JOURNEY_RUN.id) return;
      badge.outerHTML = jbadge('error', '失败');
      body.innerHTML = `<p class="jreason">步进失败：${error instanceof ApiClientError ? `HTTP ${error.status || '—'} · ${jcode(error.code || '')} ${esc(error.message)}` : esc(error && error.message ? error.message : String(error))}</p>`;
      status.textContent = `第 ${index + 1} 步失败，旅程已停止（已完成 ${index} / ${total} 步）`;
      panel.setAttribute('aria-busy', 'false');
      return;
    }
    if (runId !== JOURNEY_RUN.id) return;
    badge.outerHTML = jbadge(outcome.state, outcome.label);
    body.innerHTML = outcome.html + (outcome.note ? `<p class="jreason">${esc(outcome.note)}</p>` : '');
    status.textContent = `已完成 ${index + 1} / ${total} 步…`;
  }
  if (runId !== JOURNEY_RUN.id) return;
  status.textContent = `全部 ${total} 步完成 · ${name}`;
  panel.setAttribute('aria-busy', 'false');
}

function activateJourney(name) {
  if (!JOURNEY_NAMES.includes(name)) name = 'sources';
  document.querySelectorAll('.journey-tabs [role=tab]').forEach(tab => {
    const selected = tab.dataset.journey === name;
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
  });
  document.querySelectorAll('.journey-panel').forEach(panel => {panel.hidden = panel.id !== `journey-${name}`;});
  if (journeyName === name) return;
  journeyName = name;
  runJourney(name);
}

const journeyTabs = [...document.querySelectorAll('.journey-tabs [role=tab][data-journey]')];
journeyTabs.forEach((tab, index) => {
  tab.addEventListener('keydown', event => {
    let next = null;
    if (event.key === 'ArrowRight') next = (index + 1) % journeyTabs.length;
    else if (event.key === 'ArrowLeft') next = (index - 1 + journeyTabs.length) % journeyTabs.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = journeyTabs.length - 1;
    if (next === null) return;
    event.preventDefault();
    const target = journeyTabs[next];
    target.focus();
    if (location.hash !== `#/${target.dataset.journey}`) location.hash = `#/${target.dataset.journey}`;
    else activateJourney(target.dataset.journey);
  });
});

document.addEventListener('click', event => {
  if (!(event.target instanceof Element)) return;
  const retry = event.target.closest('[data-jretry]');
  if (retry) {runJourney(retry.dataset.jretry);return;}
  const job = event.target.closest('[data-jjob]');
  if (job) {jloadJob(job);return;}
  const tab = event.target.closest('.journey-tabs [role=tab][data-journey]');
  if (!tab) return;
  const name = tab.dataset.journey;
  if (location.hash !== `#/${name}`) location.hash = `#/${name}`;
  else activateJourney(name);
});

window.addEventListener('hashchange', () => {activateJourney(journeyFromHash());});
activateJourney(journeyFromHash());
