# Forge Public Command Contract

## Public Operator Commands

These are the only commands that the published public `forge` binary currently exposes as
operator-facing workflows:

- `forge login --server <url> --token <token>`
- `forge logout`
- `forge version`
- `forge doctor`
- `forge inject --text <content> --title <title> --source <source>`
- `forge inject --file <path> --title <title> --source <source>`
- `forge inject --feishu-link <url> --title <title> --source <source>`
- `forge review-raw --initiator <initiator>`
- `forge review-queue --initiator <initiator>`
- `forge promote-raw <raw_ref> --initiator <initiator>`
- `forge promote-ready --dry-run --limit <n> --initiator <initiator>`
- `forge promote-ready --confirm-receipt <receipt_ref> --initiator <initiator>`
- `forge synthesize-insights --initiator <initiator>`
- `forge synthesize-insights --dry-run --initiator <initiator>`
- `forge synthesize-insights --confirm-receipt <receipt_ref> --initiator <initiator>`
- `forge knowledge get <knowledge_ref>`
- `forge explain insight <receipt_ref>`
- `forge receipt get <selector>`
- `forge job get <job_id>`

## Contract Rules

- `initiator` is provenance metadata, not routing logic.
- `inject` writes raw material; `--promote-knowledge` is the only inline trigger from raw capture into knowledge.
- `promote-raw` and `promote-ready` are the only public raw-to-knowledge promotion commands.
- `synthesize-insights` is an explicit knowledge-to-insights mutation.
- `knowledge get` is the read-only publication status surface for one knowledge document.
- `explain insight` is the read-only evidence trace surface for one insight receipt.
- Receipts are the durable source of truth for completed mutations.
- Remote mutations (`inject`, `promote-raw`, `promote-ready`, and `synthesize-insights`) default to detached jobs; the common completion loop is `forge job get <job_id>` followed by `forge receipt get <receipt_ref>`. Use `--wait` to perform the synchronous path that waits for the job to finish and returns the receipt inline, and treat `--detach` as a backward-compatible but usually redundant flag.

## Safe Retry

Remote mutation commands accept `--operation-id <id>` so callers can retry safely without creating
duplicate work:

- `forge inject ... --operation-id <id>`
- `forge promote-raw <raw_ref> --operation-id <id>`
- `forge promote-ready ... --operation-id <id>`
- `forge synthesize-insights --operation-id <id>`

## Not In The Public Contract

The following commands or flags are intentionally not part of the current public contract and
must not be advertised by public docs or the `using-forge` skill:

- `forge review-sensitive`
- `forge redact-raw`

## Maintainer Entry Points

These are repo-local maintenance entry points. They are supported for maintainers but are not
the public operator surface:

- `uv run forge --repo-root . doctor`
- `uv run forge --repo-root . serve --host 0.0.0.0 --port 8000`
- `python -m automation.pipeline.cli --repo-root . doctor`
