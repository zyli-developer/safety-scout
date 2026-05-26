# Safety Scout 后端部署说明（Linux + claude_cli provider）

本文只覆盖一种部署形态：**Linux 长开机服务器 + `LLM_PROVIDER=claude_cli` + systemd 守护**。其他形态（Docker / serverless / 多副本）在当前 provider 模式下都跑不通，详见 README §部署。

## ⚠️ v2 是现行默认路径

自 2026-05-26 起，前端 `V2_TRAFFIC_SHARE = 1.0`，**所有用户请求走 v2 路径 `/api/v2/analyze`**（Claude Agent SDK + Skill 化分析管线），v1 路径 `/api/v1/inspections` 仅作 dormant fallback 保留。

本文档（`deploy.md`）只覆盖 v1 后端的运维基础设施（systemd / nginx / 升级流程），这些 v2 同样要做；**v2 增量部署步骤在两个专题文档里**，新部署 / 升级必读：

| 必读文档 | 覆盖内容 |
|---|---|
| **`docs/specs/v2-deployment.md`** | v2 后端增量：`uv sync` 装 `claude-agent-sdk` + 部署 `safety_skills/` 知识库 17 个 md + smoke 验证 + 监控字段 + 排错 |
| **`docs/specs/v2-rollout.md`** | 前端 `V2_TRAFFIC_SHARE` 灰度策略 + 改常量后必须重新打包 H5 / 小程序的实操（编译期常量，运行时改不了）+ Badcase 闭环 + Skill 维护手册 |

**最小升级清单**（v1 已部署 → 想要 v2 上线）：
1. 服务器跑 `uv sync --extra dev`（拉 `claude-agent-sdk` 依赖）
2. 拉到 `safety_skills/` 目录（git pull 自带，或单独解压 zip）
3. 重新打包前端 H5：`cd miniprogram && pnpm build:h5`（V2_TRAFFIC_SHARE 编译期固化进 bundle）
4. 重启 backend service：`systemctl restart safety-scout`
5. smoke 验证：`uv run python scripts/v2_smoke.py 1 --timeout 360`

## 前提

| 项 | 要求 |
| --- | --- |
| 服务器 | Linux（Ubuntu 22.04 LTS 验证过；Debian/CentOS 等同），**长开机**，不要 serverless |
| 用户 | 建一个专用 service user，例如 `scout`。**claude login 必须用这个用户跑**，否则 systemd 启动后子进程读不到 token |
| 网络 | 公网域名 + 443 端口（小程序 / H5 通过 HTTPS 访问） |
| Claude 账号 | 一个能登录 `claude` CLI 的 Anthropic 账号；账号的用量上限就是本服务的上限（无法多副本横向扩展） |

## 1. 准备机器

```bash
# 以 root 操作
adduser --disabled-password --gecos "" scout
mkdir -p /opt/safety-scout
chown scout:scout /opt/safety-scout

apt update
apt install -y python3.11 python3.11-venv curl git nginx
# Claude CLI 需要 node ≥ 18
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
```

## 2. 装 Claude CLI 并登录

**关键**：以 `scout` 用户身份做这一步，token 会落到 `/home/scout/.claude/.credentials.json`，systemd 用 `User=scout` 启动时才能读到。

```bash
sudo -iu scout
npm install -g @anthropic-ai/claude-code   # 若全局装受限可走 nvm
claude --version

claude login
# 终端会打印一个 URL —— 在本地浏览器打开、完成 OAuth、把回调里的 code 粘回终端

# 验证（必须返回 JSON envelope、is_error=false）
claude -p "ping" --output-format json
```

如果 `claude -p` 在 SSH session 里能跑通，systemd 拉起的服务就能跑通。

## 3. 拉代码 + 装 Python 依赖

```bash
# 仍以 scout 用户
cd /opt/safety-scout
git clone <repo-url> .
# 或 rsync 本地代码上去

cd backend
python3.11 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e .
.venv/bin/pip install "uvicorn[standard]>=0.27"

cp .env.example .env
# 编辑 .env，确认：
#   LLM_PROVIDER=claude_cli
#   CLAUDE_CLI_PATH=claude
#   CLAUDE_MODEL=claude-sonnet-4-5
# 不需要任何 API key
```

`uploads/` 和 `local_data/` 会在首次写入时自动创建。

## 4. systemd unit

把下面这份存为 `/etc/systemd/system/safety-scout.service`（也在仓库 `deploy/safety-scout.service` 留了模板）：

```ini
[Unit]
Description=Safety Scout backend (FastAPI + claude CLI)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=scout
Group=scout
WorkingDirectory=/opt/safety-scout/backend
EnvironmentFile=/opt/safety-scout/backend/.env

# scout 用户的 PATH 必须能找到 `claude`（npm 全局装的位置）。
# 如果 claude 不在 /usr/bin，把 npm prefix 加进来：`npm config get prefix` 查路径。
Environment="PATH=/usr/local/bin:/usr/bin:/bin:/home/scout/.npm-global/bin"
# HOME 必须指向跑过 claude login 的用户家目录，否则子进程找不到 ~/.claude
Environment="HOME=/home/scout"

ExecStart=/opt/safety-scout/backend/.venv/bin/uvicorn app.main:app \
    --host 127.0.0.1 --port 8000 \
    --no-access-log \
    --log-config /opt/safety-scout/backend/uvicorn-noop.json
# --no-access-log + 自定义 log-config 是为了让 uvicorn 不用自带文本格式；
# 应用内 setup_logging() 已经把 uvicorn logger 接管成 JSON，更干净。
# 若不想折腾 log-config，去掉这两行也能跑（access log 会是 plain text，但应用日志仍是 JSON）。

Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal

# 简单加固
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=read-only
ReadWritePaths=/opt/safety-scout/backend/uploads /opt/safety-scout/backend/local_data /home/scout/.claude

[Install]
WantedBy=multi-user.target
```

启用：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now safety-scout
sudo systemctl status safety-scout   # active (running)
journalctl -u safety-scout -f        # 实时看 JSON 日志流
```

启动成功的标志是 journal 里看到这两条 JSON：

```json
{"level":"INFO","message":"safety-scout backend starting","llm_provider":"claude_cli",...}
{"level":"INFO","message":"safety-scout backend ready"}
```

## 5. nginx 反代 + H5 静态托管

```nginx
# /etc/nginx/sites-available/safety-scout
server {
    listen 443 ssl http2;
    server_name your-domain.example.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain/privkey.pem;

    # 上传图片 15MB + slack，给 20MB 余量
    client_max_body_size 20m;

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # claude CLI 子进程实测复杂场景跑到 266s，前端轮询总时限 330s；
        # nginx 默认 60s 会切断 POST，必须放长
        proxy_read_timeout 360s;
        proxy_send_timeout 360s;
    }

    # H5 静态产物（miniprogram/dist/h5 上传后放在这里）
    location / {
        root /var/www/safety-scout-h5;
        try_files $uri $uri/ /index.html;
    }
}
```

启用：

```bash
sudo ln -s /etc/nginx/sites-available/safety-scout /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

⚠️ 上线前同时要改一处后端代码：`backend/app/main.py` 里 CORS `allow_origin_regex` 现在只放 localhost，把它收紧到你的实际域名（或在小程序场景里直接关 CORS）。

## 6. 升级 / 重启

```bash
sudo -iu scout
cd /opt/safety-scout
git pull
cd backend
.venv/bin/pip install -e .   # 依赖有变时才需要
exit
sudo systemctl restart safety-scout
```

重启时 `lifespan` 会把 `queued` 状态的孤儿 inspection 标 failed（架构 §2.6 + main.py 里 orphan 恢复逻辑），journal 里会看到 `orphan inspection marked failed` 告警。

## 7. 常见故障定位

所有应用日志都是 stdout JSON，通过 `journalctl -u safety-scout -f` 看。关键告警：

| journal 里看到 | 含义 / 处置 |
| --- | --- |
| `claude CLI not found on PATH at provider init` | systemd 的 `Environment="PATH=..."` 没包含 npm 全局 bin 目录 |
| `claude CLI exited non-zero ... rc=1` | OAuth token 过期 → SSH 上服务器，`sudo -iu scout claude login` 重新登 |
| `claude CLI timed out` | 单次复杂分析超过 `CLAUDE_TIMEOUT_SECONDS=300`；偶发可忽略，频繁出现考虑切 Doubao provider |
| `rate limit exceeded` | 某个 client_ip 超过 10/min；正常防滥用，不需处置 |
| `orphan inspection marked failed` | 进程刚重启，前一次有 queued 任务被中断 —— 让用户重试即可 |

健康检查：

```bash
curl http://127.0.0.1:8000/api/v1/healthz   # {"status":"ok"}
```

要做端到端验证：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/inspections \
     -F "image=@some-site-photo.jpg"
# 返回 {"inspection_id":"...","poll_url":"...","poll_interval_ms":2000,...}

curl http://127.0.0.1:8000/api/v1/inspections/<id>
# 轮询直到 status=succeeded / failed
```
