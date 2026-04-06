# Pipeline Next Steps Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Completed on 2026-04-06

**Goal:** Add an explicit opt-in `promote-ready` batch entrypoint and upgrade insight evidence selection from filtered tag-clustering to a stronger filtered-cluster reranking model.

**Architecture:** Keep Forge's explicit-trigger model intact. Add one new queue-driven promotion command that only acts on `review-queue` items with `queue_status=ready`, and strengthen `synthesize-insights` evidence selection by preserving filtered tag-clusters as candidate generation while reranking clusters with lexical and causal overlap signals.

**Tech Stack:** Python stdlib, existing `ForgeApp`/CLI/receipt patterns, unittest, Markdown docs

---

### Task 1: Queue-Driven Promotion Plan

**Files:**
- Modify: `automation/pipeline/app.py`
- Modify: `automation/pipeline/cli.py`
- Modify: `automation/pipeline/models.py`
- Test: `tests/test_pipeline_app.py`
- Test: `tests/test_cli.py`

- [x] Add failing tests for an app-level `promote_ready()` method that only promotes `review-queue` items marked `ready`.
- [x] Add a failing CLI test for `uv run forge promote-ready --initiator codex`.
- [x] Implement a new batch receipt that records the queue receipt ref, targeted ready count, and per-item results.
- [x] Implement `ForgeApp.promote_ready()` by calling `review_queue()` and then `promote_raw()` for ready items only.
- [x] Wire the new `promote-ready` subcommand into the CLI and receipt directory bootstrap.

### Task 2: Evidence Selector Upgrade

**Files:**
- Modify: `automation/pipeline/app.py`
- Modify: `tests/test_pipeline_app.py`

- [x] Add failing tests showing that filtered tag-clusters are reranked by stronger overlap instead of picking the first matching cluster.
- [x] Add a failing test showing that weakly related docs sharing one specific tag are excluded when a stronger causal/lexical cluster exists.
- [x] Implement reusable helpers for extracting signal terms from title/body/tags.
- [x] Implement cluster scoring that combines filtered specific-tag overlap with lexical/causal overlap and selects the highest-scoring eligible cluster.
- [x] Keep existing filtering behavior for `draft`, `superseded_by`, correction-like, and generic-tag knowledge.

### Task 3: Docs And Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/management/forge-operator-guide.md`
- Modify: `docs/management/forge-llm-pipeline-v1.md`

- [x] Document `promote-ready` as an explicit opt-in queue executor.
- [x] Update evidence selection wording from “filtered tag-cluster” to “filtered candidate generation plus reranking.”
- [x] Run targeted tests first, then `uv run --no-env-file python -m unittest discover -s tests`.
- [x] Run `./automation/scripts/validate-provenance.sh` and `git diff --check`.
