---
title: Forge 统一操作手册（Public CLI / Service / Maintainer）
created: 2026-04-05
updated: 2026-04-06
tags: [management, operator-guide, automation, pipeline, service]
status: active
source: "2026-04-06 会话整理：将 public CLI、service、自托管与 repo-local 维护入口重新分层"
---

# Forge 统一操作手册（Public CLI / Service / Maintainer）

## 1. 文档定位

这份文档回答的是“现在应该怎么用 Forge”，但会明确区分两类人：

- 公共操作者：只需要 `forge ...`，不需要知道仓库地址
- 仓库维护者：负责自托管、repo-local 调试和发布，使用 `uv run forge --repo-root . ...`

公共/operator 包括此处的 `forge ...` CLI 客户端，repo-local 维护者仍然走 `uv run forge --repo-root . ...` 来调试、inject、promote 等命令。本仓库在 [Forge howie_server 部署手册](docs/management/forge-howie-server-deployment.md) 中记录了 howie_server 上的标准部署/更新路径，并把 `scripts/deploy/deploy_howie_server.sh --host howie_server` 固定为生产部署入口。

关联文档：

- `docs/management/forge-operator-guide.md`：公共 CLI、service、自托管、maintainer 分层入口
- `docs/management/forge-release-distribution.md`：公共 CLI 的安装、GitHub Releases、Homebrew 与发布口径
- `docs/management/forge-llm-pipeline-v1.md`：当前实现、证据链、relay 边界
- `docs/management/repository-conventions.md`：仓库级提交、入口、文档同步规则
- `.agents/skills/using-forge/SKILL.md`：面向 AI 工具的 public operator contract

## 2. 两种入口

### 2.1 公共入口

公共用户、其他工具、Codex / Claude Code / OpenClaw 统一使用：

```bash
forge ...
```

公共入口默认通过以下方式定位 Forge service：

1. `forge login --server <url> --token <token>` 写入本地 XDG 配置
2. `FORGE_SERVER` / `FORGE_TOKEN` 环境变量覆盖

公共入口不要求调用方知道 Forge repo 地址，也不默认暴露 repo 内容。

### 2.2 维护入口

仓库维护、repo-local 调试、自托管服务启动统一使用：

```bash
uv run forge --repo-root . ...
```

兼容入口：

```bash
./automation/scripts/forge ...
python -m automation.pipeline ...
```

它们只用于维护，不再作为 public operator 文档的主入口。

## 3. 公共 CLI 快速开始

### 3.1 登录与连通性

```bash
forge login --server https://forge.example.com --token <token>
forge doctor
```

`doctor` 的重点：

- service 是否可达
- 当前 LLM/provider/relay 是否 ready
- `.env` / runtime lock / proxy 提示是否合理

### 3.2 最常用命令

写入原始材料：

```bash
forge inject \
  --title "incident summary" \
  --text "Context:\n...\n\nRoot cause:\n...\n\nFix steps:\n...\n\nVerification:\n..." \
  --source "manual note" \
  --initiator manual
```

看当前可行动队列：

```bash
forge review-queue --initiator manual
```

预览 ready 批次：

```bash
forge promote-ready --initiator manual --dry-run --limit 5
```

按 receipt 精确执行：

```bash
forge promote-ready \
  --initiator manual \
  --confirm-receipt state/receipts/ready_promote/<preview>.json
```

提升单篇 raw：

```bash
forge promote-raw raw/captures/example.md --initiator manual
```

显式合成 insights：

```bash
forge synthesize-insights --initiator manual
```

### 3.3 Receipt 与后台任务

同步执行完成后，用 receipt 校验结果：

```bash
forge receipt get state/receipts/inject/<id>.json
```

如果 mutation 带了 `--detach`，先拿到 `job_id`，再轮询：

```bash
forge job get inject-<jobid>
```

规则：

- `receipt_ref` 才是完成态结果的权威指针
- `job_id` 只代表后台执行句柄，不代表成功
- detached job 只有在 `forge job get` 返回 `status=success` 后才算完成

## 4. Trigger 语义

当前三层流转仍然是显式触发：

- `forge inject ...`
  默认只写 `snapshot + raw + inject receipt`
- `forge inject ... --promote-knowledge`
  只有显式带这个参数时才尝试 `raw -> knowledge`
- `forge promote-raw ...`
  显式提升指定 raw
- `forge promote-ready ...`
  显式执行当前 ready 队列
- `forge synthesize-insights`
  只有显式执行时才尝试 `knowledge -> insights`

这意味着：

- `raw/` 会长期存在“已摄入但尚未提升”的材料
- Forge 当前没有后台自动扫库和自动提升
- `review-queue` 是 public/operator 默认应看的高信号视图

### 4.1 `review-raw` / `review-queue` 怎么看

`review-raw` 的核心 disposition：

- `promoted`
- `pending`
- `too_short`
- `archived`
- `reference`

`review-queue` 只保留需要行动的项：

- `ready`：可以立即推进
- `blocked`：通常是 `too_short`，需要先补料或合并

### 4.2 长度不足时会怎样

如果内容低于 `runtime.knowledge.min_chars`：

- inject 仍然成功
- 内容仍然写入 `raw`
- inject receipt 仍然存在
- 但不会进入 knowledge pipeline

这类内容会保留在 `raw/`，等待后续人工补充或再次摄入。

## 5. 自托管 Forge Service

### 5.1 Docker Compose

仓库已经提供：

- `Dockerfile`
- `compose.yaml`
- `compose.deploy.yaml`

推荐路径：

1. 准备 `.env`
2. 准备两个持久化目录：
   - `./data/repo`
   - `./data/state`
3. 启动：

```bash
docker compose up -d --build
```

默认容器内服务等价于：

```bash
python -m automation.pipeline serve \
  --app-root /app \
  --repo-root /var/lib/forge/repo \
  --state-root /var/lib/forge/state \
  --host 0.0.0.0 \
  --port 8000
```

服务端 token 通过 `FORGE_SERVER_TOKEN` 控制。

三类路径的职责：

- `/app`：应用根目录，来自镜像，保存代码与 `automation/` 资源
- `/var/lib/forge/repo`：内容根目录，保存 `raw/`, `knowledge/`, `insights/` 和可选 `.env`
- `/var/lib/forge/state`：状态根目录，保存 receipts、snapshots、traces、service jobs

也就是说，应用代码和内容数据已经可以分离部署；`state_root` 继续独立于内容根目录。
当前仓库自带的 Docker 镜像会默认安装 `server,llm` extras，因此当内容根目录 `.env`
选择 `FORGE_KNOWLEDGE_CLIENT=litellm` / `FORGE_INSIGHT_CLIENT=litellm` 时，service 不需要再进容器补装 LiteLLM。

howie_server 的实际部署/更新不再建议手工敲 compose 命令，而是统一通过：

```bash
scripts/deploy/deploy_howie_server.sh --host howie_server
```

更完整的目录、验证、回滚说明见 `docs/management/forge-howie-server-deployment.md`。

### 5.2 本地开发启动

仓库内本地启动 service：

```bash
uv sync --extra server
uv run forge --repo-root . serve --host 127.0.0.1 --port 8000
```

如果还要走真实 LLM 路径，再补：

```bash
uv sync --extra server --extra llm
```

## 6. Maintainer 模式

维护者仍然需要 repo-local `.env`，且 `.env` 不进 git：

```bash
cp .env.example .env
uv run forge --repo-root . doctor
```

常用维护命令：

```bash
uv run forge --repo-root . review-raw --initiator codex
uv run forge --repo-root . promote-ready --initiator codex --dry-run --limit 5
uv run forge --repo-root . synthesize-insights --initiator codex
uv run forge --repo-root . receipt get state/receipts/inject/<id>.json
```

提交前建议：

```bash
uv run --extra server python -m unittest discover -s tests
./automation/scripts/validate-provenance.sh
./automation/scripts/generate-index.sh
git diff --check
```

## 7. `initiator` 是什么

`initiator` 是溯源标签，不是流程分支开关。

当前合法值：

- `manual`
- `codex`
- `claude-code`
- `openclaw`
- `ci`

它会进入 receipt、failure archive、review/promote receipt，用来回答“谁发起了这次操作”。
