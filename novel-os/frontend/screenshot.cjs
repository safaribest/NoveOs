const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const outDir = path.resolve(__dirname, 'screenshots');
  await fs.promises.mkdir(outDir, { recursive: true });

  const baseURL = 'http://[::1]:5175';

  // 首页
  await page.goto(`${baseURL}/`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(outDir, 'home.png'), fullPage: true });

  // 项目列表
  await page.goto(`${baseURL}/projects`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(outDir, 'projects.png'), fullPage: true });

  // LLM 设置
  await page.goto(`${baseURL}/settings/llm`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(outDir, 'llm-settings.png'), fullPage: true });

  // 写作页（使用第一个项目 ID）
  const res = await fetch('http://127.0.0.1:8001/api/v1/projects');
  const json = await res.json();
  const firstProject = json.data[0];
  if (firstProject) {
    const encodedId = encodeURIComponent(firstProject.project_id);
    await page.goto(`${baseURL}/projects/${encodedId}/write`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    await page.screenshot({ path: path.join(outDir, 'write.png'), fullPage: true });
  }

  await browser.close();
  console.log('Screenshots saved to', outDir);
})();
