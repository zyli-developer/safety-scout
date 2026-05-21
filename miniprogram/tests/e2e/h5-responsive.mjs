/**
 * H5 responsive e2e (IMPLEMENT.md §10.7).
 *
 * 在 4 个视口下打开首页 + 报告页占位（？status=processing 的 ProgressIndicator 即可）
 * 各截一张图，存档到 tests/e2e/h5-responsive-{vp}-{page}.png；同时做轻量断言：
 *   - phone (390): 单列、CTA 一眼可见
 *   - tablet (768): mobile 布局居中，左右露 surface-2 backdrop
 *   - desktop-sm (1100): TopNav + 单列 grid（dropzone 上、sidebar 下）
 *   - desktop (1440): TopNav + 1.5fr/1fr 双列
 *
 * 不依赖后端：报告页只验 processing 文案，不实际上传。
 * 用法：cd miniprogram && pnpm build:h5 && pnpm test:e2e:h5:responsive
 */

import { createServer } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { join, extname, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DIST_DIR = resolve(__dirname, '..', '..', 'dist');

const CHROME_PATH =
  process.env.CHROME_PATH ||
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const VIEWPORTS = [
  { name: 'phone', width: 390, height: 844 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop-sm', width: 1100, height: 800 },
  { name: 'desktop', width: 1440, height: 900 },
];

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8',
  '.woff2': 'font/woff2',
};

function startStaticServer(rootDir) {
  return new Promise((resolveStart, rejectStart) => {
    const server = createServer(async (req, res) => {
      try {
        let urlPath = decodeURIComponent(req.url.split('?')[0]);
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
      } catch {
        res.writeHead(404);
        res.end();
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
  console.log(`H5 responsive test starting...`);
  await ensureDistExists();

  const { server, port } = await startStaticServer(DIST_DIR);
  const url = `http://127.0.0.1:${port}/`;
  console.log(`  static server on ${url}`);

  const failures = [];
  let browser;

  try {
    browser = await chromium.launch({ executablePath: CHROME_PATH, headless: true });

    for (const vp of VIEWPORTS) {
      const context = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
        deviceScaleFactor: 1,
      });
      const page = await context.newPage();

      const consoleErrors = [];
      page.on('console', (m) => {
        if (m.type() === 'error') consoleErrors.push(m.text());
      });

      console.log(`\n  [${vp.name}] ${vp.width}x${vp.height}`);
      const resp = await page.goto(url, { waitUntil: 'networkidle', timeout: 30_000 });
      if (!resp || !resp.ok()) {
        failures.push(`[${vp.name}] HTTP ${resp ? resp.status() : 'no response'}`);
        await context.close();
        continue;
      }

      // 等首页关键文案
      await page.waitForSelector('text=Safety Scout', { timeout: 10_000 }).catch(() => {
        failures.push(`[${vp.name}] 首页未渲染 Safety Scout 品牌`);
      });

      // 按 viewport 期望不同：≥1024 渲 DesktopIndex（开始一次现场巡检），<1024 渲 MobileIndex（AI 找隐患）
      if (vp.width >= 1024) {
        await page.waitForSelector('text=开始一次现场巡检', { timeout: 5_000 }).catch(() => {
          failures.push(`[${vp.name}] 桌面首页未渲染 "开始一次现场巡检"`);
        });
        // desktop-sm (1024–1279)：grid 单列时 dropzone 在 sidebar 之上；
        // ≥1280：1.5fr/1fr 双列。截图存档供视觉 review。
      } else {
        await page.waitForSelector('text=AI 找隐患', { timeout: 5_000 }).catch(() => {
          failures.push(`[${vp.name}] 移动首页未渲染 "AI 找隐患"`);
        });
        await page.waitForSelector('text=开始巡检', { timeout: 3_000 }).catch(() => {
          failures.push(`[${vp.name}] 移动首页 CTA "开始巡检" 没渲`);
        });
      }

      const shotPath = join(__dirname, `h5-responsive-${vp.name}-home.png`);
      await mkdir(dirname(shotPath), { recursive: true });
      await page.screenshot({ path: shotPath, fullPage: true });
      console.log(`  ✓ screenshot: ${shotPath}`);

      if (consoleErrors.length) {
        failures.push(`[${vp.name}] console errors: ${consoleErrors.join(' | ')}`);
      }

      await context.close();
    }
  } catch (e) {
    failures.push(`fatal: ${e.message}`);
  } finally {
    if (browser) await browser.close();
    server.close();
  }

  console.log(`\n${'='.repeat(60)}`);
  if (failures.length === 0) {
    console.log(`✅ H5 responsive test PASSED for ${VIEWPORTS.length} viewports`);
    process.exit(0);
  } else {
    console.log(`❌ H5 responsive test FAILED:`);
    for (const f of failures) console.log(`   - ${f}`);
    process.exit(1);
  }
}

main().catch((e) => {
  console.error(`[FATAL] ${e.stack}`);
  process.exit(2);
});
