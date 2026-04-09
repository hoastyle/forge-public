# Forge Remote Mutation Job-First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make remote `inject`, `promote-raw`, `promote-ready`, and `synthesize-insights` default to detached jobs, while adding explicit `--wait` for synchronous completion.

**Architecture:** Keep the existing service-side detached job runtime unchanged. Push the new behavior into the two client surfaces: the repo-local Python CLI computes remote `detach` defaults based on `--wait` and remote/local mode, and the public Go CLI does the same for its always-remote mutation commands. Then align docs and the shipped `using-forge` skill to the new contract.

**Tech Stack:** Python (`argparse`, `unittest`), Go (`flag`, `httptest`), Markdown docs, repo-shipped skill assets.

---

> **Path override:** This public repo stores plans under `docs/archive/2026-Q2/`, so this plan intentionally lives here instead of `docs/superpowers/`.

## Scope Guardrails

- Do not redesign `automation/pipeline/service_api.py` detached execution; reuse current `detach=true => job`, `detach=false => receipt`.
- Do not change repo-local `ForgeApp` mutation semantics.
- Do not change non-mutation read commands such as `doctor`, `review-raw`, `review-queue`, `receipt get`, `job get`, `knowledge get`, or `explain insight`.
- Keep `--detach` for backward compatibility, but make it redundant in the default remote path.

### Task 1: Lock Python CLI Remote Detach Semantics

**Files:**
- Modify: `automation/pipeline/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing Python CLI tests for the new remote defaults**

```python
def test_cli_remote_inject_defaults_to_detached_job(self):
    from automation.pipeline.cli import main

    with tempfile.TemporaryDirectory() as tempdir:
        config_home = Path(tempdir) / "config"
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}, clear=False):
            main(["login", "--server", "http://127.0.0.1:8000", "--token", "secret-token"])
            stdout = StringIO()
            with patch("automation.pipeline.cli.execute_remote_command") as remote_command:
                remote_command.return_value = (0, {"status": "queued", "job_id": "inject-job-1"})
                with redirect_stdout(stdout):
                    exit_code = main(["inject", "--text", "remote note", "--title", "Remote", "--source", "cli test"])

    self.assertEqual(exit_code, 0)
    payload = remote_command.call_args.args[2]
    self.assertTrue(payload["detach"])

def test_cli_remote_promote_ready_wait_overrides_default_detach(self):
    from automation.pipeline.cli import main

    with tempfile.TemporaryDirectory() as tempdir:
        config_home = Path(tempdir) / "config"
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}, clear=False):
            main(["login", "--server", "http://127.0.0.1:8000", "--token", "secret-token"])
            stdout = StringIO()
            with patch("automation.pipeline.cli.execute_remote_command") as remote_command:
                remote_command.return_value = (0, {"status": "success", "receipt_ref": "state/receipts/ready_promote/1.json"})
                with redirect_stdout(stdout):
                    exit_code = main(["promote-ready", "--initiator", "codex", "--wait"])

    self.assertEqual(exit_code, 0)
    payload = remote_command.call_args.args[2]
    self.assertFalse(payload["detach"])

def test_cli_remote_synthesize_rejects_wait_with_detach(self):
    from automation.pipeline.cli import main

    stdout = StringIO()
    with redirect_stdout(stdout):
        exit_code = main(["synthesize-insights", "--wait", "--detach"])

    self.assertEqual(exit_code, 2)
    self.assertIn("--wait", stdout.getvalue())
    self.assertIn("--detach", stdout.getvalue())
```

- [ ] **Step 2: Run the focused Python CLI tests and confirm they fail**

Run:

```bash
uv run --no-env-file python -m unittest \
  tests.test_cli.ForgeCliTests.test_cli_remote_inject_defaults_to_detached_job \
  tests.test_cli.ForgeCliTests.test_cli_remote_promote_ready_wait_overrides_default_detach \
  tests.test_cli.ForgeCliTests.test_cli_remote_synthesize_rejects_wait_with_detach -v
```

Expected:

```text
FAIL because remote mutation payloads still default to detach=false and the parser does not yet know --wait
```

- [ ] **Step 3: Implement Python CLI `--wait` and computed remote detach behavior**

```python
inject.add_argument("--wait", action="store_true")
synthesize.add_argument("--wait", action="store_true")
promote_raw.add_argument("--wait", action="store_true")
promote_ready.add_argument("--wait", action="store_true")
```

```python
def _resolve_remote_detach(args) -> bool:
    wait = bool(getattr(args, "wait", False))
    detach = bool(getattr(args, "detach", False))
    if wait and detach:
        raise SystemExit("--wait does not allow --detach; remote mutations default to detached jobs")
    if wait:
        return False
    if detach:
        return True
    return True
```

```python
if args.command == "inject":
    payload = {
        "title": args.title,
        "source": args.source,
        "tags": args.tags,
        "initiator": args.initiator,
        "promote_knowledge": args.promote_knowledge,
        "detach": _resolve_remote_detach(args),
        "operation_id": args.operation_id,
    }
```

- [ ] **Step 4: Re-run focused Python CLI tests and the full Python suite**

Run:

```bash
uv run --no-env-file python -m unittest \
  tests.test_cli.ForgeCliTests.test_cli_remote_inject_defaults_to_detached_job \
  tests.test_cli.ForgeCliTests.test_cli_remote_promote_ready_wait_overrides_default_detach \
  tests.test_cli.ForgeCliTests.test_cli_remote_synthesize_rejects_wait_with_detach -v
uv run --extra server --no-env-file python -m unittest discover -s tests
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit the Python CLI contract change**

```bash
git add automation/pipeline/cli.py tests/test_cli.py
git commit -m "feat(cli): default remote mutations to detached jobs"
```

### Task 2: Lock Public Go CLI Remote Detach Semantics

**Files:**
- Modify: `cmd/forge/main.go`
- Test: `cmd/forge/main_test.go`

- [ ] **Step 1: Write failing Go tests for default detach and `--wait` override**

```go
func TestRunInjectDefaultsToDetachedJob(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var payload map[string]interface{}
		_ = json.NewDecoder(r.Body).Decode(&payload)
		if payload["detach"] != true {
			t.Fatalf("payload=%v", payload)
		}
		_ = json.NewEncoder(w).Encode(map[string]interface{}{"status": "queued", "job_id": "inject-job-1"})
	}))
	defer server.Close()

	code, payload := captureRun(t, []string{
		"inject",
		"--server", server.URL,
		"--token", "secret",
		"--text", "remote note",
		"--title", "Remote",
		"--source", "cli test",
	})
	if code != 0 || payload["status"] != "queued" {
		t.Fatalf("code=%d payload=%v", code, payload)
	}
}

func TestRunPromoteReadyWaitOverridesDetachDefault(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var payload map[string]interface{}
		_ = json.NewDecoder(r.Body).Decode(&payload)
		if payload["detach"] != false {
			t.Fatalf("payload=%v", payload)
		}
		_ = json.NewEncoder(w).Encode(map[string]interface{}{"status": "success"})
	}))
	defer server.Close()

	code, payload := captureRun(t, []string{
		"promote-ready",
		"--server", server.URL,
		"--token", "secret",
		"--wait",
	})
	if code != 0 || payload["status"] != "success" {
		t.Fatalf("code=%d payload=%v", code, payload)
	}
}

func TestRunPromoteRawRejectsWaitWithDetach(t *testing.T) {
	code, payload := captureRun(t, []string{
		"promote-raw",
		"--wait",
		"--detach",
		"raw/example.md",
	})
	if code != 2 {
		t.Fatalf("code=%d payload=%v", code, payload)
	}
}
```

- [ ] **Step 2: Run the focused Go tests and confirm they fail**

Run:

```bash
go test ./cmd/forge -run 'TestRunInjectDefaultsToDetachedJob|TestRunPromoteReadyWaitOverridesDetachDefault|TestRunPromoteRawRejectsWaitWithDetach' -v
```

Expected:

```text
FAIL because mutation flags do not yet include --wait and default detach is still false
```

- [ ] **Step 3: Implement Go `--wait`, shared detach resolution, and help updates**

```go
wait := fs.Bool("wait", false, "")
detach := fs.Bool("detach", false, "")
```

```go
func resolveDetach(wait bool, detach bool) (bool, error) {
	if wait && detach {
		return false, fmt.Errorf("--wait does not allow --detach; remote mutations default to detached jobs")
	}
	if wait {
		return false, nil
	}
	if detach {
		return true, nil
	}
	return true, nil
}
```

```go
resolvedDetach, err := resolveDetach(*wait, *detach)
if err != nil {
	printFailure(err.Error())
	return 2
}
payload := map[string]interface{}{
	"initiator": *initiator,
	"detach":    resolvedDetach,
}
```

- [ ] **Step 4: Re-run focused Go tests and the full Go command suite**

Run:

```bash
go test ./cmd/forge -run 'TestRunInjectDefaultsToDetachedJob|TestRunPromoteReadyWaitOverridesDetachDefault|TestRunPromoteRawRejectsWaitWithDetach' -v
go test ./cmd/forge -v
```

Expected:

```text
PASS
```

- [ ] **Step 5: Commit the public Go CLI contract change**

```bash
git add cmd/forge/main.go cmd/forge/main_test.go
git commit -m "feat(public-cli): add wait flag for remote mutations"
```

### Task 3: Align Operator Docs, Skill, And Examples

**Files:**
- Modify: `docs/management/forge-command-contract.md`
- Modify: `docs/management/forge-operator-guide.md`
- Modify: `.agents/skills/using-forge/SKILL.md`
- Modify: `.agents/skills/using-forge/references/forge-command-recipes.md`

- [ ] **Step 1: Update the command contract to state job-first defaults**

```md
- Remote `inject`, `promote-raw`, `promote-ready`, and `synthesize-insights` default to detached job submission.
- Add `--wait` when the caller must block for the final receipt.
- `--detach` remains accepted for compatibility, but is redundant in the default remote path.
```

- [ ] **Step 2: Update the operator guide with the new closed loop**

```md
forge promote-ready --initiator manual
forge job get <job_id>
forge receipt get <receipt_ref>

forge synthesize-insights --initiator manual --wait
```

- [ ] **Step 3: Update the shipped `using-forge` skill and recipes**

```md
- Remote mutations are job-first by default.
- Use `--wait` only when the caller must synchronously consume the resulting receipt.
- If the command returns `job_id`, do not infer success; poll `forge job get <job_id>` and then inspect `receipt_ref`.
```

- [ ] **Step 4: Run formatting-safe verification and inspect text diffs**

Run:

```bash
git diff -- docs/management/forge-command-contract.md docs/management/forge-operator-guide.md .agents/skills/using-forge/SKILL.md .agents/skills/using-forge/references/forge-command-recipes.md
git diff --check
```

Expected:

```text
No diff --check errors
```

- [ ] **Step 5: Commit the operator-facing contract sync**

```bash
git add docs/management/forge-command-contract.md docs/management/forge-operator-guide.md .agents/skills/using-forge/SKILL.md .agents/skills/using-forge/references/forge-command-recipes.md
git commit -m "docs: document job-first remote mutation flow"
```

### Task 4: Final End-To-End Verification

**Files:**
- Verify only: `automation/pipeline/cli.py`
- Verify only: `tests/test_cli.py`
- Verify only: `cmd/forge/main.go`
- Verify only: `cmd/forge/main_test.go`
- Verify only: `docs/management/forge-command-contract.md`
- Verify only: `docs/management/forge-operator-guide.md`
- Verify only: `.agents/skills/using-forge/SKILL.md`
- Verify only: `.agents/skills/using-forge/references/forge-command-recipes.md`

- [ ] **Step 1: Run the full Python test suite**

Run:

```bash
uv run --extra server --no-env-file python -m unittest discover -s tests
```

Expected:

```text
OK
```

- [ ] **Step 2: Run the full Go CLI suite**

Run:

```bash
go test ./cmd/forge -v
```

Expected:

```text
PASS
```

- [ ] **Step 3: Run diff hygiene checks**

Run:

```bash
git diff --check
git status --short
```

Expected:

```text
Only intended tracked file edits remain, plus the pre-existing untracked checklist file
```

- [ ] **Step 4: Commit the verification checkpoint**

```bash
git add automation/pipeline/cli.py tests/test_cli.py cmd/forge/main.go cmd/forge/main_test.go docs/management/forge-command-contract.md docs/management/forge-operator-guide.md .agents/skills/using-forge/SKILL.md .agents/skills/using-forge/references/forge-command-recipes.md docs/archive/2026-Q2/2026-04-09-forge-job-first-remote-mutations-design.md docs/archive/2026-Q2/2026-04-09-forge-job-first-remote-mutations-plan.md
git commit -m "feat(operator): default remote mutations to detached jobs"
```
