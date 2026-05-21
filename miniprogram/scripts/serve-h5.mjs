/**
 * 把 miniprogram/dist/ 起一个 0 依赖静态服务器，给本地浏览器调试用。
 * 用法：
 *   cd miniprogram && pnpm serve:h5            # 默认 http://localhost:8080
 *   PORT=9000 pnpm serve:h5                    # 指定端口
 *
 * 配套必跑：
 *   - cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload
 *   - cd miniprogram && pnpm build:h5:dev  （或 dev:h5 watch 模式）
 */

import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { join, extname, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DIST = resolve(__dirname, '..', 'dist');
const PORT = Number(process.env.PORT || 8080);

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
};

const server = createServer(async (req, res) => {
  const t0 = Date.now();
  try {
    let urlPath = decodeURIComponent(req.url.split('?')[0]);
    if (urlPath === '/favicon.ico') {
      res.writeHead(204);
      res.end();
      return;
    }
    if (urlPath === '/' || urlPath === '') urlPath = '/index.html';
    const filePath = join(DIST, urlPath);
    if (!filePath.startsWith(DIST)) {
      res.writeHead(403);
      res.end('Forbidden');
      return;
    }
    const content = await readFile(filePath);
    const ct = MIME[extname(filePath).toLowerCase()] || 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': ct, 'Cache-Control': 'no-cache' });
    res.end(content);
    console.log(`200 ${urlPath} (${Date.now() - t0}ms)`);
  } catch (e) {
    res.writeHead(404);
    res.end(`404 ${req.url}\n${e.code || e.message}`);
    console.log(`404 ${req.url}`);
  }
});

server.listen(PORT, () => {
  console.log('');
  console.log(`  H5 静态服务器：http://localhost:${PORT}`);
  console.log(`  服务目录：${DIST}`);
  console.log('');
  console.log(`  记得另开终端起 backend：`);
  console.log(`    cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload`);
  console.log('');
  console.log(`  Ctrl+C 退出`);
  console.log('');
});
