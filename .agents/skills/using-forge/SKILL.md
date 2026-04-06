---
name: using-forge
description: Use when a tool or operator has Forge CLI access or a configured Forge service and needs to operate ingestion, queue review, promotion, synthesis, or receipt/job inspection without private repo access.
---

# Using Forge

Use Forge through the public CLI (`forge ...`) or a configured Forge service endpoint.

Do not assume access to the private data repository. Public users and AI tools should be able to operate with only:

- a Forge binary
- a service URL
- a bearer token

## Quick Start

Configure the service once:

```bash
forge login --server https://forge.example.com --token "$FORGE_SERVER_TOKEN"
forge doctor
```

## Common Operations

Ingest a note:

```bash
forge inject \
  --title "incident summary" \
  --text "Context:\n...\n\nRoot cause:\n...\n\nFix steps:\n...\n\nVerification:\n..." \
  --source "manual note" \
  --initiator manual
```

Review queue state and promote ready items explicitly:

```bash
forge review-queue --initiator manual
forge promote-ready --initiator manual --dry-run --limit 5
forge promote-ready --initiator manual --confirm-receipt state/receipts/ready_promote/<preview>.json
```

Inspect receipts and detached jobs:

```bash
forge receipt get state/receipts/inject/<id>.json
forge job get inject-<jobid>
```

## Boundary

- `forge ...` is the canonical public/operator entrypoint
- Self-hosting is handled through the published runtime image, not private repo checkout
- Private `raw/`, `knowledge/`, and `insights` content are out of scope for this skill
