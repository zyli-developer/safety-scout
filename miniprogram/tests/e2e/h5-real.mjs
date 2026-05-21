/**
 * 真实端到端 e2e（不是 smoke）：起后端 + 静态服务器 + headless Chrome，
 * 模拟用户拍照 → POST 上传 → 轮询 → 看到真实 Claude CLI 返回的报告。
 *
 * 前置：
 *   1. backend 装好（pnpm/uv 装好依赖 + claude CLI 登录）
 *   2. 先跑 `pnpm build:h5:dev`（API_BASE_URL 注入 http://localhost:8000）
 *
 * 用法：
 *   cd miniprogram && pnpm test:e2e:h5:real
 *
 * 真实成本：~$0.10-0.20（1 次 Claude Sonnet 调用）+ 60-180s 延迟
 *
 * 退出码：0 通过 / 1 任一断言失败 / 2 启动失败
 */

import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { join, extname, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

import {
  BACKEND_HOST,
  BACKEND_PORT,
  HEALTH_URL,
  spawnBackend,
} from '../../scripts/start-backend.mjs';

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

// —— 后端 uvicorn 启停 —— //
// 用 scripts/start-backend.mjs 里的 spawnBackend 作为单一真相源，
// 保证 e2e 跑的 uvicorn args 跟 dev 模式（pnpm dev:backend）一字不差。

async function startBackend() {
  const proc = spawnBackend({ stdio: 'pipe' });

  proc.stdout.on('data', (b) => process.stdout.write(`[backend] ${b}`));
  proc.stderr.on('data', (b) => process.stderr.write(`[backend] ${b}`));
  proc.on('exit', (code, sig) => {
    console.log(`[backend] exited code=${code} sig=${sig}`);
  });

  // poll /healthz with backoff up to 45s（--reload 启动时 WatchFiles 多花点）
  const deadline = Date.now() + 45_000;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(HEALTH_URL);
      if (r.ok) {
        const j = await r.json();
        if (j.status === 'ok') {
          console.log(`[backend] healthz ok at ${new Date().toISOString()}`);
          return proc;
        }
      }
    } catch {
      // backend 还没起来 / 网络瞬态错；继续 backoff
    }
    await sleep(500);
  }
  throw new Error('backend /healthz 未在 45s 内就绪');
}

function stopBackend(proc) {
  if (!proc) return;
  try {
    proc.kill('SIGTERM');
  } catch (e) {
    console.error(`[backend] kill failed: ${e.message}`);
  }
  // Windows 上有时 SIGTERM 不够；兜底 taskkill
  if (process.platform === 'win32' && proc.pid) {
    spawn('taskkill', ['/F', '/T', '/PID', String(proc.pid)], { stdio: 'ignore' });
  }
}

// —— 静态服务器 —— //

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
        res.end(`Not found: ${req.url}`);
      }
    });
    server.listen(0, '127.0.0.1', () => {
      resolveStart({ server, port: server.address().port });
    });
    server.on('error', rejectStart);
  });
}

// —— util —— //

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function ensureDistExists() {
  try {
    await readFile(join(DIST_DIR, 'index.html'));
  } catch {
    console.error(`[fatal] dist/index.html 不存在。先跑 pnpm build:h5:dev`);
    process.exit(2);
  }
}

// —— 主流程 —— //

async function main() {
  console.log(`============= H5 REAL E2E (实跑 Claude CLI) =============`);
  console.log(`  sample img: ${SAMPLE_IMG}`);
  console.log(`  chrome:     ${CHROME_PATH}`);
  console.log(`  cost:       ~$0.10-0.20  duration: ~90-180s\n`);

  await ensureDistExists();

  let backendProc = null;
  let staticSrv = null;
  let browser = null;
  const failures = [];
  const consoleErrors = [];
  const pageErrors = [];

  try {
    // 1. backend
    backendProc = await startBackend();

    // 2. static server
    const { server, port: staticPort } = await startStaticServer(DIST_DIR);
    staticSrv = server;
    const h5Url = `http://127.0.0.1:${staticPort}/`;
    console.log(`[static] serving dist/ on ${h5Url}`);

    // 3. browser
    browser = await chromium.launch({
      executablePath: CHROME_PATH,
      headless: true,
    });
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      deviceScaleFactor: 2,
    });
    const page = await context.newPage();

    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });
    page.on('pageerror', (err) => pageErrors.push(err.message));
    page.on('requestfailed', (req) =>
      console.log(`[browser] request failed: ${req.url()} ${req.failure()?.errorText}`),
    );
    page.on('response', (resp) => {
      if (resp.url().includes('/api/v1/')) {
        console.log(`[browser] api ${resp.request().method()} ${resp.url()} → ${resp.status()}`);
      }
    });

    // 4. 打开首页
    console.log(`\n[step 1/5] 打开 H5 首页...`);
    await page.goto(h5Url, { waitUntil: 'networkidle', timeout: 30_000 });
    await page.waitForSelector('text=拍照检查', { timeout: 10_000 });
    await page.screenshot({ path: join(SCREENSHOT_DIR, 'h5-real-01-home.png'), fullPage: true });

    // 5. 点拍照检查 → 触发 file chooser → 喂 case_001
    console.log(`[step 2/5] 点"拍照检查"按钮并喂 case_001.jpg...`);
    const fileChooserPromise = page.waitForEvent('filechooser', { timeout: 10_000 });
    await page.locator('text=拍照检查').click();
    const chooser = await fileChooserPromise;
    await chooser.setFiles(SAMPLE_IMG);
    console.log(`[browser] file chooser 已喂入 ${SAMPLE_IMG.split('\\').pop()}`);

    // 6. 等跳转到报告页
    console.log(`[step 3/5] 等跳转到报告页（POST + navigateTo）...`);
    await page.waitForURL(/\/pages\/report\/index/i, { timeout: 30_000 });
    console.log(`[browser] 报告页 URL: ${page.url()}`);
    // 等 ProgressIndicator React 节点渲染完再截图（不然时序竞争抓到空白页）
    await page
      .waitForSelector('text=/正在为你生成报告|AI 分析中|拍照成功/', { timeout: 5_000 })
      .catch(() => console.log('[browser] 警告：未检测到 ProgressIndicator 标志文案'));
    await sleep(300);
    await page.screenshot({
      path: join(SCREENSHOT_DIR, 'h5-real-02-polling.png'),
      fullPage: true,
    });

    // 7. 等真实 Claude CLI 返回 + parse_report 成功 + UI 渲染最终报告
    console.log(`[step 4/5] 等真实 Claude CLI 返回（60-180s）...`);
    const reportDeadline = Date.now() + 200_000;
    let succeeded = false;
    while (Date.now() < reportDeadline) {
      // 成功标志：报告页里出现"高处坠落"（case_001 主隐患）或任一 hazard category 中文名
      const hasHazard = await page
        .locator('text=高处坠落')
        .first()
        .isVisible()
        .catch(() => false);
      if (hasHazard) {
        succeeded = true;
        break;
      }
      // 失败标志：报告页里出现"分析超时"/"分析失败"等 errorView 文案
      const hasError = await page
        .locator('text=/分析超时|分析失败|网络异常|请返回首页/')
        .first()
        .isVisible()
        .catch(() => false);
      if (hasError) {
        const errText = await page.locator('.errorView, [class*="errorView"]').first().textContent().catch(() => null);
        failures.push(`报告页显示错误：${errText ?? '(无法定位文案)'}`);
        break;
      }
      await sleep(2_000);
    }

    await page.screenshot({
      path: join(SCREENSHOT_DIR, 'h5-real-03-final.png'),
      fullPage: true,
    });

    if (!succeeded && failures.length === 0) {
      failures.push(`等待 200s 后仍未看到"高处坠落"文案 —— Claude CLI 可能超时或解析失败`);
    }

    if (succeeded) {
      console.log(`\n[step 5/5] ✅ 看到"高处坠落"！抓报告全文...`);
      const reportBody = await page.locator('body').textContent();
      console.log(`---REPORT TEXT (truncated)---`);
      console.log(reportBody.slice(0, 2000));
      console.log(`---END---`);
    }

    if (consoleErrors.length > 0) {
      failures.push(`浏览器 console.error: ${consoleErrors.slice(0, 5).join(' | ')}`);
    }
    if (pageErrors.length > 0) {
      failures.push(`页面 JS 异常: ${pageErrors.slice(0, 5).join(' | ')}`);
    }
  } catch (e) {
    failures.push(`测试过程异常: ${e.message}\n${e.stack}`);
  } finally {
    if (browser) await browser.close().catch(() => {});
    if (staticSrv) staticSrv.close();
    if (backendProc) stopBackend(backendProc);
  }

  console.log(`\n${'='.repeat(60)}`);
  if (failures.length === 0) {
    console.log(`✅ H5 REAL E2E PASSED`);
    console.log(`   - backend uvicorn 启动 + /healthz ok`);
    console.log(`   - 首页拍照检查 → file chooser → POST 上传`);
    console.log(`   - 报告页轮询 → 真实 Claude CLI 返回 → ReportPayload 解析`);
    console.log(`   - "高处坠落"（case_001 GT）在渲染报告中可见`);
    console.log(`   - 截图: h5-real-01-home.png / -02-polling.png / -03-final.png`);
    process.exit(0);
  } else {
    console.log(`❌ H5 REAL E2E FAILED (${failures.length} 个问题):`);
    for (const f of failures) console.log(`   - ${f}`);
    if (consoleErrors.length > 0) {
      console.log(`\n   全部 console errors:`);
      consoleErrors.forEach((e) => console.log(`     - ${e}`));
    }
    process.exit(1);
  }
}

main().catch((e) => {
  console.error(`[FATAL] ${e.stack}`);
  process.exit(2);
});
