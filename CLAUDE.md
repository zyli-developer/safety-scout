# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project intent

Safety Scout (工地安全隐患识别小程序) is an AI tool for construction-site safety officers. The product surface is intentionally three steps: **拍照 → 等待 → 看报告**. Any change that adds friction to that path (登录墙、多步表单、强制选择项) is working against the product, even if it adds capability.

Output is consumed by safety officers who forward it to crews, so model output must read as professional Chinese construction-safety language (引用规范条款、动作可执行的整改建议) — not generic vision-model prose. UX text and prompts are Chinese; code/identifiers are English.

## Current state

The repo is a **bootstrap skeleton**. `backend/` and `miniprogram/` contain only `.gitkeep`. There is no `package.json`, `requirements.txt`, test suite, or runnable code yet. When asked to "run tests" or "build," there is nothing to run — initialize the relevant scaffold first (FastAPI in `backend/`, Taro+React+TS in `miniprogram/`) and update this file with the real commands once they exist.

Planned stack (from `README.md` / `docs/architecture.md`):
- `miniprogram/` — Taro + React + TypeScript, target 微信小程序
- `backend/` — FastAPI (Python 3.11+)
- Multimodal LLM — DeepSeek Vision **or** Doubao (豆包) Vision; the provider must be swappable

## Architecture invariants

These are the load-bearing decisions in `docs/architecture.md`. Preserve them unless the user explicitly revisits the decision.

1. **LLM provider abstraction.** The backend must call vision models through a single `llm_provider` interface that wraps both DeepSeek and Doubao. Do not hardcode one vendor's SDK into route handlers — the point is A/B comparison and cheap migration.

2. **Structured JSON contract.** The prompt forces the model to return JSON with this shape:
   ```json
   {
     "summary": "整体风险等级与一句话总结",
     "hazards": [
       {
         "category": "高处作业 / 用电 / 消防 / 临边洞口 / ...",
         "description": "看到的具体现象",
         "severity": "high | medium | low",
         "regulation": "引用的规范条款（若有）",
         "suggestion": "给安全员的整改建议（动作可执行）"
       }
     ]
   }
   ```
   The backend must validate/normalize this and fall back gracefully (regex extraction or a corrective re-prompt) when the model returns malformed JSON. The frontend renders against this schema — changing field names is a breaking change across both sides.

3. **Primary endpoint.** `POST /api/v1/inspections` accepts a multipart image, persists the original (local FS or OSS — undecided), calls the LLM, and returns the structured report.

4. **Report rendering.** Hazards are sorted by severity and color-coded; the report fits one screen. Progress feedback during upload has three explicit states: 拍照成功 → AI 分析中 → 报告就绪.

## Open decisions

Listed in `docs/architecture.md §3` — DeepSeek vs Doubao first, image storage (local vs OSS), login/site-scoping, hazard taxonomy (custom vs 住建部规范), history/export. When work touches any of these, surface the tradeoff rather than silently picking one.

## Conventions

- `uploads/` and `local_data/` are gitignored — use them for runtime artifacts (uploaded site photos, local analysis records). Never commit site imagery.
- Secrets live in `.env` (gitignored); `.env.example` is the tracked template.
