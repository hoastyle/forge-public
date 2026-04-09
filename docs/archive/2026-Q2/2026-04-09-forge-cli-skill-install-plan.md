# Forge CLI + `using-forge` Skill Install Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the public Forge installer ship both the CLI and the `using-forge` skill, with a single Forge-managed skill home and automatic installation into all discovered user-level skill directories.

**Architecture:** Treat the public `using-forge` skill as a release artifact, not an implicit repo file. Release flow builds a versioned skill tarball, installer expands it into a neutral Forge skill home, then links or copies it into discovered agent skill directories. Public docs and tests move in lockstep with that contract.

**Tech Stack:** Bash installer scripts, GitHub Actions release workflow, Python `unittest`, Markdown docs, repo-shipped skill assets.

---

> **Path override:** This public repo forbids `docs/superpowers/` in packaging tests, so this plan is intentionally stored under `docs/archive/2026-Q2/`.

### Task 1: Publish The Public `using-forge` Skill Bundle Source

**Files:**
- Create: `.agents/skills/using-forge/references/forge-command-recipes.md`
- Modify: `.agents/skills/using-forge/SKILL.md`
- Modify: `tests/test_docs_contract.py`
- Test: `tests/test_docs_contract.py`

- [ ] **Step 1: Write the failing docs contract tests**

```python
class PublicDocsContractTests(unittest.TestCase):
    def test_public_skill_bundles_command_reference(self):
        root = Path(__file__).resolve().parents[1]
        reference = root / ".agents" / "skills" / "using-forge" / "references" / "forge-command-recipes.md"
        self.assertTrue(reference.exists())
        self.assertIn("forge receipt get", reference.read_text(encoding="utf-8"))

    def test_skill_mentions_receipts_and_detached_jobs(self):
        text = (
            Path(__file__).resolve().parents[1]
            / ".agents"
            / "skills"
            / "using-forge"
            / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("forge receipt get <selector>", text)
        self.assertIn("forge job get <job_id>", text)
        self.assertIn("trigger semantics remain explicit", text)
```

- [ ] **Step 2: Run the docs contract tests to verify red**

Run:

```bash
uv run --no-env-file python -m unittest tests.test_docs_contract -v
```

Expected:

```text
FAIL: test_public_skill_bundles_command_reference
```

- [ ] **Step 3: Replace the public skill body with the current operator contract and add the reference file**

```text
.agents/skills/using-forge/SKILL.md
  - sync the public skill to the current public/operator contract
  - keep the “no private repo access” boundary
  - include Core Rules, Default Workflow, Task Routing, Receipts And Jobs, References

.agents/skills/using-forge/references/forge-command-recipes.md
  - add public command recipes
  - add maintainer recipes
  - add sync rule that keeps SKILL.md aligned with CLI semantics
```

- [ ] **Step 4: Re-run the docs contract tests to verify green**

Run:

```bash
uv run --no-env-file python -m unittest tests.test_docs_contract -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit the skill-source sync**

```bash
git add .agents/skills/using-forge tests/test_docs_contract.py
git commit -m "docs(skill): sync public using-forge bundle source"
```

### Task 2: Build And Release A Versioned Skill Tarball

**Files:**
- Create: `scripts/release/build-public-skill.sh`
- Modify: `.github/workflows/release.yml`
- Modify: `tests/test_packaging.py`
- Test: `tests/test_packaging.py`

- [ ] **Step 1: Write the failing packaging tests for the skill artifact**

```python
class PackagingTests(unittest.TestCase):
    def test_release_distribution_artifacts_exist(self):
        required_paths = [
            REPO_ROOT / "scripts" / "release" / "build-public-skill.sh",
        ]
        for path in required_paths:
            self.assertTrue(path.exists(), f"{path} should exist")

    def test_public_repo_has_release_workflows(self):
        release_workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("pattern: skill-*", release_workflow)

    def test_release_build_script_builds_skill_bundle(self):
        with tempfile.TemporaryDirectory() as tempdir:
            result = subprocess.run(
                ["bash", "scripts/release/build-public-skill.sh", "v0.1.0", tempdir],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            bundles = list(Path(tempdir).glob("forge_skill_using-forge_0.1.0.tar.gz"))
            self.assertEqual(len(bundles), 1)
```

- [ ] **Step 2: Run the targeted packaging tests to verify red**

Run:

```bash
uv run --no-env-file python -m unittest \
  tests.test_packaging.PackagingTests.test_release_distribution_artifacts_exist \
  tests.test_packaging.PackagingTests.test_public_repo_has_release_workflows \
  tests.test_packaging.PackagingTests.test_release_build_script_builds_skill_bundle -v
```

Expected:

```text
FAIL because build-public-skill.sh and skill-* workflow artifact handling do not exist yet
```

- [ ] **Step 3: Add the skill bundle builder and release artifact wiring**

```bash
# scripts/release/build-public-skill.sh
# - accept <version> [output-dir]
# - stage using-forge/ as a directory root inside the tarball
# - emit forge_skill_using-forge_<version>.tar.gz
```

```yaml
# .github/workflows/release.yml
# - add a build-skill job or extend build-cli to upload a skill artifact
# - ensure publish-release downloads both cli-* and skill-* artifacts
# - copy forge_skill_using-forge_*.tar.gz into dist/release-bundle/
```

- [ ] **Step 4: Re-run the targeted packaging tests to verify green**

Run:

```bash
uv run --no-env-file python -m unittest \
  tests.test_packaging.PackagingTests.test_release_distribution_artifacts_exist \
  tests.test_packaging.PackagingTests.test_public_repo_has_release_workflows \
  tests.test_packaging.PackagingTests.test_release_build_script_builds_skill_bundle -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit the release-artifact work**

```bash
git add scripts/release/build-public-skill.sh .github/workflows/release.yml tests/test_packaging.py
git commit -m "feat(release): publish using-forge skill bundle"
```

### Task 3: Extend The Public Installer To Install CLI And Skill

**Files:**
- Modify: `scripts/release/install-public-cli.sh`
- Modify: `tests/test_packaging.py`
- Test: `tests/test_packaging.py`

- [ ] **Step 1: Write the failing installer tests**

```python
class PackagingTests(unittest.TestCase):
    def test_install_script_mentions_skill_options(self):
        text = (REPO_ROOT / "scripts" / "release" / "install-public-cli.sh").read_text(encoding="utf-8")
        self.assertIn("--no-skill", text)
        self.assertIn("--skill-only", text)
        self.assertIn("--skill-home", text)
        self.assertIn("--include-repo-skill-dir", text)

    def test_install_script_mentions_neutral_skill_home(self):
        text = (REPO_ROOT / "scripts" / "release" / "install-public-cli.sh").read_text(encoding="utf-8")
        self.assertIn(".local/share/forge/skills", text)

    def test_install_script_downloads_skill_bundle(self):
        text = (REPO_ROOT / "scripts" / "release" / "install-public-cli.sh").read_text(encoding="utf-8")
        self.assertIn("forge_skill_using-forge_", text)
        self.assertIn("using-forge", text)
```

- [ ] **Step 2: Run the targeted installer tests to verify red**

Run:

```bash
uv run --no-env-file python -m unittest \
  tests.test_packaging.PackagingTests.test_install_script_mentions_skill_options \
  tests.test_packaging.PackagingTests.test_install_script_mentions_neutral_skill_home \
  tests.test_packaging.PackagingTests.test_install_script_downloads_skill_bundle -v
```

Expected:

```text
FAIL because the installer only installs the CLI today
```

- [ ] **Step 3: Implement neutral skill-home installation and multi-directory link/copy logic**

```bash
# scripts/release/install-public-cli.sh
# - keep existing CLI install flow
# - add option parsing for --no-skill, --skill-only, --skill-home, --include-repo-skill-dir
# - default skill home to ${XDG_DATA_HOME:-$HOME/.local/share}/forge/skills
# - unpack the skill bundle to <skill-home>/using-forge
# - discover existing user-level skill dirs:
#     ${CODEX_HOME}/skills
#     ${HOME}/.codex/skills
#     ${HOME}/.claude/skills
#     ${HOME}/.continue/skills
#     ${HOME}/.factory/skills
# - deduplicate paths
# - for each target dir, prefer ln -s; if that fails, copy the directory tree
# - never touch repo-local .agents/skills unless --include-repo-skill-dir is provided
# - print a per-target summary: linked / copied / skipped
```

- [ ] **Step 4: Re-run the targeted installer tests to verify green**

Run:

```bash
uv run --no-env-file python -m unittest \
  tests.test_packaging.PackagingTests.test_install_script_mentions_skill_options \
  tests.test_packaging.PackagingTests.test_install_script_mentions_neutral_skill_home \
  tests.test_packaging.PackagingTests.test_install_script_downloads_skill_bundle -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Run the existing release-builder regression to ensure CLI packaging still works**

Run:

```bash
uv run --no-env-file python -m unittest \
  tests.test_packaging.PackagingTests.test_release_build_script_builds_default_host_target -v
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit the installer work**

```bash
git add scripts/release/install-public-cli.sh tests/test_packaging.py
git commit -m "feat(installer): install using-forge alongside CLI"
```

### Task 4: Align Public Docs With The New Install Contract

**Files:**
- Modify: `README.md`
- Modify: `docs/management/forge-operator-guide.md`
- Modify: `docs/management/forge-release-distribution.md`
- Modify: `tests/test_docs_contract.py`
- Test: `tests/test_docs_contract.py`

- [ ] **Step 1: Write the failing docs assertions for CLI + skill install**

```python
class PublicDocsContractTests(unittest.TestCase):
    def test_public_readme_advertises_cli_and_skill_install(self):
        text = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
        self.assertIn("using-forge", text)
        self.assertIn("forge doctor", text)

    def test_release_doc_mentions_skill_bundle(self):
        text = (
            Path(__file__).resolve().parents[1]
            / "docs"
            / "management"
            / "forge-release-distribution.md"
        ).read_text(encoding="utf-8")
        self.assertIn("skill bundle", text)
        self.assertIn("forge_skill_using-forge_", text)
```

- [ ] **Step 2: Run the docs contract tests to verify red**

Run:

```bash
uv run --no-env-file python -m unittest tests.test_docs_contract -v
```

Expected:

```text
FAIL because public docs do not yet advertise the skill-install contract
```

- [ ] **Step 3: Update the public docs**

```markdown
README.md
- quick start says the installer installs both the CLI and the using-forge skill
- distribution section mentions the skill bundle

docs/management/forge-operator-guide.md
- add install prerequisite section for CLI + skill
- keep operator flow focused on forge login / doctor / inject / receipts

docs/management/forge-release-distribution.md
- add the skill bundle to release artifacts
- state that public using-forge must be updated in the same change set when operator contract changes
```

- [ ] **Step 4: Re-run the docs contract tests to verify green**

Run:

```bash
uv run --no-env-file python -m unittest tests.test_docs_contract -v
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit the doc alignment**

```bash
git add README.md docs/management/forge-operator-guide.md docs/management/forge-release-distribution.md tests/test_docs_contract.py
git commit -m "docs(install): document CLI and using-forge installation"
```

### Task 5: Run The Full Verification Suite

**Files:**
- Modify: none
- Test: `tests/test_docs_contract.py`
- Test: `tests/test_packaging.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Run the full Python unit suite**

Run:

```bash
uv run --no-env-file python -m unittest discover -s tests
```

Expected:

```text
OK
```

- [ ] **Step 2: Run the Go CLI verification**

Run:

```bash
go test ./cmd/forge
```

Expected:

```text
? github.com/hoastyle/forge-public/cmd/forge [no test files]
```

- [ ] **Step 3: Run provenance validation**

Run:

```bash
./automation/scripts/validate-provenance.sh
```

Expected:

```text
Provenance validation passed
```

- [ ] **Step 4: Build fresh release artifacts**

Run:

```bash
scripts/release/build-public-cli.sh v0.2.1-dev dist/public-review
scripts/release/build-public-skill.sh v0.2.1-dev dist/public-review
```

Expected:

```text
Built Forge public CLI artifacts
Built Forge public skill bundle
```

- [ ] **Step 5: Commit the finished feature**

```bash
git status --short
git add .agents scripts tests README.md docs
git commit -m "feat(installer): ship using-forge with public CLI installs"
```
