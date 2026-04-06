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


if __name__ == "__main__":
    unittest.main()
