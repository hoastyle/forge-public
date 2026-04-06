---
title: Forge 发布与分发口径（Public CLI / Service / Maintainer）
created: 2026-04-06
updated: 2026-04-06
tags: [management, release, distribution, cli, service]
status: active
source: "2026-04-06 会话整理：补齐独立公共 Forge CLI 的发布与分发文档"
---

# Forge 发布与分发口径（Public CLI / Service / Maintainer）

## 1. 文档定位

这份文档只回答一件事：Forge 作为独立公共 CLI 时，应该如何发布、分发、安装和连接服务。

统一口径：

- 公共用户、agent、operator 使用 `forge ...`
- 仓库维护者、自托管部署、repo-local 调试使用 `uv run forge --repo-root . ...`
- 默认公共 GitHub 仓库是 `hoastyle/forge`

这意味着：

- 公共 CLI 是一个连接 Forge service 的独立客户端
- public 使用不要求调用方 checkout Forge repo
- repo-local `serve`、`.env`、LiteLLM、runtime lock 等维护语义，仍然属于 maintainer 文档范畴

## 2. 入口分层

### 2.1 公共入口

公共 CLI 的标准入口统一写成：

```bash
forge ...
```

公共入口面向的是“对已配置的 Forge service 发请求”，而不是“直接在本地仓库里跑流水线”。

它的连接来源优先级按当前实现理解为：

1. 显式 flags：`--server` / `--token`
2. 环境变量：`FORGE_SERVER` / `FORGE_TOKEN`
3. `forge login` 写入的本地配置

`forge login` 当前写入：

```text
~/.config/forge/config.toml
```

也可以通过 `XDG_CONFIG_HOME` 改写配置根目录。

### 2.2 维护入口

维护与自托管入口统一写成：

```bash
uv run forge --repo-root . ...
```

包括：

- repo-local `doctor`
- repo-local `serve`
- repo-local `.env` / LiteLLM / relay 调试
- 提交前测试、回放、调优、自托管运维

兼容入口：

```bash
./automation/scripts/forge ...
python -m automation.pipeline ...
```

这两个入口只保留为兼容或调试，不再作为公共文档主入口。

## 3. 公共分发口径

当前独立公共 CLI 的默认分发面向 `hoastyle/forge`：

1. **GitHub Releases**
   这是默认公共分发渠道。公共用户优先从 `https://github.com/hoastyle/forge/releases`
   获取与自己平台匹配的 `forge` 可执行文件或打包资产。
2. **Install script**
   对 Linux / macOS 用户，优先提供：
   ```bash
   curl -fsSL https://raw.githubusercontent.com/hoastyle/forge/master/scripts/release/install-public-cli.sh | bash
   ```
   该脚本会解析当前平台，从 GitHub Releases 下载匹配的 `forge_<version>_<os>_<arch>.tar.gz`
   并安装到 `~/.local/bin`（可用 `--install-dir` 或 `FORGE_INSTALL_DIR` 覆盖）。
   如果当前 shell 还没有把该目录放进 `PATH`，脚本会直接输出补充命令。
3. **Go install**
   面向开发者或不想手动下载 release asset 的用户，可直接：
   ```bash
   go install github.com/hoastyle/forge/cmd/forge@latest
   ```
4. **Homebrew formula（维护者分发面）**
   仓库内提供：
   - `scripts/release/render-homebrew-formula.sh`
   - `packaging/homebrew/forge.rb.tmpl`

   这套资产面向维护者生成 tap formula，不直接替代 GitHub Releases。

如果后续补 Scoop、apt、nix 等发行方式，应在同一轮同步更新 README 与本文件。

## 4. 公共安装与服务使用

### 4.1 安装后最小验证

```bash
export PATH="$HOME/.local/bin:$PATH"  # if needed
forge version
```

它应该输出独立公共 CLI 自身的版本、commit 和 build date。

### 4.2 连接到 Forge service

最直接的方式：

```bash
forge login --server https://forge.example.com --token <token>
forge doctor
```

不想落本地配置时，也可以：

```bash
export FORGE_SERVER=https://forge.example.com
export FORGE_TOKEN=<token>
forge doctor
```

公共 CLI 默认使用 `30s` HTTP 超时；如果 relay / service 网络环境更慢，可以用
`FORGE_HTTP_TIMEOUT=45s forge doctor` 这类方式显式覆盖。

### 4.3 公共 CLI 的服务语义

公共 CLI 当前覆盖的核心操作是：

- `forge doctor`
- `forge inject`
- `forge review-raw`
- `forge review-queue`
- `forge promote-raw`
- `forge promote-ready`
- `forge synthesize-insights`
- `forge receipt get`
- `forge job get`

它不负责：

- 在本地 repo 上启动 `serve`
- 直接读取 repo-local `.env`
- 直接操作 `--repo-root`
- 代替维护者执行 repo-local 校验或发布步骤

## 5. Maintainer / Self-Hosted 边界

自托管 Forge service 仍然按仓库内流程维护：

```bash
uv sync
uv run forge --repo-root . serve --host 127.0.0.1 --port 8000
```

如果维护者要验证公共 CLI 对 service 的表现，可以在 service 起好后，再用独立 `forge`：

```bash
forge login --server http://127.0.0.1:8000 --token <token>
forge doctor
```

但发布文档里必须继续明确：

- `serve` 是 maintainer/self-hosted 语义
- `forge ...` 是 public/service 语义
- `uv run forge --repo-root . ...` 是 repo-local/maintainer 语义

## 6. 最小发布流程

在默认公共仓库 `hoastyle/forge` 下，最小 release/distribution 流程建议固定为：

1. 在仓库内确认待发布版本与文档已收口
2. 构建独立公共 CLI（入口：`cmd/forge`）
   ```bash
   scripts/release/build-public-cli.sh v0.1.0
   ```
   默认只构建当前 host target，确保单机命令可直接跑通。
   如果要做多 target release matrix，再显式设置：
   ```bash
   FORGE_BUILD_TARGETS="linux/amd64 linux/arm64 darwin/arm64" \
     scripts/release/build-public-cli.sh v0.1.0
   ```
   这一步应运行在支持对应 target 的 Go toolchain / builder 上。
3. 做最小验证：
   - `forge version`
   - `forge login --server ... --token ...`
   - `forge doctor`
   - 至少一条 mutation/read 路径，例如 `forge review-queue` 或 `forge receipt get`
4. 在 `hoastyle/forge` 创建 GitHub Release，并上传公共 CLI 资产
5. 如需维护 Homebrew tap，再渲染 formula：
   ```bash
   scripts/release/render-homebrew-formula.sh \
     --version v0.1.0 \
     --archive-sha256 <archive-sha256> \
     --archive-url <release-archive-url>
   ```
6. README 与 release/distribution 文档保持同一口径

如果某个版本会改变 public operator contract，例如：

- 命令名变化
- service 鉴权方式变化
- `receipt get` / `job get` 语义变化
- public 安装渠道变化

则该版本必须同步更新：

- `README.md`
- `docs/management/forge-release-distribution.md`
- 必要时 `docs/management/forge-operator-guide.md`
- 必要时 `.agents/skills/using-forge/SKILL.md`

发布检查点应明确把 “release 说明与 `using-forge` skill 是否同步” 作为 checklist 项，
不能只停留在口头约定。

## 7. README 级别的固定口径

README 应始终保持以下表达，不要混写：

- 公共用户：`forge ...`
- 维护者：`uv run forge --repo-root . ...`
- 默认公共仓库：`hoastyle/forge`
- 公共 CLI 面向已配置服务，而不是本地仓库

只要这几条不漂移，public CLI / service / maintainer 三层关系就不会混乱。
