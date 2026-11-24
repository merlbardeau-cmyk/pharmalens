// Collect BASG (Medikamente Info Austria) search results by rendering the public site in a browser.
// Reads only the responses the page itself receives; no direct API calls. Output: JSON lines per term.
const { chromium } = require('playwright');
const terms = process.argv.slice(2);
(async () => {
  const b = await chromium.launch();
  const out = [];
  for (const term of terms) {
    const p = await b.newPage({ userAgent: 'PharmaLensResearchBot/0.1 (+public-regulatory-data; polite crawler)' });
    let got = [];
    p.on('response', async r => { if (r.url().includes('/medication/search')) { try { const j = await r.json(); got.push(...(j.items || [])); p._total = j.totalItems; } catch (e) {} } });
    await p.goto('https://medikamente.basg.gv.at/de/medicinal-products/', { waitUntil: 'networkidle', timeout: 90000 });
    await p.getByRole('button', { name: 'Ablehnen' }).click().catch(() => {});
    await p.getByLabel('Wirkstoff').fill(term);
    await p.waitForTimeout(800); await p.keyboard.press('Escape');
    await p.getByRole('button', { name: 'Suche', exact: true }).click();
    await p.waitForLoadState('networkidle'); await p.waitForTimeout(1500);
    for (let i = 0; i < 40 && got.length < (p._total || 0); i++) {  // results load on scroll (infinite list)
      const before = got.length;
      await p.evaluate(() => { for (const el of document.querySelectorAll('*')) { if (el.scrollHeight > el.clientHeight + 50 && /auto|scroll/.test(getComputedStyle(el).overflowY)) el.scrollTop = el.scrollHeight; } window.scrollTo(0, document.body.scrollHeight); });
      await p.waitForTimeout(1500); await p.waitForLoadState('networkidle');
      if (got.length === before) { await p.waitForTimeout(2000); if (got.length === before) break; }
    }
    out.push({ term, total: p._total || got.length, items: got });
    console.error(`${term}: ${got.length}/${p._total}`);
    await p.close();
    await new Promise(r => setTimeout(r, 2000));
  }
  console.log(JSON.stringify(out));
  await b.close();
})().catch(e => { console.error('ERR', e.message); process.exit(1); });
