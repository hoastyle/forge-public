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

All of these commands work against a published Forge CLI binary and a configured service endpoint.
You do not need a checkout of the private `forge-data` repository to operate the public runtime surface.
The public installer also bundles the `using-forge` skill for supported local agent skill directories.

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

Run insight synthesis explicitly:

```bash
forge synthesize-insights --initiator manual
```

## Receipts And Jobs

Use receipts as the source of truth for completed mutations:

```bash
forge receipt get state/receipts/inject/<id>.json
```

If a command ran with `--detach`, poll the detached job:

```bash
forge job get inject-<jobid>
```

`job_id` is only an execution handle. `receipt_ref` is the durable result pointer.

## Boundary

- This repo publishes the CLI, service runtime, and public operator contract
- It also publishes the `using-forge` skill bundle that tracks the public operator contract
- It does not expose private `raw/`, `knowledge/`, or `insights`
- Self-hosted service operators should use `docs/management/self-hosting.md`
- Private data-repo maintenance stays outside this public repo boundary
