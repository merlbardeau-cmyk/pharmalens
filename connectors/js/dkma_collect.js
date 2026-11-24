// Collect DKMA indlaegsseddel.dk search results (human medicines) by rendering the public JSF site.
// Output: JSON [{term, rows:[{name, company, form, strength, status, mt, pdf}]}]
const { chromium } = require('playwright');
const terms = process.argv.slice(2);
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ userAgent: 'PharmaLensResearchBot/0.1 (+public-regulatory-data; polite crawler)' });
  const out = [];
  for (const term of terms) {
    try {
      await p.goto('https://xnet.dkma.dk/indlaegsseddel/leaflets/leaflets.faces', { waitUntil: 'networkidle', timeout: 90000 });
      await p.fill('input[name="form1:searchfield"]', term);
      await p.click('input[name="form1:searchbutton"]');
      await p.waitForLoadState('networkidle'); await p.waitForTimeout(800);
      const rows = await p.$$eval('table.bigtable tbody tr', trs => trs.map(tr => {
        const td = tr.querySelectorAll('td'); const a = tr.querySelector('a.pdfLink');
        return td.length >= 6 ? { name: td[0].innerText.trim(), company: td[1].innerText.trim(), form: td[2].innerText.trim(),
          strength: td[3].innerText.trim(), status: td[4].innerText.trim(), mt: td[5].innerText.trim(), pdf: a ? a.href : null } : null;
      }).filter(Boolean));
      out.push({ term, rows });
      console.error(`${term}: ${rows.length}`);
    } catch (e) { console.error(`${term}: ERR ${e.message.slice(0, 80)}`); out.push({ term, rows: [], error: e.message.slice(0, 200) }); }
    await p.waitForTimeout(1500);
  }
  console.log(JSON.stringify(out));
  await b.close();
})();
