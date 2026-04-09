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
forge synthesize-insights --dry-run --initiator codex
forge synthesize-insights --confirm-receipt state/receipts/insights/<preview>.json --initiator codex
```

Add `--detach` to long-running mutations when the caller should return immediately.

## Inspect Knowledge Status

```bash
forge knowledge get knowledge/troubleshooting/example.md
```

## Explain Insight Evidence

```bash
forge explain insight state/receipts/insights/<id>.json
```

## Safe Retry

```bash
forge promote-ready --initiator codex --dry-run --operation-id nightly-ready-preview-20260409
forge synthesize-insights --dry-run --initiator codex --operation-id nightly-insight-preview-20260409
forge synthesize-insights --confirm-receipt state/receipts/insights/<preview>.json --initiator codex --operation-id nightly-insight-confirm-20260409
forge synthesize-insights --initiator codex --detach --operation-id nightly-insight-build-20260409
```

## Receipts And Jobs

```bash
forge receipt get state/receipts/inject/<id>.json
forge job get inject-<jobid>
```

Use `receipt get` for completed operations and `job get` for detached background jobs.

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
