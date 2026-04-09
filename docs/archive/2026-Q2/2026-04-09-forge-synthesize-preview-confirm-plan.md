# Forge `synthesize-insights` Preview/Confirm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add public `forge synthesize-insights --dry-run` and `--confirm-receipt <receipt_ref>` support with stable preview receipts, drift detection, and aligned docs/skills.

**Architecture:** Reuse the existing `InsightSynthesisReceipt` and insight evidence trace flow instead of creating a second preview receipt type. The Python app owns the preview/confirm semantics and evidence drift checks; the service API, repo-local CLI, public Go CLI, and docs surface the same contract without introducing new execution models.

**Tech Stack:** Python (`unittest`, `argparse`, `fastapi`, `pydantic`), Go (`flag`, `httptest`), Markdown docs, repo-shipped skill assets.

---

> **Path override:** This public repo stores plans under `docs/archive/2026-Q2/`, so this plan intentionally lives here instead of `docs/superpowers/`.

## Scope Guardrails

- Do not change the current insight evidence selection algorithm.
- Do not add a second explain API; continue to rely on `forge explain insight <receipt_ref>`.
- Keep `promote-ready` semantics unchanged; only mirror its preview/confirm contract for `synthesize-insights`.
- Preserve detached job semantics and `--operation-id` retry behavior.

### Task 1: Extend Insight Receipt Model And App Semantics

**Files:**
- Modify: `automation/pipeline/models.py`
- Modify: `automation/pipeline/app.py`
- Test: `tests/test_pipeline_app.py`

- [ ] **Step 1: Write failing app tests for dry-run and confirm flow**

```python
def test_synthesize_insights_dry_run_writes_preview_without_creating_insight(self):
    from automation.pipeline.app import ForgeApp

    app = ForgeApp(self.repo_root)
    receipt = app.synthesize_insights(initiator="codex", dry_run=True)

    self.assertEqual(receipt.status, "success")
    self.assertTrue(receipt.dry_run)
    self.assertIsNone(receipt.confirmed_from_receipt_ref)
    self.assertTrue(receipt.evidence_refs)
    self.assertTrue(receipt.evidence_manifest)
    self.assertIsNotNone(receipt.evidence_trace_ref)
    self.assertIsNone(receipt.insight_ref)
    self.assertEqual(sorted((self.repo_root / "insights").glob("**/*.md")), [])

def test_synthesize_insights_can_confirm_a_dry_run_receipt(self):
    from automation.pipeline.app import ForgeApp

    app = ForgeApp(self.repo_root)
    preview = app.synthesize_insights(initiator="codex", dry_run=True)
    receipt = app.synthesize_insights(initiator="codex", confirm_receipt_ref=preview.receipt_ref)

    self.assertTrue(preview.dry_run)
    self.assertEqual(receipt.status, "success")
    self.assertFalse(receipt.dry_run)
    self.assertEqual(receipt.confirmed_from_receipt_ref, preview.receipt_ref)
    self.assertEqual(receipt.evidence_refs, preview.evidence_refs)
    self.assertIsNotNone(receipt.insight_ref)

def test_synthesize_insights_confirm_fails_when_evidence_drifted(self):
    from automation.pipeline.app import ForgeApp

    app = ForgeApp(self.repo_root)
    preview = app.synthesize_insights(initiator="codex", dry_run=True)
    evidence_path = self.repo_root / preview.evidence_refs[0]
    evidence_path.write_text(evidence_path.read_text(encoding="utf-8") + "\nDrifted.\n", encoding="utf-8")

    receipt = app.synthesize_insights(initiator="codex", confirm_receipt_ref=preview.receipt_ref)

    self.assertEqual(receipt.status, "failed")
    self.assertEqual(receipt.confirmed_from_receipt_ref, preview.receipt_ref)
    self.assertIn("drift", receipt.message.lower())
```

- [ ] **Step 2: Run the focused app tests to verify they fail**

Run:

```bash
uv run --no-env-file python -m unittest \
  tests.test_pipeline_app.PipelineAppTests.test_synthesize_insights_dry_run_writes_preview_without_creating_insight \
  tests.test_pipeline_app.PipelineAppTests.test_synthesize_insights_can_confirm_a_dry_run_receipt \
  tests.test_pipeline_app.PipelineAppTests.test_synthesize_insights_confirm_fails_when_evidence_drifted -v
```

Expected:

```text
FAIL because ForgeApp.synthesize_insights() does not yet accept dry_run/confirm_receipt_ref or produce preview receipts
```

- [ ] **Step 3: Add the minimal receipt fields and app flow**

```python
@dataclass
class InsightSynthesisReceipt:
    id: str
    status: str
    initiator: str
    dry_run: bool = False
    confirmed_from_receipt_ref: Optional[str] = None
    evidence_refs: List[str] = field(default_factory=list)
    evidence_manifest: List[Dict[str, str]] = field(default_factory=list)
```

```python
def synthesize_insights(
    self,
    initiator: str = "manual",
    dry_run: bool = False,
    confirm_receipt_ref: Optional[str] = None,
) -> InsightSynthesisReceipt:
    initiator = normalize_initiator(initiator)
    synthesis_id = self._new_id()
    if confirm_receipt_ref:
        return self._confirm_insight_synthesis(
            synthesis_id=synthesis_id,
            initiator=initiator,
            confirm_receipt_ref=confirm_receipt_ref,
        )
```

```python
if dry_run:
    receipt = InsightSynthesisReceipt(
        id=synthesis_id,
        status="success",
        initiator=initiator,
        dry_run=True,
        evidence_refs=[doc["path"] for doc in evidence_docs],
        evidence_manifest=self._build_insight_evidence_manifest(evidence_docs),
        evidence_trace_ref=evidence_trace_ref,
        message="insight synthesis dry run completed",
    )
    return self._write_insight_receipt(receipt)
```

```python
def _confirm_insight_synthesis(self, synthesis_id: str, initiator: str, confirm_receipt_ref: str) -> InsightSynthesisReceipt:
    preview_payload = self._load_insight_preview_receipt(confirm_receipt_ref)
    evidence_docs = self._resolve_confirmed_insight_evidence(preview_payload)
    result = self._run_insight_pipeline(
        synthesis_id=synthesis_id,
        runtime_lock=load_or_create_runtime_lock(self.app_root / "automation" / "compiled" / "runtime.lock.json"),
        evidence_docs=evidence_docs,
    )
```

- [ ] **Step 4: Re-run the focused tests and then the full app suite**

Run:

```bash
uv run --no-env-file python -m unittest \
  tests.test_pipeline_app.PipelineAppTests.test_synthesize_insights_dry_run_writes_preview_without_creating_insight \
  tests.test_pipeline_app.PipelineAppTests.test_synthesize_insights_can_confirm_a_dry_run_receipt \
  tests.test_pipeline_app.PipelineAppTests.test_synthesize_insights_confirm_fails_when_evidence_drifted -v
uv run --extra server --no-env-file python -m unittest discover -s tests
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit the app-level preview/confirm support**

```bash
git add automation/pipeline/models.py automation/pipeline/app.py tests/test_pipeline_app.py
git commit -m "feat(app): add synthesize preview confirm receipts"
```

### Task 2: Extend Service API Preview/Confirm Contract

**Files:**
- Modify: `automation/pipeline/service_api.py`
- Test: `tests/test_service_api.py`

- [ ] **Step 1: Write failing service tests for request forwarding**

```python
def test_service_synthesize_insights_accepts_dry_run(self):
    response = client.post(
        "/v1/synthesize-insights",
        headers=headers,
        json={"initiator": "codex", "dry_run": True},
    )
    self.assertEqual(response.status_code, 200)
    self.assertTrue(response.json()["dry_run"])

def test_service_synthesize_insights_accepts_confirm_receipt(self):
    preview = client.post(
        "/v1/synthesize-insights",
        headers=headers,
        json={"initiator": "codex", "dry_run": True},
    ).json()
    response = client.post(
        "/v1/synthesize-insights",
        headers=headers,
        json={"initiator": "codex", "confirm_receipt": preview["receipt_ref"]},
    )
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.json()["confirmed_from_receipt_ref"], preview["receipt_ref"])
```

- [ ] **Step 2: Run the focused service tests to verify they fail**

Run:

```bash
uv run --no-env-file python -m unittest \
  tests.test_service_api.ServiceApiTests.test_service_synthesize_insights_accepts_dry_run \
  tests.test_service_api.ServiceApiTests.test_service_synthesize_insights_accepts_confirm_receipt -v
```

Expected:

```text
FAIL because SynthesizeRequest and /v1/synthesize-insights do not yet accept dry_run or confirm_receipt
```

- [ ] **Step 3: Add the minimal request fields and runner forwarding**

```python
class SynthesizeRequest(BaseModel):
    initiator: str = "manual"
    dry_run: bool = False
    confirm_receipt: Optional[str] = None
    detach: bool = False
    operation_id: Optional[str] = None
```

```python
runner = lambda: runtime.build_app().synthesize_insights(
    initiator=request.initiator,
    dry_run=request.dry_run,
    confirm_receipt_ref=request.confirm_receipt,
)
```

- [ ] **Step 4: Re-run focused service tests and the full suite**

Run:

```bash
uv run --no-env-file python -m unittest \
  tests.test_service_api.ServiceApiTests.test_service_synthesize_insights_accepts_dry_run \
  tests.test_service_api.ServiceApiTests.test_service_synthesize_insights_accepts_confirm_receipt -v
uv run --extra server --no-env-file python -m unittest discover -s tests
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit the service contract update**

```bash
git add automation/pipeline/service_api.py tests/test_service_api.py
git commit -m "feat(service): expose synthesize dry run and confirm"
```

### Task 3: Extend Repo-Local Python CLI And Remote Payload Mapping

**Files:**
- Modify: `automation/pipeline/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests for local and remote preview/confirm**

```python
def test_cli_synthesize_insights_supports_dry_run(self):
    exit_code = main(["--repo-root", str(repo_root), "synthesize-insights", "--initiator", "codex", "--dry-run"])
    self.assertEqual(exit_code, 0)
    self.assertTrue(json.loads(stdout.getvalue())["dry_run"])

def test_cli_remote_synthesize_insights_forwards_confirm_receipt(self):
    with patch("automation.pipeline.cli.execute_remote_command") as remote_command:
        remote_command.return_value = (0, {"status": "success", "confirmed_from_receipt_ref": "state/receipts/insights/preview.json"})
        exit_code = main(["synthesize-insights", "--initiator", "codex", "--confirm-receipt", "state/receipts/insights/preview.json"])
    payload = remote_command.call_args.args[2]
    self.assertEqual(payload["confirm_receipt"], "state/receipts/insights/preview.json")
```

- [ ] **Step 2: Run the focused CLI tests to verify they fail**

Run:

```bash
uv run --no-env-file python -m unittest \
  tests.test_cli.ForgeCliTests.test_cli_synthesize_insights_supports_dry_run \
  tests.test_cli.ForgeCliTests.test_cli_remote_synthesize_insights_forwards_confirm_receipt -v
```

Expected:

```text
FAIL because the argparse surface and remote payload builder do not yet expose the new flags
```

- [ ] **Step 3: Add argparse flags, mutual exclusion checks, and payload forwarding**

```python
synthesize = subparsers.add_parser("synthesize-insights")
synthesize.add_argument("--initiator", default="manual", type=parse_initiator, choices=ALLOWED_INITIATORS)
synthesize.add_argument("--dry-run", action="store_true")
synthesize.add_argument("--confirm-receipt")
synthesize.add_argument("--detach", action="store_true")
synthesize.add_argument("--operation-id")
```

```python
if args.command == "synthesize-insights":
    if args.confirm_receipt and args.dry_run:
        parser.error("synthesize-insights does not allow --confirm-receipt together with --dry-run")
    receipt = app.synthesize_insights(
        initiator=args.initiator,
        dry_run=args.dry_run,
        confirm_receipt_ref=args.confirm_receipt,
    )
```

```python
if args.command == "synthesize-insights":
    return {
        "initiator": args.initiator,
        "dry_run": args.dry_run,
        "confirm_receipt": args.confirm_receipt,
        "detach": args.detach,
        "operation_id": args.operation_id,
    }
```

- [ ] **Step 4: Re-run focused CLI tests and the full suite**

Run:

```bash
uv run --no-env-file python -m unittest \
  tests.test_cli.ForgeCliTests.test_cli_synthesize_insights_supports_dry_run \
  tests.test_cli.ForgeCliTests.test_cli_remote_synthesize_insights_forwards_confirm_receipt -v
uv run --extra server --no-env-file python -m unittest discover -s tests
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit the repo-local CLI update**

```bash
git add automation/pipeline/cli.py tests/test_cli.py
git commit -m "feat(cli): add synthesize dry run and confirm flags"
```

### Task 4: Extend Public Go CLI Surface

**Files:**
- Modify: `cmd/forge/main.go`
- Modify: `cmd/forge/main_test.go`

- [ ] **Step 1: Write failing Go tests for help and payload forwarding**

```go
func TestRunSynthesizeHelpShowsPreviewFlags(t *testing.T) {
    code, payload := captureRun(t, []string{"synthesize-insights", "--help"})
    if code != 0 {
        t.Fatalf("code=%d payload=%v", code, payload)
    }
    message := payload["message"].(string)
    for _, expected := range []string{"--dry-run", "--confirm-receipt", "--detach", "--operation-id"} {
        if !strings.Contains(message, expected) {
            t.Fatalf("missing %s in %q", expected, message)
        }
    }
}

func TestSynthesizeForwardsDryRunAndConfirmReceipt(t *testing.T) {
    server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        if r.URL.Path != "/v1/synthesize-insights" {
            t.Fatalf("unexpected path %s", r.URL.Path)
        }
        var payload map[string]interface{}
        if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
            t.Fatalf("decode request: %v", err)
        }
        if payload["dry_run"] != true {
            t.Fatalf("payload=%v", payload)
        }
        if payload["confirm_receipt"] != "state/receipts/insights/preview.json" {
            t.Fatalf("payload=%v", payload)
        }
        w.Header().Set("Content-Type", "application/json")
        _ = json.NewEncoder(w).Encode(map[string]interface{}{"status": "success"})
    }))
    defer server.Close()
}
```

- [ ] **Step 2: Run the focused Go tests to verify they fail**

Run:

```bash
go test ./cmd/forge -run 'Test(RunSynthesizeHelpShowsPreviewFlags|SynthesizeForwardsDryRunAndConfirmReceipt)' -v
```

Expected:

```text
FAIL because the public synthesize command does not yet expose --dry-run or --confirm-receipt
```

- [ ] **Step 3: Add flags and JSON payload forwarding**

```go
func runSynthesize(args []string) int {
    fs := flag.NewFlagSet("synthesize-insights", flag.ContinueOnError)
    dryRun := fs.Bool("dry-run", false, "")
    confirmReceipt := fs.String("confirm-receipt", "", "")
    detach := fs.Bool("detach", false, "")
    operationID := fs.String("operation-id", "", "")
```

```go
payload := map[string]interface{}{
    "initiator":       *initiator,
    "dry_run":         *dryRun,
    "confirm_receipt": strings.TrimSpace(*confirmReceipt),
    "detach":          *detach,
}
```

- [ ] **Step 4: Re-run focused Go tests and the full package suite**

Run:

```bash
go test ./cmd/forge -run 'Test(RunSynthesizeHelpShowsPreviewFlags|SynthesizeForwardsDryRunAndConfirmReceipt)' -v
go test ./cmd/forge -v
```

Expected:

```text
PASS
```

- [ ] **Step 5: Commit the public Go CLI update**

```bash
git add cmd/forge/main.go cmd/forge/main_test.go
git commit -m "feat(operator): expose synthesize preview confirm flags"
```

### Task 5: Sync Public Docs, Skill, And Contract Tests

**Files:**
- Modify: `docs/management/forge-command-contract.md`
- Modify: `docs/management/forge-operator-guide.md`
- Modify: `.agents/skills/using-forge/SKILL.md`
- Modify: `.agents/skills/using-forge/references/forge-command-recipes.md`
- Modify: `tests/test_docs_contract.py`

- [ ] **Step 1: Write failing docs-contract assertions for the new public flags**

```python
def test_public_contract_lists_synthesize_preview_and_confirm(self):
    self.assertIn("forge synthesize-insights --dry-run", public_section)
    self.assertIn("forge synthesize-insights --confirm-receipt <receipt_ref>", public_section)

def test_public_skill_mentions_synthesize_preview_and_confirm(self):
    self.assertIn("forge synthesize-insights --dry-run", text)
    self.assertIn("forge synthesize-insights --confirm-receipt <receipt_ref>", text)
```

- [ ] **Step 2: Run the docs contract tests to verify they fail**

Run:

```bash
uv run --no-env-file python -m unittest tests.test_docs_contract -v
```

Expected:

```text
FAIL because the public docs still say synthesize preview/confirm are not supported
```

- [ ] **Step 3: Update docs and skill to the new contract**

```markdown
- `forge synthesize-insights --dry-run --initiator <initiator>`
- `forge synthesize-insights --confirm-receipt <receipt_ref> --initiator <initiator>`
```

```markdown
Run insight synthesis explicitly:

    forge synthesize-insights --initiator manual --dry-run
    forge synthesize-insights --initiator manual --confirm-receipt state/receipts/insights/<preview>.json
```

- [ ] **Step 4: Re-run docs contract tests and full verification**

Run:

```bash
uv run --no-env-file python -m unittest tests.test_docs_contract -v
go test ./cmd/forge -v
uv run --extra server --no-env-file python -m unittest discover -s tests
git diff --check
```

Expected:

```text
OK / PASS / no diff check errors
```

- [ ] **Step 5: Commit the docs/skill sync**

```bash
git add docs/management/forge-command-contract.md \
  docs/management/forge-operator-guide.md \
  .agents/skills/using-forge/SKILL.md \
  .agents/skills/using-forge/references/forge-command-recipes.md \
  tests/test_docs_contract.py
git commit -m "docs(contract): publish synthesize preview confirm flow"
```

## Self-Review Checklist

- Spec coverage:
  - preview receipt fields: Task 1
  - confirm drift detection: Task 1
  - service forwarding: Task 2
  - repo-local CLI forwarding: Task 3
  - public Go CLI forwarding: Task 4
  - docs/skill/contract sync: Task 5
- Placeholder scan:
  - No unresolved blanks or deferred code hooks remain in this plan.
- Type consistency:
  - Use `dry_run`, `confirm_receipt`, and `confirm_receipt_ref` consistently by layer.
  - Keep the receipt field name `confirmed_from_receipt_ref` consistent everywhere.

## Execution Choice

This repo has already established a clean spec and the tasks split cleanly into:

- Python app/service/tests
- CLI surfaces
- docs/skill/contract sync

The recommended execution mode is **Subagent-Driven** because these tasks are mostly independent after Task 1 defines the receipt contract.
