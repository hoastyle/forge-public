# Forge Dual-Repo Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前私有混合仓库迁移为私有 `forge-data` 仓库，同时建立公开代码仓库 `hoastyle/forge`，并让 howie_server 只消费已发布、版本化的 `ghcr.io/hoastyle/forge:v0.2.0` 镜像。

**Architecture:** 使用一个全新的 sibling 工作目录 `../forge-public` 承载公开代码仓库，公开仓只保留 CLI、service、runtime、测试、release、GHCR 和公共文档。当前仓库收缩为私有数据仓库，只保留 `raw/knowledge/insights`、实例级 `.env`、部署脚本、镜像版本 pin 和私有运维文档；两仓之间唯一稳定接口固定为 `FORGE_IMAGE=ghcr.io/hoastyle/forge:v0.2.0`。

**Tech Stack:** Python 3.13, uv, Go CLI, FastAPI, bash, Docker/Compose, GitHub Actions, GHCR, unittest

---

## Repository Map

### Public Code Repo: `../forge-public`

- `../forge-public/cmd/forge/main.go`
  独立公共 CLI，公共用户入口固定为 `forge ...`
- `../forge-public/automation/`
  pipeline、service、doctor、remote client 等应用代码
- `../forge-public/tests/`
  公开仓 CI、打包、release、自托管边界测试
- `../forge-public/Dockerfile`
  自托管 runtime 镜像入口
- `../forge-public/compose.yaml`
  通用本地 self-hosted 入口
- `../forge-public/scripts/release/`
  release asset 构建、安装脚本、Homebrew formula 渲染
- `../forge-public/.github/workflows/ci.yml`
  公开仓测试流
- `../forge-public/.github/workflows/release.yml`
  tag 发布、GitHub Release、GHCR 推送
- `../forge-public/README.md`
  公共安装、连接 service、自托管说明
- `../forge-public/docs/management/forge-release-distribution.md`
  公共 release / install / GHCR 文档
- `../forge-public/docs/management/forge-operator-guide.md`
  面向公共 operator / AI 工具的 service 使用文档
- `../forge-public/docs/management/self-hosting.md`
  通用 self-hosting 文档，不包含 howie_server 专有细节
- `../forge-public/.agents/skills/using-forge/SKILL.md`
  面向其他 AI 工具的公开 operator contract

### Private Data Repo: current repository

- `raw/`
  原始输入层，长期保留，状态判断看 receipt 与 review 队列，不靠删除文件
- `knowledge/`
  显式提升后的知识层
- `insights/`
  显式综合后的洞察层
- `.env`
  私有内容运行时配置，不入 git
- `deploy/howie_server/runtime.env`
  版本化 runtime pin，固定记录 `FORGE_IMAGE` 与 `FORGE_PUBLIC_PORT`
- `compose.deploy.yaml`
  howie_server 部署 compose，只拉已发布镜像，不再 build
- `scripts/deploy/deploy_howie_server.sh`
  howie_server 标准部署入口，只同步数据和部署配置
- `docs/management/forge-howie-server-deployment.md`
  howie_server 私有部署文档
- `docs/management/forge-operator-guide.md`
  私有数据仓 operator 文档，聚焦 `raw -> knowledge -> insights`
- `docs/management/forge-llm-pipeline-v1.md`
  私有流水线实现文档
- `README.md`
  私有数据仓入口，强调这是 `forge-data` 而不是公共安装仓

## Preconditions

- 当前仓库保持私有，不做历史清洗后直接公开。
- 本地已配置 `gh`, `git`, `uv`, `go`, `docker`。
- 公开仓本地工作目录固定为 `../forge-public`。
- 公开 runtime 首个双仓版本固定为 `v0.2.0`。
- howie_server 最终消费镜像固定为 `ghcr.io/hoastyle/forge:v0.2.0`。

### Task 1: Bootstrap The Public Code Repo Without Leaking Data

**Files:**
- Create: `../forge-public/.gitignore`
- Create: `../forge-public/tests/test_repo_boundaries.py`
- Create: `../forge-public/README.md`
- Copy: `../forge-public/cmd/forge/main.go`
- Copy: `../forge-public/automation/`
- Copy: `../forge-public/tests/`
- Copy: `../forge-public/scripts/release/`
- Copy: `../forge-public/packaging/homebrew/forge.rb.tmpl`
- Copy: `../forge-public/Dockerfile`
- Copy: `../forge-public/compose.yaml`
- Copy: `../forge-public/pyproject.toml`
- Copy: `../forge-public/uv.lock`
- Copy: `../forge-public/.env.example`

- [ ] **Step 1: Create the sibling public repo workspace**

```bash
rm -rf ../forge-public
mkdir -p ../forge-public
rsync -a \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '.pytest_cache/' \
  --exclude '__pycache__/' \
  --exclude '.env' \
  --exclude 'raw/' \
  --exclude 'knowledge/' \
  --exclude 'insights/' \
  --exclude 'state/' \
  --exclude 'reports/' \
  --exclude 'data/' \
  ./ ../forge-public/
cd ../forge-public
git init
git branch -M main
git remote add origin git@github.com:hoastyle/forge.git
```

Expected: `../forge-public` 存在，但其中不包含 `raw/knowledge/insights/reports/state/data`。

- [ ] **Step 2: Add a boundary test that fails if private layers leak into the public repo**

```python
import unittest
from pathlib import Path


class PublicRepoBoundaryTests(unittest.TestCase):
    def test_private_layers_are_absent(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("raw", "knowledge", "insights", "reports", "state", "data"):
            self.assertFalse((root / name).exists(), f"{name} must not exist in the public repo")

    def test_public_runtime_artifacts_are_present(self):
        root = Path(__file__).resolve().parents[1]
        required = [
            root / "cmd" / "forge" / "main.go",
            root / "automation" / "pipeline" / "service_api.py",
            root / "Dockerfile",
            root / "compose.yaml",
            root / "scripts" / "release" / "install-public-cli.sh",
            root / "packaging" / "homebrew" / "forge.rb.tmpl",
        ]
        for path in required:
            self.assertTrue(path.exists(), f"{path} should exist in the public repo")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the boundary test**

Run:

```bash
cd ../forge-public
uv run --no-env-file python -m unittest tests.test_repo_boundaries -v
```

Expected: PASS. 如果失败，先修正提取范围，不要继续后续任务。

- [ ] **Step 4: Replace the public repo `.gitignore` and README seed**

```gitignore
.venv/
__pycache__/
.pytest_cache/
dist/
build/
*.pyc
coverage.xml
.DS_Store
```

````markdown
# Forge

Forge is a public CLI + service runtime for note ingestion, raw review, knowledge promotion, and
insight synthesis.

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/hoastyle/forge/main/scripts/release/install-public-cli.sh | bash
forge version
forge login --server https://forge.example.com --token "$FORGE_SERVER_TOKEN"
forge doctor
```

## Repository Scope

- This repository is public runtime and distribution code.
- It does not contain production `raw/`, `knowledge/`, or `insights`.
- Private data lives in a separate `forge-data` repository that consumes published images.
````

- [ ] **Step 5: Verify the extracted public repo still builds**

Run:

```bash
cd ../forge-public
go build ./cmd/forge
uv run --no-env-file python -m unittest tests.test_repo_boundaries tests.test_packaging -v
```

Expected: PASS, 且 `go build` 退出码为 `0`。

- [ ] **Step 6: Commit the public repo bootstrap**

```bash
cd ../forge-public
git add .
git commit -m "feat(automation): bootstrap public forge repository"
```

### Task 2: Add Public CI, GitHub Release, And GHCR Publishing

**Files:**
- Create: `../forge-public/.github/workflows/ci.yml`
- Create: `../forge-public/.github/workflows/release.yml`
- Modify: `../forge-public/tests/test_packaging.py`
- Modify: `../forge-public/docs/management/forge-release-distribution.md`
- Modify: `../forge-public/README.md`

- [ ] **Step 1: Add failing tests for release workflows and GHCR contract**

Append to `../forge-public/tests/test_packaging.py`:

```python
    def test_public_repo_has_release_workflows(self):
        repo_root = REPO_ROOT
        required_paths = [
            repo_root / ".github" / "workflows" / "ci.yml",
            repo_root / ".github" / "workflows" / "release.yml",
        ]
        for path in required_paths:
            self.assertTrue(path.exists(), "{0} should exist".format(path))

    def test_release_doc_mentions_ghcr_image(self):
        doc_path = REPO_ROOT / "docs" / "management" / "forge-release-distribution.md"
        text = doc_path.read_text(encoding="utf-8")
        self.assertIn("ghcr.io/hoastyle/forge", text)
        self.assertIn("GitHub Release", text)
```

- [ ] **Step 2: Run packaging tests to verify the new assertions fail before implementation**

Run:

```bash
cd ../forge-public
uv run --no-env-file python -m unittest tests.test_packaging.PackagingTests.test_public_repo_has_release_workflows -v
```

Expected: FAIL with `.github/workflows/ci.yml should exist`。

- [ ] **Step 3: Add the public CI workflow**

Create `../forge-public/.github/workflows/ci.yml`:

```yaml
name: ci

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: "1.24.3"
      - uses: astral-sh/setup-uv@v6
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - name: Sync dependencies
        run: uv sync --extra server --extra llm
      - name: Run Go CLI tests
        run: go test ./cmd/forge
      - name: Run Python tests
        run: uv run --no-env-file python -m unittest discover -s tests
      - name: Validate provenance
        run: ./automation/scripts/validate-provenance.sh
      - name: Diff check
        run: git diff --check
```

- [ ] **Step 4: Add the tag-driven release workflow**

Create `../forge-public/.github/workflows/release.yml`:

```yaml
name: release

on:
  push:
    tags:
      - "v*"

permissions:
  contents: write
  packages: write

jobs:
  build-cli:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        target:
          - linux/amd64
          - linux/arm64
          - darwin/amd64
          - darwin/arm64
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: "1.24.3"
      - name: Build archives
        env:
          FORGE_BUILD_TARGETS: ${{ matrix.target }}
        run: scripts/release/build-public-cli.sh "${GITHUB_REF_NAME}" dist/public
      - uses: actions/upload-artifact@v4
        with:
          name: cli-${{ matrix.target }}
          path: dist/public/*

  publish-image:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: |
            ghcr.io/hoastyle/forge:${{ github.ref_name }}
            ghcr.io/hoastyle/forge:sha-${{ github.sha }}

  publish-release:
    needs: [build-cli, publish-image]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
        with:
          path: dist/release-artifacts
      - uses: softprops/action-gh-release@v2
        with:
          files: dist/release-artifacts/**/*
          generate_release_notes: true
```

- [ ] **Step 5: Update the public release document and README to match the new release model**

Replace the core release section in `../forge-public/docs/management/forge-release-distribution.md` with:

```markdown
## Release Contract

- Public repository: `github.com/hoastyle/forge`
- Runtime registry: `ghcr.io/hoastyle/forge`
- Release source of truth: Git tags and GitHub Releases in `hoastyle/forge`
- Public users install the standalone CLI and connect to a Forge service; they do not clone the data repo

## Maintainer Release Flow

1. Push a semver tag such as `v0.2.0`.
2. Let GitHub Actions build CLI archives for the release matrix.
3. Let GitHub Actions push `ghcr.io/hoastyle/forge:v0.2.0`.
4. Verify the Release page contains archives and checksums.
5. Update the public `using-forge` skill in the same change set if the operator contract moved.
```

Replace the public README release paragraph with:

```markdown
Forge is distributed from GitHub Releases and GHCR:

- CLI downloads: `https://github.com/hoastyle/forge/releases`
- Runtime image: `ghcr.io/hoastyle/forge`
- Canonical user entrypoint: `forge ...`
```

- [ ] **Step 6: Run the public repo verification suite**

Run:

```bash
cd ../forge-public
go test ./...
uv run --no-env-file python -m unittest discover -s tests
bash scripts/release/build-public-cli.sh v0.2.0 dist/public
docker build -t forge-public:test .
```

Expected: PASS，并生成 `dist/public/checksums.txt`。

- [ ] **Step 7: Commit the release/GHCR work**

```bash
cd ../forge-public
git add .
git commit -m "feat(config): add public release and ghcr workflows"
```

### Task 3: Introduce The Private Runtime Image Contract

**Files:**
- Create: `deploy/howie_server/runtime.env`
- Modify: `compose.deploy.yaml`
- Modify: `tests/test_packaging.py`
- Modify: `docs/management/forge-howie-server-deployment.md`

- [ ] **Step 1: Add failing tests for image pinning**

Append to `tests/test_packaging.py`:

```python
    def test_runtime_image_pin_file_exists(self):
        repo_root = REPO_ROOT
        runtime_pin = repo_root / "deploy" / "howie_server" / "runtime.env"
        self.assertTrue(runtime_pin.exists(), f"{runtime_pin} should exist")

    def test_compose_deploy_consumes_published_image(self):
        text = (REPO_ROOT / "compose.deploy.yaml").read_text(encoding="utf-8")
        self.assertIn("image: ${FORGE_IMAGE}", text)
        self.assertIn("deploy/howie_server/runtime.env", text)
        self.assertNotIn("build:", text)
```

- [ ] **Step 2: Run the new packaging assertions**

Run:

```bash
uv run --no-env-file python -m unittest tests.test_packaging.PackagingTests.test_runtime_image_pin_file_exists -v
```

Expected: FAIL because `deploy/howie_server/runtime.env` does not exist yet.

- [ ] **Step 3: Create the versioned runtime pin file**

Create `deploy/howie_server/runtime.env`:

```dotenv
FORGE_IMAGE=ghcr.io/hoastyle/forge:v0.2.0
FORGE_PUBLIC_PORT=18080
```

- [ ] **Step 4: Rewrite `compose.deploy.yaml` to consume the pinned image**

Replace `compose.deploy.yaml` with:

```yaml
services:
  forge:
    image: ${FORGE_IMAGE}
    pull_policy: always
    command:
      - python
      - -m
      - automation.pipeline
      - serve
      - --app-root
      - /app
      - --repo-root
      - /var/lib/forge/repo
      - --state-root
      - /var/lib/forge/state
      - --host
      - 0.0.0.0
      - --port
      - "8000"
    environment:
      FORGE_SERVER_TOKEN: ${FORGE_SERVER_TOKEN:-}
    env_file:
      - .env
      - deploy/howie_server/runtime.env
    ports:
      - "${FORGE_PUBLIC_PORT:-18080}:8000"
    volumes:
      - ./data/repo:/var/lib/forge/repo
      - ./data/state:/var/lib/forge/state
```

- [ ] **Step 5: Update the howie_server deployment doc to point to the pin file**

Insert this block into `docs/management/forge-howie-server-deployment.md`:

````markdown
## Runtime Pin

howie_server 不再构建源码。版本由仓库内 `deploy/howie_server/runtime.env` 显式固定：

```dotenv
FORGE_IMAGE=ghcr.io/hoastyle/forge:v0.2.0
FORGE_PUBLIC_PORT=18080
```

升级和回滚都通过修改 `FORGE_IMAGE` 并重新部署完成。
````

- [ ] **Step 6: Run the private repo packaging checks**

Run:

```bash
uv run --no-env-file python -m unittest tests.test_packaging.PackagingTests.test_runtime_image_pin_file_exists -v
uv run --no-env-file python -m unittest tests.test_packaging.PackagingTests.test_compose_deploy_consumes_published_image -v
```

Expected: PASS。

- [ ] **Step 7: Commit the image contract**

```bash
git add deploy/howie_server/runtime.env compose.deploy.yaml tests/test_packaging.py docs/management/forge-howie-server-deployment.md
git commit -m "refactor(config): pin forge runtime image in data repo"
```

### Task 4: Rewrite howie_server Deployment To Consume Published Images Only

**Files:**
- Modify: `scripts/deploy/deploy_howie_server.sh`
- Modify: `tests/test_packaging.py`
- Modify: `docs/management/forge-howie-server-deployment.md`

- [ ] **Step 1: Add failing tests for image-only deployment**

Append to `tests/test_packaging.py`:

```python
    def test_howie_server_deploy_script_pulls_published_image(self):
        text = (REPO_ROOT / "scripts" / "deploy" / "deploy_howie_server.sh").read_text(encoding="utf-8")
        self.assertIn("docker compose -f compose.deploy.yaml pull", text)
        self.assertIn("deploy/howie_server/runtime.env", text)

    def test_howie_server_deploy_script_no_longer_syncs_application_tree(self):
        text = (REPO_ROOT / "scripts" / "deploy" / "deploy_howie_server.sh").read_text(encoding="utf-8")
        self.assertNotIn('log "syncing application tree"', text)
        self.assertNotIn('rsync -az --delete \\\n  --exclude \'.git/\'', text)
```

- [ ] **Step 2: Run the deploy-script assertion to capture the current failure**

Run:

```bash
uv run --no-env-file python -m unittest tests.test_packaging.PackagingTests.test_howie_server_deploy_script_pulls_published_image -v
```

Expected: FAIL because the current script still builds or syncs app code.

- [ ] **Step 3: Replace the deploy script usage block and sync logic**

Use this target shape in `scripts/deploy/deploy_howie_server.sh`:

```bash
Usage: scripts/deploy/deploy_howie_server.sh [options]

Options:
  --host HOST                SSH host alias or target. Default: howie_server
  --remote-dir REMOTE_DIR    Remote deploy root. Default: /home/howie/apps/forge
  --token TOKEN              Forge service bearer token. Falls back to env/.env/remote .env.
  --no-verify                Skip remote healthz/doctor verification.
  --help                     Show this message.
```

Replace the sync block with:

```bash
log "preparing remote directories on ${HOST}:${REMOTE_DIR}"
ssh "${HOST}" "mkdir -p '${REMOTE_DIR}/deploy/howie_server' '${REMOTE_DIR}/data/repo/raw' '${REMOTE_DIR}/data/repo/knowledge' '${REMOTE_DIR}/data/repo/insights' '${REMOTE_DIR}/data/state'"

log "syncing deployment contract"
rsync -az "${REPO_ROOT}/compose.deploy.yaml" "${HOST}:${REMOTE_DIR}/compose.deploy.yaml"
rsync -az "${REPO_ROOT}/deploy/howie_server/runtime.env" "${HOST}:${REMOTE_DIR}/deploy/howie_server/runtime.env"

log "syncing repository content roots"
rsync -az --delete "${REPO_ROOT}/raw/" "${HOST}:${REMOTE_DIR}/data/repo/raw/"
rsync -az --delete "${REPO_ROOT}/knowledge/" "${HOST}:${REMOTE_DIR}/data/repo/knowledge/"
rsync -az --delete "${REPO_ROOT}/insights/" "${HOST}:${REMOTE_DIR}/data/repo/insights/"
rsync -az "${LOCAL_CONTENT_ENV_TMP}" "${HOST}:${REMOTE_DIR}/data/repo/.env"
```

- [ ] **Step 4: Replace remote build with image pull + up**

Use this remote execution block:

```bash
cd "${remote_dir}"
docker compose -f compose.deploy.yaml pull
docker compose -f compose.deploy.yaml up -d
docker compose -f compose.deploy.yaml ps
```

Keep existing readiness probing:

```bash
curl -fsS "http://127.0.0.1:${public_port}/healthz"
curl -fsS -H "Authorization: Bearer ${token}" "http://127.0.0.1:${public_port}/v1/doctor"
```

- [ ] **Step 5: Rewrite the deployment doc to remove source-sync/build language**

Replace the standard-entry section in `docs/management/forge-howie-server-deployment.md` with:

````markdown
howie_server 的标准部署入口是：

```bash
scripts/deploy/deploy_howie_server.sh --host howie_server
```

脚本只做四件事：

1. 同步 `compose.deploy.yaml` 与 `deploy/howie_server/runtime.env`
2. 同步 `raw/`、`knowledge/`、`insights/` 和 repo-local `.env`
3. 在远端执行 `docker compose -f compose.deploy.yaml pull`
4. 执行 `docker compose -f compose.deploy.yaml up -d` 并跑 `healthz` / `doctor`

目标机不再接收源码副本，也不再执行本地构建。
````

- [ ] **Step 6: Validate the rewritten deployment path**

Run:

```bash
bash -n scripts/deploy/deploy_howie_server.sh
uv run --no-env-file python -m unittest tests.test_packaging.PackagingTests.test_howie_server_deploy_script_pulls_published_image -v
uv run --no-env-file python -m unittest tests.test_packaging.PackagingTests.test_howie_server_deploy_script_no_longer_syncs_application_tree -v
```

Expected: PASS。

- [ ] **Step 7: Commit the deploy rewrite**

```bash
git add scripts/deploy/deploy_howie_server.sh tests/test_packaging.py docs/management/forge-howie-server-deployment.md
git commit -m "refactor(config): switch howie_server deploy to image runtime"
```

### Task 5: Split Public And Private Documentation, Operator Contract, And Skill Surface

**Files:**
- Modify: `README.md`
- Modify: `docs/management/forge-operator-guide.md`
- Modify: `docs/management/forge-llm-pipeline-v1.md`
- Modify: `docs/management/repository-conventions.md`
- Delete: `docs/management/forge-release-distribution.md`
- Create: `../forge-public/docs/management/forge-release-distribution.md`
- Create: `../forge-public/docs/management/forge-operator-guide.md`
- Create: `../forge-public/docs/management/self-hosting.md`
- Create: `../forge-public/.agents/skills/using-forge/SKILL.md`
- Modify: `../forge-public/README.md`
- Modify: `../forge-public/tests/test_packaging.py`

- [ ] **Step 1: Add failing doc-boundary tests in both repos**

Append to private `tests/test_packaging.py`:

```python
    def test_private_readme_does_not_advertise_public_install(self):
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("install-public-cli.sh", text)
        self.assertIn("forge-data", text)
```

Create `../forge-public/tests/test_docs_contract.py`:

```python
import unittest
from pathlib import Path


class PublicDocsContractTests(unittest.TestCase):
    def test_public_readme_advertises_cli_install(self):
        text = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
        self.assertIn("install-public-cli.sh", text)
        self.assertIn("forge login", text)

    def test_skill_does_not_assume_private_repo_access(self):
        text = (Path(__file__).resolve().parents[1] / ".agents" / "skills" / "using-forge" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("configured Forge service", text)
        self.assertNotIn("working inside the Forge repository", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rewrite the private README as a data-repo entrypoint**

Replace the current public-install section in `README.md` with:

```markdown
## Repository Role

This repository is the private Forge data repo (`forge-data`).

It contains:

- `raw/`
- `knowledge/`
- `insights/`
- repo-local `.env`
- deploy materials and image pins

It does not serve as the public installation source for Forge CLI or runtime code.

Public code and releases live in `github.com/hoastyle/forge`.
```

- [ ] **Step 3: Rewrite private operator and pipeline docs around the data boundary**

Insert this contract into `docs/management/forge-operator-guide.md`:

```markdown
## Boundary

- Public CLI / service usage lives in `hoastyle/forge`
- This repo is for data operations, queue review, promotion, insight synthesis, deployment pinning, backup, and rollback
- Standard repo-local operator entrypoint remains `uv run forge --repo-root . ...`
- Public users should not need this repository path
```

Insert this contract into `docs/management/forge-llm-pipeline-v1.md`:

```markdown
## Runtime Boundary

Pipeline code is published from `hoastyle/forge`.
This private repo stores content, receipts, and deployment configuration only.
When self-hosted service instances run, their image version must come from `deploy/howie_server/runtime.env`.
```

Replace the public release section in `docs/management/repository-conventions.md` with:

```markdown
## Public/Private Repo Boundary

- Public install, release, GHCR, and `forge ...` distribution docs belong to `hoastyle/forge`
- Private data, deployment pin, backup, rollback, and `raw -> knowledge -> insights` docs belong to this repo
- If a release changes how operators or AI tools use Forge, update the public `using-forge` skill in `hoastyle/forge` in the same release
```

- [ ] **Step 4: Remove the private release-distribution document**

Run:

```bash
git rm docs/management/forge-release-distribution.md
```

Expected: file staged for deletion in the private repo.

- [ ] **Step 5: Create the public operator docs and skill**

Create `../forge-public/docs/management/forge-operator-guide.md`:

```markdown
# Forge Operator Guide

## Who This Is For

Use this guide when you have a configured Forge service and need to run:

- `forge doctor`
- `forge inject`
- `forge review-queue`
- `forge promote-ready`
- `forge synthesize-insights`
- `forge receipt get`
- `forge job get`

You do not need a checkout of the private data repo for these operations.
```

Create `../forge-public/docs/management/self-hosting.md`:

````markdown
# Forge Self-Hosting

Run a self-hosted Forge service with the published runtime image:

```bash
docker run --rm -p 8000:8000 \
  -e FORGE_SERVER_TOKEN=change-me \
  -v "$PWD/repo:/var/lib/forge/repo" \
  -v "$PWD/state:/var/lib/forge/state" \
  ghcr.io/hoastyle/forge:v0.2.0
```
````

Create `../forge-public/.agents/skills/using-forge/SKILL.md`:

```markdown
---
name: using-forge
description: Use when a tool or operator needs to use the public Forge CLI or a configured Forge service to ingest notes, review queue state, promote raw material, synthesize insights, inspect receipts, or poll detached jobs.
---

# Using Forge

Use Forge through either:

- the public CLI: `forge ...`
- a configured Forge service endpoint

Do not assume access to the private data repository. Public users and AI tools should be able to operate with only:

- a Forge binary
- a service URL
- a bearer token
```

- [ ] **Step 6: Run doc-boundary verification in both repos**

Run:

```bash
uv run --no-env-file python -m unittest tests.test_packaging.PackagingTests.test_private_readme_does_not_advertise_public_install -v
cd ../forge-public
uv run --no-env-file python -m unittest tests.test_docs_contract -v
```

Expected: PASS。

- [ ] **Step 7: Commit the doc split in both repos**

```bash
git add README.md docs/management/forge-operator-guide.md docs/management/forge-llm-pipeline-v1.md docs/management/repository-conventions.md
git commit -m "docs(config): split private data docs from public distribution"

cd ../forge-public
git add README.md docs/management .agents/skills/using-forge/SKILL.md tests/test_docs_contract.py
git commit -m "docs(config): add public operator and release documentation"
```

### Task 6: Release, Pin, Deploy, And Verify The Cutover

**Files:**
- Modify: `../forge-public/README.md`
- Modify: `deploy/howie_server/runtime.env`
- Modify: `docs/management/forge-howie-server-deployment.md`

- [ ] **Step 1: Run the full public release verification**

Run:

```bash
cd ../forge-public
go test ./...
uv run --no-env-file python -m unittest discover -s tests
bash scripts/release/build-public-cli.sh v0.2.0 dist/public
docker build -t ghcr.io/hoastyle/forge:v0.2.0 .
```

Expected: PASS。

- [ ] **Step 2: Tag and push the public release**

Run:

```bash
cd ../forge-public
git tag v0.2.0
git push origin main
git push origin v0.2.0
```

Expected: GitHub Actions starts `release.yml` and publishes `ghcr.io/hoastyle/forge:v0.2.0`。

- [ ] **Step 3: Verify the public release artifacts**

Run:

```bash
gh release view v0.2.0 --repo hoastyle/forge
docker manifest inspect ghcr.io/hoastyle/forge:v0.2.0 >/dev/null
```

Expected: `gh release view` 输出 release 存在；`docker manifest inspect` 退出码为 `0`。

- [ ] **Step 4: Pin the private repo to the released image**

Ensure `deploy/howie_server/runtime.env` is exactly:

```dotenv
FORGE_IMAGE=ghcr.io/hoastyle/forge:v0.2.0
FORGE_PUBLIC_PORT=18080
```

- [ ] **Step 5: Deploy to howie_server**

Run:

```bash
scripts/deploy/deploy_howie_server.sh --host howie_server
```

Expected: 远端执行 `docker compose pull` 与 `docker compose up -d`，最后 healthz/doctor 通过。

- [ ] **Step 6: Verify both public CLI and remote service after cutover**

Run:

```bash
forge login --server http://192.168.108.177:18080 --token "$FORGE_SERVER_TOKEN"
forge doctor
forge review-queue --initiator manual
```

Expected: 三条命令都返回 `status: success` 或等价成功 JSON。

- [ ] **Step 7: Run private repo final verification and commit the pin**

Run:

```bash
uv run --no-env-file python -m unittest discover -s tests
./automation/scripts/validate-provenance.sh
git diff --check
git add deploy/howie_server/runtime.env docs/management/forge-howie-server-deployment.md
git commit -m "chore(config): cut over data repo to public forge image"
```

Expected: 所有校验通过，private repo 保持干净。

## Self-Review

### Spec Coverage

- 仓库拓扑拆分：Task 1, Task 5
- 公共 release + GHCR：Task 2, Task 6
- 私有仓只消费镜像 tag：Task 3, Task 6
- howie_server 不再构建源码：Task 4, Task 6
- 文档边界重写：Task 5
- 非目标约束（不 public 私有仓、不保留 `forge-np`、不使用 `latest`、不依赖源码结构）：Task 1, Task 3, Task 4, Task 5

### Placeholder Scan

- 未使用 `TODO`、`TBD`、`later`、`appropriate` 之类占位语。
- 所有新增关键路径、命令、环境变量、镜像 tag 都已固定到具体值。
- 所有关键文档和脚本改动都给出了目标内容，而不是抽象描述。

### Type Consistency

- 公开镜像名统一为 `ghcr.io/hoastyle/forge:v0.2.0`
- 私有 pin 文件统一为 `deploy/howie_server/runtime.env`
- 公开仓本地工作目录统一为 `../forge-public`
- 公共入口统一为 `forge ...`
- 私有维护入口统一为 `uv run forge --repo-root . ...`
