# Forge Operator Guide

## Who this is for

Use this guide when you already have a configured Forge service and need to run the public operator
commands listed below.

- `forge doctor`
- `forge inject`
- `forge review-raw`
- `forge review-queue`
- `forge promote-raw`
- `forge promote-ready`
- `forge synthesize-insights`
- `forge receipt get`
- `forge job get`

Remote mutations (`inject`, `promote-raw`, `promote-ready`, `synthesize-insights`) default to detached jobs. Online operators should poll `forge job get <job_id>` and then `forge receipt get <receipt_ref>` as the normal completion loop; add `--wait` when you want synchronous behavior, and treat `--detach` as a backward-compatible but usually redundant flag.

All of these commands work against a published Forge CLI binary and a configured service endpoint.
You do not need a checkout of the private `forge-data` repository to operate the public runtime surface.
The public installer also bundles the `using-forge` skill for supported local agent skill directories.
The authoritative command list lives in `docs/management/forge-command-contract.md`.

## Prerequisites

You only need:

- a Forge binary
- the bundled `using-forge` skill if you are operating through an AI tool that consumes local skills
- a service URL
- a bearer token

Public install entrypoint:

```bash
curl -fsSL https://raw.githubusercontent.com/hoastyle/forge-public/main/scripts/release/install-public-cli.sh | bash
```

Configure the connection once:

```bash
forge login --server https://forge.example.com --token "$FORGE_SERVER_TOKEN"
forge doctor
```

`forge login` stores the endpoint in local client config. `FORGE_SERVER` and `FORGE_TOKEN` can override it.
If a recipe or skill example disagrees with `forge doctor`, `forge help`, or the command contract doc, treat the
contract doc and actual CLI behavior as the source of truth.

## Core Workflow

Ingest a note:

```bash
forge inject \
  --title "incident summary" \
  --text "Context:\n...\n\nRoot cause:\n...\n\nFix steps:\n...\n\nVerification:\n..." \
  --source "manual note" \
  --initiator manual
```

Inspect queue state:

```bash
forge review-queue --initiator manual
```

Preview and execute ready promotions:

```bash
forge promote-ready --initiator manual --dry-run --limit 5
forge promote-ready --initiator manual --confirm-receipt state/receipts/ready_promote/<preview>.json
```

The preview receipt and the confirmed promotion both expose the publication metadata and `last_receipt_ref` for each promoted document so you can track which receipt sealed the latest published state.
Single-item `promote-raw` replies expose the same publication metadata and `last_receipt_ref`, so the command already reports the latest durable state for that document without a separate reconciliation step.

Run insight synthesis explicitly:

```bash
forge synthesize-insights --initiator manual
forge synthesize-insights --initiator manual --wait
forge synthesize-insights --initiator manual --dry-run
forge synthesize-insights --initiator manual --confirm-receipt state/receipts/insights/<preview>.json
```

## Receipts And Jobs

Use receipts as the source of truth for completed mutations:

```bash
forge receipt get state/receipts/inject/<id>.json
```

Remote mutations (even without an explicit `--detach`) return a job handle. Poll the detached job and then the receipt:

```bash
forge job get inject-<jobid>
```

`job_id` is only an execution handle. `receipt_ref` is the durable result pointer. Add `--wait` when a command must complete synchronously, and continue to use `--detach` only when caller semantics explicitly require it to surface.

If an operator-facing command fails, expect `message`, `error_code`, and `next_step` in the failure payload. Use `error_code` for stable scripting and `next_step` for the immediate recovery action.

Inspect one knowledge document's publication state:

```bash
forge knowledge get knowledge/troubleshooting/example.md
```

`forge knowledge get` now returns publication metadata plus `last_receipt_ref`, so you can jump directly to the latest durable receipt without manually scanning receipt history.

Inspect why one insight synthesis selected or excluded evidence:

```bash
forge explain insight state/receipts/insights/<id>.json
```

## Safe Retry

If a remote mutation may be retried by automation, pin a stable operation id:

```bash
forge promote-ready --initiator manual --dry-run --operation-id nightly-ready-preview-20260409
forge synthesize-insights --initiator manual --dry-run --operation-id nightly-insight-preview-20260409
forge synthesize-insights --initiator manual --confirm-receipt state/receipts/insights/<preview>.json --operation-id nightly-insight-confirm-20260409
forge synthesize-insights --initiator manual --detach --operation-id nightly-insight-build-20260409
```

If the caller times out before seeing the HTTP response, rerun the exact same command with the same
`--operation-id`.

## Boundary

- This repo publishes the CLI, service runtime, and public operator contract
- It also publishes the `using-forge` skill bundle that tracks the public operator contract
- It does not expose private `raw/`, `knowledge/`, or `insights`
- Self-hosted service operators should use `docs/management/self-hosting.md`
- Private data-repo maintenance stays outside this public repo boundary
