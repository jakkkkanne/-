// Usage: node tools/shot.js <html> <out.png> [queryString]
// Screenshots the first <section class="page"> (used for listing mockups).
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const [html, out, query = ''] = process.argv.slice(2);
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 2000, height: 1600 } });
  await p.goto('file://' + path.resolve(html) + (query ? '?' + query : ''), { waitUntil: 'networkidle' });
  await p.evaluate(() => document.fonts.ready);
  await (await p.$('section.page')).screenshot({ path: out });
  await b.close();
})();
