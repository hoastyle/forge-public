# Forge Promote Visibility And Operator Errors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose `last_receipt_ref` across `knowledge get` and promote receipts, and upgrade key operator-facing failures to include stable `error_code` and actionable `next_step` fields.

**Architecture:** Keep promotion and read workflows intact. Add a small receipt-history lookup helper in the Python app, extend the publication and receipt models with optional metadata, introduce a structured operator error type for read endpoints, and let the existing CLI/service layers pass the richer payloads through unchanged.

**Tech Stack:** Python (`unittest`, dataclasses, FastAPI), Markdown docs, existing Forge receipt/state layout.

---

> **Path override:** This public repo stores plans under `docs/archive/2026-Q2/`, so this plan intentionally lives here instead of `docs/superpowers/`.

## Scope Guardrails

- Do not introduce a new command for receipt history lookup.
- Do not change remote job-first semantics added in the previous wave.
- Do not redesign receipt storage; reuse the current `state/receipts/**/*.json` layout.
- Keep error-code coverage focused on operator-facing read and confirm flows only.

### Task 1: Lock `last_receipt_ref` Behavior In App-Level Tests

**Files:**
- Modify: `tests/test_pipeline_app.py`
- Modify: `automation/pipeline/models.py`
- Modify: `automation/pipeline/knowledge_status.py`
- Modify: `automation/pipeline/app.py`

- [ ] **Step 1: Write failing app tests for `last_receipt_ref`**

```python
def test_read_knowledge_status_returns_last_receipt_ref(self):
    from automation.pipeline.app import ForgeApp

    self._write_raw_fixture(...)
    app = ForgeApp(self.repo_root)
    promote_receipt = app.promote_raw("raw/captures/example.md", initiator="codex")

    payload = app.read_knowledge_status(promote_receipt.knowledge_ref)

    self.assertEqual(payload["last_receipt_ref"], promote_receipt.receipt_ref)

def test_promote_raw_already_promoted_returns_historical_last_receipt_ref(self):
    from automation.pipeline.app import ForgeApp

    self._write_raw_fixture(...)
    app = ForgeApp(self.repo_root)
    first = app.promote_raw("raw/captures/example.md", initiator="codex")
    second = app.promote_raw("raw/captures/example.md", initiator="codex")

    self.assertEqual(second.status, "skipped")
    self.assertEqual(second.last_receipt_ref, first.receipt_ref)

def test_promote_ready_results_include_last_receipt_ref(self):
    from automation.pipeline.app import ForgeApp

    self._write_raw_fixture(...)
    app = ForgeApp(self.repo_root)
    receipt = app.promote_ready(initiator="codex")

    self.assertEqual(receipt.results[0]["last_receipt_ref"], receipt.results[0]["receipt_ref"])
```

- [ ] **Step 2: Run the focused app tests and confirm they fail**

Run:

```bash
uv run --no-env-file python -m unittest \
  tests.test_pipeline_app.PipelineAppTests.test_read_knowledge_status_returns_last_receipt_ref \
  tests.test_pipeline_app.PipelineAppTests.test_promote_raw_already_promoted_returns_historical_last_receipt_ref \
  tests.test_pipeline_app.PipelineAppTests.test_promote_ready_results_include_last_receipt_ref -v
```

Expected:

```text
FAIL because the publication payloads do not yet expose last_receipt_ref
```

- [ ] **Step 3: Implement `last_receipt_ref` in the publication and promotion models**

```python
@dataclass
class KnowledgePublicationStatus:
    ...
    last_receipt_ref: Optional[str]
```

```python
@dataclass
class RawPromotionReceipt:
    ...
    last_receipt_ref: Optional[str] = None
```

```python
def _find_latest_receipt_ref_for_knowledge(self, knowledge_ref: str) -> Optional[str]:
    matches = []
    for path in self.state_root.glob("receipts/**/*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if str(payload.get("knowledge_ref") or "").strip() == knowledge_ref:
            matches.append(path)
    if not matches:
        return None
    latest = max(matches, key=lambda path: (path.stat().st_mtime_ns, str(path)))
    return self._relative(latest)
```

- [ ] **Step 4: Re-run the focused app tests and the full Python suite**

Run:

```bash
uv run --no-env-file python -m unittest \
  tests.test_pipeline_app.PipelineAppTests.test_read_knowledge_status_returns_last_receipt_ref \
  tests.test_pipeline_app.PipelineAppTests.test_promote_raw_already_promoted_returns_historical_last_receipt_ref \
  tests.test_pipeline_app.PipelineAppTests.test_promote_ready_results_include_last_receipt_ref -v
uv run --extra server --no-env-file python -m unittest discover -s tests
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit the publication visibility update**

```bash
git add automation/pipeline/models.py automation/pipeline/knowledge_status.py automation/pipeline/app.py tests/test_pipeline_app.py
git commit -m "feat(app): expose last promote receipt metadata"
```

### Task 2: Lock Structured Operator Error Payloads

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `tests/test_service_api.py`
- Modify: `automation/pipeline/app.py`
- Modify: `automation/pipeline/service_api.py`
- Modify: `automation/pipeline/cli.py`

- [ ] **Step 1: Write failing tests for `error_code` and `next_step`**

```python
def test_cli_receipt_get_failure_includes_error_code_and_next_step(self):
    ...
    self.assertEqual(payload["error_code"], "RECEIPT_NOT_FOUND")
    self.assertIn("state/receipts", payload["next_step"])

def test_service_receipt_returns_structured_error_payload(self):
    ...
    self.assertEqual(payload["error_code"], "RECEIPT_NOT_FOUND")
    self.assertIn("receipt_ref", payload["next_step"])
```

```python
def test_promote_ready_confirm_missing_receipt_returns_structured_error(self):
    from automation.pipeline.app import ForgeApp

    app = ForgeApp(self.repo_root)
    receipt = app.promote_ready(initiator="codex", confirm_receipt_ref="state/receipts/ready_promote/missing.json")

    self.assertEqual(receipt.status, "failed")
    self.assertEqual(receipt.error_code, "READY_CONFIRM_NOT_FOUND")
    self.assertIn("--dry-run", receipt.next_step)
```

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run:

```bash
uv run --no-env-file python -m unittest \
  tests.test_cli.ForgeCliTests.test_cli_receipt_get_failure_includes_error_code_and_next_step \
  tests.test_service_api.ServiceApiTests.test_service_receipt_returns_structured_error_payload \
  tests.test_pipeline_app.PipelineAppTests.test_promote_ready_confirm_missing_receipt_returns_structured_error -v
```

Expected:

```text
FAIL because failures still expose only status/message
```

- [ ] **Step 3: Implement structured operator errors and failure metadata**

```python
class ForgeOperatorError(FileNotFoundError):
    def __init__(self, message: str, *, error_code: str, next_step: Optional[str], status_code: int = 404):
        super().__init__(message)
        self.error_code = error_code
        self.next_step = next_step
        self.status_code = status_code

    def to_payload(self) -> Dict[str, Any]:
        return {
            "status": "failed",
            "message": str(self),
            "error_code": self.error_code,
            "next_step": self.next_step,
        }
```

```python
raise ForgeOperatorError(
    "receipt not found: ...",
    error_code="RECEIPT_NOT_FOUND",
    next_step="Run `forge job get <job_id>` to discover `receipt_ref`, or pass a full state/receipts/... path.",
)
```

```python
return ReadyPromotionBatchReceipt(
    ...,
    error_code="READY_CONFIRM_NOT_FOUND",
    next_step="Run `forge promote-ready --dry-run` first, then pass the preview receipt to `--confirm-receipt`.",
)
```

- [ ] **Step 4: Re-run the focused tests and the full Python suite**

Run:

```bash
uv run --no-env-file python -m unittest \
  tests.test_cli.ForgeCliTests.test_cli_receipt_get_failure_includes_error_code_and_next_step \
  tests.test_service_api.ServiceApiTests.test_service_receipt_returns_structured_error_payload \
  tests.test_pipeline_app.PipelineAppTests.test_promote_ready_confirm_missing_receipt_returns_structured_error -v
uv run --extra server --no-env-file python -m unittest discover -s tests
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit the structured operator error contract**

```bash
git add automation/pipeline/app.py automation/pipeline/service_api.py automation/pipeline/cli.py tests/test_cli.py tests/test_service_api.py tests/test_pipeline_app.py
git commit -m "feat(operator): add structured promote and receipt errors"
```

### Task 3: Sync Public Docs And Skill Guidance

**Files:**
- Modify: `docs/management/forge-command-contract.md`
- Modify: `docs/management/forge-operator-guide.md`
- Modify: `.agents/skills/using-forge/SKILL.md`
- Modify: `.agents/skills/using-forge/references/forge-command-recipes.md`

- [ ] **Step 1: Document the new visibility fields**

```md
- `forge knowledge get` returns publication status plus `last_receipt_ref`.
- `promote_raw` / `promote-ready` result items expose publication metadata and `last_receipt_ref`.
```

- [ ] **Step 2: Document the new failure contract**

```md
- Operator-facing failures now include `error_code` and `next_step` in addition to `message`.
```

- [ ] **Step 3: Run diff hygiene checks**

Run:

```bash
git diff -- docs/management/forge-command-contract.md docs/management/forge-operator-guide.md .agents/skills/using-forge/SKILL.md .agents/skills/using-forge/references/forge-command-recipes.md
git diff --check
```

Expected:

```text
No diff --check errors
```

- [ ] **Step 4: Commit the doc and skill sync**

```bash
git add docs/management/forge-command-contract.md docs/management/forge-operator-guide.md .agents/skills/using-forge/SKILL.md .agents/skills/using-forge/references/forge-command-recipes.md
git commit -m "docs(skill): document promote visibility and structured errors"
```

### Task 4: Final Verification

**Files:**
- Verify only: `automation/pipeline/app.py`
- Verify only: `automation/pipeline/knowledge_status.py`
- Verify only: `automation/pipeline/models.py`
- Verify only: `automation/pipeline/service_api.py`
- Verify only: `automation/pipeline/cli.py`
- Verify only: `tests/test_pipeline_app.py`
- Verify only: `tests/test_cli.py`
- Verify only: `tests/test_service_api.py`

- [ ] **Step 1: Run the full Python suite**

Run:

```bash
uv run --extra server --no-env-file python -m unittest discover -s tests
```

Expected:

```text
OK
```

- [ ] **Step 2: Run diff hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected:

```text
Only intended tracked changes remain, plus the existing untracked checklist file
```

- [ ] **Step 3: Commit the verification checkpoint**

```bash
git add automation/pipeline/app.py automation/pipeline/knowledge_status.py automation/pipeline/models.py automation/pipeline/service_api.py automation/pipeline/cli.py tests/test_pipeline_app.py tests/test_cli.py tests/test_service_api.py docs/archive/2026-Q2/2026-04-09-forge-promote-visibility-errors-design.md docs/archive/2026-Q2/2026-04-09-forge-promote-visibility-errors-plan.md docs/management/forge-command-contract.md docs/management/forge-operator-guide.md .agents/skills/using-forge/SKILL.md .agents/skills/using-forge/references/forge-command-recipes.md
git commit -m "feat(operator): improve promote visibility and errors"
```
