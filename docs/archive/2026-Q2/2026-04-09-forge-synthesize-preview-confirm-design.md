# Forge `synthesize-insights` 预演/确认设计

日期：2026-04-09

## 背景

当前公开 contract 中，`forge synthesize-insights` 只有“直接执行”一种模式：

- public Go CLI 只支持 `forge synthesize-insights --initiator ...`
- repo-local Python CLI / service API 也只有直接执行语义
- `using-forge` skill、operator guide、command contract 明确写着暂不支持 `--dry-run` / `--confirm-receipt`

与此同时，`promote-ready` 已经形成稳定的 preview/confirm 模式：

- `--dry-run` 先产出 batch receipt
- `--confirm-receipt` 再执行刚才预览过的那一批对象
- `receipt_ref`、`job_id`、`operation_id` 的行为在 public surface 上已经固定

这意味着 insight synthesis 的下一步最合理演进，不是再发明一套新协议，而是把同一种 operator 心智模型扩展到知识到洞察的这一步。

## 目标

1. 公开支持 `forge synthesize-insights --dry-run`。
2. 公开支持 `forge synthesize-insights --confirm-receipt <receipt_ref>`。
3. preview receipt 必须是后续 confirm 的执行合同，而不是“仅供参考”的提示信息。
4. confirm 执行必须保证证据集没有漂移；一旦漂移，直接失败并要求重新 dry-run。
5. 保持 `forge receipt get`、`forge explain insight`、`--detach`、`--operation-id` 与现有 contract 一致。

## 非目标

1. 不修改当前 insight evidence selection 算法。
2. 不新增独立的 explain API；继续复用 `evidence_trace_ref`。
3. 不在本次变更中引入多批候选确认、人工挑选候选 cluster、或部分确认执行。
4. 不改动 knowledge publication 规则，只处理 knowledge 到 insights 的触发协议。

## 方案概览

采用“复用现有 `InsightSynthesisReceipt`，补齐 preview/confirm 字段”的方案，而不是新增一套 preview receipt 类型。

### 1. public contract 扩展

`forge synthesize-insights` 支持三种显式模式：

1. 直接执行

```bash
forge synthesize-insights --initiator manual
```

2. 仅预演

```bash
forge synthesize-insights --initiator manual --dry-run
```

3. 按 preview receipt 确认执行

```bash
forge synthesize-insights \
  --initiator manual \
  --confirm-receipt state/receipts/insights/<preview>.json
```

约束规则：

- `--dry-run` 与 `--confirm-receipt` 互斥
- `--detach` 允许与直接执行或 dry-run 同时出现
- `--detach` 也允许与 `--confirm-receipt` 同时出现
- `--operation-id` 继续作为远程 mutation 的 retry-safe key

### 2. receipt 设计

沿用 `InsightSynthesisReceipt`，新增以下字段：

- `dry_run: bool`
- `confirmed_from_receipt_ref: Optional[str]`
- `evidence_manifest: List[Dict[str, str]]`

其中 `evidence_manifest` 的每一项最少包含：

- `knowledge_ref`: 当前 evidence 文档路径
- `fingerprint`: 对当前 knowledge 文档完整内容做 `sha256`

继续保留并复用现有字段：

- `evidence_refs`
- `evidence_trace_ref`
- `insight_ref`
- `candidate_ref`
- `critic_ref`
- `judge_ref`
- `pipeline_mode`
- `llm_trace_ref`
- `receipt_ref`

字段语义：

- preview receipt:
  - `dry_run=true`
  - `confirmed_from_receipt_ref=null`
  - `evidence_refs`、`evidence_trace_ref`、`evidence_manifest` 都存在
  - `insight_ref` / `candidate_ref` / `critic_ref` / `judge_ref` 为空
- direct execution receipt:
  - `dry_run=false`
  - `confirmed_from_receipt_ref=null`
- confirm execution receipt:
  - `dry_run=false`
  - `confirmed_from_receipt_ref=<preview receipt_ref>`

### 3. dry-run 行为

`ForgeApp.synthesize_insights(..., dry_run=True)` 的处理顺序：

1. 加载当前可参与 synthesis 的 knowledge 文档。
2. 运行现有 `_select_insight_evidence_with_trace(...)`。
3. 若没有满足 `min_evidence` 的 cluster：
   - 写入 `status=skipped` 的 preview receipt
   - 保留 `evidence_trace_ref`
   - `evidence_refs=[]`
   - `evidence_manifest=[]`
4. 若选出 cluster：
   - 写入 `status=success` 的 preview receipt
   - 记录 `evidence_refs`
   - 为每个 knowledge 文档计算 `fingerprint`
   - 写入 `evidence_manifest`
   - 不生成 insight/candidate/judge 文件

dry-run 的价值是冻结“将被执行的证据集”，而不是预跑一遍完整 insight pipeline。

### 4. confirm 行为

`ForgeApp.synthesize_insights(..., confirm_receipt_ref=...)` 的处理顺序：

1. 读取目标 receipt。
2. 如果 receipt 不存在：
   - 返回 `status=failed`
   - `message="confirm receipt not found"`
3. 如果目标 receipt 不是 `dry_run=true`：
   - 返回 `status=failed`
   - `message="confirm receipt must reference a dry-run insight synthesis receipt"`
4. 读取 preview receipt 中的 `evidence_manifest`。
5. 对每个 evidence 项做一致性校验：
   - 文件仍存在
   - 当前文档仍可参与 insights（状态、标签、纠正类过滤等规则仍满足）
   - 当前内容 `sha256` 与 preview fingerprint 一致
6. 只要任一项不满足，直接返回 `status=failed`，并要求重新 dry-run。
7. 全部通过后，不再重新选证据，直接用 preview 中的固定 `evidence_refs` 执行 `_run_insight_pipeline(...)`。
8. confirm receipt 继续复用 preview 的 `evidence_trace_ref`，因为该 trace 就是这次执行所依据的证据选择说明。

这里的关键决策是：confirm 不重新做 candidate selection。否则 preview receipt 就不是执行合同，用户会得到“看过一批 A，执行了另一批 B”的结果。

### 5. explain 语义

`forge explain insight <receipt_ref>` 继续按 receipt 上的 `evidence_trace_ref` 工作，不增加新接口。

这意味着：

- preview receipt 可以被 `forge explain insight` 解释
- confirm 后的正式执行 receipt 也可以被 `forge explain insight` 解释
- 两者都指向同一份 evidence trace 时，operator 能看到“预览时为什么选了这批证据”

### 6. service / CLI 设计

需要同步扩展三层入口：

1. repo-local Python CLI
   - `automation/pipeline/cli.py`
   - 新增 `--dry-run`
   - 新增 `--confirm-receipt`
   - 做参数互斥校验
   - 本地执行与 remote payload 构造都支持新字段

2. service API
   - `automation/pipeline/service_api.py`
   - `SynthesizeRequest` 增加 `dry_run` 与 `confirm_receipt`
   - `/v1/synthesize-insights` 把参数透传给 `ForgeApp`

3. public Go CLI
   - `cmd/forge/main.go`
   - 新增 `--dry-run`
   - 新增 `--confirm-receipt`
   - help 文案同步更新
   - POST `/v1/synthesize-insights` 时附带新字段

## 错误处理

至少明确处理以下失败面：

1. confirm receipt 不存在
2. confirm receipt 不是 dry-run receipt
3. preview receipt 没有 evidence manifest
4. preview 中某个 knowledge 文档已删除
5. preview 中某个 knowledge 文档已不再 eligible
6. preview 中某个 knowledge 文档内容发生变化
7. preview 中没有任何 evidence refs

返回策略：

- 尽量返回 receipt 级失败，而不是抛裸异常
- 失败 receipt 要保留 `confirmed_from_receipt_ref`
- 若已有 preview `evidence_trace_ref`，失败 receipt 也应尽量带上，方便 operator 直接 explain

## 文档与 skill

以下 operator-facing 文档必须同步进入新 contract：

1. `docs/management/forge-command-contract.md`
2. `docs/management/forge-operator-guide.md`
3. `.agents/skills/using-forge/SKILL.md`
4. `.agents/skills/using-forge/references/forge-command-recipes.md`

更新原则：

- `promote-ready` 和 `synthesize-insights` 的 preview/confirm 语义保持一致
- 继续强调 receipt 是完成态真相源
- 继续强调 detached job 只代表执行句柄，不代表成功

## 验证设计

至少覆盖以下测试：

1. app:
   - dry-run 只产 receipt/trace，不产 insight 成品
   - confirm 能执行 preview 指定的固定 evidence 集
   - confirm 遇到非 dry-run receipt 失败
   - confirm 遇到 evidence 内容漂移失败
   - confirm 遇到 evidence 不再 eligible 失败

2. service API:
   - `/v1/synthesize-insights` 接受 `dry_run`
   - `/v1/synthesize-insights` 接受 `confirm_receipt`
   - `operation_id` 冲突检测对 preview/confirm payload 仍生效

3. Python CLI:
   - 本地 `synthesize-insights --dry-run`
   - 本地 `synthesize-insights --confirm-receipt`
   - remote payload 正确转发 `dry_run` / `confirm_receipt`
   - 参数互斥校验正确

4. public Go CLI:
   - help 展示新 flag
   - payload 正确发送 `dry_run` / `confirm_receipt`

5. docs contract:
   - public contract 开始正式列出 `forge synthesize-insights --dry-run`
   - public contract 开始正式列出 `forge synthesize-insights --confirm-receipt <receipt_ref>`
   - skill / guide / command recipes 与 contract 同步

## 风险与取舍

### 1. 为什么不新增独立 preview receipt 类型

因为现有 operator contract 已经依赖“一个命令一种主 receipt 类型”的阅读方式。继续复用 `InsightSynthesisReceipt`，只增加 preview/confirm 字段，学习成本和文档成本都更低。

### 2. 为什么 confirm 要做内容指纹校验

因为 insight synthesis 的输入不是简单的路径集合，而是知识文档的具体内容。只校验路径存在还不够；如果内容已改，confirm 就不应该假装自己执行了“刚才预演过的东西”。

### 3. 为什么 confirm 不重新选证据

因为 operator 使用 preview/confirm 的核心目的，就是把“将要执行什么”固定下来。重新选证据会破坏这个合同。

## 决策摘要

本次设计确认以下结论：

1. `synthesize-insights` 公开支持 `--dry-run` 与 `--confirm-receipt`。
2. 复用 `InsightSynthesisReceipt`，不新增独立 preview receipt 类型。
3. preview receipt 固化 `evidence_refs + evidence_trace_ref + evidence_manifest`。
4. confirm 必须校验证据未漂移；漂移则失败并要求重新 dry-run。
5. `forge explain insight` 继续复用 `evidence_trace_ref`，不增加新 explain surface。
