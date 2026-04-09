# Forge Promote Visibility And Operator Errors 设计

日期：2026-04-09

## 背景

上一轮已经完成了两件关键事：

- 远程 mutation 默认改成 job-first
- public CLI / docs / skill 的主流程语义已经对齐

这使得当前剩余问题更聚焦到 operator 可见性与排障体验：

1. `promote_raw` 已经返回 `publication_status` / `judge_score` / `eligible_for_insights`，但还没有把“最近一次相关 receipt”稳定暴露出来。
2. `knowledge get` 现在能看发布状态，但仍缺少 `last_receipt_ref`，operator 还需要自己倒查 receipt 历史。
3. 失败 payload 仍然过度依赖 `message` 文本，缺少更稳定的 `error_code` 和直接的下一步提示。

这意味着 checklist 里的 P0-3、P0-4、P0-5 已经有了基础，但还没形成一个完整、可操作的闭环。

## 目标

1. 在 `knowledge get` 中公开 `last_receipt_ref`。
2. 在 `promote_raw` 结果中公开 `last_receipt_ref`。
3. 让 `promote-ready` 的执行结果自动带出每个 item 的 `last_receipt_ref`，因为它复用 `promote_raw` receipt。
4. 为关键 operator-facing 失败面增加稳定的 `error_code`。
5. 为这些失败面增加直接可执行的 `next_step`。

## 非目标

1. 不新增新的 operator 命令。
2. 不在本次变更里设计完整的全局错误码体系。
3. 不修改 promotion / judge / insight selection 的业务算法。
4. 不重做 service API 路由结构，只在现有 payload 上增强。

## 方案比较

### 方案 A：只改文案，不加结构化字段

做法：

- 保持当前 payload 结构不变
- 仅把 `message` 写得更长、更具体

优点：

- 改动最小

缺点：

- 自动化脚本无法稳定匹配失败类型
- docs / skill 难以围绕稳定 contract 编写

### 方案 B：增加 `error_code`，但不加 `next_step`

做法：

- 新增稳定错误码
- 失败原因仍主要靠人读 `message`

优点：

- 自动化更稳定

缺点：

- operator 仍然要自己推断下一步动作

### 方案 C：增加 `error_code` + `next_step`，并补齐 `last_receipt_ref`

做法：

- 为关键失败面补结构化字段
- 同时把 publication/status 查询链路补齐

优点：

- 人和脚本都更容易消费
- 与 checklist 的“是什么错、为什么错、下一步怎么做”目标一致
- 不需要额外新命令就能形成闭环

缺点：

- 需要同时修改 app、service、CLI 测试与文档

## 结论

采用方案 C。

## 公开 Contract

### 1. `knowledge get`

返回字段补充：

- `last_receipt_ref`

含义：

- 指向当前 knowledge 最近一次相关的完成态 receipt
- 优先用于 operator 追溯“这条 knowledge 是如何进入当前状态的”

### 2. `promote_raw`

返回字段补充：

- `last_receipt_ref`
- `error_code`
- `next_step`

约束：

- 成功 promote 时，`last_receipt_ref` 通常等于当前 receipt 自身
- `already promoted` 时，`last_receipt_ref` 应尽量指向历史上最近一次与该 knowledge 相关的 receipt，而不是当前这个“skipped receipt”

### 3. `promote-ready`

不新增顶层 publication 字段；继续复用批量 `results`。

变化：

- 每个成功或 skipped 的结果项，通过复用 `promote_raw` receipt，自然带出
  - `publication_status`
  - `judge_score`
  - `judge_decision`
  - `eligible_for_insights`
  - `excluded_reason`
  - `updated_at`
  - `last_receipt_ref`

这样 operator 在 batch promote 结束后，不需要额外猜测哪条 knowledge 当前可用。

## Operator Error Contract

本次只覆盖最常见的 operator-facing 失败面。

### 1. Read 路径

覆盖：

- `receipt get`
- `knowledge get`
- `explain insight`

返回字段：

- `status=failed`
- `message`
- `error_code`
- `next_step`

示例：

- `RECEIPT_NOT_FOUND`
- `RECEIPT_SELECTOR_AMBIGUOUS`
- `KNOWLEDGE_NOT_FOUND`
- `INSIGHT_RECEIPT_MISSING_TRACE`
- `EVIDENCE_TRACE_NOT_FOUND`

### 2. Promote / Confirm 路径

覆盖：

- `promote_raw`
- `promote_ready --confirm-receipt`
- `synthesize-insights --confirm-receipt`

失败 receipt 也补：

- `error_code`
- `next_step`

示例：

- `RAW_NOT_FOUND`
- `RAW_BELOW_PROMOTION_THRESHOLD`
- `READY_CONFIRM_NOT_FOUND`
- `READY_CONFIRM_INVALID_TYPE`
- `INSIGHT_CONFIRM_NOT_FOUND`
- `INSIGHT_CONFIRM_INVALID_TYPE`
- `INSIGHT_CONFIRM_MISSING_MANIFEST`

## `last_receipt_ref` 解析策略

采用“扫描 state receipts 并按最近写入排序”的策略，而不是改动 knowledge 文档 schema。

理由：

- 不污染 knowledge frontmatter
- 能兼容历史数据
- 对 inject / promote_raw 等不同来源 receipt 都可复用

规则：

1. 扫描 `state/receipts/**/*.json`
2. 识别 payload 中直接包含 `knowledge_ref` 的 receipt
3. 按文件最近写入时间倒序选最新项
4. 返回相对路径形式的 `receipt_ref`

非目标：

- 本次不尝试解析所有 batch receipt 的内嵌历史作为 `last_receipt_ref` 候选

## 实现边界

### 1. Models

扩展：

- `KnowledgePublicationStatus.last_receipt_ref`
- `RawPromotionReceipt.last_receipt_ref`
- `RawPromotionReceipt.error_code`
- `RawPromotionReceipt.next_step`
- `ReadyPromotionBatchReceipt.error_code`
- `ReadyPromotionBatchReceipt.next_step`
- `InsightSynthesisReceipt.error_code`
- `InsightSynthesisReceipt.next_step`

### 2. App

新增：

- `_find_latest_receipt_ref_for_knowledge(knowledge_ref)`
- 结构化 operator error 类型，供 read 路径抛出

增强：

- `read_knowledge_status`
- `promote_raw`
- `_confirm_ready_promotion`
- `_confirm_insight_synthesis`
- `read_receipt`
- `explain_insight_receipt`

### 3. Service / CLI

原则：

- 不改 transport 语义
- 只保证结构化错误字段能完整透传到 public payload

## 验证要求

至少覆盖：

1. `knowledge get` 返回 `last_receipt_ref`
2. `promote_raw` 新建成功时返回 `last_receipt_ref`
3. `promote_raw` already promoted 时返回历史 `last_receipt_ref`
4. `promote-ready` batch 结果项包含 `last_receipt_ref`
5. `receipt get` 缺失 / 歧义时返回 `error_code` 与 `next_step`
6. confirm receipt 缺失 / 类型错误时返回结构化错误字段
