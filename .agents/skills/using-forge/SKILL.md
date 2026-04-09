---
name: using-forge
description: "Use when a tool or operator needs to use the public Forge CLI or a configured Forge service to ingest notes, review queue state, promote raw material, synthesize insights, inspect receipts, or poll detached jobs."
---

# Using Forge

## Overview

This skill defines the public operator contract for Forge. Prefer the public `forge ...` CLI and service receipts when
capturing material, promoting queue items, synthesizing insights, or inspecting job state. Do not assume direct access
to the Forge repository or its documents.

## Core Rules

- Public entrypoint: `forge ...`
- Configure the target service with `forge login --server <url> --token <token>`, or with `FORGE_SERVER` and `FORGE_TOKEN`.
- Use `forge receipt get <selector>` and `forge job get <job_id>` before claiming what happened.
- `initiator` is provenance only. Allowed values are `manual`, `codex`, `claude-code`, `openclaw`, and `ci`.
- trigger semantics remain explicit:
  - `inject` without `--promote-knowledge` writes `snapshot + raw + inject receipt` only.
  - `raw -> knowledge` happens only through `--promote-knowledge`, `promote-raw`, or `promote-ready`.
  - `knowledge -> insights` happens only through `synthesize-insights`.
- Use `uv run forge --repo-root <repo> ...` only when maintaining the local Forge repository or running the service itself.
- When public CLI semantics, receipt fields, detached job semantics, or service deployment steps change, update this skill in
  the same change set.

## Default Workflow

1. Authenticate with `forge login --server <url> --token <token>`.
2. Check readiness with `forge doctor`.
3. Capture material with `forge inject --text`, `forge inject --file`, or `forge inject --feishu-link`.
4. Review actionable backlog with `forge review-queue`.
5. If secrets may be present, inspect `forge review-sensitive` and remediate with `forge redact-raw`.
6. Promote ready raw explicitly with `forge promote-ready`, or use `--dry-run` plus `--confirm-receipt`.
7. Synthesize patterns with `forge synthesize-insights`, or preview evidence with `--dry-run` before confirming.
8. Inspect outcomes with `forge receipt get <receipt_ref>`.
9. If a mutation was detached, poll it with `forge job get <job_id>`.

## Task Routing

- Capture a session summary:
  - use `forge inject --text` or `forge inject --file`
- Inspect what is actionable:
  - use `forge review-queue`
- Inspect only the sensitive remediation backlog:
  - use `forge review-sensitive`
- Preview or apply redaction on one raw note:
  - use `forge redact-raw raw/...md --dry-run`
  - use `forge redact-raw raw/...md`
- Preview a safe batch:
  - use `forge promote-ready --dry-run --limit N`
- Execute exactly the previewed batch:
  - use `forge promote-ready --confirm-receipt <receipt_ref>`
- Promote one known raw item:
  - use `forge promote-raw raw/...md`
- Preview insight evidence without writing an insight:
  - use `forge synthesize-insights --dry-run`
- Execute exactly the previewed insight evidence set:
  - use `forge synthesize-insights --confirm-receipt <receipt_ref>`
- Run a long mutation asynchronously:
  - add `--detach`, then poll with `forge job get <job_id>`
- Diagnose provider / relay / service state:
  - use `forge doctor`

## Receipts And Jobs

- Treat the receipt JSON as the source of truth.
- `receipt_ref` remains the canonical pointer to a completed operation.
- Detached mutations return a `job_id`; they do not imply success until `forge job get` reports `status=success`.
- For `promote-ready`, use the batch receipt as the execution contract:
  - dry-run receipts expose the previewed batch
  - confirmed execution receipts link back through `confirmed_from_receipt_ref`
- For `redact-raw`, receipts include only `sensitive_signals`, replacement counts, and `[REDACTED]`; they never echo the original secret.
- For insight synthesis, inspect `evidence_trace_ref` to understand evidence filtering, document `quality_score` /
  `quality_signals`, component `quality_score`, and the final selection.

## References

- `references/forge-command-recipes.md` is bundled with this skill and should be resolved relative to the skill directory.
- This skill is public/operator-facing; it does not require direct repository visibility.
