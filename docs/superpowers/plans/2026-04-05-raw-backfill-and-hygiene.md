# Raw Backfill And Hygiene Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Completed on 2026-04-05

**Goal:** Clean existing raw document hygiene issues, resolve the four orphan raw captures, and add explicit `review-raw` / `promote-raw` CLI entrypoints without changing the default explicit-trigger model.

**Architecture:** Keep the current explicit pipeline semantics intact. Add a small raw-document loading/review layer in `automation/pipeline/documents.py`, expose explicit review/promote methods on `ForgeApp`, and wire them into CLI and tests. In parallel, clean the identified raw content issues and either promote or archive the four orphan captures.

**Tech Stack:** Python stdlib, unittest, existing Forge pipeline/app/CLI structure, Markdown docs

---

### Task 1: Raw Hygiene And Orphan Resolution

**Files:**
- Modify: `raw/captures/2026-04-03-agent-browser-install-capture.md`
- Modify: `raw/captures/2026-04-03-gateway-dns-diagnostic.md`
- Modify: `raw/captures/2026-04-04-codex-env-extension-summary.md`
- Modify: `raw/captures/2026-04-04-skills-installation-attempt.md`
- Modify: `raw/captures/2026-04-04-superpowers-install.md`
- Create: `knowledge/tools/agent-browser-installation-guide.md`
- Create: `knowledge/tools/skills-installation-guide.md`
- Create: `knowledge/tools/superpowers-installation-guide.md`

- [x] Clean the known garbled text and empty distillation placeholder.
- [x] Decide and apply disposition for each orphan raw capture: promote, archive/supersede, or summary.
- [x] When promoting, add valid `derived_from` frontmatter and update the raw distillation note.

### Task 2: Raw Review / Promote Tests (RED)

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `tests/test_pipeline_app.py`

- [x] Add failing tests for `review-raw` CLI output and `promote-raw` CLI behavior.
- [x] Add failing tests for app-level raw review classification and explicit promotion of an existing raw document.

### Task 3: Raw Review / Promote Implementation (GREEN)

**Files:**
- Modify: `automation/pipeline/cli.py`
- Modify: `automation/pipeline/app.py`
- Modify: `automation/pipeline/documents.py`
- Modify: `automation/pipeline/models.py`

- [x] Add raw document loader/helpers that can classify existing raw docs and extract promotable content.
- [x] Add `ForgeApp.review_raw()` and `ForgeApp.promote_raw()`.
- [x] Add `uv run forge review-raw` and `uv run forge promote-raw <raw_ref>` subcommands.
- [x] Keep default semantics unchanged: no background scan, no implicit auto-promotion.

### Task 4: Verification And Docs Sync

**Files:**
- Modify: `docs/management/forge-operator-guide.md` (only if CLI naming/details need final sync)
- Modify: `INDEX.md` (if content changes require refresh)

- [x] Run targeted tests for CLI and pipeline app.
- [x] Run provenance validation and index generation if raw/knowledge changed.
- [x] Confirm help text and runtime behavior still match the operator docs.
