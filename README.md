# Forge

Forge is a public CLI and service runtime for note ingestion, raw review, knowledge promotion, and
insight synthesis.

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/hoastyle/forge/main/scripts/release/install-public-cli.sh | bash
forge version
forge login --server https://forge.example.com --token "$FORGE_SERVER_TOKEN"
forge doctor
```

## Repository Scope

- This repository is public runtime and distribution code.
- It does not contain production `raw/`, `knowledge/`, or `insights`.
- Private data lives in a separate `forge-data` repository that consumes published images.

## Public Interface

- Public/operator usage: `forge ...`
- Maintainer/self-hosted/repo-local usage: `uv run forge --repo-root . ...`
- Canonical public repository: `github.com/hoastyle/forge`

Release/distribution details live in
[`docs/management/forge-release-distribution.md`](./docs/management/forge-release-distribution.md).

```bash
uv run forge --repo-root . doctor
```

doctor 会输出 `dependencies.litellm.repo_local_enablement`（可执行步骤）以及根据当前被 LiteLLM 管理的 runtime sections 推断的 `provider_credentials`（当前是否缺 key / base_url、来自进程环境还是 repo-local `.env`）。
如果当前 shell 带有 SOCKS 代理，doctor 还会在 `dependencies.litellm.proxy_support` 里提示是否缺少 `socksio`。

### 4) LiteLLM smoke test（会真实调用 LLM）

这一步需要有效的 provider key / base URL。为了确保触发知识流水线，请带上 `--promote-knowledge` 且文本长度足够。

```bash
uv run forge --repo-root . inject \
  --title "litellm smoke test" \
  --text "Context:\nA packet capture confirmed the gateway was rewriting DNS answers after the router reboot.\n\nRoot cause:\nThe repo-local .env was missing the OpenAI-compatible relay base URL, so LiteLLM could not use the intended endpoint.\n\nFix steps:\n- Add OPENAI_API_KEY to .env.\n- Set OPENAI_BASE_URL to your relay endpoint.\n- Re-run the doctor command to confirm provider readiness.\n\nVerification:\n- doctor reports the openai provider as ready.\n- the inject receipt reports pipeline_mode as llm and includes llm_trace_ref plus relay_request_ids." \
  --promote-knowledge
```

如果启用成功，输出的 receipt 里应能看到 `pipeline_mode` 为 `llm`（而不是 `heuristic` / `heuristic-fallback`），并且 `llm_trace_ref` 会指向 `state/traces/...` 下的运行证据文件。当前 receipt 还会汇总 `relay_request_ids`，而 trace 的每个 stage 会记录 `relay_request_id`、`prompt_name`、`provider`、`model`、`api_base`、`api_*_source`、`response_id`，以及 `request_correlation_id` / `request_header_name` / `request_metadata`。这意味着仓库内证据现在可以直接拿 `relay_request_ids` 去 join relay 管理面里的 `request_id`；`x-forge-trace-id` / `forge_trace_id` 仍然保留为辅助 correlation key，但在默认 `new-api` 实现里不会自动落日志。

兼容入口 `./automation/scripts/forge ...` 仍然保留；public/operator 文档示例统一写成 `forge ...`，
maintainer 示例统一写成 `uv run forge --repo-root . ...`。

除调试兼容外，不建议再把 `python -m automation.pipeline ...` 作为日常入口。

如果你显式传 `--initiator`，当前允许值是：`manual`、`codex`、`claude-code`、`openclaw`、`ci`。

---
*For AI agents working in this repository, see [`CLAUDE.md`](./CLAUDE.md) for strict operational guidelines.*
