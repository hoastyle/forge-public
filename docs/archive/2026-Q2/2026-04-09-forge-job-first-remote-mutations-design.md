# Forge 远程 Mutation Job-First 设计

日期：2026-04-09

## 背景

当前 Forge 已经具备较完整的远程执行基础设施：

- service API 支持 mutation 请求带 `detach`
- 服务端可返回稳定的 `job_id`
- 操作者可以通过 `forge job get <job_id>` 查看后台执行状态
- 远程 mutation 也已经支持 `operation_id`，可以作为 retry-safe key

但 public surface 仍然存在一个关键问题：

- 远程 mutation 默认仍偏同步等待
- 一旦 HTTP 超时、网络抖动、代理中断，CLI 可能返回失败
- 与此同时，服务端 mutation 可能已经开始，甚至最终成功

这会让操作者陷入“CLI 说失败，但后台可能成功”的不确定状态。`forge-system-improvement-checklist.md` 已明确把它列为 P0：长耗时 mutation 默认提供稳定异步语义。

## 目标

1. 让远程 mutation 默认采用 detached job 语义。
2. 让操作者显式使用 `--wait` 才进入同步等待模式。
3. 保持 repo-local 模式不变，避免把本地快速操作强行改成异步。
4. 继续复用 `job_id`、`receipt`、`operation_id` 作为事实来源。
5. 保证 public Go CLI、repo-local Python CLI、help、文档、skill 的公开语义一致。

## 非目标

1. 不重做服务端任务执行模型。
2. 不引入“超过阈值自动切后台”的混合模式。
3. 不修改 mutation 的业务逻辑本身，只调整远程调用默认语义。
4. 不改变 `review-raw`、`review-queue`、`doctor`、`receipt get`、`job get` 等非 mutation 读操作。

## 方案比较

### 方案 A：远程默认 detached，`--wait` 显式同步

做法：

- 对远程 `inject`、`promote-raw`、`promote-ready`、`synthesize-insights`
- 默认向 service API 发送 `detach=true`
- 新增 `--wait`，显式请求同步执行

优点：

- operator 心智最稳定
- `job get` 成为默认跟踪路径
- 避免把超时和业务失败混在一起
- 最大程度复用现有后台 job 基础设施

缺点：

- 用户首次使用时需要适应“默认返回 job，而不是直接返回 receipt”

### 方案 B：默认同步，超时后自动后台化

做法：

- 继续先同步等待
- 达到阈值后自动切换 detached job

优点：

- 表面上兼顾“简单场景立即拿结果”和“慢场景不超时”

缺点：

- 客户端和服务端边界更复杂
- 容易出现切换时机不透明、重试语义模糊的问题
- operator 仍然需要理解两套返回形态

### 方案 C：每个命令单独决定默认行为

做法：

- 只改最慢的命令，比如 `promote-ready` / `synthesize-insights`
- `inject` 等保持同步

优点：

- 单次改动最小

缺点：

- 文档、help、skill 更容易继续漂移
- 用户需要记住每个命令不同的默认规则

## 结论

采用方案 A。

理由：

- 它直接解决 checklist 的核心问题，而不是绕开问题
- 现有实现已经具备 detached/job/operation-id 支撑
- 公开 contract 可以形成非常简单的规则：
  - 远程 mutation 默认提交 job
  - 想同步等结果时显式加 `--wait`
  - 想确认是否成功时看 `job` / `receipt`

## 适用命令

本次变更只覆盖远程模式下的以下 mutation：

- `forge inject`
- `forge promote-raw`
- `forge promote-ready`
- `forge synthesize-insights`

其中：

- public Go CLI 只支持远程模式，因此这些命令默认都变成 job-first
- repo-local Python CLI 只有在“解析到远程连接且未显式要求本地执行”时，才应用 job-first

以下情况保持同步语义：

- Python CLI 使用 `--repo-root`
- Python CLI 使用 `--local`
- 任何 repo-local 直接调用 `ForgeApp` 的场景

## 公开 Contract

### 1. 默认行为

远程 mutation 默认等价于：

```bash
forge <mutation> ...
```

等价于：

```bash
forge <mutation> ... --detach
```

成功时通常返回：

```json
{
  "job_id": "promote-ready-abc123",
  "status": "queued",
  "message": "job queued",
  "operation_id": "..."
}
```

这里的 `status=queued|running|success|failed` 是 job 状态，不代表 mutation 最终 receipt 已经生成。最终完成态仍需通过 `forge job get` 追踪，必要时再读取 `receipt_ref`。

### 2. `--wait`

远程 mutation 新增：

```bash
forge <mutation> ... --wait
```

语义：

- 明确要求同步等待服务端返回最终 receipt
- CLI 向服务端发送 `detach=false`
- 更适合脚本里必须立即消费 receipt 的场景

规则：

- `--wait` 与 `--detach` 互斥
- 未指定两者时，远程默认使用 detached

### 3. `--detach`

`--detach` 继续保留，主要价值变成：

- 明确表达“我就是要 job-first”
- 让 help/skill 与现有 contract 保持向后兼容

虽然它在远程默认模式下通常是冗余的，但保留它可以降低破坏性，并避免老脚本直接失效。

## 返回与事实来源

### 1. Job-first 场景

远程默认 mutation 返回 job payload。操作者应当使用：

```bash
forge job get <job_id>
```

在 job 成功后，再根据 `receipt_ref` 使用：

```bash
forge receipt get <receipt_ref>
```

### 2. 同步等待场景

显式 `--wait` 时，CLI 直接返回最终 receipt payload。

### 3. 设计原则

继续强调以下事实来源优先级：

1. `job` 是后台执行状态的事实来源
2. `receipt` 是 mutation 结果的事实来源
3. CLI 进程退出本身不应被视为业务完成证据

## 错误处理

### 1. 远程默认 detached 时

如果 job 提交成功，CLI 应返回 0，即使业务尚未完成。

如果 job 提交阶段失败，CLI 返回非 0，并输出明确错误：

- 无法连接服务端
- 鉴权失败
- 参数冲突
- operation id 冲突

### 2. `--wait` 时

若最终 receipt `status=failed`，CLI 返回非 0。

### 3. 参数规则

以下冲突必须在 CLI 层直接拦截：

- `--wait` 与 `--detach` 同时出现

错误信息应明确指出：

- 哪两个 flag 冲突
- 当前命令默认行为是什么
- 下一步如何修正

## 实现边界

### 1. Python CLI

`automation/pipeline/cli.py` 需要：

- 给远程 mutation 增加 `--wait`
- 构造远程 payload 时根据 `--wait` / `--detach` 计算最终 `detach`
- 本地执行路径忽略 `--wait`

计算规则：

- 本地模式：不使用 `detach`
- 远程模式：
  - `--wait=true` => `detach=false`
  - `--detach=true` => `detach=true`
  - 都未指定 => `detach=true`

### 2. Public Go CLI

`cmd/forge/main.go` 需要：

- 给四个 mutation 命令都增加 `--wait`
- 做 `--wait` / `--detach` 互斥校验
- 默认向服务端发送 `detach=true`

### 3. Service API

服务端原则上无需新增接口，也无需改动 job 执行模型。

它已经支持：

- `detach=true` 返回 `202 + job`
- `detach=false` 返回 `200 + receipt`

本波只需要保证客户端 contract 与现有服务端行为一致。

## 文档与 Skill

以下文档必须同步更新：

1. `docs/management/forge-command-contract.md`
2. `docs/management/forge-operator-guide.md`
3. `.agents/skills/using-forge/SKILL.md`
4. `.agents/skills/using-forge/references/forge-command-recipes.md`

更新重点：

- 远程 mutation 默认 job-first
- `--wait` 的使用场景
- `job get -> receipt get` 的闭环
- `operation_id` 继续作为 retry-safe 语义

## 验证要求

至少覆盖以下验证：

1. Python CLI 远程 `inject` / `promote-raw` / `promote-ready` / `synthesize-insights`
   - 默认 payload 为 `detach=true`
   - `--wait` 时 payload 为 `detach=false`
   - `--wait` 与 `--detach` 冲突时报错
2. Public Go CLI
   - 四个 mutation 默认发送 `detach=true`
   - `--wait` 覆盖为 `detach=false`
   - 帮助文案与解析规则一致
3. 文档与 skill
   - 示例命令、默认语义、闭环步骤一致
4. 回归测试
   - `uv run --extra server --no-env-file python -m unittest discover -s tests`
   - `go test ./cmd/forge -v`
   - `git diff --check`
