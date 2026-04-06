---
title: Forge 重要 TODO 清单
created: 2026-04-03
updated: 2026-04-06
tags: [management, roadmap, todo, automation, pipeline, insights, litellm]
status: active
source: "2026-04-03 会话整理：将长期演进方向固化为持续迭代 TODO"
---

# Forge 重要 TODO 清单

## 使用原则

本清单只记录 **Forge 仓库自身** 需要持续推进、会跨多个会话反复回看的事项。

维护规则：

- 新增 repo 级目标时，先写入本清单，再拆分为实施文档或阶段任务
- 每次阶段性推进后，更新状态、里程碑和下一步动作
- 背景记忆与外部长期设想不写成当前 backlog
- 避免把一次性小修小补写进这里

## Priority 1: Forge LLM 自动化流水线

**状态**: in-progress

**目标**:

- 将 `raw -> knowledge -> insights` 自动化能力升级为基于 LLM 的高质量流水线
- 保持轻量、可扩展、可微调、可审计
- 通过自然语言控制系统演进，但生产运行只执行锁定后的 flow / policy

**基线文档**:

- `docs/management/forge-llm-pipeline-v1.md`
- `docs/management/forge-operator-guide.md`
- `docs/management/repository-conventions.md`

**核心要求**:

- 控制平面 / 运行平面分离
- 结构化输出优先于自由文本输出
- writer / critic / judge 分层
- deterministic validators + replay evals + 保守发布
- 模型接入层独立，可接 LiteLLM

**已完成里程碑**:

- [x] 建立 `automation/pipeline/` 最小骨架
- [x] 实现 `llm_client.py` 并接入 LiteLLM SDK 接口
- [x] 落地 `raw -> knowledge` 的 writer / critic / judge 流
- [x] 建立 `synthesize-insights` 批处理流程
- [x] 建立控制平面的 patch schema 与 `runtime.lock.json`
- [x] 建立 failure review / replay / auto-retune 最小闭环
- [x] 将 `validate-provenance.sh` 接入发布门禁
- [x] 为 `doctor` 补充 repo-local LiteLLM 启用路径与 provider 诊断
- [x] 在 repo-local `.env` 下完成一次真实 LiteLLM inject smoke test，并确认 `pipeline_mode=llm`
- [x] 为真实 LiteLLM 运行补充 `llm_trace_ref` 与 stage trace 证据链
- [x] 为真实 LiteLLM 请求补充 `x-forge-trace-id` 请求头，并在本地 trace/request metadata 中保留 `forge_trace_id`
- [x] 将 relay 返回的 `request_id` 纳入 trace / receipt，并覆盖 fallback 回填路径
- [x] 在 relay token log API (`/api/log/token`) 上验证失败流 `request_id` 回查链
- [x] 验证 `/v1/responses + metadata` 会触发 relay `502`，并在 Forge 侧改为仅发送 `x-forge-trace-id`
- [x] 补一次成功流 `pipeline_mode=llm` 的 `request_id` 回查验证，并将 `/api/log/token` 固化为最小验证路径
- [x] 在 `doctor` 与 CLI 入口显式提示残留 `all_proxy/http_proxy/https_proxy`
- [x] 产出第一篇 `insights/patterns/` 文档
- [x] 新增统一 operator guide，收口 `Codex / Claude Code / Feishu / OpenClaw` 的使用说明

**当前 backlog**:

- [ ] 持续维护 `docs/management/forge-llm-pipeline-v1.md`、`docs/management/forge-operator-guide.md` 与 README 和当前实现的一致性，
  重点收口 raw `status` vs `disposition`、`review-queue` / `promote-ready --dry-run --limit` 用法、
  `promote-raw --all` batch 语义、`evidence_trace_ref` / evidence trace，以及 insight 字段名/标题名映射
- [ ] 评估是否需要在 relay / provider 侧定制写入 `x-forge-trace-id` 或 `forge_trace_id`，形成更强的外部侧证
- [ ] 评估 proxy warning 是否需要升级为自动隔离或命令级 opt-in
- [x] 强化 `insight_writer` prompt 与 insight renderer，使默认产物能更稳定表达 `Pattern / Diagnostic Ladder / Mitigation / Anti-Patterns` 这类模式层结构
- [x] 提高 insight evidence gate：保留 tag-cluster 作为 evidence 候选入口，但在聚类前过滤 correction-like /
  superseded / generic-tag knowledge，并把 `pattern / diagnostic_ladder / mitigation` 纳入 deterministic 质量门
- [ ] 根据实际使用反馈决定是否继续细化 heuristic / llm fallback 行为
- [x] 为现存 `raw` 补上显式 `review-raw` / `promote-raw` 入口，降低“只落 raw、不再提升”的长期积压
- [x] 补上 `promote-raw --all`，避免历史材料只能单篇 backfill
- [x] 补上 `review-queue`，避免长期依赖人工读全量 `review-raw` receipt
- [x] 补上 `promote-ready`，让当前 `review-queue` 中的 `ready` 项可以走显式半自动推进
- [x] 为 `promote-ready` 增加 `--dry-run` / `--limit`，支持队列预览与分批执行
- [x] 为 `promote-ready` 增加 `--confirm-receipt`，支持 dry run 之后按 receipt 显式确认执行
- [x] 为 insight synthesis 落地 `evidence_trace_ref`，把 evidence 过滤 / 候选 / 选中路径持久化到 `state/traces/insights/`
- [x] 将 evidence candidate generation 从单纯 filtered tag-cluster 升级到 tag-seed + retrieval-graph，再做 signal/causal reranking
- [ ] 评估是否要在保留显式默认值的前提下，继续强化 opt-in 的半自动推进策略（例如 dry-run 后确认执行、手工确认后批量 promote、定时 synthesize 仍保持关闭）
- [ ] 继续扩充高价值 `raw` / `knowledge`，为 insight 层提供更扎实的证据基座

## 背景记忆 / 外部长期议题

以下两项继续保存在 Forge 的记忆体系中，但 **不作为本仓库当前直接 backlog**：

- **Code Map**：公司层面 / 个人层面的代码地图设计与可视化
- **Autoresearch**：更高阶的自我迭代、自我评估与制度化自校正机制

这些议题可以为未来更大的系统提供方向参考，但当前 repo 的执行重点仍是 Forge 自身的 pipeline、knowledge、insight 与运行诊断能力。

## 下一步建议

1. 持续维护 pipeline 设计文档、operator guide 与 README 和当前实现的对齐
2. 在已有 `review-raw` / `review-queue` / `promote-raw` / `promote-raw --all` / `promote-ready --dry-run/--limit/--confirm-receipt` 的基础上，继续设计更强的 opt-in 半自动推进
3. 评估是否需要继续定制 `forge_trace_id` 日志，并决定 proxy warning 是否升级为更强隔离
4. 继续验证并收紧已落地的 insight gate，重点观察 filtered candidate generation + retrieval graph + signal/causal reranking 的误吸入率，并评估何时升级到更强检索 / 因果判定
