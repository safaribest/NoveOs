import { chromium } from 'playwright';
import fs from 'fs';

const results = {
  pages: [],
  consoleErrors: [],
  networkErrors: [],
  summary: {}
};

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });

// Collect console errors
context.on('page', page => {
  page.on('console', msg => {
    const type = msg.type();
    const text = msg.text();
    if (type === 'error' || type === 'warning' || text.includes('404') || text.includes('Failed') || text.includes('Error')) {
      results.consoleErrors.push({
        page: page.url(),
        type,
        text: text.substring(0, 500)
      });
    }
  });
  page.on('pageerror', err => {
    results.consoleErrors.push({
      page: page.url(),
      type: 'pageerror',
      text: err.message?.substring(0, 500) || 'Unknown page error'
    });
  });
  page.on('response', response => {
    const status = response.status();
    if (status >= 400) {
      results.networkErrors.push({
        page: page.url(),
        url: response.url(),
        status
      });
    }
  });
});

async function auditPage(path, name) {
  const page = await context.newPage();
  const url = `http://127.0.0.1:5176${path}`;
  console.log(`Auditing ${name}: ${url}`);
  
  try {
    const response = await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 });
    const status = response?.status() || 0;
    
    // Wait a bit for JS to execute
    await page.waitForTimeout(2000);
    
    const title = await page.title().catch(() => '');
    const bodyText = await page.locator('body').textContent().catch(() => '');
    const hasErrorText = bodyText.includes('error') || bodyText.includes('Error') || bodyText.includes('404') || bodyText.includes('Not Found') || bodyText.includes('无法加载');
    const isBlank = bodyText.trim().length < 10;
    
    // Check for common error indicators
    const hasWhiteScreen = await page.evaluate(() => {
      const body = document.body;
      return body && body.children.length === 0;
    });
    
    results.pages.push({
      name,
      path,
      url,
      status,
      title,
      isBlank,
      hasWhiteScreen,
      hasErrorText,
      bodyPreview: bodyText.trim().substring(0, 300).replace(/\s+/g, ' ')
    });
    
    // Screenshot
    await page.screenshot({ path: `audit-runtime-${name.replace(/\//g, '_')}.png`, fullPage: true });
    
    await page.close();
  } catch (e) {
    results.pages.push({
      name,
      path,
      url,
      status: 0,
      error: e.message
    });
    await page.close().catch(() => {});
  }
}

// 1. Home page
await auditPage('/', 'home');

// 2. Projects page
await auditPage('/projects', 'projects');

// 3. Settings LLM page
await auditPage('/settings/llm', 'settings-llm');

// 4. Try to get project list from API and check a writing page
let projectPath = '/projects/租金300块99条禁忌/write';
try {
  const apiPage = await context.newPage();
  const apiRes = await apiPage.goto('http://127.0.0.1:5176/api/projects', { timeout: 10000 });
  if (apiRes && apiRes.status() === 200) {
    const apiText = await apiPage.textContent('body');
    try {
      const projects = JSON.parse(apiText);
      if (Array.isArray(projects) && projects.length > 0) {
        const p = projects[0];
        const slug = p.slug || p.id || p.name;
        if (slug) {
          projectPath = `/projects/${encodeURIComponent(slug)}/write`;
        }
      }
    } catch (e) {
      // ignore
    }
  }
  await apiPage.close();
} catch (e) {
  // ignore
}

// 4. Writing page
await auditPage(projectPath, 'write');

await browser.close();

fs.writeFileSync('audit-runtime-results.json', JSON.stringify(results, null, 2));
console.log('\n=== Audit Complete ===');
console.log(JSON.stringify(results, null, 2));
