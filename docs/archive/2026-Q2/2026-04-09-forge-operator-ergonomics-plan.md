# Forge Operator Ergonomics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stabilize the public Forge operator contract, make long-running mutations retry-safe, and expose knowledge publication / insight-evidence state without breaking the public/private boundary.

**Architecture:** Treat this work as four separate surfaces: the public Go CLI, the repo-local Python CLI, the service API/runtime, and the shared docs/skill contract. First freeze the public contract and help behavior, then add mutation operation semantics, then expose publication state in receipts, and only after that add read-only status/explain surfaces that reuse existing internal evidence-trace signals.

**Tech Stack:** Go (`flag`, `httptest`), Python (`argparse`, `fastapi`, `pydantic`, `unittest`), Markdown docs, repo-shipped skill assets.

---

> **Path override:** This public repo already stores implementation plans under `docs/archive/2026-Q2/`, so this plan intentionally lives there instead of `docs/superpowers/`.

## Scope Guardrails

- Public contract means the published `forge` binary, `docs/management/forge-operator-guide.md`, and `.agents/skills/using-forge/**`.
- Repo-local maintenance commands such as `uv run forge --repo-root . serve --host 0.0.0.0 --port 8000` stay supported, but they are not allowed to leak into the public operator contract.
- This execution wave does **not** implement content taxonomy, health dashboards, or a public `synthesize-insights --dry-run` flow.
- This execution wave **does** fix the highest-value operator ergonomics gaps called out in `forge-system-improvement-checklist.md`.

## Checklist Triage Before Implementation

- Keep as active work:
  - CLI / docs / skill contract drift
  - help and discoverability
  - timeout / detach / retry ambiguity
  - publication-state visibility after `promote-raw`
  - explainability for “why was this knowledge excluded from insight synthesis?”
- Treat as already implemented and only verify:
  - `forge promote-ready --confirm-receipt <receipt_ref>` is already supported in both the public Go CLI and the repo-local Python CLI.
- Remove from the public contract until intentionally implemented:
  - `forge review-sensitive`
  - `forge redact-raw`
  - `forge synthesize-insights --dry-run`
  - `forge synthesize-insights --confirm-receipt <receipt_ref>`
- Defer to a later design pass:
  - content taxonomy (`reference`, `workflow`, `incident`, `heuristic`, `pattern`)
  - schema-level evidence-strength enforcement
  - health metrics and dashboards

### Task 1: Freeze The Public Contract Matrix

**Files:**
- Create: `docs/management/forge-command-contract.md`
- Modify: `.agents/skills/using-forge/SKILL.md`
- Modify: `.agents/skills/using-forge/references/forge-command-recipes.md`
- Modify: `docs/management/forge-operator-guide.md`
- Modify: `tests/test_docs_contract.py`
- Test: `tests/test_docs_contract.py`

**Execution:** Serial prerequisite. No later task should start until the supported public command list is written down and tested.

- [ ] **Step 1: Write the failing docs-contract assertions**

```python
class PublicDocsContractTests(unittest.TestCase):
    def test_public_contract_lists_only_supported_operator_commands(self):
        contract = (
            Path(__file__).resolve().parents[1]
            / "docs"
            / "management"
            / "forge-command-contract.md"
        ).read_text(encoding="utf-8")
        self.assertIn("forge promote-ready --confirm-receipt <receipt_ref>", contract)
        self.assertNotIn("forge synthesize-insights --dry-run", contract)
        self.assertNotIn("forge review-sensitive", contract)
        self.assertNotIn("forge redact-raw", contract)

    def test_public_skill_does_not_advertise_unsupported_commands(self):
        text = (
            Path(__file__).resolve().parents[1]
            / ".agents"
            / "skills"
            / "using-forge"
            / "SKILL.md"
        ).read_text(encoding="utf-8")
        for unsupported in (
            "forge review-sensitive",
            "forge redact-raw",
            "forge synthesize-insights --dry-run",
            "forge synthesize-insights --confirm-receipt",
        ):
            self.assertNotIn(unsupported, text)
```

- [ ] **Step 2: Run the docs contract tests to verify they fail on current drift**

Run:

```bash
uv run --no-env-file python -m unittest tests.test_docs_contract -v
```

Expected:

```text
FAIL: test_public_skill_does_not_advertise_unsupported_commands
```

- [ ] **Step 3: Add the contract source-of-truth doc and sync the operator-facing docs**

```markdown
# Forge Public Command Contract

## Public Operator Commands

- `forge login --server <url> --token <token>`
- `forge logout`
- `forge version`
- `forge doctor`
- `forge inject --text <content> --title <title> --source <source>`
- `forge review-raw`
- `forge review-queue`
- `forge promote-raw <raw_ref>`
- `forge promote-ready --dry-run --limit N`
- `forge promote-ready --confirm-receipt <receipt_ref>`
- `forge synthesize-insights`
- `forge receipt get <selector>`
- `forge job get <job_id>`

## Maintainer-Only Entry Points

- `uv run forge --repo-root . doctor`
- `uv run forge --repo-root . serve --host 0.0.0.0 --port 8000`
- `python -m automation.pipeline.cli --repo-root . doctor`
```

```markdown
# `.agents/skills/using-forge/SKILL.md`

- remove `review-sensitive` and `redact-raw`
- replace synthesize preview language with “run `forge synthesize-insights` and inspect `evidence_trace_ref` or future explain surfaces”
- keep `promote-ready --dry-run` and `--confirm-receipt`
- explicitly say the public skill tracks `docs/management/forge-command-contract.md`
```

- [ ] **Step 4: Re-run the docs contract tests to verify the public docs are aligned**

Run:

```bash
uv run --no-env-file python -m unittest tests.test_docs_contract -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit the contract freeze**

```bash
git add docs/management/forge-command-contract.md \
  docs/management/forge-operator-guide.md \
  .agents/skills/using-forge/SKILL.md \
  .agents/skills/using-forge/references/forge-command-recipes.md \
  tests/test_docs_contract.py
git commit -m "docs(contract): freeze public forge operator surface"
```

### Task 2: Add Public Go CLI Help And Usage Semantics

**Files:**
- Create: `cmd/forge/main_test.go`
- Modify: `cmd/forge/main.go`
- Test: `cmd/forge/main_test.go`

**Execution:** Serial after Task 1. This sets the behavioral contract for `forge`, `forge help`, and per-command help before new flags are introduced.

- [ ] **Step 1: Write failing Go tests for top-level and subcommand help**

```go
func TestRunTopLevelHelpTokensSucceed(t *testing.T) {
    for _, args := range [][]string{{"help"}, {"--help"}, {"-h"}} {
        code, payload := captureRun(t, args)
        if code != 0 {
            t.Fatalf("args %v returned %d", args, code)
        }
        if payload["status"] != "success" {
            t.Fatalf("args %v payload=%v", args, payload)
        }
        if !strings.Contains(payload["message"].(string), "usage: forge") {
            t.Fatalf("missing usage in payload=%v", payload)
        }
    }
}

func TestRunPromoteReadyHelpShowsSupportedFlagsOnly(t *testing.T) {
    code, payload := captureRun(t, []string{"promote-ready", "--help"})
    if code != 0 {
        t.Fatalf("code=%d payload=%v", code, payload)
    }
    message := payload["message"].(string)
    if !strings.Contains(message, "--confirm-receipt") {
        t.Fatalf("missing confirm flag in %q", message)
    }
    if strings.Contains(message, "synthesize-insights --dry-run") {
        t.Fatalf("unexpected synth preview text in %q", message)
    }
}
```

- [ ] **Step 2: Run the Go tests to verify the current help behavior is insufficient**

Run:

```bash
go test ./cmd/forge -run 'TestRun(TopLevelHelpTokensSucceed|PromoteReadyHelpShowsSupportedFlagsOnly)' -v
```

Expected:

```text
FAIL because `--help` is currently treated as an unknown command and subcommand help is discarded
```

- [ ] **Step 3: Implement explicit help handling in the public Go CLI**

```go
func run(args []string) int {
    if len(args) == 0 {
        printUsageFailure()
        return 2
    }
    if isHelpToken(args[0]) {
        printUsageSuccess()
        return 0
    }
    switch args[0] {
    case "promote-ready":
        return runPromoteReady(args[1:])
    }
}

func parseFlags(fs *flag.FlagSet, args []string, usage func()) (bool, int) {
    if err := fs.Parse(args); err != nil {
        if errors.Is(err, flag.ErrHelp) {
            usage()
            return false, 0
        }
        printFailure(err.Error())
        return false, 2
    }
    return true, 0
}
```

```go
func printUsageSuccess() {
    printJSON(map[string]any{
        "status": "success",
        "message": "usage: forge <login|logout|version|doctor|inject|review-raw|review-queue|promote-raw|promote-ready|synthesize-insights|receipt get|job get> ...",
    })
}
```

- [ ] **Step 4: Re-run the Go tests and the full CLI package suite**

Run:

```bash
go test ./cmd/forge -v
```

Expected:

```text
ok  	.../cmd/forge
```

- [ ] **Step 5: Commit the help-contract changes**

```bash
git add cmd/forge/main.go cmd/forge/main_test.go
git commit -m "feat(cli): add explicit help contract for public forge"
```

### Task 3: Add Retry-Safe Operation Semantics To The Service Runtime

**Files:**
- Create: `automation/pipeline/operations.py`
- Modify: `automation/pipeline/service_api.py`
- Modify: `automation/pipeline/cli.py`
- Modify: `tests/test_service_api.py`
- Modify: `tests/test_cli.py`
- Test: `tests/test_service_api.py`
- Test: `tests/test_cli.py`

**Execution:** Serial after Task 2. This defines the service-side mutation contract before the public Go CLI starts forwarding new retry fields.

- [ ] **Step 1: Write failing service and repo-local CLI tests for `operation_id`**

```python
class ForgeServiceApiTests(unittest.TestCase):
    def test_service_reuses_existing_operation_result(self):
        response = client.post(
            "/v1/promote-ready",
            headers=headers,
            json={"initiator": "codex", "dry_run": True, "operation_id": "op-ready-1"},
        )
        self.assertEqual(response.status_code, 200)
        second = client.post(
            "/v1/promote-ready",
            headers=headers,
            json={"initiator": "codex", "dry_run": True, "operation_id": "op-ready-1"},
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["operation_id"], "op-ready-1")
        self.assertEqual(second.json()["receipt_ref"], response.json()["receipt_ref"])

    def test_service_rejects_operation_id_reuse_with_different_payload(self):
        client.post(
            "/v1/promote-ready",
            headers=headers,
            json={"initiator": "codex", "dry_run": True, "operation_id": "op-ready-2"},
        )
        response = client.post(
            "/v1/promote-ready",
            headers=headers,
            json={"initiator": "codex", "dry_run": False, "operation_id": "op-ready-2"},
        )
        self.assertEqual(response.status_code, 409)
```

```python
def test_execute_remote_command_returns_zero_for_queued_operation(self):
    exit_code, payload = execute_remote_command(
        "synthesize-insights",
        connection,
        {"initiator": "codex", "detach": True, "operation_id": "op-sync-1"},
    )
    self.assertEqual(exit_code, 0)
    self.assertEqual(payload["status"], "queued")
    self.assertEqual(payload["operation_id"], "op-sync-1")
```

- [ ] **Step 2: Run the targeted Python tests to verify the new contract is not implemented yet**

Run:

```bash
uv run --no-env-file python -m unittest \
  tests.test_service_api.ForgeServiceApiTests.test_service_reuses_existing_operation_result \
  tests.test_service_api.ForgeServiceApiTests.test_service_rejects_operation_id_reuse_with_different_payload \
  tests.test_cli -v
```

Expected:

```text
FAIL because mutation payloads do not accept or persist `operation_id`
```

- [ ] **Step 3: Implement an operation registry and thread it through remote mutation flows**

```python
@dataclass
class OperationRecord:
    operation_id: str
    command: str
    fingerprint: str
    status: str
    job_id: str | None = None
    receipt_ref: str | None = None
    response: dict[str, Any] | None = None

class OperationStore:
    def claim(self, command: str, payload: dict[str, Any], operation_id: str | None) -> tuple[str, OperationRecord | None]:
        normalized_payload = normalize_operation_payload(command, payload)
        resolved_operation_id = operation_id or new_operation_id(command)
        existing = self.read(resolved_operation_id)
        if existing is None:
            return resolved_operation_id, None
        if existing.command != command or existing.fingerprint != normalized_payload["fingerprint"]:
            raise OperationConflictError(resolved_operation_id, command, existing.command)
        return resolved_operation_id, existing
```

```python
class PromoteReadyRequest(BaseModel):
    initiator: str = "manual"
    dry_run: bool = False
    limit: Optional[int] = None
    confirm_receipt: Optional[str] = None
    detach: bool = False
    operation_id: Optional[str] = None
```

```python
def execute_remote_command(command_name: str, connection: RemoteConnection, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    base_url = connection.server.rstrip("/")
    response = request_json(
        "POST",
        "{0}/v1/{1}".format(base_url, command_name),
        token=connection.token,
        payload=payload,
    )
    return _exit_code_from_payload(response), response
```

Implementation rules:

- Persist operation records under `state/service/operations/<operation_id>.json`.
- A repeated request with the same normalized payload returns the stored response instead of mutating twice.
- A repeated request with a different payload returns HTTP `409` and a JSON body that names the conflicting command and stored fingerprint.
- Both inline and detached mutation responses include `operation_id`.

- [ ] **Step 4: Re-run the targeted Python tests plus the full service suite**

Run:

```bash
uv run --no-env-file python -m unittest tests.test_service_api tests.test_cli -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit the service/runtime mutation semantics**

```bash
git add automation/pipeline/operations.py \
  automation/pipeline/service_api.py \
  automation/pipeline/cli.py \
  tests/test_service_api.py \
  tests/test_cli.py
git commit -m "feat(service): add retry-safe forge operation semantics"
```

### Task 4: Expose Operation Semantics In The Public Go CLI

**Files:**
- Modify: `cmd/forge/main.go`
- Modify: `cmd/forge/main_test.go`
- Modify: `docs/management/forge-command-contract.md`
- Modify: `docs/management/forge-operator-guide.md`
- Modify: `.agents/skills/using-forge/SKILL.md`
- Modify: `.agents/skills/using-forge/references/forge-command-recipes.md`
- Modify: `tests/test_docs_contract.py`
- Test: `cmd/forge/main_test.go`
- Test: `tests/test_docs_contract.py`

**Execution:** Can start after Task 3 defines the payload shape. This task is parallel-safe with Task 5 because it does not touch the knowledge pipeline internals.

- [ ] **Step 1: Add failing Go tests that assert mutation commands forward `operation_id`**

```go
func TestPromoteReadyForwardsOperationID(t *testing.T) {
    server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        if r.URL.Path != "/v1/promote-ready" {
            t.Fatalf("unexpected path %s", r.URL.Path)
        }
        var payload map[string]any
        if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
            t.Fatal(err)
        }
        if payload["operation_id"] != "op-ready-1" {
            t.Fatalf("payload=%v", payload)
        }
        _ = json.NewEncoder(w).Encode(map[string]any{"status": "queued", "operation_id": "op-ready-1"})
    }))
    defer server.Close()

    code, payload := captureRun(t, []string{
        "promote-ready",
        "--server", server.URL,
        "--token", "secret",
        "--operation-id", "op-ready-1",
        "--detach",
    })
    if code != 0 || payload["operation_id"] != "op-ready-1" {
        t.Fatalf("code=%d payload=%v", code, payload)
    }
}
```

- [ ] **Step 2: Run the Go tests and docs-contract tests to verify the new flag is still absent**

Run:

```bash
go test ./cmd/forge -run 'Test(PromoteReadyForwardsOperationID|RunPromoteReadyHelpShowsSupportedFlagsOnly)' -v
uv run --no-env-file python -m unittest tests.test_docs_contract -v
```

Expected:

```text
FAIL because the public Go CLI does not yet parse `--operation-id`
```

- [ ] **Step 3: Add `--operation-id` to public mutation commands and document the safe-retry workflow**

```go
operationID := fs.String("operation-id", "", "")
payload := map[string]interface{}{
    "initiator": *initiator,
    "detach":    *detach,
}
if strings.TrimSpace(*operationID) != "" {
    payload["operation_id"] = strings.TrimSpace(*operationID)
}
```

````markdown
## Safe Retry

For remote mutations, pin an operation identifier when the caller may need to retry safely:

```bash
forge promote-ready --dry-run --operation-id nightly-ready-preview-20260409
forge synthesize-insights --detach --operation-id nightly-insight-build-20260409
```

If the first call times out client-side, re-run the exact same command with the same `--operation-id`.
````

- [ ] **Step 4: Re-run the Go tests and docs-contract tests**

Run:

```bash
go test ./cmd/forge -v
uv run --no-env-file python -m unittest tests.test_docs_contract -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit the public CLI retry-safety changes**

```bash
git add cmd/forge/main.go \
  cmd/forge/main_test.go \
  docs/management/forge-command-contract.md \
  docs/management/forge-operator-guide.md \
  .agents/skills/using-forge/SKILL.md \
  .agents/skills/using-forge/references/forge-command-recipes.md \
  tests/test_docs_contract.py
git commit -m "feat(public-cli): expose operation ids for safe retries"
```

### Task 5: Return Publication State Directly In Promotion Results

**Files:**
- Create: `automation/pipeline/knowledge_status.py`
- Modify: `automation/pipeline/models.py`
- Modify: `automation/pipeline/documents.py`
- Modify: `automation/pipeline/app.py`
- Modify: `tests/test_pipeline_app.py`
- Modify: `tests/test_cli.py`
- Modify: `docs/management/forge-operator-guide.md`
- Test: `tests/test_pipeline_app.py`
- Test: `tests/test_cli.py`

**Execution:** Can run in parallel with Task 4 once Task 1 is complete. This task does not depend on `operation_id`, but Task 6 depends on the field names introduced here.

- [ ] **Step 1: Write failing tests for receipt visibility on both new promotions and `already promoted` cases**

```python
def test_promote_raw_receipt_includes_publication_fields(self):
    receipt = app.promote_raw("raw/captures/pending.md", initiator="codex")
    self.assertEqual(receipt.status, "success")
    self.assertIn(receipt.publication_status, {"active", "draft"})
    self.assertIsNotNone(receipt.judge_score)
    self.assertIn(receipt.judge_decision, {"publish", "downgrade"})
    self.assertIn(receipt.eligible_for_insights, {True, False})

def test_promote_raw_already_promoted_reports_current_publication_state(self):
    receipt = app.promote_raw("raw/captures/archived-promoted.md", initiator="codex")
    self.assertEqual(receipt.status, "skipped")
    self.assertEqual(receipt.knowledge_ref, "knowledge/workflow/archived-promoted.md")
    self.assertIsNotNone(receipt.publication_status)
    self.assertIsNotNone(receipt.updated_at)
```

- [ ] **Step 2: Run the targeted pipeline and CLI tests to verify the new fields do not exist yet**

Run:

```bash
uv run --no-env-file python -m unittest \
  tests.test_pipeline_app \
  tests.test_cli -v
```

Expected:

```text
FAIL because `RawPromotionReceipt` does not yet expose publication metadata
```

- [ ] **Step 3: Introduce a reusable knowledge-status helper and thread it into receipts**

```python
@dataclass
class KnowledgePublicationStatus:
    knowledge_ref: str
    publication_status: str
    judge_score: float | None
    judge_decision: str | None
    release_reason: str | None
    eligible_for_insights: bool
    excluded_reason: str | None
    updated_at: str | None
```

```python
@dataclass
class RawPromotionReceipt:
    id: str
    status: str
    initiator: str
    raw_ref: str
    knowledge_ref: Optional[str] = None
    candidate_ref: Optional[str] = None
    critic_ref: Optional[str] = None
    judge_ref: Optional[str] = None
    pipeline_mode: Optional[str] = None
    llm_trace_ref: Optional[str] = None
    relay_request_ids: Optional[List[str]] = None
    receipt_ref: Optional[str] = None
    message: Optional[str] = None
    publication_status: Optional[str] = None
    judge_score: Optional[float] = None
    judge_decision: Optional[str] = None
    eligible_for_insights: Optional[bool] = None
    excluded_reason: Optional[str] = None
    updated_at: Optional[str] = None
```

```python
return RawPromotionReceipt(
    id=promotion_id,
    status="success",
    initiator=initiator,
    raw_ref=relative_raw_ref,
    knowledge_ref=result["knowledge_ref"],
    candidate_ref=result["candidate_ref"],
    critic_ref=result["critic_ref"],
    judge_ref=result["judge_ref"],
    pipeline_mode=result["pipeline_mode"],
    llm_trace_ref=result["llm_trace_ref"],
    relay_request_ids=result["relay_request_ids"],
    message="raw promotion completed",
    publication_status=status.publication_status,
    judge_score=status.judge_score,
    judge_decision=status.judge_decision,
    eligible_for_insights=status.eligible_for_insights,
    excluded_reason=status.excluded_reason,
    updated_at=status.updated_at,
)
```

Implementation rules:

- Persist `judge_score`, `judge_decision`, and `release_reason` in knowledge frontmatter going forward.
- Reuse the same exclusion logic that already powers `_select_insight_evidence_with_trace`.
- For historical knowledge files that lack frontmatter judge metadata, return `None` instead of fabricating values.

- [ ] **Step 4: Re-run the targeted tests and then the full Python suite**

Run:

```bash
uv run --no-env-file python -m unittest discover -s tests
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit the promotion-visibility work**

```bash
git add automation/pipeline/knowledge_status.py \
  automation/pipeline/models.py \
  automation/pipeline/documents.py \
  automation/pipeline/app.py \
  tests/test_pipeline_app.py \
  tests/test_cli.py \
  docs/management/forge-operator-guide.md
git commit -m "feat(promotion): expose publication status in receipts"
```

### Task 6: Add Read-Only Status And Explain Surfaces

**Files:**
- Create: `automation/pipeline/explain.py`
- Modify: `automation/pipeline/app.py`
- Modify: `automation/pipeline/service_api.py`
- Modify: `automation/pipeline/cli.py`
- Modify: `cmd/forge/main.go`
- Modify: `cmd/forge/main_test.go`
- Modify: `tests/test_service_api.py`
- Modify: `tests/test_cli.py`
- Modify: `docs/management/forge-command-contract.md`
- Modify: `docs/management/forge-operator-guide.md`
- Modify: `.agents/skills/using-forge/SKILL.md`
- Modify: `.agents/skills/using-forge/references/forge-command-recipes.md`
- Test: `tests/test_service_api.py`
- Test: `tests/test_cli.py`
- Test: `cmd/forge/main_test.go`

**Execution:** Serial after Task 5. This task depends on the knowledge-status field names from Task 5 and intentionally exposes existing evidence-trace internals before attempting a public dry-run synthesize flow.

- [ ] **Step 1: Write failing tests for `knowledge get` and `explain insight`**

```python
class ForgeServiceApiTests(unittest.TestCase):
    def test_service_returns_knowledge_status(self):
        response = client.get(
            "/v1/knowledge",
            headers=headers,
            params={"selector": "knowledge/workflow/example.md"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["knowledge_ref"], "knowledge/workflow/example.md")
        self.assertIn(payload["publication_status"], {"active", "draft"})

    def test_service_explains_insight_receipt(self):
        response = client.get(
            "/v1/explain/insight",
            headers=headers,
            params={"receipt_ref": insight_receipt_ref},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("selected_paths", payload)
        self.assertIn("excluded_documents", payload)
```

```go
func TestExplainInsightCommandUsesPublicEndpoint(t *testing.T) {
    code, payload := captureRun(t, []string{
        "explain", "insight", "state/receipts/insights/example.json",
        "--server", server.URL,
        "--token", "secret",
    })
    if code != 0 || payload["status"] != "success" {
        t.Fatalf("code=%d payload=%v", code, payload)
    }
}
```

- [ ] **Step 2: Run the targeted tests to verify the new read-only surfaces are missing**

Run:

```bash
go test ./cmd/forge -run 'TestExplainInsightCommandUsesPublicEndpoint' -v
uv run --no-env-file python -m unittest \
  tests.test_service_api \
  tests.test_cli -v
```

Expected:

```text
FAIL because neither the service API nor the public CLI exposes `knowledge` / `explain` commands yet
```

- [ ] **Step 3: Implement thin read-only surfaces over existing knowledge metadata and evidence traces**

```python
def explain_insight_from_receipt(self, receipt_ref: str) -> dict[str, Any]:
    receipt = self.read_receipt(receipt_ref)
    evidence_trace_ref = str(receipt.get("evidence_trace_ref") or "").strip()
    trace = json.loads((self.repo_root / evidence_trace_ref).read_text(encoding="utf-8"))
    excluded = [
        item
        for item in trace.get("documents", [])
        if str(item.get("excluded_reason") or "").strip()
    ]
    return {
        "status": "success",
        "receipt_ref": receipt_ref,
        "evidence_trace_ref": evidence_trace_ref,
        "selected_paths": trace.get("selected_paths", []),
        "candidate_clusters": trace.get("candidate_clusters", []),
        "excluded_documents": excluded,
    }
```

```go
// public CLI command tree
case "knowledge":
    return runKnowledge(args[1:])
case "explain":
    return runExplain(args[1:])
```

Implementation rules:

- `forge knowledge get <knowledge_ref>` returns the Task 5 publication payload.
- `forge explain insight <receipt_ref>` returns selected paths, candidate clusters, and excluded documents with their exclusion reasons.
- The explain response is read-only. Do **not** add `synthesize-insights --dry-run` in this wave.

- [ ] **Step 4: Re-run targeted tests and the full repo test suite**

Run:

```bash
go test ./cmd/forge -v
uv run --no-env-file python -m unittest discover -s tests
git diff --check
```

Expected:

```text
all tests pass and `git diff --check` is clean
```

- [ ] **Step 5: Commit the new read-only operator surfaces**

```bash
git add automation/pipeline/explain.py \
  automation/pipeline/app.py \
  automation/pipeline/service_api.py \
  automation/pipeline/cli.py \
  cmd/forge/main.go \
  cmd/forge/main_test.go \
  tests/test_service_api.py \
  tests/test_cli.py \
  docs/management/forge-command-contract.md \
  docs/management/forge-operator-guide.md \
  .agents/skills/using-forge/SKILL.md \
  .agents/skills/using-forge/references/forge-command-recipes.md
git commit -m "feat(operator): add knowledge status and insight explain commands"
```

## Execution Order

### Serial dependencies

1. Task 1 must land first because it defines the contract boundary.
2. Task 2 must land before any new public CLI flags or commands are added.
3. Task 3 must land before Task 4 because the public Go CLI needs a stable `operation_id` payload contract.
4. Task 5 must land before Task 6 because `knowledge get` and `explain insight` depend on the field names introduced there.

### Parallel windows

- After Task 1, Task 3 and Task 5 can proceed on separate branches because they touch different code paths:
  - Task 3: `automation/pipeline/service_api.py`, `automation/pipeline/cli.py`, `automation/pipeline/operations.py`
  - Task 5: `automation/pipeline/models.py`, `automation/pipeline/app.py`, `automation/pipeline/documents.py`, `automation/pipeline/knowledge_status.py`
- After Task 3 lands, Task 4 can run while Task 5 is finishing.
- Task 6 is intentionally serial and should start only after Task 5 merges.

## Deferred After This Execution Wave

- Public `synthesize-insights --dry-run` / `--confirm-receipt`
- content taxonomy and differentiated publish policy
- candidate-schema hardening for evidence strength
- operator health metrics / dashboards

## Final Verification Gate

Run exactly these commands before merging the full wave:

```bash
go test ./cmd/forge -v
uv run --no-env-file python -m unittest discover -s tests
git diff --check
```
