# CONTEXT.md - 会话状态与进度摘要

> 本文档记录跨会话的工作状态，由 /sc:load 和 /sc:commit 自动维护
> 最后更新: 2026-04-06

---

## 会话历史

### 2026-04-06

**工作内容**:
- ✅ 为 `promote-ready` 增加 `--dry-run` 与 `--limit`，让 ready 队列支持显式预览与分批执行
- ✅ 为 `promote-ready` 增加 `--confirm-receipt`，让 dry run 结果可以显式确认后再执行
- ✅ 为 insight synthesis 收据补充 `evidence_trace_ref`，并将 evidence 选择 trace 落盘到 `state/traces/insights/`
- ✅ 将 evidence 选择 trace 扩展为可回看 `documents` 过滤原因、`candidate_clusters`、`selected_paths` 与 `selected_score`
- ✅ 将 evidence candidate generation 从单纯 tag-seed 扩展到 tag-seed + retrieval-graph，再做 signal/causal reranking
- ✅ 为上述能力补充 CLI / app 回归测试，并再次通过完整单测、provenance 校验与 `git diff --check`
- ✅ 对齐 README、operator guide、pipeline baseline、TODO 与 CONTEXT 的当前口径

**新增产物**:
- `state/traces/insights/*-evidence.json`（运行时产物，按 receipt 引用）

### 2026-04-05

**工作内容**:
- ✅ 明确纠偏：`Code Map` / `Autoresearch` 仅作为本仓库存放的背景记忆，不作为 Forge 当前直接 backlog
- ✅ 收口本地工作区：补充 `.gitignore`，收录 `raw/captures/2026-04-04-skills-installation-attempt.md`，刷新 `INDEX.md`
- ✅ 新增第一篇 insight：`insights/patterns/pattern-ipv6-ra-rdnss-hidden-control-plane.md`
- ✅ 增强 `doctor` 与 `README`，提供 LiteLLM 的 repo-local 启用路径与 provider key 诊断
- ✅ 在 repo-local `.env` 下跑通真实 LiteLLM inject smoke test，receipt 显示 `pipeline_mode=llm`
- ✅ 为 knowledge / insight 收据补充 `llm_trace_ref`，落地 `state/traces/` 级别的 LiteLLM 运行证据
- ✅ 补齐 LiteLLM transport/auth 失败时的 partial trace 保留与 `heuristic-fallback` 回传
- ✅ 清理测试噪音：移除 `datetime.utcnow()` 弃用告警，并固定 LiteLLM 测试使用本地 model cost map
- ✅ 收录 `raw/captures/2026-04-05-litellm-smoke-test.md` 与对应 `knowledge/workflow/` 草稿记录
- ✅ 已把 `docs/management/forge-llm-pipeline-v1.md` 从“早期设想”对齐到“当前实现 + 明确差距”
- ✅ 新增统一 operator guide，收口 `Codex / Claude Code / Feishu / OpenClaw` 的使用入口与角色语义
- ✅ 新增 `docs/management/repository-conventions.md`，把 commit / CLI / 校验约定补成面向人的管理文档

**提交**:
- `6e7cb81` - 收录 skills 安装记录并清理本地噪音

**新增产物**:
- `raw/captures/2026-04-04-skills-installation-attempt.md`
- `raw/captures/2026-04-05-litellm-smoke-test.md`
- `knowledge/workflow/litellm-smoke-test.md`
- `insights/patterns/pattern-ipv6-ra-rdnss-hidden-control-plane.md`
- `docs/management/forge-operator-guide.md`
- `docs/management/repository-conventions.md`

---

### 2026-04-04

**工作内容**:
- ✅ 在 `feature/unified-injection-baseline` 中完成统一注入与自动化流水线基线实现
- ✅ 建立 `automation/pipeline/`、控制平面 patch schema、runtime lock、failure replay / review / auto-retune 最小闭环
- ✅ 抽象通用 writer / critic / judge 接口
- ✅ 将 `feature/unified-injection-baseline` 快进合并回 `master`
- ✅ 在合并后的 `master` 上再次通过 31 个单元测试与 provenance 校验
- ✅ 删除 `feature/unified-injection-baseline` 分支与对应 worktree
- ✅ 整理 `wip/root-dirty-2026-04-04` 上的知识库 / raw / 管理文档改动
- ✅ 将 `wip/root-dirty-2026-04-04` 快进合并回 `master`
- ✅ 当前工作区已回到 `master`
- ✅ 新增详细交接文档：`docs/management/2026-04-04-unified-injection-baseline-handoff.md`
- ⚠ `github` MCP 启动环境变量继承问题仍待后续处理

**提交**:
- `68f3e07` - 建立统一注入与知识流水线骨架
- `917bbc4` - 增加 insight 批处理流水线
- `ff1667b` - 增加控制平面 patch schema 校验
- `4e5b6a2` - 增加失败案例归档与回放能力
- `681d163` - 增加 auto-retune 最小闭环
- `0abcc4d` - 抽象通用 writer critic judge 接口
- `8f61822` - 同步自动化流水线里程碑状态

**交接文档**:
- `docs/management/2026-04-04-unified-injection-baseline-handoff.md`

---

### 2026-04-03

**工作内容**:
- ✅ 建立 raw→knowledge→insights 溯源验证系统
- ✅ 新增 validate-provenance.sh 脚本
- ✅ 创建 raw/captures/ 目录，补录 5 个历史源文件
- ✅ 更新模板文件支持溯源链
- ✅ 溯源验证通过 (10 files)
- ✅ 落档 Forge LLM 自动化流水线设计 v1
- ✅ 新建长期重要 TODO 清单

**提交**:
- `bc55621` - feat(automation): 建立 raw->knowledge 溯源验证系统

**知识统计**:
- Knowledge: 5 篇
- Raw Captures: 5 篇
- Insights: 0 篇

---

## 项目焦点

**当前阶段**: Priority 1 baseline 已进入 `master`。当前重点不是外部长期议题，而是把 Forge 自身的 pipeline、knowledge、insight、运行诊断与管理文档继续收紧。

**本仓库当前执行目标**:
- 持续校验并巩固 `automation/pipeline/` 的控制平面、运行平面和验证门，确保 `raw -> knowledge -> insights` 的溯源链与锁定状态保持一致
- 把管理文档、README、operator guide 和实际代码能力保持对齐，避免后续会话继续被早期设想误导
- 已新增 `docs/management/forge-operator-guide.md` 作为 `Codex / Claude Code / Feishu / OpenClaw` 的统一操作入口
- 已明确当前 trigger 语义：`inject` 默认只落 `raw`；只有显式 `--promote-knowledge` 才会尝试 `raw -> knowledge`；只有显式 `synthesize-insights` 才会尝试 `knowledge -> insights`
- 已补上显式 `review-raw` / `review-queue` / `promote-raw` / `promote-ready` 入口，并新增 `promote-raw --all`，用于盘点、聚焦待处理项与批量补跑现存 `raw -> knowledge`
- `review-raw.documents[*].status` 与 `disposition` 是两套语义；当前没有正式的 `processed raw` 状态名，`promoted`
  只是由 knowledge backlink 反推出来的 disposition
- `promote-ready` 已支持 `--dry-run`、`--limit` 与 `--confirm-receipt`，可以先预览 ready 队列，再做分批显式确认推进
- 继续把高价值 `knowledge` 提升为 `insights`，让三层知识闭环开始产生真实复用
- 为真实 LiteLLM 运行保留 repo-local 启用路径与诊断信息，但不依赖系统级安装
- 已在真实 provider key 环境下完成一次 smoke test，并通过 `llm_trace_ref` 保留 stage 级运行证据
- 已为 LiteLLM 请求补充 `x-forge-trace-id` 请求头，并在本地 trace/request metadata 中保留 `forge_trace_id`，同时将 relay-native `request_id` 回填到 trace / receipt
- 已确认当前 relay 的 `/v1/responses + metadata` 会触发 `502`；Forge 现已停止向实际请求发送 `metadata`，
  只保留 header 级 correlation key 与本地 trace 中的 `request_metadata`
- `doctor` 已把残留 proxy 环境收进结构化报告，CLI 入口在 LiteLLM 路径上也会向 `stderr` 输出 warning
- 已完成首篇 insight 的内容复核，并将结论落回 `insight_writer` prompt、renderer、deterministic validators 与 evidence selector
- 当前没有后台扫库去回头处理现存 `raw`；如果 inject 未显式带 `--promote-knowledge`，或者内容长度不足 `runtime.knowledge.min_chars`，材料会稳定停留在 `raw`，但现在可以通过显式 `review-raw` / `review-queue` / `promote-raw` / `promote-raw --all` 补处理
- 默认 insight 现要求 `observation / pattern / diagnostic_ladder / mitigation` 完整，渲染结构已补齐
  `Pattern / Diagnostic Ladder / Mitigation Strategy / Anti-Patterns`
- 当前 evidence 选择会跳过 superseded / correction-like / generic-tag knowledge，组合 tag-seed 与 retrieval-graph candidate，
  再对过滤后的候选 cluster 做 lexical signal / causal overlap reranking
- insight synthesis receipt 现已补充 `evidence_trace_ref`，并将 evidence 过滤与候选选择过程持久化到
  `state/traces/insights/`
- 处理本机 `github` / `serena` MCP 启动体验问题作为周边任务

**背景记忆 / 外部长期议题（不作为本仓库当前 backlog）**:
- `Code Map`：公司层面 / 个人层面的代码地图设计与可视化，保留为外部长期记忆
- `Autoresearch`：更高阶的自我迭代、自我评估与制度化自校正机制，保留为外部长期记忆

**已确认的 relay 实现侧证（2026-04-05）**:
- 当前本机 Codex 主配置实际使用的 OpenAI-compatible relay 为 `https://dawclaudecode.com/v1`，而不是早先参考配置里的 `api.aicoding.sh`
- 该 relay 的实现形态高度吻合 `new-api` 家族（更准确地说，是 `new-api` 部署或其定制 fork），而不是 LiteLLM Proxy
- 侧证包括：
  - 站点根路径首页文案与 `QuantumNous/new-api` 的 `web/index.html` 描述一致，均为“统一的 AI 模型聚合与分发网关”
  - `/api/status` 暴露了 `HeaderNavModules`、`SidebarModulesAdmin` 等典型 `new-api` 配置字段
  - 未鉴权访问 `/v1/models` 返回的错误类型为 `new_api_error`
  - 已鉴权访问 `/v1/models` 的模型枚举包含 `supported_endpoint_types=["anthropic","openai"]` 这类 `new-api` 风格字段
  - `/v1/responses` 已可直接走 OpenAI Responses API 兼容入口，因此 Forge 当前的 LiteLLM 请求实际上是“LiteLLM -> new-api relay -> 上游 provider”

**已确认的 relay 记录边界（2026-04-05）**:
- `new-api` 原生日志表会持久化 `request_id`，并且管理端 / API 都支持按 `request_id` 查询
- 对当前 token 而言，`GET /api/log/token` 是最小可用的 API 回查路径；它使用 `TokenAuthReadOnly()`，可直接返回该 token 对应的 logs
- `logs.other` 只会保存 relay 显式构造的结构化字段，例如 `request_path`、倍率/价格、`request_conversion`、`po`、`admin_info`
- `x-forge-trace-id` 请求头会随请求发送给 relay；`forge_trace_id` 当前只保留在 Forge 本地 trace/request metadata 中
- 在 `new-api` 默认实现里，这两类相关键都不会自动落进 `logs.other`
- `RelayInfo.RequestHeaders` 虽然会捕获入站请求头，但当前只用于 header override / param override 的运行时上下文，不会自动持久化为日志证据
- 当前 relay 对 OpenAI Responses API 的兼容是“按参数组合成立”的：`/v1/responses` 本身可用，但附带 `metadata`
  会触发 `502`；只携带 `x-forge-trace-id` header 不会复现该问题
- 结论：当前可落地的外部侧证主键应优先使用 relay-native `request_id`；如果希望在 relay 管理面直接搜索 `forge_trace_id`，需要定制 relay 日志写入逻辑

**当前仓库优先级**:
1. ⏳ 继续对齐 pipeline 设计文档、operator guide、README 与代码实现
2. ⏳ 继续扩充 `insights/` 层，并把当前审阅结论落回 prompt / renderer / evidence gate
3. ⏳ 在已有 `review-raw` / `review-queue` / `promote-raw` / `promote-raw --all` / `promote-ready --dry-run/--limit/--confirm-receipt` 的基础上继续补更强的 opt-in 半自动推进，避免长期积压
4. ⏳ 评估是否要把 `forge_trace_id` 定制持久化到 relay 日志，并决定 proxy warning 是否需要升级为自动隔离

---

## 下一步行动

### 短期 (本周)
- [ ] 继续审阅并维护 `docs/management/forge-llm-pipeline-v1.md`、`docs/management/forge-operator-guide.md` 与实现的一致性
- [x] 在现有 `review-raw` / `promote-raw` 之上补 batch promote CLI 入口
- [x] 在现有 `review-raw` / `promote-raw` / `promote-raw --all` 之上补 review queue 的产品语义与 CLI 入口
- [x] 为 `promote-ready` 补 `--dry-run` / `--limit`，支持半自动队列预览与分批执行
- [x] 为 `promote-ready` 补 `--confirm-receipt`，支持 dry run 后显式确认执行
- [x] 审阅新增 insight 的质量与命名方式，确认当前 exemplar 强于默认 insight 模板
- [x] 把 relay 返回的 `request_id` 纳入 Forge trace / receipt，形成仓库内外一致的关联键
- [x] 在 relay API 侧验证失败流 `relay_request_ids -> /api/log/token -> request_id` 回查链路
- [x] 在 relay 管理面 / API 侧补一条成功流 `pipeline_mode=llm` 的 `request_id` 回查验证
- [x] 在 `doctor` 与 CLI 入口显式提示残留 `all_proxy/http_proxy/https_proxy`
- [ ] 评估是否需要在 relay 侧把 `x-forge-trace-id` / `forge_trace_id` 额外写入 `logs.other`
- [ ] 复核 `docs/management/2026-04-04-unified-injection-baseline-handoff.md` 与当前主线状态是否仍有陈旧表述

### 中期 (本月)
- [ ] 在已并入主线的自动化流水线基线之上继续扩展真实 LLM 运行时与质量门
- [ ] 形成更稳定的 `knowledge -> insights` 提升节奏，继续把 evidence trace 升级到更强的检索 / 因果判定
- [ ] 视实际使用情况决定是否继续细化 failure review / auto-retune 的制度化程度

---

## 关键决策

| 决策 | 日期 | 理由 |
|------|------|------|
| 三层知识结构 | 2026-03-17 | 分离捕获与提炼，降低认知负担 |
| YAML frontmatter | 2026-03-17 | 统一元数据格式，便于自动化解析 |
| 溯源验证 | 2026-04-03 | 确保知识可追溯，防止源头丢失 |
| 控制平面 / 运行平面分离 | 2026-04-03 | 在自然语言可控的同时保持生产确定性 |
| 统一注入基线先落在独立 worktree | 2026-04-04 | 避免与根工作区知识库整理改动互相污染 |
| 将 Code Map / Autoresearch 降级为背景记忆 | 2026-04-05 | 避免把外部长期设想误当作 Forge 当前 backlog |

---

## 技术债务

- [ ] `docs/management/forge-llm-pipeline-v1.md` 与 `docs/management/forge-operator-guide.md` 仍需继续随实现演进保持同步
- [ ] LiteLLM 已具备 receipt + `llm_trace_ref` + `relay_request_ids` + correlation key 的内部证据链，但仍缺少 relay / provider 侧长期稳定的独立侧证
- [ ] 新增 insight 已落库，且 evidence trace 已可审计，但当前 evidence 仍主要依赖过滤后的 tag/retrieval candidate + signal/causal reranking，
  还不是语义检索或强因果验证
- [ ] 当前活跃 insight 文档的结构明显强于默认 `insight_writer.md` + `_render_insight_document()` 的稳定产出，现有 exemplar 不能直接当作流水线默认质量基线
- [ ] 虽然已排除 superseded / correction-like / generic-tag 文档，但弱相关 active knowledge 仍可能因共享具体 tag 被吸入同一 evidence cluster
- [ ] `INDEX.md` 还可以补充 insights 层索引与自动化入口说明
- [ ] `github` / `serena` MCP 的本机启动体验问题尚未独立收口

---

## 配置参考

| 项目 | Forge |
|------|-------|
| **路径** | /home/hao/Workspace/Forge |
| **主分支** | master |
| **当前工作分支** | master |
| **语言** | 中文交互，英文代码 |
| **日期格式** | `$(date +%Y-%m-%d)` |

## 最近收口动作

- 已补录 `raw/captures/2026-04-04-skills-installation-attempt.md` 并刷新 `INDEX.md`
- 已新增首篇 `insights/patterns/` 文档，标志 `knowledge -> insights` 开始有实际产物
- 已补充 `.gitignore`，将本地 skills 安装目录与 `*.pyc` 等环境噪音排除出仓库视野
- 已跑通一次真实 LiteLLM inject smoke test，并补齐 `llm_trace_ref` / partial trace 证据链
- 已把 relay-native `request_id` 收进 stage trace 与 receipt，并补齐 fallback 回填回归测试
- 已在真实 relay 上通过 `/api/log/token` 重复命中失败流 `request_id`，确认 token log API 可作为最小外部侧证路径
- 已为 insight fallback 与 failure archive 的 trace 引用补齐回归测试
- 已复核首篇 insight：确认当前内容质量可作为人工 exemplar，但不能直接代表默认自动生成质量
