import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SANITIZED_RUNTIME_ENV = {
    "OPENAI_API_KEY": "",
    "OPENAI_BASE_URL": "",
    "OPENAI_API_BASE": "",
    "ANTHROPIC_API_KEY": "",
    "ANTHROPIC_BASE_URL": "",
    "ANTHROPIC_API_BASE": "",
    "FORGE_KNOWLEDGE_CLIENT": "",
    "FORGE_INSIGHT_CLIENT": "",
    "ALL_PROXY": "",
    "all_proxy": "",
    "HTTP_PROXY": "",
    "HTTPS_PROXY": "",
    "http_proxy": "",
    "https_proxy": "",
    "UV_ENV_FILE": "",
    "UV_NO_ENV_FILE": "1",
    "LITELLM_LOCAL_MODEL_COST_MAP": "true",
}


class PackagingTests(unittest.TestCase):
    def test_pyproject_exposes_forge_console_entrypoint(self):
        pyproject_path = REPO_ROOT / "pyproject.toml"

        self.assertTrue(pyproject_path.exists(), "pyproject.toml should exist for uv-managed CLI entrypoints")

        text = pyproject_path.read_text(encoding="utf-8")
        self.assertIn("[project.scripts]", text)
        self.assertIn('forge = "automation.pipeline.cli:main"', text)

    def test_env_example_defaults_litellm_to_local_model_cost_map(self):
        env_example_path = REPO_ROOT / ".env.example"

        self.assertTrue(env_example_path.exists(), ".env.example should exist")
        text = env_example_path.read_text(encoding="utf-8")
        self.assertIn("LITELLM_LOCAL_MODEL_COST_MAP=true", text)

    def test_pyproject_defines_server_optional_dependencies(self):
        pyproject_path = REPO_ROOT / "pyproject.toml"

        text = pyproject_path.read_text(encoding="utf-8")
        self.assertIn('[project.optional-dependencies]', text)
        self.assertIn('server = ["fastapi', text)
        self.assertIn('uvicorn', text)

    def test_self_hosting_artifacts_exist(self):
        repo_root = REPO_ROOT

        self.assertTrue((repo_root / "Dockerfile").exists())
        self.assertTrue((repo_root / "compose.yaml").exists())

    def test_dockerfile_includes_litellm_for_self_hosted_service(self):
        dockerfile_path = REPO_ROOT / "Dockerfile"

        text = dockerfile_path.read_text(encoding="utf-8")
        self.assertIn("uv.lock", text)
        self.assertIn("uv sync --frozen --no-dev --extra server --extra llm", text)

    def test_release_distribution_artifacts_exist(self):
        repo_root = REPO_ROOT

        required_paths = [
            repo_root / "go.mod",
            repo_root / "cmd" / "forge" / "main.go",
            repo_root / "scripts" / "release" / "build-public-cli.sh",
            repo_root / "scripts" / "release" / "install-public-cli.sh",
            repo_root / "scripts" / "release" / "render-homebrew-formula.sh",
            repo_root / "packaging" / "homebrew" / "forge.rb.tmpl",
            repo_root / "docs" / "management" / "forge-release-distribution.md",
        ]

        for path in required_paths:
            self.assertTrue(path.exists(), "{0} should exist".format(path))

    def test_howie_server_deploy_artifacts_exist(self):
        repo_root = REPO_ROOT

        required_paths = [
            repo_root / "scripts" / "deploy" / "deploy_howie_server.sh",
            repo_root / "docs" / "management" / "forge-howie-server-deployment.md",
        ]

        for path in required_paths:
            self.assertTrue(path.exists(), "{0} should exist".format(path))

    def test_howie_server_deploy_script_is_bash_parseable(self):
        if shutil.which("bash") is None:
            self.skipTest("bash is required for deploy script validation")

        script_path = REPO_ROOT / "scripts" / "deploy" / "deploy_howie_server.sh"
        result = subprocess.run(
            ["bash", "-n", str(script_path)],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_howie_server_deploy_script_supports_local_image_transfer(self):
        script_path = REPO_ROOT / "scripts" / "deploy" / "deploy_howie_server.sh"

        text = script_path.read_text(encoding="utf-8")
        self.assertIn("--build-local", text)
        self.assertIn("docker save", text)
        self.assertIn("docker load", text)

    def test_howie_server_deploy_script_passes_proxy_to_local_build(self):
        script_path = REPO_ROOT / "scripts" / "deploy" / "deploy_howie_server.sh"

        text = script_path.read_text(encoding="utf-8")
        self.assertIn("docker_build_args+=(--build-arg", text)
        self.assertIn("HTTP_PROXY=${PROXY}", text)
        self.assertIn("HTTPS_PROXY=${PROXY}", text)
        self.assertIn("ALL_PROXY=${PROXY}", text)

    def test_howie_server_deploy_script_retries_remote_health_checks(self):
        script_path = REPO_ROOT / "scripts" / "deploy" / "deploy_howie_server.sh"

        text = script_path.read_text(encoding="utf-8")
        self.assertIn("for attempt in $(seq 1 30)", text)
        self.assertIn("sleep 2", text)
        self.assertIn("service failed readiness checks after", text)

    def test_howie_server_doc_mentions_standard_deploy_script(self):
        doc_path = REPO_ROOT / "docs" / "management" / "forge-howie-server-deployment.md"

        text = doc_path.read_text(encoding="utf-8")
        self.assertIn("scripts/deploy/deploy_howie_server.sh", text)
        self.assertIn("--host howie_server", text)

    def test_go_public_cli_builds(self):
        if shutil.which("go") is None:
            self.skipTest("go is required for public CLI build validation")

        repo_root = REPO_ROOT
        with tempfile.TemporaryDirectory() as tempdir:
            result = subprocess.run(
                ["go", "build", "-o", str(Path(tempdir) / "forge"), "./cmd/forge"],
                cwd=repo_root,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_release_build_script_builds_default_host_target(self):
        if shutil.which("go") is None or shutil.which("bash") is None:
            self.skipTest("go and bash are required for release build validation")

        with tempfile.TemporaryDirectory() as tempdir:
            result = subprocess.run(
                ["bash", "scripts/release/build-public-cli.sh", "v0.1.0", tempdir],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue((Path(tempdir) / "checksums.txt").exists())
            archives = list(Path(tempdir).glob("forge_0.1.0_*.tar.gz"))
            self.assertEqual(len(archives), 1)

    def test_homebrew_formula_renderer_preserves_archive_url_query(self):
        if shutil.which("bash") is None:
            self.skipTest("bash is required for renderer validation")

        result = subprocess.run(
            [
                "bash",
                "scripts/release/render-homebrew-formula.sh",
                "--version",
                "v0.1.0",
                "--archive-sha256",
                "deadbeef",
                "--archive-url",
                "https://example.com/forge.tgz?foo=1&bar=2",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn('url "https://example.com/forge.tgz?foo=1&bar=2"', result.stdout)

    def test_uv_run_forge_doctor_invokes_console_entrypoint(self):
        if shutil.which("uv") is None:
            self.skipTest("uv is required for console entrypoint validation")

        repo_root = REPO_ROOT
        with tempfile.TemporaryDirectory() as tempdir:
            env = os.environ.copy()
            env.update(SANITIZED_RUNTIME_ENV)
            result = subprocess.run(
                ["uv", "run", "--no-env-file", "--no-sync", "forge", "--repo-root", tempdir, "doctor"],
                cwd=repo_root,
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn("Failed to fetch remote model cost map", result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "doctor")
        self.assertEqual(payload["default_knowledge_client"], "heuristic")


if __name__ == "__main__":
    unittest.main()
