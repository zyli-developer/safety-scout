/**
 * 桌面 H5 端到端 e2e —— 与 h5-real.mjs 完全相同的后端 / Claude 真调，
 * 但 viewport=1440×900，触发 useIsDesktop=true 进 Desktop 分支。
 *
 * 上传方式：在 page 上找到隐藏 <input type=file>，调 setInputFiles 喂图。
 * （Mobile 版是先点击 BigButton 等 fileChooser；桌面 dropzone 直接点击也行
 * 但 setInputFiles 更稳，避免 fileChooser event 时序竞争）
 *
 * 用法：cd miniprogram && pnpm test:e2e:h5:desktop:real
 *
 * 退出码：0 通过 / 1 任一断言失败 / 2 启动失败
 */

import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { join, extname, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

import { HEALTH_URL, spawnBackend } from '../../scripts/start-backend.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '..', '..', '..');
const DIST_DIR = resolve(__dirname, '..', '..', 'dist');
const BACKEND_DIR = resolve(REPO_ROOT, 'backend');
const SAMPLE_IMG = resolve(
  BACKEND_DIR,
  'tests',
  'fixtures',
  'images',
  'case_001_stepladder_over_2_meters.jpg',
);
const SCREENSHOT_DIR = __dirname;

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
};

async function startBackend() {
  const proc = spawnBackend({ stdio: 'pipe' });
  proc.stdout.on('data', (b) => process.stdout.write(`[backend] ${b}`));
  proc.stderr.on('data', (b) => process.stderr.write(`[backend] ${b}`));
  const deadline = Date.now() + 45_000;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(HEALTH_URL);
      if (r.ok && (await r.json()).status === 'ok') return proc;
    } catch {
      /* not ready */
    }
    await sleep(500);
  }
  throw new Error('backend /healthz 未在 45s 内就绪');
}

function stopBackend(proc) {
  if (!proc) return;
  try { proc.kill('SIGTERM'); } catch {}
  if (process.platform === 'win32' && proc.pid) {
    spawn('taskkill', ['/F', '/T', '/PID', String(proc.pid)], { stdio: 'ignore' });
  }
}

function startStaticServer(rootDir) {
  return new Promise((resolveStart, rejectStart) => {
    const server = createServer(async (req, res) => {
      try {
        let urlPath = decodeURIComponent(req.url.split('?')[0]);
        if (urlPath === '/favicon.ico') { res.writeHead(204); res.end(); return; }
        if (urlPath === '/' || urlPath === '') urlPath = '/index.html';
        const filePath = join(rootDir, urlPath);
        if (!filePath.startsWith(rootDir)) { res.writeHead(403); res.end(); return; }
        const content = await readFile(filePath);
        const ct = MIME[extname(filePath).toLowerCase()] || 'application/octet-stream';
        res.writeHead(200, { 'Content-Type': ct });
        res.end(content);
      } catch { res.writeHead(404); res.end(); }
    });
    server.listen(0, '127.0.0.1', () => {
      resolveStart({ server, port: server.address().port });
    });
    server.on('error', rejectStart);
  });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function ensureDistExists() {
  try { await readFile(join(DIST_DIR, 'index.html')); }
  catch { console.error('dist/index.html 不存在；先跑 pnpm build:h5:dev'); process.exit(2); }
}

async function main() {
  console.log(`========== H5 DESKTOP REAL E2E ==========`);
  console.log(`  viewport: 1440x900 (desktop branch)`);

  await ensureDistExists();

  let backendProc = null;
  let staticSrv = null;
  let browser = null;
  const failures = [];
  const consoleErrors = [];

  try {
    backendProc = await startBackend();
    const { server, port } = await startStaticServer(DIST_DIR);
    staticSrv = server;
    const h5Url = `http://127.0.0.1:${port}/`;

    browser = await chromium.launch({ executablePath: CHROME_PATH, headless: true });
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
    page.on('pageerror', (err) => consoleErrors.push(err.message));

    console.log(`[step 1/4] 打开 H5 首页 (desktop)...`);
    await page.goto(h5Url, { waitUntil: 'networkidle', timeout: 30_000 });

    // 桌面分支：找到 dropzone 副标题 "CAPTURE INSPECTION PHOTO"
    await page.waitForSelector('text=/CAPTURE INSPECTION PHOTO/i', { timeout: 10_000 });
    await page.screenshot({ path: join(SCREENSHOT_DIR, 'h5-desktop-01-home.png'), fullPage: true });

    // 验证桌面分栏存在：查询拍摄要点卡片（仅桌面 DesktopIndex 渲染）
    const tipsVisible = await page.locator('text=拍摄要点').first().isVisible();
    if (!tipsVisible) failures.push('桌面首页未渲染 "拍摄要点" 侧栏');

    console.log(`[step 2/4] 把图片塞进隐藏 <input>...`);
    await page.locator('input[type="file"]').setInputFiles(SAMPLE_IMG);

    console.log(`[step 3/4] 等跳转报告页...`);
    await page.waitForURL(/\/pages\/report\/index/i, { timeout: 30_000 });
    // ProgressIndicator 真实 step labels：拍照已就绪 / AI 识别中 / 报告生成中
    await page.waitForSelector('text=/AI 识别中|拍照已就绪|报告生成中/', { timeout: 5_000 })
      .catch(() => console.log('未匹配到 polling 文案'));
    await page.screenshot({ path: join(SCREENSHOT_DIR, 'h5-desktop-02-polling.png'), fullPage: true });

    console.log(`[step 4/4] 等真实 Claude CLI 返回...`);
    const deadline = Date.now() + 200_000;
    let ok = false;
    while (Date.now() < deadline) {
      const sidebarVisible = await page.locator('text=现场巡检报告').first().isVisible().catch(() => false);
      const hazardVisible = await page.locator('text=高处坠落').first().isVisible().catch(() => false);
      if (sidebarVisible && hazardVisible) {
        // 桌面分支 sentinel：<View className={styles.aside}> 只出现在
        // pages/report/desktop.tsx 的 DesktopSucceededReport 里。若 useIsDesktop
        // 在 1440×900 下回归到 false，MobileReport 会渲染相同的标题文案但没有
        // aside wrapper，下面的断言会失败，回归会被抓住。
        const asideVisible = await page.locator('[class*="aside"]').first().isVisible().catch(() => false);
        if (!asideVisible) {
          failures.push('报告页找不到桌面专属 [class*="aside"] sticky 侧栏 —— 可能进了 mobile 分支');
        }
        ok = true;
        break;
      }
      // 错误文案：DesktopErrorView 走 mapApiError 的多数路径都带 "AI" 前缀，
      // 但 result.error.user_message 缺失时回退到裸 "分析失败"（report/desktop.tsx:65）。
      const errVisible = await page.locator('text=/(?:AI )?分析超时|(?:AI )?分析失败|网络异常|请返回首页/').first().isVisible().catch(() => false);
      if (errVisible) {
        failures.push('报告页显示错误页');
        break;
      }
      await sleep(2_000);
    }
    await page.screenshot({ path: join(SCREENSHOT_DIR, 'h5-desktop-03-final.png'), fullPage: true });
    if (!ok && failures.length === 0) failures.push('200s 内未看到桌面侧栏 + "高处坠落"');

    if (consoleErrors.length > 0) failures.push(`浏览器 error: ${consoleErrors.slice(0, 5).join(' | ')}`);
  } catch (e) {
    failures.push(`异常: ${e.message}\n${e.stack}`);
  } finally {
    if (browser) await browser.close().catch(() => {});
    if (staticSrv) staticSrv.close();
    if (backendProc) stopBackend(backendProc);
  }

  if (failures.length === 0) {
    console.log(`✅ H5 DESKTOP E2E PASSED`);
    process.exit(0);
  } else {
    console.log(`❌ H5 DESKTOP E2E FAILED:`);
    for (const f of failures) console.log(`   - ${f}`);
    process.exit(1);
  }
}

main().catch((e) => { console.error(`[FATAL] ${e.stack}`); process.exit(2); });
