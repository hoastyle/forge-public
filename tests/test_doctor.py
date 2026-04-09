import json
import os
import sys
import tempfile
import unittest
from types import ModuleType
from pathlib import Path
from unittest.mock import patch

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
    "LITELLM_LOCAL_MODEL_COST_MAP": "true",
    "ALL_PROXY": "",
    "all_proxy": "",
    "HTTP_PROXY": "",
    "HTTPS_PROXY": "",
    "http_proxy": "",
    "https_proxy": "",
}


class ForgeDoctorTests(unittest.TestCase):
    def setUp(self):
        self.env_patcher = patch.dict(os.environ, SANITIZED_RUNTIME_ENV, clear=False)
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_collect_dependency_report_has_required_sections(self):
        from automation.pipeline.doctor import collect_dependency_report

        report = collect_dependency_report()

        self.assertIn("python_version", report)
        self.assertIn("python_environment", report)
        self.assertIn("default_knowledge_client", report)
        self.assertIn("dependencies", report)
        self.assertIn("third_party_dependencies", report)
        self.assertIn("content_health", report)
        self.assertIn("lark_cli", report["dependencies"])
        self.assertIn("litellm", report["dependencies"])

        python_env = report["python_environment"]
        self.assertIn("executable", python_env)
        self.assertIn("in_venv", python_env)

        lark_cli = report["dependencies"]["lark_cli"]
        self.assertIn("available", lark_cli)
        self.assertIn("required_for", lark_cli)

        litellm = report["dependencies"]["litellm"]
        self.assertIn("installed", litellm)
        self.assertIn("importable", litellm)
        self.assertIn("import_error", litellm)
        self.assertTrue(litellm["optional"])
        self.assertIn("requested", litellm)
        self.assertIn("ready", litellm)
        self.assertIn("repo_local_enablement", litellm)
        self.assertIn("provider_credentials", litellm)
        self.assertIn("proxy_support", litellm)

        proxy_support = litellm["proxy_support"]
        self.assertIn("proxy_env_present", proxy_support)
        self.assertIn("socks_proxy_configured", proxy_support)
        self.assertIn("socksio_installed", proxy_support)
        self.assertIn("ready", proxy_support)

        third_party = report["third_party_dependencies"]
        self.assertEqual(third_party["required_python_packages"], [])
        self.assertEqual(third_party["core_runtime"], "python-stdlib")
        self.assertEqual(third_party["optional_python_packages"][0]["name"], "litellm")
        self.assertIn("install_hint", third_party["optional_python_packages"][0])
        self.assertIn("importable", third_party["optional_python_packages"][0])
        self.assertEqual(third_party["optional_python_packages"][1]["name"], "socksio")
        self.assertEqual(third_party["external_clis"][0]["name"], "lark-cli")

    def test_collect_dependency_report_summarizes_content_health(self):
        from automation.pipeline.doctor import collect_dependency_report

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            troubleshooting = repo_root / "knowledge" / "troubleshooting"
            tools = repo_root / "knowledge" / "tools"
            workflow = repo_root / "knowledge" / "workflow"
            troubleshooting.mkdir(parents=True, exist_ok=True)
            tools.mkdir(parents=True, exist_ok=True)
            workflow.mkdir(parents=True, exist_ok=True)
            (troubleshooting / "dns.md").write_text(
                (
                    "---\n"
                    "title: DNS incident\n"
                    "created: 2026-04-04\n"
                    "updated: 2026-04-05\n"
                    "tags: [network, dns]\n"
                    "status: active\n"
                    "derived_from: [raw/captures/dns.md]\n"
                    "---\n\n"
                    "# DNS incident\n\nReusable troubleshooting knowledge.\n"
                ),
                encoding="utf-8",
            )
            (tools / "reference.md").write_text(
                (
                    "---\n"
                    "title: DNS reference\n"
                    "created: 2026-04-04\n"
                    "updated: 2026-04-05\n"
                    "tags: [network, dns, reference]\n"
                    "status: active\n"
                    "knowledge_kind: reference\n"
                    "derived_from: [raw/captures/reference.md]\n"
                    "---\n\n"
                    "# DNS reference\n\nReference material.\n"
                ),
                encoding="utf-8",
            )
            (workflow / "draft.md").write_text(
                (
                    "---\n"
                    "title: Workflow note\n"
                    "created: 2026-04-04\n"
                    "updated: 2026-04-05\n"
                    "tags: [workflow]\n"
                    "status: draft\n"
                    "derived_from: [raw/captures/workflow.md]\n"
                    "---\n\n"
                    "# Workflow note\n\nWorkflow draft.\n"
                ),
                encoding="utf-8",
            )

            report = collect_dependency_report(repo_root)

        content_health = report["content_health"]
        self.assertEqual(content_health["knowledge_total"], 3)
        self.assertEqual(content_health["publication_status_counts"]["active"], 2)
        self.assertEqual(content_health["publication_status_counts"]["draft"], 1)
        self.assertEqual(content_health["knowledge_kind_counts"]["heuristic"], 1)
        self.assertEqual(content_health["knowledge_kind_counts"]["reference"], 1)
        self.assertEqual(content_health["knowledge_kind_counts"]["workflow"], 1)
        self.assertEqual(content_health["eligible_for_insights_count"], 1)
        self.assertEqual(content_health["excluded_reason_counts"]["knowledge_kind_reference"], 1)

    def test_provider_report_reads_openai_credentials_and_base_url_from_repo_env(self):
        from automation.pipeline.doctor import _collect_litellm_provider_report, _load_runtime_lock

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            compiled = repo_root / "automation" / "compiled"
            compiled.mkdir(parents=True, exist_ok=True)
            (compiled / "runtime.lock.json").write_text(
                json.dumps(
                    {
                        "profiles": {
                            "writer_cheap": {"model": "openai/gpt-4.1-mini", "temperature": 0.1},
                            "judge_mid": {"model": "openai/gpt-4.1", "temperature": 0.0},
                        },
                        "runtime": {
                            "knowledge": {
                                "writer_profile": "writer_cheap",
                                "critic_profile": "judge_mid",
                                "judge_profile": "judge_mid",
                            },
                            "insight": {
                                "writer_profile": "writer_cheap",
                                "critic_profile": "judge_mid",
                                "judge_profile": "judge_mid",
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            (repo_root / ".env").write_text(
                "OPENAI_API_KEY=test-key\n"
                "OPENAI_BASE_URL=https://relay.example/v1\n",
                encoding="utf-8",
            )

            runtime_lock = _load_runtime_lock(repo_root)
            report = _collect_litellm_provider_report(runtime_lock, repo_root)

        self.assertIn("repo_env", report)
        self.assertTrue(report["repo_env"]["present"])
        provider = report["providers"][0]
        self.assertEqual(provider["provider"], "openai")
        self.assertTrue(provider["credentials_present"])
        self.assertEqual(provider["credentials_source"], ".env")
        self.assertEqual(provider["base_url"], "https://relay.example/v1")
        self.assertEqual(provider["base_url_source"], ".env")

    def test_collect_dependency_report_marks_litellm_not_ready_without_provider_credentials(self):
        from automation.pipeline.doctor import collect_dependency_report

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            compiled = repo_root / "automation" / "compiled"
            compiled.mkdir(parents=True, exist_ok=True)
            (compiled / "runtime.lock.json").write_text(
                json.dumps(
                    {
                        "profiles": {
                            "writer_cheap": {"model": "openai/gpt-4.1-mini", "temperature": 0.1},
                            "judge_mid": {"model": "openai/gpt-4.1", "temperature": 0.0},
                        },
                        "runtime": {
                            "knowledge": {
                                "writer_profile": "writer_cheap",
                                "critic_profile": "judge_mid",
                                "judge_profile": "judge_mid",
                            },
                            "insight": {
                                "writer_profile": "writer_cheap",
                                "critic_profile": "judge_mid",
                                "judge_profile": "judge_mid",
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"FORGE_KNOWLEDGE_CLIENT": "litellm"}, clear=False):
                report = collect_dependency_report(repo_root)

        self.assertFalse(report["dependencies"]["litellm"]["ready"])
        providers = report["dependencies"]["litellm"]["provider_credentials"]["providers"]
        self.assertEqual(providers[0]["provider"], "openai")
        self.assertFalse(providers[0]["credentials_present"])

    def test_collect_dependency_report_reads_default_clients_from_repo_env(self):
        from automation.pipeline.doctor import collect_dependency_report

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            (repo_root / ".env").write_text(
                "FORGE_KNOWLEDGE_CLIENT=litellm\n"
                "FORGE_INSIGHT_CLIENT=litellm\n",
                encoding="utf-8",
            )

            report = collect_dependency_report(repo_root)

        self.assertEqual(report["default_knowledge_client"], "litellm")
        self.assertEqual(report["default_insight_client"], "litellm")
        self.assertTrue(report["dependencies"]["litellm"]["requested"])

    def test_collect_dependency_report_default_lock_is_ready_with_openai_only_repo_env(self):
        from automation.pipeline.doctor import collect_dependency_report

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            (repo_root / ".env").write_text(
                "FORGE_KNOWLEDGE_CLIENT=litellm\n"
                "FORGE_INSIGHT_CLIENT=litellm\n"
                "OPENAI_API_KEY=test-key\n"
                "OPENAI_BASE_URL=https://relay.example/v1\n",
                encoding="utf-8",
            )

            with patch(
                "automation.pipeline.doctor._collect_litellm_runtime_report",
                return_value={"installed": True, "importable": True, "import_error": ""},
            ):
                with patch(
                    "automation.pipeline.doctor._collect_proxy_support_report",
                    return_value={
                        "proxy_env_present": False,
                        "proxy_env_names": [],
                        "socks_proxy_configured": False,
                        "socksio_installed": False,
                        "ready": True,
                        "install_hint": "",
                    },
                ):
                    report = collect_dependency_report(repo_root)

        self.assertTrue(report["dependencies"]["litellm"]["ready"])
        providers = report["dependencies"]["litellm"]["provider_credentials"]["providers"]
        self.assertEqual([provider["provider"] for provider in providers], ["openai"])

    def test_collect_dependency_report_honors_explicit_heuristic_insight_override(self):
        from automation.pipeline.doctor import collect_dependency_report

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            compiled = repo_root / "automation" / "compiled"
            compiled.mkdir(parents=True, exist_ok=True)
            (compiled / "runtime.lock.json").write_text(
                json.dumps(
                    {
                        "profiles": {
                            "writer_openai": {"model": "openai/gpt-4.1-mini", "temperature": 0.1},
                            "judge_openai": {"model": "openai/gpt-4.1", "temperature": 0.0},
                            "writer_anthropic": {"model": "anthropic/claude-sonnet-4", "temperature": 0.2},
                        },
                        "runtime": {
                            "knowledge": {
                                "writer_profile": "writer_openai",
                                "critic_profile": "judge_openai",
                                "judge_profile": "judge_openai",
                            },
                            "insight": {
                                "writer_profile": "writer_anthropic",
                                "critic_profile": "judge_openai",
                                "judge_profile": "judge_openai",
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            (repo_root / ".env").write_text(
                "FORGE_KNOWLEDGE_CLIENT=litellm\n"
                "FORGE_INSIGHT_CLIENT=heuristic\n"
                "OPENAI_API_KEY=test-key\n"
                "OPENAI_BASE_URL=https://relay.example/v1\n",
                encoding="utf-8",
            )

            with patch(
                "automation.pipeline.doctor._collect_litellm_runtime_report",
                return_value={"installed": True, "importable": True, "import_error": ""},
            ):
                with patch(
                    "automation.pipeline.doctor._collect_proxy_support_report",
                    return_value={
                        "proxy_env_present": False,
                        "proxy_env_names": [],
                        "socks_proxy_configured": False,
                        "socksio_installed": False,
                        "ready": True,
                        "install_hint": "",
                    },
                ):
                    report = collect_dependency_report(repo_root)

        self.assertEqual(report["default_knowledge_client"], "litellm")
        self.assertEqual(report["default_insight_client"], "heuristic")
        self.assertTrue(report["dependencies"]["litellm"]["ready"])
        providers = report["dependencies"]["litellm"]["provider_credentials"]["providers"]
        self.assertEqual([provider["provider"] for provider in providers], ["openai"])

    def test_collect_dependency_report_checks_litellm_responses_entrypoint(self):
        from automation.pipeline.doctor import _collect_litellm_runtime_report

        def fake_find_spec(name):
            if name == "litellm":
                return object()
            return None

        with patch("automation.pipeline.doctor.importlib.util.find_spec", side_effect=fake_find_spec):
            with patch(
                "automation.pipeline.doctor.importlib.import_module",
                side_effect=ImportError("responses missing"),
            ):
                report = _collect_litellm_runtime_report()

        self.assertTrue(report["installed"])
        self.assertFalse(report["importable"])
        self.assertIn("responses", report["import_error"])

    def test_collect_dependency_report_preserves_repo_env_source_before_litellm_side_effects(self):
        from automation.pipeline.doctor import collect_dependency_report

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            (repo_root / ".env").write_text(
                "FORGE_KNOWLEDGE_CLIENT=litellm\n"
                "FORGE_INSIGHT_CLIENT=litellm\n"
                "OPENAI_API_KEY=repo-key\n"
                "OPENAI_BASE_URL=https://repo.example/v1\n",
                encoding="utf-8",
            )

            def fake_runtime_report():
                os.environ["OPENAI_API_KEY"] = "runtime-side-effect"
                os.environ["OPENAI_BASE_URL"] = "https://runtime.example/v1"
                return {"installed": True, "importable": True, "import_error": ""}

            with patch(
                "automation.pipeline.doctor._collect_litellm_runtime_report",
                side_effect=fake_runtime_report,
            ):
                with patch(
                    "automation.pipeline.doctor._collect_proxy_support_report",
                    return_value={
                        "proxy_env_present": False,
                        "proxy_env_names": [],
                        "socks_proxy_configured": False,
                        "socksio_installed": False,
                        "ready": True,
                        "install_hint": "",
                    },
                ):
                    with patch.dict(os.environ, {}, clear=False):
                        report = collect_dependency_report(repo_root)

        provider = report["dependencies"]["litellm"]["provider_credentials"]["providers"][0]
        self.assertEqual(provider["credentials_source"], ".env")
        self.assertEqual(provider["base_url_source"], ".env")

    def test_collect_dependency_report_smoke_test_guidance_matches_real_receipt_shape(self):
        from automation.pipeline.doctor import collect_dependency_report

        report = collect_dependency_report(REPO_ROOT)
        steps = report["dependencies"]["litellm"]["repo_local_enablement"]["steps"]
        smoke_test = report["dependencies"]["litellm"]["repo_local_enablement"]["smoke_test"]

        self.assertIn("pipeline_mode == 'llm'", smoke_test["expect"])
        self.assertIn("llm_trace_ref", smoke_test["expect"])
        self.assertIn("relay_request_ids", smoke_test["expect"])
        self.assertNotIn("knowledge_status", smoke_test["expect"])
        self.assertIn("uv run forge doctor", steps[-1]["run"][0])
        self.assertIn("uv run forge inject", smoke_test["run"][0])
        self.assertIn("A packet capture confirmed the gateway was rewriting DNS answers", smoke_test["run"][0])

    def test_collect_dependency_report_surfaces_proxy_runtime_warning_for_litellm(self):
        from automation.pipeline.doctor import collect_dependency_report

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            (repo_root / ".env").write_text(
                "FORGE_KNOWLEDGE_CLIENT=litellm\n"
                "OPENAI_API_KEY=test-key\n"
                "OPENAI_BASE_URL=https://relay.example/v1\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"http_proxy": "http://127.0.0.1:7890"}, clear=False):
                with patch(
                    "automation.pipeline.doctor._collect_litellm_runtime_report",
                    return_value={"installed": True, "importable": True, "import_error": ""},
                ):
                    report = collect_dependency_report(repo_root)

        proxy_support = report["dependencies"]["litellm"]["proxy_support"]
        self.assertTrue(proxy_support["proxy_env_present"])
        self.assertEqual(proxy_support["proxy_env_names"], ["http_proxy"])
        self.assertIn("http_proxy", proxy_support["warnings"][0])
        self.assertIn("env -u all_proxy -u http_proxy -u https_proxy", proxy_support["clear_env_command"])
        steps = report["dependencies"]["litellm"]["repo_local_enablement"]["steps"]
        self.assertIn("clear inherited proxy env", steps[1]["name"])
        self.assertIn("uv run forge doctor", steps[1]["run"][0])


if __name__ == "__main__":
    unittest.main()
