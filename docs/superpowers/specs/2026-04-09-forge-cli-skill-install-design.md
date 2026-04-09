# Forge CLI + `using-forge` Skill 安装设计

日期：2026-04-09

## 背景

当前公开安装面只覆盖 Forge CLI：

- `scripts/release/install-public-cli.sh` 只安装 `forge` 二进制
- `README.md` 和 `docs/management/forge-operator-guide.md` 只描述 CLI 安装与操作
- `forge-public/.agents/skills/using-forge/SKILL.md` 没有随着私有仓版本同步演进
- 公开仓目前也没有把 `using-forge` 的配套引用文件一起作为公开分发资产

结果是：用户可以装到 CLI，但 agent 侧拿到的 skill contract 可能缺失、过期，或者必须靠手工复制。

## 目标

1. 公开安装入口默认同时交付 Forge CLI 与 `using-forge` skill。
2. skill 的真实内容只有一份主副本，避免多目录多副本漂移。
3. 默认自动安装到所有已发现的用户级 skill 目录。
4. 不默认改写当前仓库内的 `.agents/skills`，避免把“工具安装”变成“修改项目内容”。
5. 公开仓中的 `using-forge` 内容与当前 operator contract 对齐，包含必要的 reference 文件。

## 非目标

1. 不尝试管理所有 agent 产品的完整安装生态，只覆盖当前已知、可稳定识别的本地 skill 目录。
2. 不默认修改任意 repo-local `.agents/skills`。
3. 不做后台自动更新；升级仍由用户重新运行安装脚本完成。
4. 不在本次变更里扩展新的 Forge 功能命令。

## 方案概览

采用“中立主目录 + 多目标软链接，失败时回退拷贝”的模型。

### 1. 中立主目录

Forge 维护自己的 skill 主目录，而不是把某个 agent 目录当权威源。

建议主目录：

```text
${XDG_DATA_HOME:-$HOME/.local/share}/forge/skills/using-forge
```

这里保存 `using-forge` 的完整公开分发内容，例如：

- `SKILL.md`
- `references/forge-command-recipes.md`
- 未来仍需公开分发的附属文件

### 2. 自动发现用户级 skill 目录

安装脚本默认发现并写入这些用户级目录（存在则安装，不存在则跳过）：

- `${CODEX_HOME}/skills`
- `${HOME}/.codex/skills`
- `${HOME}/.claude/skills`
- `${HOME}/.continue/skills`
- `${HOME}/.factory/skills`

说明：

- `${CODEX_HOME}/skills` 与 `${HOME}/.codex/skills` 需要去重。
- 只处理用户级目录，不处理当前项目目录。

### 3. 安装策略

对每个已发现目标目录：

1. 目标路径是 `<dir>/using-forge`
2. 优先创建指向 Forge 主目录的软链接
3. 如果软链接不可用，或现有路径不适合直接替换，则回退为内容拷贝
4. 安装结果要明确输出：`linked`、`copied`、`skipped`

### 4. repo-local 目录策略

repo-local `.agents/skills` 默认不写入。

只有显式参数，例如 `--include-repo-skill-dir <path>` 或 `--repo-skill-dir <path>`，才允许把 skill 安装到指定项目目录中。

原因：

- 避免污染用户当前仓库
- 避免把全局工具安装与项目版本控制混在一起
- 降低误提交和误覆盖风险

## 发布物设计

### 1. skill 内容进入公开仓

`forge-public` 需要把公开可分发的 `using-forge` 完整化，而不是只保留单个 `SKILL.md`。

至少包括：

- `.agents/skills/using-forge/SKILL.md`
- `.agents/skills/using-forge/references/forge-command-recipes.md`

公开 skill 必须以 `forge-public` 为权威源，不再依赖 `forge-data` 才能拿到完整内容。

### 2. skill bundle 进入 release 资产

release 产物除了 CLI tarball 外，还应增加 skill bundle，例如：

```text
forge_skill_using-forge_<version>.tar.gz
```

bundle 内部包含 `using-forge/` 完整目录树。

这样安装脚本可以直接从 release 下载 skill bundle，而不是从 `main` 分支原始文件拼装安装。

### 3. 安装脚本升级

`scripts/release/install-public-cli.sh` 扩展为：

1. 下载并安装 CLI archive
2. 下载并展开 `using-forge` skill bundle 到 Forge 主目录
3. 自动发现用户级 skill 目录
4. 对每个目录创建软链接；不行时回退拷贝
5. 输出安装摘要与后续验证命令

可选参数建议包括：

- `--no-skill`
- `--skill-only`
- `--skill-home <dir>`
- `--include-repo-skill-dir <path>`

默认行为仍然是“CLI + skill 一起安装”。

## 文档设计

以下文档需要同步更新：

1. `README.md`
   明确公开安装默认会安装 CLI 与 `using-forge` skill。
2. `docs/management/forge-operator-guide.md`
   增加“安装后如何登录、如何使用、如何查看 receipts/jobs”的最短路径。
3. `docs/management/forge-release-distribution.md`
   明确 release 资产现在包含 CLI 和 skill bundle，并要求 operator contract 更新时同步发版。
4. `.agents/skills/using-forge/SKILL.md`
   以公开仓为权威源，补齐当前 operator contract、initiator 约束、trigger 语义、receipt/job 规则和 references。

## 错误处理

安装脚本应当区分这些状态：

1. CLI 安装成功，skill 安装成功
2. CLI 安装成功，部分 skill 目录 link/copy 失败
3. `--skill-only` 成功
4. skill bundle 下载失败
5. 目标目录不可写
6. 目标路径已有冲突文件且无法安全替换

对部分失败，脚本不应静默吞掉；应输出逐目录结果，并给出手工修复提示。

## 验证设计

至少覆盖以下验证：

1. installer 在只装 CLI 时的兼容行为
2. installer 默认安装 CLI + skill
3. 发现多个用户级 skill 目录时会全部处理
4. 软链接成功路径
5. 软链接失败后的拷贝回退路径
6. 不会默认写 repo-local `.agents/skills`
7. skill bundle 的打包内容包含 `SKILL.md` 和 references
8. README / operator docs / skill contract 的口径一致

## 推荐实现顺序

1. 先同步公开版 `using-forge` skill 内容与 references
2. 再增加 skill bundle release 产物
3. 再扩展安装脚本
4. 最后更新 README / operator docs / release docs 和测试

## 风险与取舍

### 1. 为什么不是“直接拷贝到所有目录”

因为多副本升级最容易漂移，后续很难知道哪一份是最新权威源。

### 2. 为什么不是“直接以某个 agent 目录为主目录”

因为这会把 Forge 安装绑定到某一种工具布局，其他工具反而变成附属关系。

### 3. 为什么 repo-local 目录默认不写

因为项目目录属于版本控制对象，默认写入会引入高副作用和误提交风险。

## 决策摘要

本次设计确认以下产品决策：

1. 公开安装默认同时安装 CLI 与 `using-forge` skill。
2. skill 使用 Forge 自己的中立主目录作为唯一真实副本。
3. 自动发现的用户级 skill 目录全部处理。
4. 默认优先创建软链接，失败时回退拷贝。
5. repo-local `.agents/skills` 必须显式参数才会写入。
