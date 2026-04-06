import sys
import os
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch


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
}


class LiteLLMClientEnvTests(unittest.TestCase):
    def setUp(self):
        self.env_patcher = patch.dict(os.environ, SANITIZED_RUNTIME_ENV, clear=False)
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_build_default_knowledge_client_uses_repo_env_client_selection(self):
        from automation.pipeline.llm_client import LiteLLMKnowledgeClient, build_default_knowledge_client

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            (repo_root / ".env").write_text("FORGE_KNOWLEDGE_CLIENT=litellm\n", encoding="utf-8")

            fake_litellm = ModuleType("litellm")
            fake_litellm_responses = ModuleType("litellm.responses")
            fake_litellm_responses_main = ModuleType("litellm.responses.main")
            fake_litellm_responses_main.responses = lambda **kwargs: None
            with patch.dict(
                sys.modules,
                {
                    "litellm": fake_litellm,
                    "litellm.responses": fake_litellm_responses,
                    "litellm.responses.main": fake_litellm_responses_main,
                },
            ):
                client = build_default_knowledge_client(repo_root)

        self.assertIsInstance(client, LiteLLMKnowledgeClient)

    def test_call_json_uses_repo_env_openai_key_and_base_url_via_responses_api(self):
        from automation.pipeline.llm_client import LiteLLMStructuredClient

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            prompt_dir = repo_root / "automation" / "prompts"
            prompt_dir.mkdir(parents=True, exist_ok=True)
            (prompt_dir / "knowledge_writer.md").write_text("You are a test prompt.", encoding="utf-8")
            (repo_root / ".env").write_text(
                "OPENAI_API_KEY=test-key\n"
                "OPENAI_BASE_URL=https://relay.example/v1\n",
                encoding="utf-8",
            )

            captured = {}

            def fake_responses(**kwargs):
                captured.update(kwargs)
                return SimpleNamespace(
                    id="resp-123",
                    _hidden_params={
                        "additional_headers": {
                            "llm_provider-x-oneapi-request-id": "relay-req-123",
                        }
                    },
                    output=[
                        SimpleNamespace(
                            type="message",
                            content=[
                                SimpleNamespace(
                                    type="output_text",
                                    text='{"status": "ok"}',
                                )
                            ],
                        )
                    ]
                )

            fake_litellm = ModuleType("litellm")
            fake_litellm_responses = ModuleType("litellm.responses")
            fake_litellm_responses_main = ModuleType("litellm.responses.main")
            fake_litellm_responses_main.responses = fake_responses

            with patch.dict(
                sys.modules,
                {
                    "litellm": fake_litellm,
                    "litellm.responses": fake_litellm_responses,
                    "litellm.responses.main": fake_litellm_responses_main,
                },
            ):
                client = LiteLLMStructuredClient(repo_root)
                response = client._call_json(
                    "knowledge_writer",
                    {"model": "openai/gpt-4.1-mini", "temperature": 0.1},
                    {"title": "relay smoke test"},
                )
                trace = client.consume_last_call_trace()

        self.assertEqual(response, {"status": "ok"})
        self.assertEqual(
            trace,
            {
                "prompt_name": "knowledge_writer",
                "model": "openai/gpt-4.1-mini",
                "provider": "openai",
                "api_base": "https://relay.example/v1",
                "api_base_source": ".env",
                "api_key_source": ".env",
                "response_id": "resp-123",
                "relay_request_id": "relay-req-123",
                "output_text_present": True,
                "request_correlation_id": trace["request_correlation_id"],
                "request_header_name": "x-forge-trace-id",
                "request_metadata": {
                    "forge_trace_id": trace["request_correlation_id"],
                    "forge_prompt_name": "knowledge_writer",
                },
            },
        )
        self.assertTrue(trace["request_correlation_id"].startswith("forge-"))
        self.assertEqual(captured["api_key"], "test-key")
        self.assertEqual(captured["api_base"], "https://relay.example/v1")
        self.assertEqual(captured["input"], 'You are a test prompt.\n\nPayload JSON:\n{"title": "relay smoke test"}')
        self.assertEqual(captured["text"], {"format": {"type": "json_object"}})
        self.assertEqual(captured["extra_headers"], {"x-forge-trace-id": trace["request_correlation_id"]})
        self.assertNotIn("metadata", captured)
        self.assertFalse(captured["store"])
        self.assertNotIn("instructions", captured)

    def test_call_json_rejects_missing_output_text_from_responses_api(self):
        from automation.pipeline.llm_client import LiteLLMStructuredClient

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            prompt_dir = repo_root / "automation" / "prompts"
            prompt_dir.mkdir(parents=True, exist_ok=True)
            (prompt_dir / "knowledge_writer.md").write_text("You are a test prompt.", encoding="utf-8")

            def fake_responses(**kwargs):
                return SimpleNamespace(output=[SimpleNamespace(type="message", content=[])])

            fake_litellm = ModuleType("litellm")
            fake_litellm_responses = ModuleType("litellm.responses")
            fake_litellm_responses_main = ModuleType("litellm.responses.main")
            fake_litellm_responses_main.responses = fake_responses

            with patch.dict(
                sys.modules,
                {
                    "litellm": fake_litellm,
                    "litellm.responses": fake_litellm_responses,
                    "litellm.responses.main": fake_litellm_responses_main,
                },
            ):
                client = LiteLLMStructuredClient(repo_root)
                with self.assertRaisesRegex(RuntimeError, "did not return output text"):
                    client._call_json(
                        "knowledge_writer",
                        {"model": "openai/gpt-4.1-mini", "temperature": 0.1},
                        {"title": "relay smoke test"},
                    )
                trace = client.consume_last_call_trace()
                self.assertEqual(
                    trace,
                    {
                        "prompt_name": "knowledge_writer",
                        "model": "openai/gpt-4.1-mini",
                        "provider": "openai",
                        "api_base": "",
                        "api_base_source": "",
                        "api_key_source": "",
                        "response_id": "",
                        "relay_request_id": "",
                        "output_text_present": False,
                        "request_correlation_id": trace["request_correlation_id"],
                        "request_header_name": "x-forge-trace-id",
                        "request_metadata": {
                            "forge_trace_id": trace["request_correlation_id"],
                            "forge_prompt_name": "knowledge_writer",
                        },
                    },
                )
                self.assertTrue(trace["request_correlation_id"].startswith("forge-"))

    def test_call_json_preserves_partial_trace_when_responses_transport_fails(self):
        from automation.pipeline.llm_client import LiteLLMStructuredClient

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            prompt_dir = repo_root / "automation" / "prompts"
            prompt_dir.mkdir(parents=True, exist_ok=True)
            (prompt_dir / "knowledge_writer.md").write_text("You are a test prompt.", encoding="utf-8")
            (repo_root / ".env").write_text(
                "OPENAI_API_KEY=test-key\n"
                "OPENAI_BASE_URL=https://relay.example/v1\n",
                encoding="utf-8",
            )

            def fake_responses(**kwargs):
                raise RuntimeError("auth failed")

            fake_litellm = ModuleType("litellm")
            fake_litellm_responses = ModuleType("litellm.responses")
            fake_litellm_responses_main = ModuleType("litellm.responses.main")
            fake_litellm_responses_main.responses = fake_responses

            with patch.dict(
                sys.modules,
                {
                    "litellm": fake_litellm,
                    "litellm.responses": fake_litellm_responses,
                    "litellm.responses.main": fake_litellm_responses_main,
                },
            ):
                client = LiteLLMStructuredClient(repo_root)
                with self.assertRaisesRegex(RuntimeError, "auth failed"):
                    client._call_json(
                        "knowledge_writer",
                        {"model": "openai/gpt-4.1-mini", "temperature": 0.1},
                        {"title": "relay smoke test"},
                    )
                trace = client.consume_last_call_trace()
                self.assertEqual(
                    trace,
                    {
                        "prompt_name": "knowledge_writer",
                        "model": "openai/gpt-4.1-mini",
                        "provider": "openai",
                        "api_base": "https://relay.example/v1",
                        "api_base_source": ".env",
                        "api_key_source": ".env",
                        "response_id": "",
                        "relay_request_id": "",
                        "output_text_present": False,
                        "request_correlation_id": trace["request_correlation_id"],
                        "request_header_name": "x-forge-trace-id",
                        "request_metadata": {
                            "forge_trace_id": trace["request_correlation_id"],
                            "forge_prompt_name": "knowledge_writer",
                        },
                    },
                )
                self.assertTrue(trace["request_correlation_id"].startswith("forge-"))

    def test_call_json_extracts_relay_request_id_from_exception_headers(self):
        from automation.pipeline.llm_client import LiteLLMStructuredClient

        class FakeGatewayError(RuntimeError):
            def __init__(self):
                super().__init__("gateway failed")
                self._hidden_params = {
                    "additional_headers": {
                        "x-oneapi-request-id": "relay-exc-123",
                    }
                }

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            prompt_dir = repo_root / "automation" / "prompts"
            prompt_dir.mkdir(parents=True, exist_ok=True)
            (prompt_dir / "knowledge_writer.md").write_text("You are a test prompt.", encoding="utf-8")
            (repo_root / ".env").write_text(
                "OPENAI_API_KEY=test-key\n"
                "OPENAI_BASE_URL=https://relay.example/v1\n",
                encoding="utf-8",
            )

            def fake_responses(**kwargs):
                raise FakeGatewayError()

            fake_litellm = ModuleType("litellm")
            fake_litellm_responses = ModuleType("litellm.responses")
            fake_litellm_responses_main = ModuleType("litellm.responses.main")
            fake_litellm_responses_main.responses = fake_responses

            with patch.dict(
                sys.modules,
                {
                    "litellm": fake_litellm,
                    "litellm.responses": fake_litellm_responses,
                    "litellm.responses.main": fake_litellm_responses_main,
                },
            ):
                client = LiteLLMStructuredClient(repo_root)
                with self.assertRaisesRegex(FakeGatewayError, "gateway failed"):
                    client._call_json(
                        "knowledge_writer",
                        {"model": "openai/gpt-4.1-mini", "temperature": 0.1},
                        {"title": "relay smoke test"},
                    )
                trace = client.consume_last_call_trace()

        self.assertEqual(trace["response_id"], "")
        self.assertEqual(trace["relay_request_id"], "relay-exc-123")
        self.assertFalse(trace["output_text_present"])
        self.assertTrue(trace["request_correlation_id"].startswith("forge-"))

    def test_call_json_extracts_relay_request_id_from_private_response_headers(self):
        from automation.pipeline.llm_client import LiteLLMStructuredClient

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            prompt_dir = repo_root / "automation" / "prompts"
            prompt_dir.mkdir(parents=True, exist_ok=True)
            (prompt_dir / "knowledge_writer.md").write_text("You are a test prompt.", encoding="utf-8")
            (repo_root / ".env").write_text(
                "OPENAI_API_KEY=test-key\n"
                "OPENAI_BASE_URL=https://relay.example/v1\n",
                encoding="utf-8",
            )

            def fake_responses(**kwargs):
                return SimpleNamespace(
                    id="resp-private-headers",
                    _response_headers={"x-oneapi-request-id": "relay-private-123"},
                    output=[
                        SimpleNamespace(
                            type="message",
                            content=[
                                SimpleNamespace(
                                    type="output_text",
                                    text='{"status": "ok"}',
                                )
                            ],
                        )
                    ],
                )

            fake_litellm = ModuleType("litellm")
            fake_litellm_responses = ModuleType("litellm.responses")
            fake_litellm_responses_main = ModuleType("litellm.responses.main")
            fake_litellm_responses_main.responses = fake_responses

            with patch.dict(
                sys.modules,
                {
                    "litellm": fake_litellm,
                    "litellm.responses": fake_litellm_responses,
                    "litellm.responses.main": fake_litellm_responses_main,
                },
            ):
                client = LiteLLMStructuredClient(repo_root)
                response = client._call_json(
                    "knowledge_writer",
                    {"model": "openai/gpt-4.1-mini", "temperature": 0.1},
                    {"title": "relay smoke test"},
                )
                trace = client.consume_last_call_trace()

        self.assertEqual(response, {"status": "ok"})
        self.assertEqual(trace["response_id"], "resp-private-headers")
        self.assertEqual(trace["relay_request_id"], "relay-private-123")


if __name__ == "__main__":
    unittest.main()
