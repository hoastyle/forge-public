import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
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
    "ALL_PROXY": "",
    "all_proxy": "",
    "HTTP_PROXY": "",
    "HTTPS_PROXY": "",
    "http_proxy": "",
    "https_proxy": "",
}


class ForgeCliTests(unittest.TestCase):
    def setUp(self):
        self.env_patcher = patch.dict(os.environ, SANITIZED_RUNTIME_ENV, clear=False)
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_cli_login_and_logout_manage_xdg_config(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            config_home = Path(tempdir)
            config_path = config_home / "forge" / "config.toml"
            stdout = StringIO()
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}, clear=False):
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "login",
                            "--server",
                            "http://127.0.0.1:8000",
                            "--token",
                            "secret-token",
                        ]
                    )

                self.assertEqual(exit_code, 0)
                payload = json.loads(stdout.getvalue())
                self.assertEqual(payload["status"], "success")
                self.assertEqual(payload["server"], "http://127.0.0.1:8000")
                self.assertEqual(payload["config_path"], str(config_path))
                self.assertTrue(config_path.exists())
                self.assertIn('server = "http://127.0.0.1:8000"', config_path.read_text(encoding="utf-8"))

                stdout = StringIO()
                with redirect_stdout(stdout):
                    exit_code = main(["logout"])

                self.assertEqual(exit_code, 0)
                payload = json.loads(stdout.getvalue())
                self.assertEqual(payload["status"], "success")
                self.assertFalse(config_path.exists())

    def test_cli_doctor_prefers_remote_server_when_logged_in(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            config_home = Path(tempdir)
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}, clear=False):
                main(
                    [
                        "login",
                        "--server",
                        "http://127.0.0.1:8000",
                        "--token",
                        "secret-token",
                    ]
                )

                stdout = StringIO()
                with patch("automation.pipeline.cli.execute_remote_command") as remote_command:
                    remote_command.return_value = (0, {"command": "doctor", "transport": "remote"})
                    with redirect_stdout(stdout):
                        exit_code = main(["doctor"])

                self.assertEqual(exit_code, 0)
                payload = json.loads(stdout.getvalue())
                self.assertEqual(payload["transport"], "remote")
                remote_command.assert_called_once()
                connection = remote_command.call_args.args[1]
                self.assertEqual(connection.server, "http://127.0.0.1:8000")
                self.assertEqual(connection.token, "secret-token")

    def test_cli_repo_root_forces_local_execution_even_when_logged_in(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            config_home = Path(tempdir) / "config"
            repo_root = Path(tempdir) / "repo"
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}, clear=False):
                main(
                    [
                        "login",
                        "--server",
                        "http://127.0.0.1:8000",
                        "--token",
                        "secret-token",
                    ]
                )

                stdout = StringIO()
                with patch("automation.pipeline.cli.execute_remote_command") as remote_command:
                    with redirect_stdout(stdout):
                        exit_code = main(["--repo-root", str(repo_root), "doctor"])

                self.assertEqual(exit_code, 0)
                payload = json.loads(stdout.getvalue())
                self.assertEqual(payload["command"], "doctor")
                remote_command.assert_not_called()

    def test_cli_remote_inject_file_sends_file_content_to_server(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            config_home = Path(tempdir) / "config"
            source_path = Path(tempdir) / "note.md"
            source_path.write_text("Context:\nA remote file note.\n", encoding="utf-8")
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}, clear=False):
                main(
                    [
                        "login",
                        "--server",
                        "http://127.0.0.1:8000",
                        "--token",
                        "secret-token",
                    ]
                )

                stdout = StringIO()
                with patch("automation.pipeline.cli.execute_remote_command") as remote_command:
                    remote_command.return_value = (
                        0,
                        {
                            "id": "remote-1",
                            "status": "success",
                            "title": "Remote file",
                            "receipt_ref": "state/receipts/inject/remote-1.json",
                        },
                    )
                    with redirect_stdout(stdout):
                        exit_code = main(
                            [
                                "inject",
                                "--file",
                                str(source_path),
                                "--title",
                                "Remote file",
                                "--source",
                                "cli test",
                                "--initiator",
                                "codex",
                            ]
                        )

                self.assertEqual(exit_code, 0)
                remote_command.assert_called_once()
                command_name = remote_command.call_args.args[0]
                payload = remote_command.call_args.args[2]
                self.assertEqual(command_name, "inject")
                self.assertEqual(payload["input_kind"], "file")
                self.assertEqual(payload["content"], "Context:\nA remote file note.\n")
                self.assertEqual(payload["source_ref"], str(source_path))
                self.assertTrue(payload["detach"])

    def test_cli_remote_promote_ready_forwards_operation_id(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            config_home = Path(tempdir) / "config"
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}, clear=False):
                main(
                    [
                        "login",
                        "--server",
                        "http://127.0.0.1:8000",
                        "--token",
                        "secret-token",
                    ]
                )

                stdout = StringIO()
                with patch("automation.pipeline.cli.execute_remote_command") as remote_command:
                    remote_command.return_value = (0, {"status": "queued", "operation_id": "op-ready-1"})
                    with redirect_stdout(stdout):
                        exit_code = main(
                            [
                                "promote-ready",
                                "--initiator",
                                "codex",
                                "--dry-run",
                                "--operation-id",
                                "op-ready-1",
                            ]
                        )

                self.assertEqual(exit_code, 0)
                payload = remote_command.call_args.args[2]
                self.assertEqual(payload["operation_id"], "op-ready-1")
                self.assertTrue(payload["dry_run"])
                self.assertTrue(payload["detach"])

    def test_cli_remote_synthesize_wait_overrides_default_detach(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            config_home = Path(tempdir) / "config"
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}, clear=False):
                main(
                    [
                        "login",
                        "--server",
                        "http://127.0.0.1:8000",
                        "--token",
                        "secret-token",
                    ]
                )

                stdout = StringIO()
                with patch("automation.pipeline.cli.execute_remote_command") as remote_command:
                    remote_command.return_value = (0, {"status": "success", "receipt_ref": "state/receipts/insights/1.json"})
                    with redirect_stdout(stdout):
                        exit_code = main(
                            [
                                "synthesize-insights",
                                "--initiator",
                                "codex",
                                "--wait",
                            ]
                        )

                self.assertEqual(exit_code, 0)
                payload = remote_command.call_args.args[2]
                self.assertFalse(payload["detach"])

    def test_cli_remote_mutation_rejects_wait_with_detach(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            config_home = Path(tempdir) / "config"
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}, clear=False):
                main(
                    [
                        "login",
                        "--server",
                        "http://127.0.0.1:8000",
                        "--token",
                        "secret-token",
                    ]
                )
                stderr = StringIO()
                with self.assertRaises(SystemExit) as exc:
                    with redirect_stderr(stderr):
                        main(
                            [
                                "synthesize-insights",
                                "--initiator",
                                "codex",
                                "--wait",
                                "--detach",
                            ]
                        )

                self.assertEqual(exc.exception.code, 2)
                self.assertIn("--wait", stderr.getvalue())
                self.assertIn("--detach", stderr.getvalue())

    def test_cli_serve_accepts_repo_and_state_roots_after_command(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            app_root = Path(tempdir) / "app"
            repo_root = Path(tempdir) / "repo"
            state_root = Path(tempdir) / "state"
            with patch("automation.pipeline.cli._load_create_app") as load_create_app:
                with patch("automation.pipeline.cli._load_uvicorn_run") as load_uvicorn_run:
                    create_app = load_create_app.return_value
                    uvicorn_run = load_uvicorn_run.return_value
                    exit_code = main(
                        [
                            "serve",
                            "--app-root",
                            str(app_root),
                            "--repo-root",
                            str(repo_root),
                            "--state-root",
                            str(state_root),
                            "--host",
                            "127.0.0.1",
                            "--port",
                            "18081",
                            "--token",
                            "secret-token",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            create_app.assert_called_once_with(
                app_root=app_root,
                repo_root=repo_root,
                state_root=state_root,
                bearer_token="secret-token",
            )
            uvicorn_run.assert_called_once()

    def test_cli_receipt_get_returns_failure_json_for_missing_selector(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "receipt",
                        "get",
                        "state/receipts/inject/missing.json",
                    ]
                )

            self.assertEqual(exit_code, 1)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "failed")
            self.assertEqual(payload["error_code"], "RECEIPT_NOT_FOUND")
            self.assertIn("receipt_ref", payload["next_step"])

    def test_cli_knowledge_get_returns_status_json(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            knowledge_path = repo_root / "knowledge" / "troubleshooting" / "example.md"
            knowledge_path.parent.mkdir(parents=True, exist_ok=True)
            knowledge_path.write_text(
                (
                    "---\n"
                    "title: Example knowledge\n"
                    "created: 2026-04-04\n"
                    "updated: 2026-04-05\n"
                    "tags: [network, dns]\n"
                    "status: active\n"
                    "judge_score: 0.91\n"
                    "judge_decision: publish\n"
                    "release_reason: Meets the release bar.\n"
                    "reuse_count: 0\n"
                    "derived_from: [raw/captures/example.md]\n"
                    "---\n\n"
                    "# Example knowledge\n\n"
                    "Reusable DNS troubleshooting knowledge.\n"
                ),
                encoding="utf-8",
            )

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "knowledge",
                        "get",
                        "knowledge/troubleshooting/example.md",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["knowledge_ref"], "knowledge/troubleshooting/example.md")
            self.assertEqual(payload["publication_status"], "active")

    def test_cli_inject_command_writes_receipt_json(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "inject",
                        "--text",
                        "Context:\nA note.\n",
                        "--title",
                        "CLI note",
                        "--source",
                        "manual",
                        "--initiator",
                        "codex",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn('"status": "success"', stdout.getvalue())

            receipts = sorted((repo_root / "state" / "receipts" / "inject").glob("*.json"))
            self.assertEqual(len(receipts), 1)
            payload = json.loads(receipts[0].read_text())
            self.assertEqual(payload["title"], "CLI note")
            self.assertEqual(payload["status"], "success")

    def test_cli_inject_command_normalizes_initiator(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "inject",
                        "--text",
                        "Context:\nA note.\n",
                        "--title",
                        "CLI note",
                        "--source",
                        "manual",
                        "--initiator",
                        "CoDeX",
                    ]
                )

            self.assertEqual(exit_code, 0)
            receipts = sorted((repo_root / "state" / "receipts" / "inject").glob("*.json"))
            payload = json.loads(receipts[0].read_text())
            self.assertEqual(payload["initiator"], "codex")

    def test_cli_rejects_unknown_initiator(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            stderr = StringIO()
            with patch("sys.stderr", stderr):
                with self.assertRaises(SystemExit) as exc:
                    main(
                        [
                            "--repo-root",
                            str(repo_root),
                            "inject",
                            "--text",
                            "Context:\nA note.\n",
                            "--initiator",
                            "unknown-bot",
                        ]
                    )

        self.assertEqual(exc.exception.code, 2)
        self.assertIn("invalid initiator", stderr.getvalue())

    def test_cli_doctor_reports_dependency_status(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "doctor",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["command"], "doctor")
            self.assertIn("python_version", payload)
            self.assertIn("lark_cli", payload["dependencies"])
            self.assertIn("litellm", payload["dependencies"])
            self.assertIn(payload["default_knowledge_client"], {"heuristic", "litellm"})
            self.assertEqual(
                payload["dependencies"]["litellm"]["provider_credentials"]["runtime_lock"]["path"],
                str(repo_root / "automation" / "compiled" / "runtime.lock.json"),
            )
            self.assertFalse((repo_root / "automation" / "compiled" / "runtime.lock.json").exists())

    def test_cli_review_raw_command_reports_pending_documents(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            raw_path = repo_root / "raw" / "captures" / "pending.md"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(
                (
                    "---\n"
                    "title: Pending raw\n"
                    "created: 2026-04-04\n"
                    "updated: 2026-04-05\n"
                    "tags: [workflow]\n"
                    "status: active\n"
                    "source: manual note\n"
                    "---\n\n"
                    "# Pending raw\n\n"
                    "This raw document is long enough to qualify for promotion but has not been processed yet.\n"
                ),
                encoding="utf-8",
            )
            archived_path = repo_root / "raw" / "captures" / "archived.md"
            archived_path.write_text(
                (
                    "---\n"
                    "title: Archived raw\n"
                    "created: 2026-04-04\n"
                    "updated: 2026-04-05\n"
                    "tags: [workflow]\n"
                    "status: archived\n"
                    "source: manual note\n"
                    "---\n\n"
                    "# Archived raw\n\n"
                    "This archived historical summary is intentionally not queued for promotion.\n"
                ),
                encoding="utf-8",
            )

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "review-raw",
                        "--initiator",
                        "codex",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["pending_count"], 1)
            by_path = {item["path"]: item for item in payload["documents"]}
            self.assertEqual(by_path["raw/captures/pending.md"]["disposition"], "pending")
            self.assertEqual(by_path["raw/captures/archived.md"]["disposition"], "archived")

    def test_cli_review_queue_command_reports_summary_counts(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            raw_path = repo_root / "raw" / "captures" / "pending.md"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(
                (
                    "---\n"
                    "title: Pending raw\n"
                    "created: 2026-04-04\n"
                    "updated: 2026-04-05\n"
                    "tags: [workflow]\n"
                    "status: active\n"
                    "source: manual note\n"
                    "---\n\n"
                    "# Pending raw\n\n"
                    "This raw document is long enough to qualify for promotion but has not been processed yet.\n"
                ),
                encoding="utf-8",
            )
            short_path = repo_root / "raw" / "captures" / "short.md"
            short_path.write_text(
                (
                    "---\n"
                    "title: Short raw\n"
                    "created: 2026-04-04\n"
                    "updated: 2026-04-05\n"
                    "tags: [workflow]\n"
                    "status: active\n"
                    "source: manual note\n"
                    "---\n\n"
                    "# Short raw\n\n"
                    "Too short.\n"
                ),
                encoding="utf-8",
            )

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "review-queue",
                        "--initiator",
                        "codex",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["queue_count"], 2)
            self.assertEqual(payload["ready_count"], 1)
            self.assertEqual(payload["blocked_count"], 1)

    def test_cli_review_queue_command_reports_actionable_items(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            pending_path = repo_root / "raw" / "captures" / "pending.md"
            pending_path.parent.mkdir(parents=True, exist_ok=True)
            pending_path.write_text(
                (
                    "---\n"
                    "title: Pending raw\n"
                    "created: 2026-04-04\n"
                    "updated: 2026-04-05\n"
                    "tags: [workflow]\n"
                    "status: active\n"
                    "source: manual note\n"
                    "---\n\n"
                    "# Pending raw\n\n"
                    "This raw document is long enough to qualify for promotion but has not been processed yet.\n"
                ),
                encoding="utf-8",
            )
            short_path = repo_root / "raw" / "captures" / "short.md"
            short_path.write_text(
                (
                    "---\n"
                    "title: Short raw\n"
                    "created: 2026-04-04\n"
                    "updated: 2026-04-05\n"
                    "tags: [workflow]\n"
                    "status: active\n"
                    "source: manual note\n"
                    "---\n\n"
                    "# Short raw\n\n"
                    "Too short.\n"
                ),
                encoding="utf-8",
            )

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "review-queue",
                        "--initiator",
                        "codex",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["queue_name"], "raw_to_knowledge")
            self.assertEqual(payload["total_count"], 2)
            self.assertEqual(payload["pending_count"], 1)
            self.assertEqual(payload["too_short_count"], 1)

    def test_cli_promote_raw_command_creates_knowledge(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            raw_path = repo_root / "raw" / "captures" / "existing.md"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(
                (
                    "---\n"
                    "title: Existing raw\n"
                    "created: 2026-04-04\n"
                    "updated: 2026-04-05\n"
                    "tags: [network, dns]\n"
                    "status: active\n"
                    "source: manual note\n"
                    "---\n\n"
                    "# Existing raw\n\n"
                    "## Context\n\n"
                    "The gateway reboot was followed by fake DNS answers.\n\n"
                    "## Root Cause\n\n"
                    "The upstream resolver injected fake-ip ranges.\n\n"
                    "## Fix Steps\n\n"
                    "- Override the resolver.\n"
                    "- Restart the affected service.\n\n"
                    "## Verification\n\n"
                    "- Public domains resolve to public IPs.\n"
                ),
                encoding="utf-8",
            )

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "promote-raw",
                        "raw/captures/existing.md",
                        "--initiator",
                        "codex",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["raw_ref"], "raw/captures/existing.md")
            self.assertIsNotNone(payload["knowledge_ref"])

    def test_cli_promote_raw_all_command_reports_batch_receipt(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            pending_path = repo_root / "raw" / "captures" / "pending.md"
            pending_path.parent.mkdir(parents=True, exist_ok=True)
            pending_path.write_text(
                (
                    "---\n"
                    "title: Pending raw\n"
                    "created: 2026-04-04\n"
                    "updated: 2026-04-05\n"
                    "tags: [network, dns]\n"
                    "status: active\n"
                    "source: manual note\n"
                    "---\n\n"
                    "# Pending raw\n\n"
                    "## Context\n\n"
                    "The gateway reboot was followed by fake DNS answers.\n\n"
                    "## Root Cause\n\n"
                    "The upstream resolver injected fake-ip ranges.\n\n"
                    "## Fix Steps\n\n"
                    "- Override the resolver.\n"
                    "- Restart the affected service.\n\n"
                    "## Verification\n\n"
                    "- Public domains resolve to public IPs.\n"
                ),
                encoding="utf-8",
            )
            archived_path = repo_root / "raw" / "captures" / "archived.md"
            archived_path.write_text(
                (
                    "---\n"
                    "title: Archived raw\n"
                    "created: 2026-04-04\n"
                    "updated: 2026-04-05\n"
                    "tags: [workflow]\n"
                    "status: archived\n"
                    "source: manual note\n"
                    "---\n\n"
                    "# Archived raw\n\n"
                    "This archived historical summary is intentionally not queued for promotion.\n"
                ),
                encoding="utf-8",
            )

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "promote-raw",
                        "--all",
                        "--initiator",
                        "codex",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["total_count"], 2)
            self.assertEqual(payload["success_count"], 1)
            self.assertEqual(payload["skipped_count"], 1)

    def test_cli_promote_ready_command_reports_batch_receipt(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            pending_path = repo_root / "raw" / "captures" / "pending.md"
            pending_path.parent.mkdir(parents=True, exist_ok=True)
            pending_path.write_text(
                (
                    "---\n"
                    "title: Pending raw\n"
                    "created: 2026-04-04\n"
                    "updated: 2026-04-05\n"
                    "tags: [network, dns]\n"
                    "status: active\n"
                    "source: manual note\n"
                    "---\n\n"
                    "# Pending raw\n\n"
                    "## Context\n\n"
                    "The gateway reboot was followed by fake DNS answers.\n\n"
                    "## Root Cause\n\n"
                    "The upstream resolver injected fake-ip ranges.\n\n"
                    "## Fix Steps\n\n"
                    "- Override the resolver.\n"
                    "- Restart the affected service.\n\n"
                    "## Verification\n\n"
                    "- Public domains resolve to public IPs.\n"
                ),
                encoding="utf-8",
            )
            short_path = repo_root / "raw" / "captures" / "short.md"
            short_path.write_text(
                (
                    "---\n"
                    "title: Short raw\n"
                    "created: 2026-04-04\n"
                    "updated: 2026-04-05\n"
                    "tags: [workflow]\n"
                    "status: active\n"
                    "source: manual note\n"
                    "---\n\n"
                    "# Short raw\n\n"
                    "Too short.\n"
                ),
                encoding="utf-8",
            )

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "promote-ready",
                        "--initiator",
                        "codex",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["ready_count"], 1)
            self.assertEqual(payload["targeted_count"], 1)
            self.assertEqual(payload["success_count"], 1)
            self.assertEqual(payload["failed_count"], 0)

    def test_cli_promote_ready_command_supports_dry_run_and_limit(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            for suffix in ("a", "b"):
                path = repo_root / "raw" / "captures" / "pending-{0}.md".format(suffix)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    (
                        "---\n"
                        "title: Pending raw {0}\n"
                        "created: 2026-04-04\n"
                        "updated: 2026-04-05\n"
                        "tags: [network, dns]\n"
                        "status: active\n"
                        "source: manual note\n"
                        "---\n\n"
                        "# Pending raw {0}\n\n"
                        "## Context\n\nThe gateway reboot was followed by fake DNS answers.\n\n"
                        "## Root Cause\n\nThe upstream resolver injected fake-ip ranges.\n\n"
                        "## Fix Steps\n\n- Override the resolver.\n\n"
                        "## Verification\n\n- Public domains resolve to public IPs.\n"
                    ).format(suffix.upper()),
                    encoding="utf-8",
                )

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "promote-ready",
                        "--initiator",
                        "codex",
                        "--dry-run",
                        "--limit",
                        "1",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "success")
            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["limit"], 1)
            self.assertEqual(payload["planned_count"], 1)
            self.assertEqual(payload["success_count"], 0)

    def test_cli_promote_ready_command_can_confirm_a_dry_run_receipt(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            for suffix in ("a", "b"):
                path = repo_root / "raw" / "captures" / "pending-{0}.md".format(suffix)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    (
                        "---\n"
                        "title: Pending raw {0}\n"
                        "created: 2026-04-04\n"
                        "updated: 2026-04-05\n"
                        "tags: [network, dns]\n"
                        "status: active\n"
                        "source: manual note\n"
                        "---\n\n"
                        "# Pending raw {0}\n\n"
                        "## Context\n\nThe gateway reboot was followed by fake DNS answers.\n\n"
                        "## Root Cause\n\nThe upstream resolver injected fake-ip ranges.\n\n"
                        "## Fix Steps\n\n- Override the resolver.\n\n"
                        "## Verification\n\n- Public domains resolve to public IPs.\n"
                    ).format(suffix.upper()),
                    encoding="utf-8",
                )

            preview_stdout = StringIO()
            with redirect_stdout(preview_stdout):
                preview_exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "promote-ready",
                        "--initiator",
                        "codex",
                        "--dry-run",
                        "--limit",
                        "1",
                    ]
                )

            preview_payload = json.loads(preview_stdout.getvalue())
            confirm_stdout = StringIO()
            with redirect_stdout(confirm_stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "promote-ready",
                        "--initiator",
                        "codex",
                        "--confirm-receipt",
                        preview_payload["receipt_ref"],
                    ]
                )

            self.assertEqual(preview_exit_code, 0)
            self.assertEqual(exit_code, 0)
            payload = json.loads(confirm_stdout.getvalue())
            self.assertEqual(payload["status"], "success")
            self.assertFalse(payload["dry_run"])
            self.assertEqual(payload["confirmed_from_receipt_ref"], preview_payload["receipt_ref"])
            self.assertEqual(payload["success_count"], 1)

    def test_cli_inject_warns_when_litellm_runtime_inherits_proxy_env(self):
        from automation.pipeline.cli import main
        from automation.pipeline.models import IngestReceipt

        class FakeApp:
            def __init__(self, repo_root):
                self.repo_root = repo_root

            def inject_text(self, **kwargs):
                return IngestReceipt(
                    id="test-id",
                    status="success",
                    title=kwargs.get("title") or "CLI note",
                    input_kind="text",
                    initiator=kwargs["initiator"],
                    source_ref="inline:text",
                )

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            (repo_root / ".env").write_text(
                "FORGE_KNOWLEDGE_CLIENT=litellm\n"
                "OPENAI_API_KEY=test-key\n"
                "OPENAI_BASE_URL=https://relay.example/v1\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            with patch.dict(os.environ, {"http_proxy": "http://127.0.0.1:7890"}, clear=False):
                with patch("automation.pipeline.cli.ForgeApp", FakeApp):
                    with redirect_stdout(stdout):
                        with patch("sys.stderr", stderr):
                            exit_code = main(
                                [
                                    "--repo-root",
                                    str(repo_root),
                                    "inject",
                                    "--text",
                                    "Context:\nA note.\n",
                                    "--title",
                                    "CLI note",
                                    "--initiator",
                                    "codex",
                                ]
                            )

        self.assertEqual(exit_code, 0)
        self.assertIn('"status": "success"', stdout.getvalue())
        self.assertIn("proxy", stderr.getvalue().lower())
        self.assertIn("http_proxy", stderr.getvalue())
        self.assertIn("env -u all_proxy -u http_proxy -u https_proxy", stderr.getvalue())

    def test_cli_inject_does_not_warn_about_proxy_when_heuristic_client_is_active(self):
        from automation.pipeline.cli import main
        from automation.pipeline.models import IngestReceipt

        class FakeApp:
            def __init__(self, repo_root):
                self.repo_root = repo_root

            def inject_text(self, **kwargs):
                return IngestReceipt(
                    id="test-id",
                    status="success",
                    title=kwargs.get("title") or "CLI note",
                    input_kind="text",
                    initiator=kwargs["initiator"],
                    source_ref="inline:text",
                )

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            stdout = StringIO()
            stderr = StringIO()
            with patch.dict(os.environ, {"http_proxy": "http://127.0.0.1:7890"}, clear=False):
                with patch("automation.pipeline.cli.ForgeApp", FakeApp):
                    with redirect_stdout(stdout):
                        with patch("sys.stderr", stderr):
                            exit_code = main(
                                [
                                    "--repo-root",
                                    str(repo_root),
                                    "inject",
                                    "--text",
                                    "Context:\nA note.\n",
                                    "--title",
                                    "CLI note",
                                    "--initiator",
                                    "codex",
                                ]
                            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")

    def test_cli_tune_command_updates_lock_and_bootstraps_patch_schema(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "tune",
                        "把 insight 生成改得更保守：evidence 至少 3 篇 knowledge，judge 改用更强模型。",
                        "--initiator",
                        "codex",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "success")
            self.assertEqual(len(payload["patches"]), 2)

            lock_payload = json.loads((repo_root / payload["lock_ref"]).read_text())
            self.assertEqual(lock_payload["runtime"]["insight"]["min_evidence"], 3)
            self.assertEqual(lock_payload["runtime"]["insight"]["judge_profile"], "judge_strong")

            schema_path = repo_root / "automation" / "schemas" / "patch.schema.json"
            self.assertTrue(schema_path.exists())
            schema_payload = json.loads(schema_path.read_text())
            self.assertEqual(schema_payload["version"], 1)

    def test_cli_synthesize_insights_command_writes_receipt_json(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            knowledge_dir = repo_root / "knowledge" / "workflow"
            knowledge_dir.mkdir(parents=True)
            for idx in range(2):
                (knowledge_dir / f"note-{idx}.md").write_text(
                    (
                        "---\n"
                        f"title: Note {idx}\n"
                        "created: 2026-04-04\n"
                        "updated: 2026-04-04\n"
                        "tags: [network, dns]\n"
                        "status: active\n"
                        "reuse_count: 0\n"
                        "derived_from: [raw/captures/source.md]\n"
                        "---\n\n"
                        f"# Note {idx}\n\n"
                        "This is reusable DNS troubleshooting knowledge.\n"
                    )
                )

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "synthesize-insights",
                        "--initiator",
                        "codex",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "success")
            self.assertIsNotNone(payload["insight_ref"])
            self.assertIsNotNone(payload["evidence_trace_ref"])

    def test_cli_synthesize_insights_supports_dry_run(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            knowledge_dir = repo_root / "knowledge" / "workflow"
            knowledge_dir.mkdir(parents=True)
            for idx in range(2):
                (knowledge_dir / f"note-{idx}.md").write_text(
                    (
                        "---\n"
                        f"title: Note {idx}\n"
                        "created: 2026-04-04\n"
                        "updated: 2026-04-04\n"
                        "tags: [network, dns]\n"
                        "status: active\n"
                        "reuse_count: 0\n"
                        "derived_from: [raw/captures/source.md]\n"
                        "---\n\n"
                        f"# Note {idx}\n\n"
                        "This is reusable DNS troubleshooting knowledge.\n"
                    ),
                    encoding="utf-8",
                )

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "synthesize-insights",
                        "--initiator",
                        "codex",
                        "--dry-run",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "success")
            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["confirmed_from_receipt_ref"], None)
            self.assertIsNotNone(payload["evidence_trace_ref"])
            self.assertIsNone(payload["insight_ref"])

    def test_cli_remote_synthesize_insights_forwards_confirm_receipt(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            config_home = Path(tempdir) / "config"
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}, clear=False):
                main(
                    [
                        "login",
                        "--server",
                        "http://127.0.0.1:8000",
                        "--token",
                        "secret-token",
                    ]
                )

                stdout = StringIO()
                with patch("automation.pipeline.cli.execute_remote_command") as remote_command:
                    remote_command.return_value = (
                        0,
                        {
                            "status": "success",
                            "confirmed_from_receipt_ref": "state/receipts/insights/preview.json",
                        },
                    )
                    with redirect_stdout(stdout):
                        exit_code = main(
                            [
                                "synthesize-insights",
                                "--initiator",
                                "codex",
                                "--confirm-receipt",
                                "state/receipts/insights/preview.json",
                            ]
                        )

                self.assertEqual(exit_code, 0)
                payload = remote_command.call_args.args[2]
                self.assertEqual(payload["confirm_receipt"], "state/receipts/insights/preview.json")
                self.assertFalse(payload["dry_run"])

    def test_cli_synthesize_insights_rejects_confirm_receipt_with_dry_run(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            with self.assertRaises(SystemExit):
                main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "synthesize-insights",
                        "--initiator",
                        "codex",
                        "--dry-run",
                        "--confirm-receipt",
                        "state/receipts/insights/preview.json",
                    ]
                )

    def test_cli_explain_insight_returns_trace_summary(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            knowledge_dir = repo_root / "knowledge" / "troubleshooting"
            knowledge_dir.mkdir(parents=True)
            for idx in range(2):
                (knowledge_dir / "note-{0}.md".format(idx)).write_text(
                    (
                        "---\n"
                        "title: Note {0}\n"
                        "created: 2026-04-04\n"
                        "updated: 2026-04-04\n"
                        "tags: [network, dns]\n"
                        "status: active\n"
                        "judge_score: 0.92\n"
                        "judge_decision: publish\n"
                        "release_reason: Meets the release bar.\n"
                        "reuse_count: 0\n"
                        "derived_from: [raw/captures/source-{0}.md]\n"
                        "---\n\n"
                        "# Note {0}\n\n"
                        "Reusable DNS troubleshooting knowledge.\n"
                    ).format(idx),
                    encoding="utf-8",
                )

            synthesize_stdout = StringIO()
            with redirect_stdout(synthesize_stdout):
                synthesize_exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "synthesize-insights",
                        "--initiator",
                        "codex",
                    ]
                )
            self.assertEqual(synthesize_exit_code, 0)
            receipt_ref = json.loads(synthesize_stdout.getvalue())["receipt_ref"]

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "explain",
                        "insight",
                        receipt_ref,
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["receipt_ref"], receipt_ref)
            self.assertIn("selected_paths", payload)
            self.assertIn("candidate_clusters", payload)
            self.assertIn("excluded_documents", payload)

    def test_cli_replay_failure_command_replays_archived_case(self):
        from automation.pipeline.app import ForgeApp
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            app = ForgeApp(repo_root)
            app.inject_text(
                text=(
                    "Context:\n"
                    "SSH became slow after the container IP changed.\n\n"
                    "Root cause:\n"
                    "The SSH host key changed after container recreation.\n\n"
                    "Fix steps:\n"
                    "- Remove the stale known_hosts entry.\n"
                ),
                title="SSH host key mismatch",
                source="shell transcript",
                tags=["ssh"],
                promote_knowledge=True,
            )

            failure_case = sorted((repo_root / "state" / "failure_cases" / "knowledge").glob("*.json"))[0]

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "replay-failure",
                        str(failure_case),
                        "--initiator",
                        "codex",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["replay_command"], "inject_text")
            self.assertEqual(payload["result_status"], "success")

    def test_cli_replay_failure_command_returns_nonzero_for_missing_case(self):
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "replay-failure",
                        "state/failure_cases/knowledge/missing.json",
                        "--initiator",
                        "codex",
                    ]
                )

            self.assertEqual(exit_code, 1)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "failed")
            self.assertEqual(payload["result_status"], "failed")

    def test_cli_review_failures_command_writes_summary_receipt(self):
        from automation.pipeline.app import ForgeApp
        from automation.pipeline.cli import main
        from tests.test_pipeline_app import FakeFeishuFetcher

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            app = ForgeApp(repo_root, feishu_fetcher=FakeFeishuFetcher(error="auth required"))
            app.inject_feishu_link(
                "https://example.feishu.cn/docx/abc123",
                source="shared feishu note",
                initiator="codex",
            )

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "review-failures",
                        "--initiator",
                        "codex",
                        "--limit",
                        "5",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["case_count"], 1)
            self.assertIsNotNone(payload["summary_ref"])

            summary_payload = json.loads((repo_root / payload["summary_ref"]).read_text())
            self.assertIn("patch_suggestions", summary_payload)

    def test_cli_auto_retune_command_updates_runtime_lock(self):
        from automation.pipeline.app import ForgeApp
        from automation.pipeline.cli import main

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            app = ForgeApp(repo_root)
            lock_path = repo_root / "automation" / "compiled" / "runtime.lock.json"
            lock_payload = json.loads(lock_path.read_text())
            lock_payload["runtime"]["insight"]["min_evidence"] = 3
            lock_path.write_text(json.dumps(lock_payload, indent=2) + "\n")

            app.inject_text(
                text=(
                    "Context:\n"
                    "SSH became slow after the container IP changed.\n\n"
                    "Root cause:\n"
                    "The SSH host key changed after container recreation.\n\n"
                    "Fix steps:\n"
                    "- Remove the stale known_hosts entry.\n"
                ),
                title="SSH host key mismatch",
                source="shell transcript",
                tags=["ssh"],
                promote_knowledge=True,
            )

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(repo_root),
                        "auto-retune",
                        "--initiator",
                        "codex",
                        "--limit",
                        "10",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["applied_actions"], ["tighten_knowledge_input_or_prompt"])

            updated_lock = json.loads((repo_root / payload["lock_ref"]).read_text())
            self.assertEqual(
                updated_lock["prompts"]["knowledge_writer"]["domain_appendix"]["network"],
                "必须明确 root cause、验证命令和回滚点。",
            )


if __name__ == "__main__":
    unittest.main()
