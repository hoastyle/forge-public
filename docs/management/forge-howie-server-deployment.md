---
title: Forge howie_server 部署手册（脚本化入口）
created: 2026-04-06
updated: 2026-04-06
tags: [management, deployment, howie, service]
status: active
source: "2026-04-06 会话整理：将 howie_server 部署流程收敛为仓库内标准脚本与 compose 入口"
---

# Forge howie_server 部署手册（脚本化入口）

## 1. 拓扑与目录职责

- `app_root`: `/app`
  镜像内应用代码目录，对应远端 `~/apps/forge` 下同步过去的仓库副本。
- `content_root`: `/var/lib/forge/repo`
  绑定到远端 `~/apps/forge/data/repo`，保存 `raw/`、`knowledge/`、`insights/` 和 repo-local `.env`。
- `state_root`: `/var/lib/forge/state`
  绑定到远端 `~/apps/forge/data/state`，保存 receipts、snapshots、traces、service jobs 等状态文件。
- 服务入口端口：`18080`
  对外暴露在 howie_server 主机上，容器内仍然监听 `8000`。
- 远端部署根目录：`/home/howie/apps/forge`
- 服务鉴权文件：`/home/howie/apps/forge/.env`
  只放服务级变量，如 `FORGE_SERVER_TOKEN`、`FORGE_PUBLIC_PORT`。
- 内容运行时配置：`/home/howie/apps/forge/data/repo/.env`
  放 provider 选择、relay base URL、API key 等 repo 内容相关配置。

现在的标准部署形态已经明确区分代码、内容和状态。镜像重建不会覆盖 `data/repo` 与 `data/state`，因此内容和运行证据都能持续保留。

## 2. 标准入口

howie_server 的标准部署入口不再是手工敲一串 `docker compose`，而是仓库内脚本：

```bash
scripts/deploy/deploy_howie_server.sh --host howie_server
```

第一次部署或需要轮换 token 时，显式传入：

```bash
scripts/deploy/deploy_howie_server.sh \
  --host howie_server \
  --token "$FORGE_SERVER_TOKEN"
```

如果远端构建阶段需要代理，可以附加：

```bash
scripts/deploy/deploy_howie_server.sh \
  --host howie_server \
  --proxy 192.168.108.4:7890
```

如果 howie_server 上的 Docker daemon 拉镜像层或构建依赖不稳定，优先切换到本地构建再传输镜像：

```bash
scripts/deploy/deploy_howie_server.sh \
  --host howie_server \
  --build-local \
  --proxy 192.168.108.4:7890
```

脚本会完成这几件事：

- 同步应用代码到 `/home/howie/apps/forge`
- 同步 `raw/`、`knowledge/`、`insights/` 到 `/home/howie/apps/forge/data/repo/`
- 将本地 repo `.env` 过滤后写到远端 `data/repo/.env`
  过滤项目前是 `FORGE_SERVER_TOKEN` 与 `FORGE_PUBLIC_PORT`，避免把服务级变量混进内容层
- 更新远端服务 `.env`
- 默认使用仓库内 `compose.deploy.yaml` 执行 `docker compose -f compose.deploy.yaml up -d --build`
- 在 `--build-local` 模式下，本地 `docker build` 完成后会通过 `docker save | ssh docker load` 把镜像传到 howie_server，然后远端只执行 `docker compose -f compose.deploy.yaml up -d --no-build`
- 默认执行远端 `healthz` 与 `doctor` 验证

## 3. 相关文件

- `scripts/deploy/deploy_howie_server.sh`
  howie_server 的标准部署/更新脚本
- `compose.deploy.yaml`
  howie_server 使用的 compose 入口，端口默认读 `FORGE_PUBLIC_PORT`，默认值 `18080`
- `/home/howie/apps/forge/.env`
  远端服务级配置
- `/home/howie/apps/forge/data/repo/.env`
  远端内容级配置

## 4. 本地前置检查

执行脚本前，本地应满足：

- 仓库根目录存在 `.env`
- `.env` 至少包含知识/insight 所需的 provider 配置
- 如果要由脚本初始化或覆盖远端服务 token，则本地 shell 环境或 `.env` 中应能提供 `FORGE_SERVER_TOKEN`
- 本机能通过 `ssh howie_server` 直连目标机器

如果只想先同步文件、不触发重建，可临时使用：

```bash
scripts/deploy/deploy_howie_server.sh --host howie_server --skip-build --no-verify
```

如果本地已经完成镜像传输，只想让 howie_server 重新起容器并执行 readiness 校验，可以直接：

```bash
scripts/deploy/deploy_howie_server.sh --host howie_server --skip-build
```

## 5. 验证与巡检

脚本默认会在远端执行：

- `curl -fsS http://127.0.0.1:18080/healthz`
- `curl -fsS -H "Authorization: Bearer <token>" http://127.0.0.1:18080/v1/doctor`

如果要手工复查，使用：

```bash
ssh howie_server
cd /home/howie/apps/forge
source .env
docker compose -f compose.deploy.yaml ps
docker compose -f compose.deploy.yaml logs --tail 80 forge
curl -fsS http://127.0.0.1:18080/healthz
curl -fsS -H "Authorization: Bearer ${FORGE_SERVER_TOKEN}" http://127.0.0.1:18080/v1/doctor
```

如果只是从公网/局域网侧确认服务可用，再用 public CLI：

```bash
forge login --server http://192.168.108.177:18080 --token <token>
forge doctor
```

## 6. 回滚

如果本次更新引入回归，先回到远端机器，然后回退到已知可用版本并重新起服务：

```bash
ssh howie_server
cd /home/howie/apps/forge
git checkout <known-good-commit>
docker compose -f compose.deploy.yaml up -d --build
```

`data/repo` 与 `data/state` 不会因为这一步被清空，因此 receipts、知识层与 insight 层内容仍然保留。

## 7. 运维说明

- howie_server 的标准入口已经固定为 `scripts/deploy/deploy_howie_server.sh`，不要再把手工 `docker compose` 命令串当成主流程写进其他文档。
- `compose.deploy.yaml` 是 howie_server 的标准 compose 文件；repo-local 自测仍然优先使用 `compose.yaml` 或 `uv run forge --repo-root . serve ...`。
- public/operator 只需要知道 service URL + token，统一走 `forge ...`；他们不需要知道这个仓库地址。
