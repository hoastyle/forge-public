---
name: using-forge
description: "Use when a tool or operator needs to use the public Forge CLI or a configured Forge service to ingest notes, review queue state, promote raw material, synthesize insights, inspect receipts, or poll detached jobs."
---

# Using Forge

## Overview

This skill defines the public operator contract for Forge. Prefer the public `forge ...` CLI and service receipts when
capturing material, promoting queue items, synthesizing insights, or inspecting job state. Do not assume direct access
to the Forge repository or its documents. The authoritative command list lives in
`docs/management/forge-command-contract.md`.

## Core Rules

- Public entrypoint: `forge ...`
- Configure the target service with `forge login --server <url> --token <token>`, or with `FORGE_SERVER` and `FORGE_TOKEN`.
- Use `forge receipt get <selector>` and `forge job get <job_id>` before claiming what happened.
- Use `forge knowledge get <knowledge_ref>` to inspect publication state.
- Use `forge explain insight <receipt_ref>` to inspect evidence selection and exclusions for one insight receipt.
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
5. Promote ready raw explicitly with `forge promote-ready`, or use `--dry-run` plus `--confirm-receipt`.
6. Preview insight synthesis with `forge synthesize-insights --dry-run`, then confirm with `--confirm-receipt` when an exact batch must be frozen.
7. Inspect publication state with `forge knowledge get <knowledge_ref>` when a promotion result needs explanation.
8. Inspect outcomes with `forge receipt get <receipt_ref>` or `forge explain insight <receipt_ref>`.
9. If a mutation was detached, poll it with `forge job get <job_id>`.

## Task Routing

- Capture a session summary:
  - use `forge inject --text` or `forge inject --file`
- Inspect what is actionable:
  - use `forge review-queue`
- Preview a safe batch:
  - use `forge promote-ready --dry-run --limit N`
- Execute exactly the previewed batch:
  - use `forge promote-ready --confirm-receipt <receipt_ref>`
- Promote one known raw item:
  - use `forge promote-raw raw/...md`
- Run an explicit insight synthesis:
  - use `forge synthesize-insights`
- Preview an insight batch before execution:
  - use `forge synthesize-insights --dry-run`
- Execute exactly the previewed insight batch:
  - use `forge synthesize-insights --confirm-receipt <receipt_ref>`
- Inspect one knowledge document's publication state:
  - use `forge knowledge get <knowledge_ref>`
- Explain one insight receipt's evidence selection:
  - use `forge explain insight <receipt_ref>`
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
- For `synthesize-insights`, use the insight receipt as the execution contract:
  - dry-run receipts expose `evidence_refs`, `evidence_manifest`, and `evidence_trace_ref`
  - confirmed execution receipts link back through `confirmed_from_receipt_ref`
- For retry-safe automation, pin `--operation-id <id>` on remote mutations and reuse the exact same value on retries.
- For insight synthesis, inspect `evidence_trace_ref` to understand evidence filtering, document `quality_score` /
  `quality_signals`, component `quality_score`, and the final selection.

## References

- `references/forge-command-recipes.md` is bundled with this skill and should be resolved relative to the skill directory.
- This skill is public/operator-facing; it does not require direct repository visibility.
- If public command semantics change, update this skill and the command contract doc in the same change set.
