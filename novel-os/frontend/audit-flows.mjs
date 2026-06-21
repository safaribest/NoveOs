import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE_URL = 'http://127.0.0.1:5176';
const OUTPUT_DIR = 'audit-screenshots';
if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
const page = await context.newPage();

const allErrors = [];
page.on('console', msg => {
  if (msg.type() === 'error') allErrors.push({ page: page.url(), text: msg.text() });
});
page.on('pageerror', err => {
  allErrors.push({ page: page.url(), error: err.message });
});

const results = [];

async function screenshot(name) {
  const p = path.join(OUTPUT_DIR, `${name}.png`);
  await page.screenshot({ path: p, fullPage: true });
  return p;
}

// 1. 测试 LLM 设置页和测试连接按钮
try {
  await page.goto(`${BASE_URL}/settings/llm`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  const testBtn = page.locator('button:has-text("测试连接")').first();
  if (await testBtn.isVisible().catch(() => false)) {
    await testBtn.click();
    await page.waitForTimeout(5000);
  }
  await screenshot('flow-llm-test');
  results.push({ step: 'llm-test', ok: true });
} catch (e) {
  results.push({ step: 'llm-test', ok: false, error: e.message });
}

// 2. 从项目列表点击进入项目写作页
let projectId = null;
try {
  await page.goto(`${BASE_URL}/projects`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  const card = page.locator('[class*="card"]').first();
  if (await card.isVisible().catch(() => false)) {
    await card.click();
    await page.waitForTimeout(2000);
    const url = page.url();
    projectId = url.match(/\/projects\/([^/]+)\/write/)?.[1];
    await screenshot('flow-project-write');
    results.push({ step: 'navigate-to-write', ok: true, projectId, url });
  } else {
    results.push({ step: 'navigate-to-write', ok: false, error: '无项目卡片' });
  }
} catch (e) {
  results.push({ step: 'navigate-to-write', ok: false, error: e.message });
}

// 3. 进入项目 dashboard
if (projectId) {
  try {
    await page.goto(`${BASE_URL}/projects/${projectId}/dashboard`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await screenshot('flow-project-dashboard');
    results.push({ step: 'navigate-to-dashboard', ok: true, url: page.url() });
  } catch (e) {
    results.push({ step: 'navigate-to-dashboard', ok: false, error: e.message });
  }
}

// 4. 测试创建项目流程第一步（选择分类）
try {
  await page.goto(`${BASE_URL}/create/category`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  const category = page.locator('text=都市').first();
  if (await category.isVisible().catch(() => false)) {
    await category.click();
    await page.waitForTimeout(2000);
  }
  await screenshot('flow-create-category');
  results.push({ step: 'create-category', ok: true, url: page.url() });
} catch (e) {
  results.push({ step: 'create-category', ok: false, error: e.message });
}

await browser.close();

const report = { results, errors: allErrors };
fs.writeFileSync(path.join(OUTPUT_DIR, 'flow-report.json'), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
