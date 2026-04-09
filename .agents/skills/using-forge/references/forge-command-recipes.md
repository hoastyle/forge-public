# Forge Command Recipes

## Public Entry

Prefer the public CLI:

```bash
forge <command> ...
```

Use repo-local entrypoints only for maintenance:

```bash
uv run forge --repo-root . doctor
uv run forge --repo-root . serve --host 0.0.0.0 --port 8000
python -m automation.pipeline.cli --repo-root . doctor
```

## Login And Readiness

```bash
forge login --server https://forge.example.com --token <token>
forge doctor
```

Use `FORGE_SERVER` and `FORGE_TOKEN` when a non-interactive tool should not write local config.

## Inject Text

```bash
forge inject \
  --title "incident summary" \
  --text "Context:\n...\n\nRoot cause:\n...\n\nFix steps:\n...\n\nVerification:\n..." \
  --source "codex session summary" \
  --initiator codex \
  --promote-knowledge
```

## Review Queue

```bash
forge review-queue --initiator codex
```

Use `review-raw` only when you need the full inventory view.

## Preview Ready Promotion

```bash
forge promote-ready --initiator codex --dry-run --limit 5
```

This writes a preview receipt that can be reused exactly.

The preview receipt and the confirmed promotion both surface publication metadata and `last_receipt_ref` for every promoted document so the receipt itself documents the published state.

## Confirm Ready Promotion

```bash
forge promote-ready \
  --initiator codex \
  --confirm-receipt state/receipts/ready_promote/<preview>.json
```

## Promote One Raw

```bash
forge promote-raw raw/captures/example.md --initiator codex
```

## Synthesize Insights

Preview template:

```text
forge synthesize-insights --dry-run
forge synthesize-insights --confirm-receipt <receipt_ref>
```

```bash
forge synthesize-insights --initiator codex
forge synthesize-insights --initiator codex --wait
forge synthesize-insights --dry-run --initiator codex
forge synthesize-insights --confirm-receipt state/receipts/insights/<preview>.json --initiator codex
```

Remote mutations default to detached jobs. Poll `forge job get <job_id>` and then `forge receipt get <receipt_ref>` as the typical completion loop, add `--wait` when the caller needs to remain synchronous, and treat `--detach` as a backward-compatible but usually redundant flag.

## Inspect Knowledge Status

```bash
forge knowledge get knowledge/troubleshooting/example.md
```

Use the returned `last_receipt_ref` to jump straight to the latest durable receipt for that knowledge document.

## Explain Insight Evidence

```bash
forge explain insight state/receipts/insights/<id>.json
```

## Safe Retry

```bash
forge promote-ready --initiator codex --dry-run --operation-id nightly-ready-preview-20260409
forge synthesize-insights --dry-run --initiator codex --operation-id nightly-insight-preview-20260409
forge synthesize-insights --confirm-receipt state/receipts/insights/<preview>.json --initiator codex --operation-id nightly-insight-confirm-20260409
forge synthesize-insights --initiator codex --operation-id nightly-insight-build-20260409
```

## Receipts And Jobs

```bash
forge receipt get state/receipts/inject/<id>.json
forge job get inject-<jobid>
```

Remote mutations present a job handle even without `--detach`; poll `job get` and then `receipt get`. Add `--wait` for synchronous expectations and keep `--detach` only if you must surface explicit asynchronous behavior.

If a command fails, use `error_code` for automation and `next_step` for the immediate operator action.

## Maintainer Recipes

```bash
uv run forge --repo-root . doctor
uv run forge --repo-root . serve --host 0.0.0.0 --port 8000
uv run --no-env-file python -m unittest discover -s tests
./automation/scripts/validate-provenance.sh
./automation/scripts/generate-index.sh
git diff --check
```

## Sync Rule

If any of the following change, update `../SKILL.md` in the same change set:

- public `forge` commands or arguments
- detached job / receipt semantics
- trigger semantics for `raw -> knowledge -> insights`
- service login / token / deployment workflow
- maintainer repo-local entrypoints
- `docs/management/forge-command-contract.md`
