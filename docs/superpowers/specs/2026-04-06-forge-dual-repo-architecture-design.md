---
title: Forge 双仓架构与公开分发设计
created: 2026-04-06
updated: 2026-04-06
tags: [spec, architecture, distribution, deploy, repository]
status: active
source: "2026-04-06 会话整理：基于代码可 public、数据必须 private 的前提重定义 Forge 仓库边界"
---

# Forge 双仓架构与公开分发设计

## 1. 背景

当前 Forge 仓库同时承担了四种角色：

- 代码仓库
- 数据仓库
- 部署仓库
- release / install script 分发仓库

这导致两个结构性问题：

1. `forge ...` 被当作面向公共操作者的入口，但安装与 release 分发仍绑定在私有源码仓库上。
2. 真正需要保护的是 `raw -> knowledge -> insights` 数据，而不是 CLI / service / runtime 代码本身。

由此带来的直接症状包括：

- 私有仓库上的 GitHub Release / raw.githubusercontent 下载链天然不适合作为公共安装入口
- operator 文档混杂了 public usage、repo-local 维护和实例级数据运维
- howie_server 目前仍在消费“源码副本 + 本地构建”，而不是稳定的 runtime artifact

本设计的目标是把“代码可 public、数据必须 private”落实为清晰的仓库边界、发布链路和部署模型。

## 2. 设计目标

- 将 Forge 工具代码与 Forge 数据彻底解耦
- 让 `forge ...` 保持为面向操作者的统一入口
- 让公开分发面不再依赖私有源码仓库可见性
- 让私有数据仓库只消费稳定 runtime，而不是依赖源码目录结构
- 让 howie_server 以及后续环境统一消费版本化镜像，而不是在目标机上构建源码

## 3. 非目标

- 不保留当前“从私有源码仓库直接 public install”的模型
- 不把 SSH alias 视为长期的 service discovery 方案
- 不将 `forge-np` 这类本地 workaround 进入正式产品或正式文档
- 不使用 `latest` 作为私有数据仓库的默认运行时依赖
- 不使用 `git submodule` 将公共代码仓库嵌入私有数据仓库

## 4. 仓库拓扑

### 4.1 公共代码仓库

仓库名：

```text
hoastyle/forge
```

职责：

- 承载 CLI、service、automation 和 runtime 相关代码
- 承载测试、打包、镜像构建、GitHub Release 与 GHCR 发布
- 承载 install script、公共 README、operator 文档、release 文档

应包含：

- `cmd/forge`
- `automation/`
- `scripts/`
- `packaging/`
- `tests/`
- `Dockerfile`
- 公共使用与发布文档

不应包含：

- 任何真实 `raw/knowledge/insights`
- 任何实例级 `.env`
- 任何真实 token、relay endpoint、私有 service URL
- 任何只对 howie_server 或单一实例成立的部署状态

### 4.2 私有数据仓库

当前仓库保留为私有数据仓库，逻辑上定位为：

```text
forge-data
```

职责：

- 承载所有 `raw/knowledge/insights`
- 承载实例级配置与部署配置
- 承载环境相关运维材料
- 承载运行时版本 pin

应包含：

- `raw/`
- `knowledge/`
- `insights/`
- 私有 `.env`
- `docker compose` 覆盖配置
- howie_server 等环境级部署材料
- runtime version pin 文件

不应包含：

- CLI / service 源码
- 通用测试代码
- GitHub Release 分发资产
- install script 本体
- “公共安装方式”文档

## 5. 两仓之间的唯一稳定接口

私有数据仓库只消费稳定镜像 tag，不消费源码结构。

标准接口：

```text
ghcr.io/hoastyle/forge:<tag>
```

例如：

```text
ghcr.io/hoastyle/forge:v0.1.0
```

运行时 pin 推荐写入私有数据仓库中的固定文件，例如：

```bash
FORGE_IMAGE=ghcr.io/hoastyle/forge:v0.1.0
FORGE_PUBLIC_PORT=18080
```

关键约束：

- 私有数据仓库不依赖公共代码仓库目录结构
- 私有数据仓库不记录源码 commit 作为部署依赖
- 私有数据仓库不使用 submodule
- 升级 runtime 必须显式修改 image tag 并提交

## 6. 发布与分发模型

### 6.1 公共代码仓库负责的发布链路

公共代码仓库 `hoastyle/forge` 负责：

1. 运行测试
2. 构建 `forge` CLI release assets
3. 创建 GitHub Release
4. 发布镜像到：

```text
ghcr.io/hoastyle/forge
```

### 6.2 私有数据仓库的消费模型

私有数据仓库不构建代码，只消费已发布 runtime：

- 拉取固定镜像 tag
- 用私有数据目录作为 `repo_root`
- 用独立状态目录作为 `state_root`
- 显式 pin 版本，显式升级，显式回滚

### 6.3 安装与使用口径

用户入口保持为：

```bash
forge ...
```

但该入口的 install / release 文档全部由公共代码仓库承载。

私有数据仓库不再承担以下职责：

- 提供 public install 入口
- 提供 GitHub Release 资产
- 提供 `go install` 路径

## 7. howie_server 的目标部署模型

### 7.1 当前模型

当前 howie_server 仍基于“同步源码副本 + 本地构建 / 远端构建”的思路运行。

这在过渡期可接受，但不是目标模型。

### 7.2 目标模型

howie_server 应改为消费：

- 已发布的公共镜像
- 私有数据仓库中的数据与配置

不再依赖：

- 源码同步到目标机
- 目标机构建源码
- `--build-local` 作为常规路径

目标部署流程：

1. 从私有数据仓库同步数据与部署配置
2. 读取 `FORGE_IMAGE`
3. `docker compose pull`
4. `docker compose up -d`
5. 执行 `healthz` / `doctor` readiness 校验

### 7.3 回滚模型

回滚以镜像 tag 为核心：

- 公共代码仓库回滚依赖旧 tag / 旧镜像
- 私有数据仓库只需把 `FORGE_IMAGE` 改回旧版本并重新部署

这比回滚源码副本更加稳定、可审计，也更符合运维习惯。

## 8. 文档口径

### 8.1 公共代码仓库文档

公共代码仓库只讲：

- 如何安装 `forge`
- 如何连接 service
- 如何查看 release / image tag
- 如何自托管 runtime
- 如何做公共 release / GHCR 发布

### 8.2 私有数据仓库文档

私有数据仓库只讲：

- `raw -> knowledge -> insights`
- 数据仓库结构
- 实例级配置
- 如何 pin `FORGE_IMAGE`
- 如何部署到 howie_server
- 如何备份、回滚、迁移数据

### 8.3 文档归属规则

以下主题默认应属于公共代码仓库：

- public
- install
- release
- ghcr
- GitHub Releases
- `go install`

以下主题默认应属于私有数据仓库：

- `raw`
- `knowledge`
- `insights`
- howie_server
- 私有 token
- 实例配置

## 9. 网络与访问边界

过渡期内，对内网 service 的访问可以使用：

- 稳定 IP 或稳定域名
- `NO_PROXY` / `no_proxy`

但以下方案不进入正式设计：

- 把 SSH alias 当作 public service 地址
- 在 wrapper 中硬编码 `FORGE_TOKEN`
- 在正式文档中推广 `forge-np`

`forge-np` 在本设计中被明确视为一次性 workaround，不保留。

## 10. 迁移策略

### 10.1 迁移阶段

1. 编写并确认双仓架构设计
2. 新建公共代码仓库 `hoastyle/forge`
3. 从当前仓库提取代码面到公共代码仓库
4. 在公共代码仓库打通 GitHub Release 与 GHCR
5. 将当前仓库收缩为私有数据仓库
6. 重写 howie_server 部署方式，使其消费镜像而非源码
7. 全量改写文档口径

### 10.2 风险控制

- 不对当前仓库做历史清洗后直接公开
- 不让数据与代码在迁移期间继续混写新职责
- 在公共代码仓库发布链路稳定前，不切断旧部署能力
- 在私有数据仓库完成 image pin 前，不切换为纯镜像部署

## 11. 实施顺序建议

推荐顺序：

1. 新建公共代码仓库骨架
2. 迁移代码与测试
3. 打通 release + GHCR
4. 为私有数据仓库新增 `FORGE_IMAGE` pin 文件
5. 重写 howie_server 部署脚本 / compose 逻辑
6. 重写 README / operator / release / deployment 文档
7. 删除过时的“public install from private repo”口径

## 12. 成功判据

当以下条件同时满足时，视为双仓架构迁移完成：

- `hoastyle/forge` 成为公开代码仓库
- GitHub Release 与 GHCR 均由公共代码仓库发布
- 私有数据仓库只保存数据、配置和部署材料
- 私有数据仓库通过显式 `FORGE_IMAGE` pin 消费 runtime
- howie_server 不再构建源码
- README / release / operator / deployment 文档全部不再混淆 public code 与 private data

