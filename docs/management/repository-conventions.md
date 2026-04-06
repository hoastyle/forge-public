---
title: Forge 仓库约定
created: 2026-04-05
updated: 2026-04-06
tags: [management, conventions, git, commit, automation]
status: active
source: "2026-04-05 会话整理：将提交规则与仓库级约定从 agent 规则补到人类可读文档"
---

# Forge 仓库约定

## 1. 文档定位

这份文档记录的是 **仓库级约定**，不是流水线架构设计，也不是日常操作手册。

分工如下：

- `docs/management/forge-operator-guide.md` 负责“怎么用 Forge”
- `docs/management/forge-llm-pipeline-v1.md` 负责“Forge 当前怎么实现”
- `docs/management/repository-conventions.md` 负责“提交、入口、校验这些全仓库通用约定”

## 2. CLI 入口约定

公共用户文档中的标准入口统一写成：

```bash
forge ...
```

维护者 / 仓库内操作的标准入口统一写成：

```bash
uv run forge --repo-root . ...
```

兼容 / 维护入口说明：

- `./automation/scripts/forge ...` 只是 repo-local 兼容包装器
- `python -m automation.pipeline ...` 只保留为底层兼容 / 调试入口

除兼容性说明外：

- 面向公共用户、agent、operator 的文档应优先使用 `forge ...`
- 面向仓库维护者、自托管部署、repo-local 调试的文档应优先使用 `uv run forge --repo-root . ...`

## 3. Commit 规则

### 3.1 Canonical Format

提交主题格式固定为：

```text
type(scope): summary
```

允许值：

- `type`: `docs` `feat` `fix` `refactor` `chore` `revert`
- `scope`: `raw` `knowledge` `insight` `automation` `config`

### 3.2 何时必须写 body

以下情况必须补 body：

- 变更跨多个文档或目录
- 调整了结构、约定、规范
- 含有显著技术内容
- 会影响知识组织或管理文档

### 3.3 Body 模板

```text
type(scope): 简要说明

一句话概述本次提交。

背景：
- ...

本次改动：
- ...

收益：
- ...

结果：
- ...
```

### 3.4 行宽

- commit message 每一行都不应超过 `100` 个字符

## 4. 文档同步约定

如果改动影响以下内容，应该在同一轮收口里同步文档：

- CLI 入口或命令语义
- `raw -> knowledge -> insights` 的 trigger 规则
- `.env`、`doctor`、LiteLLM、relay 证据链
- `review-raw` / `review-queue` / `promote-raw` / `promote-raw --all` / `promote-ready` 这类运维入口

同步优先级如下：

1. 代码 / CLI 实现
2. `docs/management/forge-operator-guide.md`
3. `docs/management/forge-llm-pipeline-v1.md`
4. `README.md`
5. 必要时补 `docs/management/CONTEXT.md` / `docs/management/TODO.md`
6. `.agents/skills/using-forge/SKILL.md`（AI-facing operator contract）

## 4.1 AI-facing Skill 同步规则

`.agents/skills/using-forge/SKILL.md` 是本仓库面向 AI 工具与操作者的标准化入口之一。

以下变更必须在同一轮收口中同步更新该 skill：

- 公共 `forge ...` 的命令语义、参数、入口优先级
- `forge login` / `forge logout` / `forge receipt get` / `forge job get` / `forge serve`
- receipt / trace 字段
- detached job 语义
- `raw -> knowledge -> insights` 的 trigger 规则
- `.env` / `doctor` / LiteLLM / relay / service token 操作口径
- 版本发布、release gate、或标准 operator workflow

这条规则同样适用于版本发布：

- 如果一个版本的发布说明或能力变化会改变“其他工具/人应该如何使用 Forge”，则该版本必须同步更新
  `.agents/skills/using-forge/SKILL.md`

## 5. 提交前校验

默认建议至少执行：

```bash
uv run --no-env-file python -m unittest discover -s tests
./automation/scripts/validate-provenance.sh
./automation/scripts/generate-index.sh
git diff --check
```

如果本次改动只涉及纯文档，可按实际范围减少测试，但 `git diff --check` 仍应执行。
