/**
 * Phase 3.5 H5 端 smoke test。
 *
 * 目的：验证 `taro build --type h5` 产物在浏览器里能正常加载 + 首页 React 渲染
 * 我们的组件（BigButton 等），不报 JS 运行时错。
 *
 * 不依赖 Browser MCP —— 用 playwright-core 启系统 Chrome（headless）跑：
 *   1. 起一个 dist/ 的静态文件服务器（stdlib http，零依赖）
 *   2. playwright-core 启系统 Chrome，访问 http://127.0.0.1:PORT/
 *   3. 等 #app 挂载 + 期待文案出现
 *   4. 抓 console errors / page errors
 *   5. 截图存到 tests/e2e/h5-smoke.png
 *   6. 退出码：0 全过 / 1 任一断言失败 / 2 启动失败
 *
 * 用法：
 *   cd miniprogram && pnpm build:h5 && pnpm test:e2e:h5
 */

import { createServer } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { join, extname, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DIST_DIR = resolve(__dirname, '..', '..', 'dist');
const SCREENSHOT_PATH = join(__dirname, 'h5-smoke.png');

// Windows 上 Chrome 的标准位置；其他平台 / 路径可由 CHROME_PATH 覆盖
const CHROME_PATH =
  process.env.CHROME_PATH ||
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8',
};

function startStaticServer(rootDir, missLog) {
  return new Promise((resolveStart, rejectStart) => {
    const server = createServer(async (req, res) => {
      try {
        let urlPath = decodeURIComponent(req.url.split('?')[0]);
        // 浏览器对 favicon.ico 是隐式请求；dist/ 里没有，给个空 204 别污染日志
        if (urlPath === '/favicon.ico') {
          res.writeHead(204);
          res.end();
          return;
        }
        if (urlPath === '/' || urlPath === '') urlPath = '/index.html';
        const filePath = join(rootDir, urlPath);
        if (!filePath.startsWith(rootDir)) {
          res.writeHead(403);
          res.end();
          return;
        }
        const content = await readFile(filePath);
        const ct = MIME[extname(filePath).toLowerCase()] || 'application/octet-stream';
        res.writeHead(200, { 'Content-Type': ct });
        res.end(content);
      } catch (e) {
        missLog.push(req.url);
        res.writeHead(404);
        res.end(`Not found: ${req.url} (${e.code || e.message})`);
      }
    });
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      resolveStart({ server, port });
    });
    server.on('error', rejectStart);
  });
}

async function ensureDistExists() {
  try {
    await readFile(join(DIST_DIR, 'index.html'));
  } catch {
    console.error(`[FAIL] dist/index.html 不存在。先跑 pnpm build:h5`);
    process.exit(2);
  }
}

async function main() {
  console.log(`H5 smoke test starting...`);
  console.log(`  dist dir: ${DIST_DIR}`);
  console.log(`  chrome:   ${CHROME_PATH}`);

  await ensureDistExists();

  const missLog = [];
  const { server, port } = await startStaticServer(DIST_DIR, missLog);
  const url = `http://127.0.0.1:${port}/`;
  console.log(`  static server on ${url}`);

  let browser;
  const failures = [];
  const consoleErrors = [];
  const pageErrors = [];

  try {
    browser = await chromium.launch({
      executablePath: CHROME_PATH,
      headless: true,
    });
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 }, // iPhone 14 Pro 视口（小程序也是竖屏）
      deviceScaleFactor: 2,
    });
    const page = await context.newPage();

    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });
    page.on('pageerror', (err) => pageErrors.push(err.message));

    console.log(`\n  navigating to ${url}...`);
    const resp = await page.goto(url, { waitUntil: 'networkidle', timeout: 30_000 });
    if (!resp || !resp.ok()) {
      failures.push(`首页 HTTP 状态非 2xx: ${resp ? resp.status() : 'no response'}`);
    }

    // 等 React 挂载 + 渲染我们的首页
    await page.waitForSelector('text=Safety Scout', { timeout: 10_000 }).catch(() => {
      failures.push('首页找不到 "Safety Scout" 标题文案 —— React 可能没挂载');
    });
    await page.waitForSelector('text=拍照检查', { timeout: 5_000 }).catch(() => {
      failures.push('找不到 "拍照检查" 按钮 —— BigButton 没渲染');
    });
    await page.waitForSelector('text=AI 隐患识别', { timeout: 3_000 }).catch(() => {
      // 子标题，缺了不算严重，只是 warning
      console.log(`  [warn] 副标题 "拍一张照片..." 没找到（可能 hint 文案位置变了）`);
    });

    // 截图存档
    await mkdir(dirname(SCREENSHOT_PATH), { recursive: true });
    await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true });
    console.log(`  screenshot saved: ${SCREENSHOT_PATH}`);

    // console / page error 都视为失败
    if (consoleErrors.length > 0) {
      failures.push(`浏览器 console.error: ${consoleErrors.join(' | ')}`);
    }
    if (pageErrors.length > 0) {
      failures.push(`页面 JS 异常: ${pageErrors.join(' | ')}`);
    }
    if (missLog.length > 0) {
      console.log(`\n  [info] 静态服务器 404 了这些路径（调试参考）:`);
      for (const m of missLog) console.log(`     - ${m}`);
    }

    // 输出 DOM 关键内容简报
    const titleText = await page.locator('text=Safety Scout').first().textContent().catch(() => null);
    const buttonText = await page.locator('text=拍照检查').first().textContent().catch(() => null);
    console.log(`\n  rendered title:  ${JSON.stringify(titleText)}`);
    console.log(`  rendered button: ${JSON.stringify(buttonText)}`);
  } catch (e) {
    failures.push(`测试过程异常: ${e.message}`);
  } finally {
    if (browser) await browser.close();
    server.close();
  }

  console.log(`\n${'='.repeat(60)}`);
  if (failures.length === 0) {
    console.log(`✅ H5 smoke test PASSED`);
    console.log(`   - dist/index.html 加载成功`);
    console.log(`   - React 挂载 + 首页文案渲染 + 大按钮就位`);
    console.log(`   - 浏览器 console 无 error，页面无 JS 异常`);
    console.log(`   - 截图: tests/e2e/h5-smoke.png`);
    process.exit(0);
  } else {
    console.log(`❌ H5 smoke test FAILED (${failures.length} 个问题):`);
    for (const f of failures) console.log(`   - ${f}`);
    if (consoleErrors.length || pageErrors.length) {
      console.log(`\n   完整 console errors: ${JSON.stringify(consoleErrors, null, 2)}`);
      console.log(`   完整 page errors:    ${JSON.stringify(pageErrors, null, 2)}`);
    }
    process.exit(1);
  }
}

main().catch((e) => {
  console.error(`[FATAL] ${e.stack}`);
  process.exit(2);
});
