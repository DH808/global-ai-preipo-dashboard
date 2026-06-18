const assert = require('assert');
const { parseInterVestPortfolio, parseNewsRss, sourceStatus } = require('../src/connectors');

function test(name, fn) {
  try { fn(); console.log('✓', name); }
  catch (err) { console.error('✗', name); console.error(err); process.exitCode = 1; }
}

test('parseInterVestPortfolio extracts company cards', () => {
  const html = `<div class="col-4" data-tab="ICT" data-type="Semiconductor"><a href="https://kr.rebellions.ai" target="_blank" rel="noopener noreferrer" aria-label="Rebellions logo"><img src="x" alt="Rebellions logo"></a></div>`;
  const items = parseInterVestPortfolio(html);
  assert.equal(items.length, 1);
  assert.equal(items[0].name, 'Rebellions');
  assert.equal(items[0].category, 'Semiconductor');
});

test('parseNewsRss extracts RSS items', () => {
  const xml = `<rss><channel><item><title>Rebellions raises funding</title><link>https://example.com</link><pubDate>Wed, 17 Jun 2026</pubDate></item></channel></rss>`;
  const items = parseNewsRss(xml);
  assert.equal(items[0].title, 'Rebellions raises funding');
});

test('sourceStatus reports Crunchbase credential missing or present', () => {
  const sources = sourceStatus();
  const cb = sources.find(s => s.id === 'crunchbase');
  assert(cb);
  assert(['missing_credential', 'credential_present_not_tested'].includes(cb.runtimeStatus));
});
