/**
 * 启动 backend uvicorn 的单点入口。
 *
 * dev 模式（默认）：`pnpm dev:backend` 调本文件 → 前台跑、含 --reload
 * e2e 模式：tests/e2e/h5-real.mjs `import { spawnBackend } from`、
 *           带 stdio capture，结束后 spawn 出来的进程被脚本管理
 *
 * 关键约束：dev / e2e / production-like 三种启动方式的 uvicorn args 完全一致，
 * 唯一区别是 stdio + 是否前台。这样保证 e2e 跑过的路径就是用户本地真跑的路径。
 */

import { spawn } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '..', '..');
const BACKEND_DIR = resolve(REPO_ROOT, 'backend');
const PY_EXE = resolve(BACKEND_DIR, '.venv', 'Scripts', 'python.exe');

export const BACKEND_HOST = '127.0.0.1';
// 8000 在本机被 zombie socket 占用（之前 --reload 时代留下的 ghost listener，
// taskkill 找不到但 LISTENING 还在），换 8001 绕开。
export const BACKEND_PORT = 8001;
export const HEALTH_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}/api/v1/healthz`;

/** uvicorn args 单一真相源 —— dev / e2e 一致使用。
 *
 * **不用 --reload**：Windows 上 uvicorn --reload 会强制 worker 走
 * SelectorEventLoop（watchfiles ipc 限制），导致 asyncio.create_subprocess_exec
 * 报 NotImplementedError，ClaudeCLIProvider 必挂。
 * 见 https://github.com/encode/uvicorn/issues/1972
 *
 * Dev 模式想要"改文件自动重启"用外层 nodemon 包裹（pnpm dev:backend）：
 * nodemon 监听 backend/app/*.py 变化 → kill+spawn uvicorn → 干净重启。
 * 里层 uvicorn 不开 --reload，默认 ProactorEventLoop，subprocess 工作。
 *
 * e2e 模式直接 spawn 这个 uvicorn（无 nodemon 包裹），路径与 dev 一致。
 */
export const UVICORN_ARGS = [
  '-m',
  'uvicorn',
  'app.main:app',
  '--host',
  BACKEND_HOST,
  '--port',
  String(BACKEND_PORT),
];

/**
 * Spawn uvicorn 子进程。
 * @param {object} opts
 * @param {'inherit' | 'pipe'} [opts.stdio] —— 'inherit' = 前台 dev 模式；
 *   'pipe' = e2e 模式（脚本捕获 stdout/stderr 加前缀打印）
 * @returns {import('node:child_process').ChildProcess}
 */
export function spawnBackend({ stdio = 'inherit' } = {}) {
  console.log(`[backend] spawning uvicorn at ${BACKEND_HOST}:${BACKEND_PORT}`);
  console.log(`[backend] cwd:    ${BACKEND_DIR}`);
  console.log(`[backend] python: ${PY_EXE}`);
  console.log(`[backend] args:   uvicorn ${UVICORN_ARGS.slice(1).join(' ')}`);
  console.log('');

  const stdioOpt = stdio === 'pipe' ? ['ignore', 'pipe', 'pipe'] : 'inherit';

  return spawn(PY_EXE, UVICORN_ARGS, {
    cwd: BACKEND_DIR,
    stdio: stdioOpt,
    detached: false,
  });
}

// —— CLI 模式（pnpm dev:backend）—— //

const isCli = process.argv[1] === fileURLToPath(import.meta.url);
if (isCli) {
  const proc = spawnBackend({ stdio: 'inherit' });
  proc.on('exit', (code, sig) => {
    console.log(`\n[backend] exited code=${code} sig=${sig}`);
    process.exit(code ?? 0);
  });
  // 转发 Ctrl+C 给子进程
  const onSig = () => {
    try {
      proc.kill('SIGTERM');
    } catch {
      /* noop */
    }
  };
  process.on('SIGINT', onSig);
  process.on('SIGTERM', onSig);
}
