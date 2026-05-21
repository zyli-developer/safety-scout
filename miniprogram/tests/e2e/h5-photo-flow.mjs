/**
 * H5 photo-flow e2e（stubbed backend）。
 *
 * 验证 fix(miniprogram): wire photos —— 上传后报告页能渲出原图。
 *   1. 启 dist 静态服务器
 *   2. Playwright route() mock：POST /api/v1/inspections → 200 + queued
 *      GET /api/v1/inspections/:id → 200 + succeeded（含 hazards）
 *   3. 桌面视口（1440×900）打开首页 → 喂入 1×1 红色 PNG 文件
 *   4. 等跳转到报告页
 *   5. 断言 hero 区有 <img>，src 是 blob: 开头
 *   6. 截图 h5-photo-flow-report.png
 *
 * 不依赖后端 / Claude CLI。
 * 用法：cd miniprogram && pnpm build:h5 && pnpm test:e2e:h5:photo
 */

import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { join, extname, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DIST_DIR = resolve(__dirname, '..', '..', 'dist');

const CHROME_PATH =
  process.env.CHROME_PATH ||
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.woff2': 'font/woff2',
};

// 1×1 红色 PNG（base64）
const RED_PIXEL_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
  'base64',
);

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
      resolveStart({ server, port: server.address().port });
    });
    server.on('error', rejectStart);
  });
}

const STUB_INSPECTION_ID = 'stub-test-1';

async function main() {
  console.log('H5 photo-flow test starting...');
  await readFile(join(DIST_DIR, 'index.html')).catch(() => {
    console.error('[FAIL] dist/index.html 不存在。先跑 pnpm build:h5');
    process.exit(2);
  });

  const { server, port } = await startStaticServer(DIST_DIR);
  const url = `http://127.0.0.1:${port}/`;
  console.log(`  static server: ${url}`);

  const failures = [];
  let browser;

  try {
    browser = await chromium.launch({ executablePath: CHROME_PATH, headless: true });
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();

    // Stub backend API
    await context.route('**/api/v1/inspections', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            inspection_id: STUB_INSPECTION_ID,
            poll_url: `/api/v1/inspections/${STUB_INSPECTION_ID}`,
            poll_interval_ms: 20,
            timeout_ms: 60_000,
            status: 'queued',
          }),
        });
      } else {
        await route.continue();
      }
    });
    await context.route(`**/api/v1/inspections/${STUB_INSPECTION_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          inspection_id: STUB_INSPECTION_ID,
          status: 'succeeded',
          created_at: '2026-05-21T10:00:00Z',
          updated_at: '2026-05-21T10:00:30Z',
          report: {
            inspection_id: STUB_INSPECTION_ID,
            created_at: '2026-05-21T10:00:00Z',
            plain_warning: '注意临边坠落',
            summary: '现场存在 2 项高风险作业，需立即整改',
            overall_severity: 'high',
            hazards: [
              {
                category_code: 'H1',
                category_name: '高处作业',
                description: '人字梯使用高度超过 2m 且未挂安全带',
                severity: 'high',
                regulation: 'JGJ 80-2016 §3.2',
                suggestion: '立即停工配发安全带并改用合规直梯',
              },
            ],
            model_meta: { provider: 'claude_cli', model: 'sonnet', latency_ms: 30000 },
          },
          error: null,
        }),
      });
    });

    const consoleErrors = [];
    page.on('console', (m) => {
      if (m.type() === 'error') consoleErrors.push(m.text());
    });
    page.on('pageerror', (err) => consoleErrors.push(`pageerror: ${err.message}`));

    console.log('  → goto home');
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30_000 });
    await page.waitForSelector('text=开始一次现场巡检', { timeout: 10_000 });

    console.log('  → feed red-pixel PNG into <input type="file">');
    const input = page.locator('input[type="file"]').first();
    await input.setInputFiles({
      name: 'site.png',
      mimeType: 'image/png',
      buffer: RED_PIXEL_PNG,
    });

    console.log('  → wait for navigate to report page');
    await page.waitForURL(/\/pages\/report\/index/i, { timeout: 10_000 });

    console.log('  → wait for succeeded report (hero img)');
    // 等隐患明细出现，证明 report 已加载 + 渲染
    await page.waitForSelector('text=高处作业', { timeout: 10_000 });

    // 关键：找到 hero 区的 <img>（不是 icon SVG），src 应是 blob:
    const heroImg = await page.locator('img[src^="blob:"]').first();
    const heroImgCount = await page.locator('img[src^="blob:"]').count();
    if (heroImgCount === 0) {
      failures.push('报告页没找到 <img src="blob:..."> —— Photo 没拿到 lastPhotoStore 的 src');
    } else {
      const src = await heroImg.getAttribute('src');
      console.log(`  ✓ <img> rendered with src: ${src?.slice(0, 60)}...`);

      // 确认 img 真有可见尺寸（>0×0）—— 如果 size 是 0，前面 CSS 链路某处出问题。
      const box = await heroImg.boundingBox();
      if (!box || box.width < 50 || box.height < 50) {
        failures.push(
          `<img> 几何尺寸异常：width=${box?.width} height=${box?.height} —— 父容器 aspect-ratio / .img CSS 链路 broke`,
        );
      } else {
        console.log(`  ✓ <img> bounding box: ${box.width}×${box.height}`);
      }

      // naturalWidth > 0 验证图确实加载完毕，不是 404/解码失败
      const natural = await heroImg.evaluate(
        (el) => (el instanceof HTMLImageElement ? el.naturalWidth : 0),
      );
      if (natural === 0) {
        failures.push(`<img>.naturalWidth=0 —— blob URL 解码失败或被 revoke`);
      } else {
        console.log(`  ✓ <img>.naturalWidth = ${natural}`);
      }
    }

    // 等所有动画 / 二次渲染稳定后再截，避免抓到 processing 帧
    await page.waitForSelector('text=立即处置', { timeout: 5_000 }).catch(() => undefined);
    await page.waitForTimeout(400);

    const shotPath = join(__dirname, 'h5-photo-flow-report.png');
    await mkdir(dirname(shotPath), { recursive: true });
    await page.screenshot({ path: shotPath, fullPage: true });
    console.log(`  ✓ screenshot: ${shotPath}`);

    if (consoleErrors.length) {
      failures.push(`browser errors: ${consoleErrors.join(' | ')}`);
    }
  } catch (e) {
    failures.push(`fatal: ${e.message}`);
  } finally {
    if (browser) await browser.close();
    server.close();
  }

  console.log(`\n${'='.repeat(60)}`);
  if (failures.length === 0) {
    console.log('✅ H5 photo-flow PASSED — uploaded photo renders on report page');
    process.exit(0);
  } else {
    console.log('❌ H5 photo-flow FAILED:');
    for (const f of failures) console.log(`   - ${f}`);
    process.exit(1);
  }
}

main().catch((e) => {
  console.error(`[FATAL] ${e.stack}`);
  process.exit(2);
});
