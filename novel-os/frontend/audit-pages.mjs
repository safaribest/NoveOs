import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE_URL = 'http://127.0.0.1:5176';
const OUTPUT_DIR = 'audit-screenshots';

const routes = [
  { path: '/', name: 'home' },
  { path: '/projects', name: 'projects' },
  { path: '/settings/llm', name: 'settings-llm' },
  { path: '/create/category', name: 'create-category' },
  { path: '/create/topics', name: 'create-topics' },
  { path: '/create/outline', name: 'create-outline' },
  { path: '/create/confirm', name: 'create-confirm' },
];

if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
const page = await context.newPage();

const consoleErrors = [];
const pageErrors = [];

page.on('console', msg => {
  if (msg.type() === 'error') {
    consoleErrors.push({ route: page.url(), text: msg.text() });
  }
});

page.on('pageerror', err => {
  pageErrors.push({ route: page.url(), error: err.message });
});

const results = [];

for (const route of routes) {
  const url = `${BASE_URL}${route.path}`;
  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(1000);
    const screenshotPath = path.join(OUTPUT_DIR, `${route.name}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: true });
    const title = await page.title();
    results.push({ name: route.name, url, title, screenshot: screenshotPath, ok: true });
    console.log(`✅ ${route.name}: ${title}`);
  } catch (e) {
    results.push({ name: route.name, url, error: e.message, ok: false });
    console.log(`❌ ${route.name}: ${e.message}`);
  }
}

// 带 projectId 的路由，用第一个项目测试
let projectId = null;
try {
  await page.goto(`${BASE_URL}/projects`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  const firstLink = await page.locator('a[href*="/projects/"]').first();
  const href = await firstLink.getAttribute('href');
  if (href) {
    projectId = href.split('/projects/')[1]?.split('/')[0];
  }
} catch (e) {
  console.log('无法获取项目ID:', e.message);
}

if (projectId) {
  for (const route of [
    { path: `/projects/${projectId}/dashboard`, name: 'project-dashboard' },
    { path: `/projects/${projectId}/write`, name: 'project-write' },
  ]) {
    const url = `${BASE_URL}${route.path}`;
    try {
      await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 });
      await page.waitForTimeout(1000);
      const screenshotPath = path.join(OUTPUT_DIR, `${route.name}.png`);
      await page.screenshot({ path: screenshotPath, fullPage: true });
      const title = await page.title();
      results.push({ name: route.name, url, title, screenshot: screenshotPath, ok: true });
      console.log(`✅ ${route.name}: ${title}`);
    } catch (e) {
      results.push({ name: route.name, url, error: e.message, ok: false });
      console.log(`❌ ${route.name}: ${e.message}`);
    }
  }
}

await browser.close();

const report = {
  results,
  consoleErrors,
  pageErrors,
};

fs.writeFileSync(path.join(OUTPUT_DIR, 'report.json'), JSON.stringify(report, null, 2));
console.log('\n报告已保存到', path.join(OUTPUT_DIR, 'report.json'));
