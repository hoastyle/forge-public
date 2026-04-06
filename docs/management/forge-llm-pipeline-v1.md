---
title: Forge LLM 自动化流水线设计与实现基线 v1
created: 2026-04-03
updated: 2026-04-06
tags: [llm, automation, litellm, architecture, workflow, orchestration, pipeline]
status: active
source: "2026-04-03 初稿，2026-04-05 按当前实现重写为基线说明文档"
---

# Forge LLM 自动化流水线设计与实现基线 v1

## 1. 文档定位

这份文档不再把 Forge 描述成“未来可能会做什么”的抽象蓝图，而是记录 **当前仓库已经实现的基线**，以及仍然存在的差距。

一句话定位：

- 它既是设计文档，也是当前 `master` 上自动化流水线的状态说明
- 它关注 Forge 自身的 `raw -> knowledge -> insights` 闭环
- 它不承接 `Code Map` / `Autoresearch` 这类外部长期议题
- 它不是日常操作手册；如果你要看 public `forge ...`、maintainer `uv run forge --repo-root . ...`、
  `initiator`、Feishu 接入和角色用法，请先读 `docs/management/forge-operator-guide.md`

## 2. 当前实现快照（截至 2026-04-06）

当前仓库已经具备以下最小可运行能力：

- 统一注入入口：`text` / `file` / `feishu-link`
- `raw -> knowledge` 的 writer / critic / judge 流
- `review-queue` 高信号待处理视图
- `promote-ready --dry-run / --limit / --confirm-receipt` 半自动队列执行控制
- `knowledge -> insights` 的批处理合成流
- 自然语言调优入口：`uv run forge tune`
- failure archive / replay / review / auto-retune 最小闭环
- `runtime.lock.json`、`patch.schema.json`、`golden_cases.json` 等控制平面基线文件
- `doctor` 诊断与 LiteLLM repo-local 启用说明
- 已在 repo-local `.env` 下跑通一次真实 LiteLLM inject smoke test，receipt 显示
  `pipeline_mode=llm`
- 对真实 LiteLLM 运行落地 `llm_trace_ref` 与 `state/traces/` 级别的 stage trace
- 对 insight evidence selection 落地 `evidence_trace_ref` 与 `state/traces/insights/` 级别的选择 trace
- 在 transport / auth 失败并回退到 `heuristic-fallback` 时保留 partial trace
- 非 LLM 命令现已改成 lazy client 初始化，避免 `review-raw` 之类的入口因为 LiteLLM 预热触发额外网络请求

当前默认运行模式仍然是 **heuristic**：

- 不依赖任何额外 Python 包即可跑通基础闭环
- 当显式设置 `FORGE_KNOWLEDGE_CLIENT=litellm` / `FORGE_INSIGHT_CLIENT=litellm` 时，才会切换到真实 LLM 路径

这意味着 Forge 已经不是“只有设计，没有实现”，但也还没有进入“所有设计全部落地”的阶段。

## 3. 当前代码结构

截至当前主线，自动化相关目录以 **代码驱动** 为主，而不是以独立 flow / policy 文件驱动。

```text
automation/
  compiled/
    runtime.lock.json
  evals/
    golden_cases.json
  pipeline/
    __main__.py
    app.py
    cli.py
    controller.py
    doctor.py
    documents.py
    fetchers.py
    llm_client.py
    models.py
    validators.py
  prompts/
    critic.md
    insight_writer.md
    judge.md
    knowledge_writer.md
  schemas/
    patch.schema.json
  scripts/
    extract-tags.sh
    forge
    generate-index.sh
    quick-capture.sh
    validate-provenance.sh
state/
  candidates/
  failure_cases/
  receipts/
  reviews/
  snapshots/
  traces/
    insights/
    knowledge/
```

### 当前明确不存在的组件

下列内容在早期设想里出现过，但 **当前仓库并没有实现**：

- `automation/flows/default.flow.yaml`
- `automation/policies/`
- `automation/connectors/`
- `automation/pipeline/runner.py`
- `automation/pipeline/renderer.py`
- `automation/pipeline/state.py`
- `automation/prompts/controller.md`
- `automation/prompts/extract.md`
- `compiled/prompts.lock.json`
- `compiled/flow.lock.yaml`
- `compiled/policies.lock.yaml`

这不是 bug，而是说明当前 v1 选择了更保守的实现路径：先把核心逻辑收敛在 Python 代码里，再决定是否值得把 orchestration 外置成 DSL / YAML。

## 4. 当前控制平面

### 4.1 已实现能力

当前控制平面由 `automation/pipeline/controller.py` 和 `uv run forge tune` 共同承担。

实际工作流是：

1. 用户通过自然语言表达调优意图
2. `compile_intent_to_patches()` 将意图编译成受限 patch
3. `validate_patch_bundle()` 对 patch 进行 schema 校验
4. `apply_patches()` 将 patch 应用到 `runtime.lock.json`
5. `run_replay_evals()` 在 golden cases 上做最小回放验证
6. 只有通过验证后，新的 lock 才会写回仓库

当前已支持的 patch 目标是白名单制，集中在：

- `runtime.insight.min_evidence`
- `runtime.insight.judge_profile`
- `runtime.knowledge.writer_profile`
- `prompts.knowledge_writer.domain_appendix.network`

### 4.2 当前限制

控制平面目前仍然是 **收敛版 DSL**，而不是通用编排系统：

- 不能自由修改 flow DAG
- 不能增删任意节点
- 不能直接改 shell / Python 行为
- 不能直接生成新的 prompt 文件

这是有意为之。当前 repo 的目标是先守住“可审计、可回放、可锁定”，而不是追求一个过早泛化的控制平面。

## 5. 当前运行平面

运行平面主要集中在 `automation/pipeline/app.py` 的 `ForgeApp`。

### 5.1 注入与知识生成

CLI 入口：

- `uv run forge inject --text ...`
- `uv run forge inject --file ...`
- `uv run forge inject --feishu-link ...`
- `uv run forge review-raw`
- `uv run forge review-queue`
- `uv run forge promote-raw raw/...md`
- `uv run forge promote-raw --all`
- `uv run forge promote-ready`

运行过程：

1. 接收输入内容并保存 snapshot
2. 生成 `raw/` 文档
3. 仅在显式启用 `--promote-knowledge` 且内容长度达到 `runtime.knowledge.min_chars` 时进入 knowledge pipeline
4. 调用 writer / critic / judge
5. 产出 `knowledge/` 文档，并归档候选、评审、trace 和 receipt

说明：

- 内容完整度主要影响的是后续 critique / judge 后的 `active` / `draft` 判定，而不是是否进入 pipeline
- 如果未显式传 `--promote-knowledge`，本次 inject 会停在 `raw`，这是当前的设计，不是异常
- 如果显式传了 `--promote-knowledge`，但内容长度低于 `runtime.knowledge.min_chars`，本次也会只落 `raw` + inject receipt，不会报错
- raw frontmatter 的 `status` 与 `review-raw` 的 `disposition` 是两层语义；`promoted` 不是 raw 自身状态，而是由
  `knowledge/*.md` 的 `derived_from` 反向推导出来的视图结果
- 当前没有后台 watcher / scheduler 去自动回扫现存 `raw`
- 当前已经补上显式 `review-raw` / `review-queue` / `promote-raw` / `promote-raw --all` 入口，但仍然没有 scheduler
  或默认自动推进
- `review-queue` 本质上是 `review-raw` 的过滤层，只保留 `pending / too_short`，再映射成 `ready / blocked`
- `promote-raw --all` 的真实行为是“遍历全部 raw，并对每项分别产出 success / skipped / failed”；它不是全量强制 promote
- `promote-ready` 是更保守的 opt-in 半自动入口：先读取 `review-queue`，再只执行当前 `ready` 条目
- `promote-ready --dry-run` 只做计划预览，不创建 knowledge 文档；`--limit N` 用于限制本次消费的 ready 项数量
- `promote-ready --confirm-receipt <receipt_ref>` 会执行某次 dry run receipt 中记录的 `raw_ref` 集合，而不是重新扫描当前队列
- dry run batch receipt 仍为 `success`，但 `results[*].status=planned`，并额外给出 `planned_count`；确认执行后的 receipt 会带 `confirmed_from_receipt_ref`

### 5.2 insight 合成

CLI 入口：

- `uv run forge synthesize-insights`

运行过程：

1. 从非 `draft` 的 `knowledge` 中加载候选集合，并仅从 `active` knowledge 中做 evidence 选择
2. 调用 insight writer / critic / judge
3. 生成 `insights/patterns/*.md`
4. 写入 candidate / review / receipt
5. 若 evidence 不足或质量不达标，则归档 failure case

说明：

- `knowledge -> insights` 当前同样是显式触发，不会因为新增或更新了 `knowledge` 就自动执行
- 当前只有 `uv run forge synthesize-insights` 会启动这一步
- 如果 evidence cluster 不满足 `runtime.insight.min_evidence`，结果会是 `skipped`，而不是隐式重试或后台排队
- 默认 insight 渲染结构已补到 `Pattern / Diagnostic Ladder / Mitigation Strategy / Anti-Patterns`
- writer candidate 的 canonical 字段合同在 `automation/prompts/insight_writer.md`，最终 Markdown 标题合同在
  `ForgeApp._render_insight_document()`
- evidence 选择会跳过 `superseded_by` 非空或 correction-like 的 knowledge，并忽略过泛 tag 后生成候选 cluster
- 当前实现不再只从 tag cluster 里选最大/首个组件，而是同时生成 tag-seed candidate 与 retrieval-graph candidate，
  再对候选 cluster 做 lexical signal / causal overlap reranking
- 每次 synthesize receipt 都会保留 `evidence_trace_ref`，包括 `success` 与 `skipped` 两类结果
- `evidence_trace_ref` 指向 `state/traces/insights/<synthesis_id>-evidence.json`，trace 中包含文档过滤原因、
  `candidate_generation_modes`、`candidate_clusters`、`selected_paths` 与 `selected_score`
- 它仍然不是完整的语义检索或因果验证系统，但已经能把“共享宽泛 tag 的弱相关文档”从强组件里剥离出去

### 5.2.1 对当前显式模型的判断

当前这套显式模型的优点是：

- 保守，避免一条低质量或半成品输入自动污染上层
- 容易审计，操作者知道哪一步是“摄入”、哪一步是“提升”、哪一步是“模式合成”
- 更适合现在这个仍在收口 prompt / evidence gate / fallback 行为的阶段
- 配合 `review-raw` / `promote-raw` 后，历史材料至少已有显式 backfill 路径，不再完全依赖人工手写 knowledge

当前的主要缺点是：

- `raw/` 很容易积压“已摄入但尚未提升”的材料
- 短内容会稳定停在 `raw`，但系统不会主动提示后续怎么处理
- 仍然缺少定时 synthesize / 更完整的显式确认工作流 这类更高层的运维入口

### 5.3 失败回放与自动调优

CLI 入口：

- `uv run forge replay-failure`
- `uv run forge review-failures`
- `uv run forge auto-retune`

这部分已经构成最小闭环：

- 失败会进入 `state/failure_cases/`
- 可以按 case 回放
- 可以聚合失败模式并生成 patch suggestions
- 可以在白名单 patch 范围内自动更新 `runtime.lock.json`

## 6. Client 层与 LiteLLM 的位置

### 6.1 当前实现

`automation/pipeline/llm_client.py` 里当前有两类 client：

- `HeuristicKnowledgeClient` / `HeuristicInsightClient`
- `LiteLLMKnowledgeClient` / `LiteLLMInsightClient`

调度逻辑是：

- 默认用 heuristic client
- 当环境变量指定 `litellm` 时切换到 LiteLLM client
- 如果 LLM 路径失败，insight / knowledge 流可回退到 heuristic fallback

### 6.2 当前定位

LiteLLM 在 Forge 中承担的是 **provider 接入层**，而不是流程编排层。

它适合做：

- 多 provider 统一调用接口
- 不同 model profile 的切换
- 作为 writer / critic / judge 的底层实现

它当前不负责：

- flow 编排
- provenance 校验
- release gate
- failure archive
- 控制平面的 patch 编译

### 6.3 当前实际状态与缺口

虽然代码已经支持 LiteLLM 路径，但目前仓库已经完成了：

- repo-local 启用说明
- `doctor` 的环境诊断
- provider key presence 检查
- 一次真实 `uv run forge inject` smoke test，确认 receipt 为 `pipeline_mode=llm`
- receipt 级 `llm_trace_ref` 与 `state/traces/` 中的 stage trace 聚合文件
- receipt 级 `relay_request_ids` 与 stage 级 `relay_request_id`
- 对每次 LiteLLM 请求注入 `x-forge-trace-id` 头，并在本地 trace 中保留 `forge_trace_id`
- 已确认当前 relay 的 `/v1/responses + metadata` 组合会稳定触发 `502`，因此 Forge 已停止向实际请求体发送 `metadata`，
  仅保留 header 级 correlation key 与 relay-native `request_id`
- 在 fallback 场景下保留 partial trace，而不是只留下 `heuristic-fallback` 结果
- `doctor` 已结构化暴露残留 proxy 环境风险，CLI 入口在 LiteLLM 路径上也会向 `stderr` 输出显式 warning

仍然缺少的关键证据是：

- 当前已确认实际 relay 为 `new-api` 家族部署（本机 Codex 指向 `https://dawclaudecode.com/v1`），
  因此外部侧证的优先落点应是该 relay 的日志 / 管理面，而不是把 LiteLLM 误当成网关
- `new-api` 默认不会把 `x-forge-trace-id` 或 `forge_trace_id` 自动持久化进 `logs.other`，
  因此这两个字段暂时还不能直接作为 relay 管理面的检索键
- 比一次 smoke test 更稳定的长期验收口径，避免把单次成功误写成稳定结论
- 当前对本机运行环境已经补上 warning 级保护，但还未做到自动隔离残留 `all_proxy/http_proxy/https_proxy`

### 6.4 `new-api` relay 的当前可观测性边界

基于对 `QuantumNous/new-api` 源码和当前 relay 行为的核对，当前结论是：

- `middleware/request-id.go` 会为每个请求生成 `request_id`，并通过响应头返回给调用方
- `model/log.go` 中的 `RecordConsumeLog` / `RecordErrorLog` 会把 gin context 里的 `request_id` 写入日志表 `logs.request_id`
- `controller/log.go` 与管理端 `UsageLogsFilters.jsx` 都支持按 `request_id` 查询 usage logs
- `logs.other` 并不是自动抓取所有请求信息；它只保存调用方显式构造的 map
- `service/log_info_generate.go` 当前会写入的典型字段包括 `request_path`、倍率/价格、`request_conversion`、`po`、`admin_info`、`stream_status` 等
- `relay/common/relay_info.go` 虽然会把入站请求头复制到 `RelayInfo.RequestHeaders`，但这份数据当前只用于 param override / header override 的运行时逻辑，不会自动持久化到日志表
- 因此 `x-forge-trace-id` 和 `forge_trace_id` 在默认 `new-api` 实现中不会自动出现在 `logs.other`

这意味着 Forge 当前的外部侧证应采用两级关联：

1. 仓库内保留 `llm_trace_ref`、stage 级 `relay_request_id` / receipt 级 `relay_request_ids`，以及 request-local `forge_trace_id`
2. relay 侧保留 `request_id` 与 usage log

如果要把两级关联打通，有两个可选方向：

- 已落地方案：Forge 在每次 LiteLLM 调用后把 relay 响应头里的 `request_id` 收进 trace / receipt
- 定制方案：在 relay 的 `GenerateTextOtherInfo` / `GenerateClaudeOtherInfo` / `GenerateAudioOtherInfo` 或 `RecordConsumeLog` 入口显式写入 `x-forge-trace-id` / `forge_trace_id`

当前更现实的建议是先基于已落地的 `request_id` 关联继续验证回查流程，因为它已经是 relay-native、可查询、无需改动外部网关的现成主键。

### 6.5 2026-04-05 实测回查结果

在真实 relay 上，当前最小可用的外部回查路径是：

- `GET /api/log/token`
- 鉴权方式：直接使用当前 API key，对应 `TokenAuthReadOnly()`
- 用途：返回当前 token 关联的 usage / error logs，然后按 `request_id` 精确匹配

同一天已完成的实测包括：

- 用现有 receipt `state/receipts/inject/20260405100914-384361e1.json` 中的 `relay_request_ids[0]`
  命中 relay token log，返回一条 `type=5` 的错误日志
- 重新发起一次 live inject 后，receipt 仍为 `heuristic-fallback`，但新的 `relay_request_ids[0]`
  同样能在 `/api/log/token` 命中对应错误日志
- 两次命中的 `other` 字段都包含 `request_path=\"/v1/responses\"` 与 `status_code=502`
- 直接对 `/v1/responses` 做对照实验后确认：
  `plain responses` 可成功，`responses + metadata` 会触发 `502`，而只携带 `x-forge-trace-id` header 可成功
- Forge 移除请求级 `metadata` 后，重新执行
  `state/receipts/inject/20260405114750-66e7b560.json`
  获得真实 `pipeline_mode=llm` 成功样本，并产出 3 个 `relay_request_ids`
- 其中 writer 阶段 `request_id=202604051147505123349988268d9d6SD9G3r9l`
  已再次通过 `/api/log/token` 命中一条 `type=2` 成功日志，`other` 中包含
  `request_path=\"/v1/responses\"` 与 `request_conversion=[\"OpenAI Responses\"]`
- 同轮调试还确认：如果 shell 残留 `all_proxy/http_proxy/https_proxy`，LiteLLM 会在 `httpx`
  初始化阶段直接抛 `APIConnectionError`；这属于本机环境噪声，不是 relay 502

这说明：

- 失败流的 `receipt -> relay_request_ids -> /api/log/token -> request_id` 已经重复验证成功
- 成功流的 `receipt -> relay_request_ids -> /api/log/token -> request_id` 也已完成一次真实验证
- 当前主要剩余问题不再是证据链闭环，而是是否需要继续把 `forge_trace_id` 定制落进 relay 日志，
  以及是否要把当前的 proxy warning 进一步升级为更强的运行时隔离策略

## 7. 当前质量门

Forge 当前真正落地的质量门有 5 类：

1. **Frontmatter / provenance gate**
   `./automation/scripts/validate-provenance.sh`

2. **Deterministic validators**
   `automation/pipeline/validators.py`
   - knowledge 至少要求 `root_cause / fix_steps / verification`
   - insight 至少要求 `observation / pattern / diagnostic_ladder / mitigation`
   - evidence 数量低于 `runtime.insight.min_evidence` 时，insight 会被直接判为结构不完整

3. **Critic / Judge 分层**
   knowledge 与 insight 都采用 writer / critic / judge 三段式

4. **Replay eval gate**
   控制平面 patch 生效前要过 `golden_cases.json`

5. **测试基线**
   `tests/test_cli.py`
   `tests/test_controller.py`
   `tests/test_doctor.py`
   `tests/test_pipeline_app.py`

这些门已经足以支撑当前基线，但还不足以替代真实 LLM 运行下的长期线上经验。

## 8. 与早期 v1 设想的差距

下面这些内容属于 **“设计里提过，但当前没有实现”** 的部分：

### 8.1 外置 flow / policy

早期设想中希望有：

- Flow YAML
- Policy YAML
- 编译后的多类 lock 文件

当前没有落地。实际系统仍然是 **代码内编排 + 单一 `runtime.lock.json`**。

### 8.2 更完整的 schema 体系

当前只明确落地了 `patch.schema.json`。

knowledge / insight 候选对象虽然走了规范化与 deterministic 校验，但还没有把所有对象合同外置成独立 JSON schema 文件。

### 8.3 独立 renderer / state / DB

早期曾设想把 renderer、state、SQLite 进一步模块化。

当前：

- renderer 逻辑仍在 `ForgeApp` 内
- state 主要落在 `state/` 目录的 JSON 文件
- 没有引入 SQLite

### 8.4 更通用的控制平面

当前 `tune` 只支持受限 patch，不支持：

- 节点级 flow 编辑
- 新 prompt 注入
- 通用控制器 prompt
- 复杂 flow 结构演化

这是刻意保守，而不是遗漏。

## 9. 当前剩余工作

如果只看 Forge 自身，不引入外部长期议题，当前最重要的剩余工作是：

1. 继续验证已落地的 insight gate 覆盖面与稳定性，避免把单篇 exemplar 误当作默认自动生成质量
2. 继续评估是否需要把 `forge_trace_id` 或等价 correlation key 定制落进 relay / provider 侧日志
3. 决定是否有必要把当前代码内 orchestration 外置为 flow / policy 文件
4. 继续扩充高质量 `raw` / `knowledge`，避免 insight 层只靠少量历史故障支撑
5. 保持 README、管理文档和代码实现同步，防止文档再次漂移

## 10. 当前 v1 的推荐边界

为了避免系统过早复杂化，当前 v1 建议继续坚持以下边界：

- 运行平面继续以 Python 代码驱动，不急于引入 Flow YAML
- 控制平面继续维持白名单 patch，而不是开放式自然语言编排
- 默认 heuristic，LiteLLM 作为可选增强路径
- 所有正式文档都必须经过 provenance / evidence gate
- 先把现有闭环跑稳，再考虑 LiteLLM Proxy、SQLite、复杂 policy 系统

## 11. 一句话总结

Forge 当前已经拥有一个 **可运行、可验证、可调优的 LLM 自动化流水线基线**；它还不是早期设想中的完整控制/运行平面体系，但已经足够支撑 `raw -> knowledge -> insights` 的保守落地与后续迭代。
