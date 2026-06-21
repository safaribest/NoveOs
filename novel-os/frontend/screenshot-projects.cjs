const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto('http://127.0.0.1:5173/projects');
  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'screenshots/projects-now.png', fullPage: true });
  await browser.close();
})();
