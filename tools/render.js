// Usage: node tools/render.js <html> <out.pdf> [previewPrefix] [queryString]
// Renders an HTML page to PDF (page size from the HTML's @page rule) and
// saves one PNG preview per <section class="page">.
const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const [html, outPdf, previewPrefix, query = ''] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 900, height: 1200 }, deviceScaleFactor: 1 });
  await page.goto('file://' + path.resolve(html) + (query ? '?' + query : ''), { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.pdf({ path: outPdf, printBackground: true, preferCSSPageSize: true });
  if (previewPrefix) {
    const sections = await page.$$('section.page');
    for (let i = 0; i < sections.length; i++) {
      await sections[i].screenshot({ path: `${previewPrefix}_p${String(i + 1).padStart(2, '0')}.png` });
    }
  }
  await browser.close();
})();
