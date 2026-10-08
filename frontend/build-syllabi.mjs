// Builds frontend/syllabi.json from official sources (network access required).
// Run manually: node build-syllabi.mjs
// CIE: subject list pages -> each syllabus page -> syllabus PDF links.
// Pearson: Algolia servlet -> Specification records for the IAL subject list.
import { readFile, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const CIE_ORIGIN = 'https://www.cambridgeinternational.org';
const PEARSON_ORIGIN = 'https://qualifications.pearson.com';
const PEARSON_SERVLET = PEARSON_ORIGIN + '/services/pearson/algolia/GET.servlet';
const CIE_SUBJECT_PAGES = [
  'https://www.cambridgeinternational.org/programmes-and-qualifications/cambridge-advanced/cambridge-international-as-and-a-levels/subjects/',
  'https://www.cambridgeinternational.org/programmes-and-qualifications/cambridge-upper-secondary/cambridge-igcse/subjects/',
  'https://www.cambridgeinternational.org/programmes-and-qualifications/cambridge-upper-secondary/cambridge-o-level/subjects/',
];
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36';

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

const decode = value => String(value)
  .replace(/&amp;/g, '&').replace(/&#39;|&apos;/g, "'").replace(/&quot;/g, '"')
  .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ');

export const cleanText = html => decode(String(html).replace(/<!--[\s\S]*?-->/g, ' ').replace(/<[^>]*>/g, ' '))
  .replace(/\s+/g, ' ').trim();

// Subject list pages: anchors end in "-NNNN" (the syllabus code). Both plain
// href and the menu's data-href (some point at /view/ wrappers) are accepted.
export function extractCieSubjects(html) {
  const found = new Map();
  const re = /<a\b[^>]*?(?:href|data-href)="\/programmes-and-qualifications\/(?:view\/)?([a-z0-9-]+-(\d{4}))\/"[^>]*>([\s\S]*?)<\/a>/gi;
  for (const match of String(html).matchAll(re)) {
    const [, slug, code, inner] = match;
    if (found.has(code)) continue;
    found.set(code, { slug, code, title: cleanText(inner) });
  }
  return found;
}

// Syllabus pages: PDF links live inside "syllabus-block" sections. Keep links
// whose label mentions "Syllabus" so unrelated PDFs (notation lists, key
// information) are not returned.
export function extractCieSyllabusLinks(html) {
  const text = String(html);
  const positions = [...text.matchAll(/class="syllabus-block"/g)].map(match => match.index);
  const links = [];
  const seen = new Set();
  for (let i = 0; i < positions.length; i++) {
    const slice = text.slice(positions[i], i + 1 < positions.length ? positions[i + 1] : positions[i] + 30000);
    for (const match of slice.matchAll(/<a\b[^>]*href="([^"]+\.pdf)"[^>]*>([\s\S]*?)<\/a>/gi)) {
      const url = match[1].startsWith('/') ? CIE_ORIGIN + match[1] : match[1];
      const label = cleanText(match[2]).replace(/\s*\(PDF[^)]*\)\s*$/i, '').trim();
      if (!/syllabus/i.test(label) || seen.has(url)) continue;
      seen.add(url);
      links.push({ title: label, url });
    }
  }
  return links;
}

// Pearson servlet records: keep Specification titles when present (an erratum
// notice can share the Document-Type), and never expose gated paths.
export function pickPearsonSpecifications(records) {
  const usable = (records || []).filter(record => record && record.url && !/\/(?:secure|silver|gold|\.\.)\//i.test(record.url));
  const specs = usable.filter(record => /specification/i.test(record.title || ''));
  return (specs.length ? specs : usable).map(record => ({
    title: record.title,
    url: record.url.startsWith('/') ? PEARSON_ORIGIN + record.url : record.url,
  }));
}

async function fetchText(url, { attempts = 2, timeout = 45000 } = {}) {
  let lastError;
  for (let i = 0; i < attempts; i++) {
    try {
      const response = await fetch(url, { headers: { 'User-Agent': UA, 'Accept-Language': 'en' }, signal: AbortSignal.timeout(timeout), redirect: 'follow' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.text();
    } catch (error) {
      lastError = error;
      await delay(1200);
    }
  }
  throw lastError;
}

async function pool(items, worker, { concurrency = 3, delayMs = 200 } = {}) {
  const results = new Array(items.length);
  let next = 0;
  async function run() {
    while (next < items.length) {
      const index = next++;
      try {
        results[index] = { status: 'fulfilled', value: await worker(items[index]) };
      } catch (error) {
        results[index] = { status: 'rejected', reason: error?.message || String(error) };
      }
      await delay(delayMs);
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, run));
  return results;
}

function localIso(date) {
  const pad = value => String(value).padStart(2, '0');
  const offset = -date.getTimezoneOffset();
  const sign = offset >= 0 ? '+' : '-';
  const abs = Math.abs(offset);
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}${sign}${pad(Math.floor(abs / 60))}${pad(abs % 60)}`;
}

async function main() {
  const subjects = new Map();
  for (const page of CIE_SUBJECT_PAGES) {
    const html = await fetchText(page);
    for (const [code, record] of extractCieSubjects(html)) if (!subjects.has(code)) subjects.set(code, record);
    await delay(300);
  }
  const subjectList = [...subjects.values()];
  console.log(`CIE subjects: ${subjectList.length}`);

  const ciePages = await pool(subjectList, async record => {
    const page = `${CIE_ORIGIN}/programmes-and-qualifications/${record.slug}/`;
    const html = await fetchText(page);
    return { code: record.code, title: record.title, page, syllabuses: extractCieSyllabusLinks(html) };
  }, { concurrency: 3, delayMs: 200 });

  const cie = {};
  const cieFailures = [];
  let cieEmpty = 0;
  ciePages.forEach((result, index) => {
    const subject = subjectList[index];
    const page = `${CIE_ORIGIN}/programmes-and-qualifications/${subject.slug}/`;
    if (result.status === 'fulfilled') {
      cie[result.value.code] = { title: result.value.title, page: result.value.page, syllabuses: result.value.syllabuses };
      if (!result.value.syllabuses.length) cieEmpty++;
    } else {
      cie[subject.code] = { title: subject.title, page, syllabuses: [] };
      cieFailures.push({ code: subject.code, slug: subject.slug, error: result.reason });
    }
  });
  console.log(`CIE crawled: ${Object.keys(cie).length}, without syllabus links: ${cieEmpty}, failed: ${cieFailures.length}`);

  const pearsonSource = JSON.parse((await readFile(new URL('./edexcel-subjects-source.json', import.meta.url), 'utf8')).replace(/^\uFEFF/, ''));
  const edexcel = {};
  const edexcelFailures = [];
  for (const entry of pearsonSource) {
    const code = (entry.category || []).find(category => /^Pearson-UK:Specification-Code\/[^/]+$/.test(category))?.split('/').pop();
    if (!code) continue;
    const page = PEARSON_ORIGIN + entry.url;
    try {
      const fq = `category:"Pearson-UK:Specification-Code/${code}" AND category:"Pearson-UK:Document-Type/Specification"`;
      const payload = JSON.parse(await fetchText(`${PEARSON_SERVLET}?${new URLSearchParams({ fq, hitsPerPage: '50' })}`));
      const records = payload.searchResults?.algoliaRecords || [];
      edexcel[code] = { title: entry.title, page, syllabuses: pickPearsonSpecifications(records) };
    } catch (error) {
      edexcel[code] = { title: entry.title, page, syllabuses: [] };
      edexcelFailures.push({ code, error: error?.message || String(error) });
    }
    await delay(250);
  }
  console.log(`Edexcel subjects: ${Object.keys(edexcel).length}, failed: ${edexcelFailures.length}`);

  const output = {
    generated_at: localIso(new Date()),
    source: {
      cie_subject_pages: CIE_SUBJECT_PAGES,
      cie_subjects: Object.keys(cie).length,
      cie_page_failures: cieFailures,
      edexcel_servlet: PEARSON_SERVLET,
      edexcel_subjects: Object.keys(edexcel).length,
      edexcel_failures: edexcelFailures,
    },
    cie,
    edexcel,
  };
  await writeFile(new URL('./syllabi.json', import.meta.url), JSON.stringify(output, null, 2) + '\n');
  console.log(`Wrote syllabi.json: ${Object.keys(cie).length} CIE + ${Object.keys(edexcel).length} Edexcel subjects`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await main();
