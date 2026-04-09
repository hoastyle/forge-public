import json
import tempfile
import time
import unittest
from pathlib import Path


class ForgeServiceApiTests(unittest.TestCase):
    def test_service_doctor_reports_separated_application_content_and_state_roots(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError as exc:
            self.skipTest(str(exc))
        from automation.pipeline.service_api import create_app

        with tempfile.TemporaryDirectory() as tempdir:
            app_root = Path(tempdir) / "app"
            repo_root = Path(tempdir) / "repo"
            state_root = Path(tempdir) / "state-store"
            (app_root / "automation" / "compiled").mkdir(parents=True, exist_ok=True)
            (app_root / "automation" / "compiled" / "runtime.lock.json").write_text("{}", encoding="utf-8")
            app = create_app(
                app_root=app_root,
                repo_root=repo_root,
                state_root=state_root,
                bearer_token="secret-token",
            )
            client = TestClient(app)
            headers = {"Authorization": "Bearer secret-token"}

            response = client.get("/v1/doctor", headers=headers)

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["application_storage"], "separate")
            self.assertEqual(payload["content_storage"], "external")
            self.assertEqual(payload["state_storage"], "external")
            self.assertEqual(payload["paths"]["app_root"], str(app_root))
            self.assertEqual(payload["paths"]["repo_root"], str(repo_root))

    def test_service_requires_bearer_token_when_configured(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError as exc:
            self.skipTest(str(exc))
        from automation.pipeline.service_api import create_app

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir) / "repo"
            state_root = Path(tempdir) / "state-store"
            app = create_app(repo_root=repo_root, state_root=state_root, bearer_token="secret-token")
            client = TestClient(app)

            response = client.get("/v1/doctor")

            self.assertEqual(response.status_code, 401)

    def test_service_inject_round_trip_uses_separate_state_root(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError as exc:
            self.skipTest(str(exc))
        from automation.pipeline.service_api import create_app

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir) / "repo"
            state_root = Path(tempdir) / "state-store"
            app = create_app(repo_root=repo_root, state_root=state_root, bearer_token="secret-token")
            client = TestClient(app)
            headers = {"Authorization": "Bearer secret-token"}

            response = client.post(
                "/v1/inject",
                headers=headers,
                json={
                    "input_kind": "text",
                    "content": "Context:\nA service note.\n",
                    "title": "Service note",
                    "source": "service test",
                    "initiator": "codex",
                    "promote_knowledge": False,
                },
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["status"], "success")
            self.assertTrue(payload["raw_ref"].startswith("raw/captures/"))
            self.assertTrue(payload["raw_ref"].endswith("service-note.md"))

            receipt_file = state_root / "receipts" / "inject" / "{0}.json".format(payload["id"])
            self.assertTrue(receipt_file.exists())
            self.assertFalse((repo_root / "state" / "receipts" / "inject" / "{0}.json".format(payload["id"])).exists())

            receipt_response = client.get(
                "/v1/receipt",
                headers=headers,
                params={"selector": payload["receipt_ref"]},
            )
            self.assertEqual(receipt_response.status_code, 200)
            self.assertEqual(receipt_response.json()["id"], payload["id"])

    def test_service_detached_job_can_be_polled_to_completion(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError as exc:
            self.skipTest(str(exc))
        from automation.pipeline.service_api import create_app

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir) / "repo"
            state_root = Path(tempdir) / "state-store"
            app = create_app(repo_root=repo_root, state_root=state_root, bearer_token="secret-token")
            client = TestClient(app)
            headers = {"Authorization": "Bearer secret-token"}

            response = client.post(
                "/v1/inject",
                headers=headers,
                json={
                    "input_kind": "text",
                    "content": "Context:\nA detached note.\n",
                    "title": "Detached note",
                    "source": "service test",
                    "initiator": "codex",
                    "promote_knowledge": False,
                    "detach": True,
                },
            )

            self.assertEqual(response.status_code, 202)
            payload = response.json()
            self.assertEqual(payload["status"], "queued")
            job_id = payload["job_id"]

            final_payload = None
            for _ in range(40):
                job_response = client.get("/v1/jobs/{0}".format(job_id), headers=headers)
                self.assertEqual(job_response.status_code, 200)
                final_payload = job_response.json()
                if final_payload["status"] in {"success", "failed"}:
                    break
                time.sleep(0.05)

            self.assertIsNotNone(final_payload)
            self.assertEqual(final_payload["status"], "success")
            self.assertTrue(final_payload["receipt_ref"].startswith("state/receipts/inject/"))

    def test_service_reuses_existing_inline_operation_result(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError as exc:
            self.skipTest(str(exc))
        from automation.pipeline.service_api import create_app

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir) / "repo"
            state_root = Path(tempdir) / "state-store"
            app = create_app(repo_root=repo_root, state_root=state_root, bearer_token="secret-token")
            client = TestClient(app)
            headers = {"Authorization": "Bearer secret-token"}

            request_payload = {
                "input_kind": "text",
                "content": "Context:\nInline retry-safe note.\n",
                "title": "Retry-safe inline",
                "source": "service test",
                "initiator": "codex",
                "promote_knowledge": False,
                "operation_id": "op-inline-1",
            }
            first = client.post("/v1/inject", headers=headers, json=request_payload)
            second = client.post("/v1/inject", headers=headers, json=request_payload)

            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)
            first_payload = first.json()
            second_payload = second.json()
            self.assertEqual(first_payload.get("operation_id"), "op-inline-1")
            self.assertEqual(second_payload, first_payload)

            receipt_files = sorted((state_root / "receipts" / "inject").glob("*.json"))
            self.assertEqual(len(receipt_files), 1)

            operation_file = state_root / "service" / "operations" / "op-inline-1.json"
            self.assertTrue(operation_file.exists())
            operation_payload = json.loads(operation_file.read_text(encoding="utf-8"))
            self.assertEqual(operation_payload["response"]["id"], first_payload["id"])

    def test_service_reuses_existing_detached_operation_result(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError as exc:
            self.skipTest(str(exc))
        from automation.pipeline.service_api import create_app

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir) / "repo"
            state_root = Path(tempdir) / "state-store"
            app = create_app(repo_root=repo_root, state_root=state_root, bearer_token="secret-token")
            client = TestClient(app)
            headers = {"Authorization": "Bearer secret-token"}

            request_payload = {
                "initiator": "codex",
                "detach": True,
                "operation_id": "op-detached-1",
            }
            first = client.post("/v1/synthesize-insights", headers=headers, json=request_payload)
            second = client.post("/v1/synthesize-insights", headers=headers, json=request_payload)

            first_payload = first.json()
            second_payload = second.json()
            try:
                self.assertEqual(first.status_code, 202)
                self.assertEqual(second.status_code, 202)
                self.assertEqual(first_payload.get("operation_id"), "op-detached-1")
                self.assertEqual(second_payload, first_payload)

                job_files = sorted((state_root / "service" / "jobs").glob("*.json"))
                self.assertEqual(len(job_files), 1)

                operation_file = state_root / "service" / "operations" / "op-detached-1.json"
                self.assertTrue(operation_file.exists())
                operation_payload = json.loads(operation_file.read_text(encoding="utf-8"))
                self.assertEqual(operation_payload["response"]["job_id"], first_payload["job_id"])
            finally:
                job_id = first_payload.get("job_id")
                if job_id:
                    for _ in range(40):
                        job_response = client.get("/v1/jobs/{0}".format(job_id), headers=headers)
                        if job_response.status_code == 200 and job_response.json()["status"] in {"success", "failed"}:
                            break
                        time.sleep(0.05)

    def test_service_synthesize_insights_supports_dry_run_requests(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError as exc:
            self.skipTest(str(exc))
        from automation.pipeline.service_api import create_app

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir) / "repo"
            state_root = Path(tempdir) / "state-store"
            app = create_app(repo_root=repo_root, state_root=state_root, bearer_token="secret-token")
            client = TestClient(app)
            headers = {"Authorization": "Bearer secret-token"}

            response = client.post(
                "/v1/synthesize-insights",
                headers=headers,
                json={"initiator": "codex", "dry_run": True},
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload.get("dry_run"))

    def test_service_synthesize_insights_confirm_returns_receipt_ref(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError as exc:
            self.skipTest(str(exc))
        from automation.pipeline.service_api import create_app

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir) / "repo"
            state_root = Path(tempdir) / "state-store"
            app = create_app(repo_root=repo_root, state_root=state_root, bearer_token="secret-token")
            client = TestClient(app)
            headers = {"Authorization": "Bearer secret-token"}

            dry_response = client.post(
                "/v1/synthesize-insights",
                headers=headers,
                json={"initiator": "codex", "dry_run": True},
            )
            self.assertEqual(dry_response.status_code, 200)
            receipt_ref = dry_response.json().get("receipt_ref")
            self.assertIsNotNone(receipt_ref)

            confirm_response = client.post(
                "/v1/synthesize-insights",
                headers=headers,
                json={"initiator": "codex", "confirm_receipt": receipt_ref},
            )

            self.assertEqual(confirm_response.status_code, 200)
            payload = confirm_response.json()
            self.assertEqual(payload.get("confirmed_from_receipt_ref"), receipt_ref)

    def test_service_rejects_operation_id_reuse_with_different_payload(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError as exc:
            self.skipTest(str(exc))
        from automation.pipeline.service_api import create_app

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir) / "repo"
            state_root = Path(tempdir) / "state-store"
            app = create_app(repo_root=repo_root, state_root=state_root, bearer_token="secret-token")
            client = TestClient(app)
            headers = {"Authorization": "Bearer secret-token"}

            first = client.post(
                "/v1/promote-ready",
                headers=headers,
                json={
                    "initiator": "codex",
                    "dry_run": True,
                    "operation_id": "op-ready-conflict-1",
                },
            )
            second = client.post(
                "/v1/promote-ready",
                headers=headers,
                json={
                    "initiator": "codex",
                    "dry_run": False,
                    "operation_id": "op-ready-conflict-1",
                },
            )

            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 409)
            payload = second.json()
            self.assertEqual(payload["status"], "failed")
            self.assertEqual(payload["operation_id"], "op-ready-conflict-1")
            self.assertEqual(payload["command"], "promote-ready")
            self.assertEqual(payload["stored_command"], "promote-ready")
            self.assertIn("stored_fingerprint", payload)

    def test_service_returns_knowledge_status(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError as exc:
            self.skipTest(str(exc))
        from automation.pipeline.service_api import create_app

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir) / "repo"
            state_root = Path(tempdir) / "state-store"
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
            app = create_app(repo_root=repo_root, state_root=state_root, bearer_token="secret-token")
            client = TestClient(app)
            headers = {"Authorization": "Bearer secret-token"}

            response = client.get(
                "/v1/knowledge",
                headers=headers,
                params={"selector": "knowledge/troubleshooting/example.md"},
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["knowledge_ref"], "knowledge/troubleshooting/example.md")
            self.assertEqual(payload["publication_status"], "active")
            self.assertEqual(payload["judge_decision"], "publish")
            self.assertTrue(payload["eligible_for_insights"])
            self.assertEqual(payload["knowledge_kind"], "heuristic")

    def test_service_explains_insight_receipt(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError as exc:
            self.skipTest(str(exc))
        from automation.pipeline.service_api import create_app

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir) / "repo"
            state_root = Path(tempdir) / "state-store"
            for idx in range(2):
                knowledge_path = repo_root / "knowledge" / "troubleshooting" / "note-{0}.md".format(idx)
                knowledge_path.parent.mkdir(parents=True, exist_ok=True)
                knowledge_path.write_text(
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
            app = create_app(repo_root=repo_root, state_root=state_root, bearer_token="secret-token")
            client = TestClient(app)
            headers = {"Authorization": "Bearer secret-token"}

            synthesize_response = client.post(
                "/v1/synthesize-insights",
                headers=headers,
                json={"initiator": "codex"},
            )
            self.assertEqual(synthesize_response.status_code, 200)
            receipt_ref = synthesize_response.json()["receipt_ref"]

            response = client.get(
                "/v1/explain/insight",
                headers=headers,
                params={"receipt_ref": receipt_ref},
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["receipt_ref"], receipt_ref)
            self.assertIn("selected_paths", payload)
            self.assertIn("candidate_clusters", payload)
            self.assertIn("excluded_documents", payload)
            if payload["excluded_documents"]:
                self.assertIn("knowledge_kind", payload["excluded_documents"][0])

    def test_service_receipt_returns_404_for_unknown_selector(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError as exc:
            self.skipTest(str(exc))
        from automation.pipeline.service_api import create_app

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir) / "repo"
            state_root = Path(tempdir) / "state-store"
            app = create_app(repo_root=repo_root, state_root=state_root, bearer_token="secret-token")
            client = TestClient(app)
            headers = {"Authorization": "Bearer secret-token"}

            response = client.get(
                "/v1/receipt",
                headers=headers,
                params={"selector": "state/receipts/inject/missing.json"},
            )

            self.assertEqual(response.status_code, 404)
            payload = response.json()
            self.assertEqual(payload["status"], "failed")
            self.assertEqual(payload["error_code"], "RECEIPT_NOT_FOUND")
            self.assertIn("receipt_ref", payload["next_step"])


if __name__ == "__main__":
    unittest.main()
