import test from 'node:test';
import assert from 'node:assert/strict';
import { extractCieSubjects, extractCieSyllabusLinks, pickPearsonSpecifications } from './build-syllabi.mjs';
import { syllabusFor } from './resources.mjs';

test('CIE subject list anchors resolve code, slug and title', () => {
  const html = '<a href="/programmes-and-qualifications/cambridge-international-as-and-a-level-mathematics-9709/">Mathematics</a>'
    + '<a data-href="/programmes-and-qualifications/view/cambridge-igcse-accounting-9-1-0985/">Accounting</a>';
  const map = extractCieSubjects(html);
  assert.deepEqual([...map.keys()], ['9709', '0985']);
  assert.equal(map.get('9709').slug, 'cambridge-international-as-and-a-level-mathematics-9709');
  assert.equal(map.get('0985').title, 'Accounting');
});

test('CIE syllabus block keeps syllabus PDFs and drops other documents', () => {
  const html = `
    <div class="syllabus-block"><a class="file-link" href="/Images/697427-2026-2027-syllabus.pdf">2026 - 2027 Syllabus <!-- -->(PDF, 1MB)</a></div>
    <div class="syllabus-block"><a class="file-link" href="/Images/123-key-information.pdf">Key Information</a><a class="file-link" href="/Images/456-notation-list.pdf">Notation List</a></div>`;
  assert.deepEqual(extractCieSyllabusLinks(html), [{
    title: '2026 - 2027 Syllabus',
    url: 'https://www.cambridgeinternational.org/Images/697427-2026-2027-syllabus.pdf',
  }]);
});

test('Pearson specifications prefer specification titles and reject gated paths', () => {
  const records = [
    { title: 'Erratum notice', url: '/content/dam/pdf/x/errata.pdf' },
    { title: 'Specification - Issue 3', url: '/content/dam/pdf/x/spec.pdf' },
    { title: 'Specification', url: '/content/dam/secure/silver/spec.pdf' },
  ];
  assert.deepEqual(pickPearsonSpecifications(records), [{
    title: 'Specification - Issue 3',
    url: 'https://qualifications.pearson.com/content/dam/pdf/x/spec.pdf',
  }]);
});

test('syllabusFor resolves each board and tolerates a missing snapshot', () => {
  const snapshot = {
    cie: { '9709': { title: 'Mathematics - 9709', page: 'https://www.cambridgeinternational.org/programmes-and-qualifications/cambridge-international-as-and-a-level-mathematics-9709/', syllabuses: [{ title: '2026 - 2027 Syllabus', url: 'https://www.cambridgeinternational.org/Images/697427-2026-2027-syllabus.pdf' }] } },
    edexcel: { 'ial18-biology': { title: 'Biology (2018)', page: 'https://qualifications.pearson.com/en/qualifications/edexcel-international-advanced-levels/biology-2018.html', syllabuses: [] } },
  };
  const cie = syllabusFor(snapshot, { board: 'cie', subject: '9709' });
  assert.equal(cie.origin, 'snapshot');
  assert.equal(cie.syllabuses.length, 1);
  assert.equal(syllabusFor(snapshot, { board: 'edexcel', subject: 'ial18-biology' }).page.includes('biology-2018'), true);
  assert.equal(syllabusFor(snapshot, { board: 'cie', subject: '9999' }), null);
  assert.equal(syllabusFor(null, { board: 'cie', subject: '9709' }), null);
});
