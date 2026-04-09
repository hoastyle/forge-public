import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class FakeFeishuFetcher:
    def __init__(self, payload=None, error=None):
        self.payload = payload or {}
        self.error = error

    def fetch(self, link):
        if self.error:
            raise RuntimeError(self.error)
        return self.payload


class FakeKnowledgeClient:
    mode = "llm"

    def __init__(self, candidate=None, critique=None, verdict=None, error_on=None):
        self.candidate = candidate or {}
        self.critique = critique or {"issues": [], "requires_downgrade": False, "summary": "looks good"}
        self.verdict = verdict or {
            "score": 0.93,
            "decision": "publish",
            "status": "active",
            "reason": "complete candidate",
        }
        self.error_on = error_on
        self._last_trace = None

    def write_knowledge_candidate(self, **kwargs):
        if self.error_on == "write":
            raise RuntimeError("writer unavailable")
        self._last_trace = {
            "prompt_name": "knowledge_writer",
            "model": kwargs["profile"]["model"],
            "provider": "openai",
            "api_base": "https://relay.example/v1",
            "api_base_source": ".env",
            "api_key_source": ".env",
            "response_id": "resp-write",
            "relay_request_id": "relay-write",
            "output_text_present": True,
        }
        return self.candidate

    def critique_knowledge_candidate(self, **kwargs):
        if self.error_on == "critique":
            raise RuntimeError("critic unavailable")
        self._last_trace = {
            "prompt_name": "critic",
            "model": kwargs["profile"]["model"],
            "provider": "openai",
            "api_base": "https://relay.example/v1",
            "api_base_source": ".env",
            "api_key_source": ".env",
            "response_id": "resp-critic",
            "relay_request_id": "relay-critic",
            "output_text_present": True,
        }
        return self.critique

    def judge_knowledge_candidate(self, **kwargs):
        if self.error_on == "judge":
            raise RuntimeError("judge unavailable")
        self._last_trace = {
            "prompt_name": "judge",
            "model": kwargs["profile"]["model"],
            "provider": "openai",
            "api_base": "https://relay.example/v1",
            "api_base_source": ".env",
            "api_key_source": ".env",
            "response_id": "resp-judge",
            "relay_request_id": "relay-judge",
            "output_text_present": True,
        }
        return self.verdict

    def consume_last_call_trace(self):
        payload = self._last_trace
        self._last_trace = None
        return payload


class FakeInsightClient:
    mode = "llm"

    def __init__(self, candidate=None, critique=None, verdict=None):
        self.candidate = candidate or {}
        self.critique = critique or {"issues": [], "requires_downgrade": False, "summary": "looks good"}
        self.verdict = verdict or {
            "score": 0.91,
            "decision": "publish",
            "status": "active",
            "reason": "enough evidence",
        }
        self._last_trace = None

    def write_insight_candidate(self, **kwargs):
        self._last_trace = {
            "prompt_name": "insight_writer",
            "model": kwargs["profile"]["model"],
            "provider": "openai",
            "api_base": "https://relay.example/v1",
            "api_base_source": ".env",
            "api_key_source": ".env",
            "response_id": "resp-insight-write",
            "relay_request_id": "relay-insight-write",
            "output_text_present": True,
        }
        return self.candidate

    def critique_insight_candidate(self, **kwargs):
        self._last_trace = {
            "prompt_name": "critic",
            "model": kwargs["profile"]["model"],
            "provider": "openai",
            "api_base": "https://relay.example/v1",
            "api_base_source": ".env",
            "api_key_source": ".env",
            "response_id": "resp-insight-critic",
            "relay_request_id": "relay-insight-critic",
            "output_text_present": True,
        }
        return self.critique

    def judge_insight_candidate(self, **kwargs):
        self._last_trace = {
            "prompt_name": "judge",
            "model": kwargs["profile"]["model"],
            "provider": "openai",
            "api_base": "https://relay.example/v1",
            "api_base_source": ".env",
            "api_key_source": ".env",
            "response_id": "resp-insight-judge",
            "relay_request_id": "relay-insight-judge",
            "output_text_present": True,
        }
        return self.verdict

    def consume_last_call_trace(self):
        payload = self._last_trace
        self._last_trace = None
        return payload


class TraceThenFailKnowledgeClient(FakeKnowledgeClient):
    def write_knowledge_candidate(self, **kwargs):
        self._last_trace = {
            "prompt_name": "knowledge_writer",
            "model": kwargs["profile"]["model"],
            "provider": "openai",
            "api_base": "https://relay.example/v1",
            "api_base_source": ".env",
            "api_key_source": ".env",
            "response_id": "",
            "relay_request_id": "relay-failed-write",
            "output_text_present": False,
        }
        raise RuntimeError("writer unavailable")


class TraceThenFailInsightClient(FakeInsightClient):
    def write_insight_candidate(self, **kwargs):
        self._last_trace = {
            "prompt_name": "insight_writer",
            "model": kwargs["profile"]["model"],
            "provider": "openai",
            "api_base": "https://relay.example/v1",
            "api_base_source": ".env",
            "api_key_source": ".env",
            "response_id": "",
            "relay_request_id": "relay-failed-insight-write",
            "output_text_present": False,
        }
        raise RuntimeError("writer unavailable")


class FailingFallbackKnowledgeClient:
    mode = "heuristic"

    def write_candidate(self, **kwargs):
        raise RuntimeError("fallback writer unavailable")


class FailingFallbackInsightClient:
    mode = "heuristic"

    def write_candidate(self, **kwargs):
        raise RuntimeError("fallback insight writer unavailable")


class GenericKnowledgeInterfaceClient:
    mode = "llm"

    def write_candidate(self, **kwargs):
        return {
            "title": kwargs["title"],
            "context": "Normalized through generic pipeline interface.",
            "root_cause": "A stale SSH host key remained after the container IP changed.",
            "fix_steps": ["Remove the stale known_hosts entry"],
            "verification": ["SSH login succeeds after refreshing host keys"],
            "related": [],
            "tags": list(kwargs.get("tags") or []),
            "confidence": 0.92,
        }

    def critique_candidate(self, **kwargs):
        return {
            "issues": [],
            "requires_downgrade": False,
            "summary": "Generic critique passed.",
        }

    def judge_candidate(self, **kwargs):
        return {
            "score": 0.93,
            "decision": "publish",
            "status": "active",
            "reason": "Generic judge passed.",
        }


class GenericInsightInterfaceClient:
    mode = "llm"

    def write_candidate(self, **kwargs):
        return {
            "title": "Pattern: dns incidents",
            "observation": "Multiple incidents point to the same upstream DNS issue.",
            "analysis": "The gateway DNS layer is the common bottleneck.",
            "application": "Check upstream DNS before container-level debugging.",
            "impact": "medium",
            "evidence": [doc["path"] for doc in kwargs["evidence_docs"]],
            "tags": ["network", "pattern"],
            "confidence": 0.91,
        }

    def critique_candidate(self, **kwargs):
        return {
            "issues": [],
            "requires_downgrade": False,
            "summary": "Generic insight critique passed.",
        }

    def judge_candidate(self, **kwargs):
        return {
            "score": 0.92,
            "decision": "publish",
            "status": "active",
            "reason": "Generic insight judge passed.",
        }


class ForgeAppTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def _write_knowledge_fixture(self, relative_path, title, tags, status="active", body=None):
        path = self.repo_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            (
                "---\n"
                f"title: {title}\n"
                "created: 2026-04-04\n"
                "updated: 2026-04-04\n"
                f"tags: [{', '.join(tags)}]\n"
                f"status: {status}\n"
                "reuse_count: 0\n"
                "derived_from: [raw/captures/source.md]\n"
                "---\n\n"
                f"# {title}\n\n"
                f"{body or 'Structured knowledge content.'}\n"
            )
        )

    def _write_raw_fixture(self, relative_path, title, tags, source, body, status="active"):
        path = self.repo_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            (
                "---\n"
                f"title: {title}\n"
                "created: 2026-04-04\n"
                "updated: 2026-04-05\n"
                f"tags: [{', '.join(tags)}]\n"
                f"status: {status}\n"
                f"source: {source}\n"
                "---\n\n"
                f"# {title}\n\n"
                f"{body}\n"
            ),
            encoding="utf-8",
        )

    def test_inject_text_creates_snapshot_raw_and_receipt(self):
        from automation.pipeline.app import ForgeApp

        app = ForgeApp(self.repo_root)
        receipt = app.inject_text(
            text=(
                "Context:\n"
                "Container traffic started failing after the gateway reboot.\n\n"
                "Signals:\n"
                "- dig github.com returned fake-ip answers.\n\n"
                "Root cause:\n"
                "The upstream gateway DNS resolver injected fake IP ranges.\n\n"
                "Fix steps:\n"
                "- Override resolv.conf to use 1.1.1.1.\n"
                "- Restart the affected service.\n\n"
                "Verification:\n"
                "- curl https://openai.com succeeds.\n"
            ),
            title="Gateway DNS incident",
            source="manual note",
            tags=["network", "dns"],
            initiator="codex",
        )

        self.assertEqual(receipt.status, "success")
        self.assertIsNotNone(receipt.snapshot_ref)
        self.assertIsNotNone(receipt.raw_ref)
        self.assertIsNotNone(receipt.receipt_ref)
        self.assertIsNone(receipt.knowledge_ref)

        snapshot = json.loads((self.repo_root / receipt.snapshot_ref).read_text())
        self.assertEqual(snapshot["input_kind"], "text")
        self.assertEqual(snapshot["source_ref"], "inline:text")
        self.assertIn("fake-ip answers", snapshot["content"])

        raw_text = (self.repo_root / receipt.raw_ref).read_text()
        self.assertIn("title: Gateway DNS incident", raw_text)
        self.assertIn("status: active", raw_text)
        self.assertIn("source: manual note", raw_text)
        self.assertIn("tags: [network, dns]", raw_text)

        receipt_payload = json.loads((self.repo_root / receipt.receipt_ref).read_text())
        self.assertEqual(receipt_payload["initiator"], "codex")
        self.assertEqual(receipt_payload["raw_ref"], receipt.raw_ref)

    def test_review_raw_reports_promoted_pending_archived_and_too_short_documents(self):
        from automation.pipeline.app import ForgeApp

        self._write_raw_fixture(
            "raw/captures/promoted.md",
            "Promoted raw",
            ["network"],
            "manual note",
            "## Context\n\nA full incident record that should qualify for promotion.\n",
        )
        self._write_raw_fixture(
            "raw/captures/pending.md",
            "Pending raw",
            ["workflow"],
            "manual note",
            "## Context\n\nThis raw document is long enough to promote but has not been processed yet.\n",
        )
        self._write_raw_fixture(
            "raw/captures/short.md",
            "Short raw",
            ["workflow"],
            "manual note",
            "Too short.\n",
        )
        self._write_raw_fixture(
            "raw/captures/archived-summary.md",
            "Archived summary",
            ["workflow"],
            "manual note",
            "This historical rollup is intentionally archived instead of promoted.\n",
            status="archived",
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/promoted-raw.md",
            "Promoted knowledge",
            ["network"],
            body="Structured knowledge content.\n",
        )
        knowledge_path = self.repo_root / "knowledge" / "troubleshooting" / "promoted-raw.md"
        knowledge_path.write_text(
            knowledge_path.read_text(encoding="utf-8").replace(
                "derived_from: [raw/captures/source.md]",
                "derived_from: [raw/captures/promoted.md]",
            ),
            encoding="utf-8",
        )

        app = ForgeApp(self.repo_root)
        receipt = app.review_raw(initiator="codex")

        self.assertEqual(receipt.status, "success")
        self.assertEqual(receipt.total_count, 4)
        self.assertEqual(receipt.promoted_count, 1)
        self.assertEqual(receipt.pending_count, 1)
        self.assertEqual(receipt.too_short_count, 1)
        self.assertEqual(len(receipt.documents), 4)

        by_path = {item["path"]: item for item in receipt.documents}
        self.assertEqual(by_path["raw/captures/promoted.md"]["disposition"], "promoted")
        self.assertEqual(by_path["raw/captures/pending.md"]["disposition"], "pending")
        self.assertEqual(by_path["raw/captures/short.md"]["disposition"], "too_short")
        self.assertEqual(by_path["raw/captures/archived-summary.md"]["disposition"], "archived")

    def test_review_raw_does_not_initialize_default_llm_clients(self):
        from automation.pipeline.app import ForgeApp

        (self.repo_root / ".env").write_text(
            (
                "FORGE_KNOWLEDGE_CLIENT=litellm\n"
                "FORGE_INSIGHT_CLIENT=litellm\n"
                "OPENAI_API_KEY=test-key\n"
                "OPENAI_BASE_URL=https://relay.example/v1\n"
            ),
            encoding="utf-8",
        )
        self._write_raw_fixture(
            "raw/captures/pending.md",
            "Pending raw",
            ["workflow"],
            "manual note",
            "This raw document is long enough to qualify for promotion but has not been processed yet.\n",
        )

        with patch("automation.pipeline.app.build_default_knowledge_client", side_effect=AssertionError("knowledge client should stay lazy")):
            with patch("automation.pipeline.app.build_default_insight_client", side_effect=AssertionError("insight client should stay lazy")):
                app = ForgeApp(self.repo_root)
                receipt = app.review_raw(initiator="codex")

        self.assertEqual(receipt.status, "success")
        self.assertEqual(receipt.pending_count, 1)

    def test_review_queue_reports_ready_and_blocked_documents(self):
        from automation.pipeline.app import ForgeApp

        self._write_raw_fixture(
            "raw/captures/pending.md",
            "Pending raw",
            ["workflow"],
            "manual note",
            "## Context\n\nThis raw document is long enough to qualify for promotion but has not been processed yet.\n",
        )
        self._write_raw_fixture(
            "raw/captures/short.md",
            "Short raw",
            ["workflow"],
            "manual note",
            "Too short.\n",
        )
        self._write_raw_fixture(
            "raw/captures/archived.md",
            "Archived raw",
            ["workflow"],
            "manual note",
            "Historical rollup kept for traceability.\n",
            status="archived",
        )
        self._write_knowledge_fixture(
            "knowledge/workflow/promoted.md",
            "Promoted knowledge",
            ["workflow"],
            body="Structured knowledge content.\n",
        )
        self._write_raw_fixture(
            "raw/captures/promoted.md",
            "Promoted raw",
            ["workflow"],
            "manual note",
            "## Context\n\nAlready promoted.\n",
        )
        knowledge_path = self.repo_root / "knowledge" / "workflow" / "promoted.md"
        knowledge_path.write_text(
            knowledge_path.read_text(encoding="utf-8").replace(
                "derived_from: [raw/captures/source.md]",
                "derived_from: [raw/captures/promoted.md]",
            ),
            encoding="utf-8",
        )

        app = ForgeApp(self.repo_root)
        receipt = app.review_queue(initiator="codex")

        self.assertEqual(receipt.status, "success")
        self.assertEqual(receipt.scanned_count, 4)
        self.assertEqual(receipt.queue_count, 2)
        self.assertEqual(receipt.ready_count, 1)
        self.assertEqual(receipt.blocked_count, 1)
        by_path = {item["path"]: item for item in receipt.documents}
        self.assertEqual(set(by_path), {"raw/captures/pending.md", "raw/captures/short.md"})
        self.assertEqual(by_path["raw/captures/pending.md"]["queue_status"], "ready")
        self.assertIn("promote-raw raw/captures/pending.md", by_path["raw/captures/pending.md"]["suggested_command"])
        self.assertEqual(by_path["raw/captures/short.md"]["queue_status"], "blocked")
        self.assertEqual(by_path["raw/captures/short.md"]["suggested_command"], "")

    def test_review_queue_returns_only_actionable_raw_items(self):
        from automation.pipeline.app import ForgeApp

        self._write_raw_fixture(
            "raw/captures/pending.md",
            "Pending raw",
            ["workflow"],
            "manual note",
            "This raw document is long enough to qualify for promotion but has not been processed yet.\n",
        )
        self._write_raw_fixture(
            "raw/captures/short.md",
            "Short raw",
            ["workflow"],
            "manual note",
            "Too short.\n",
        )
        self._write_raw_fixture(
            "raw/captures/archived.md",
            "Archived raw",
            ["workflow"],
            "manual note",
            "Historical rollup kept for traceability.\n",
            status="archived",
        )
        self._write_raw_fixture(
            "raw/references/reference.md",
            "Reference raw",
            ["reference"],
            "manual note",
            "External material kept as a reference document.\n",
        )
        self._write_raw_fixture(
            "raw/captures/promoted.md",
            "Promoted raw",
            ["network"],
            "manual note",
            "A full incident record that already has knowledge.\n",
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/promoted.md",
            "Promoted knowledge",
            ["network"],
            body="Structured knowledge content.\n",
        )
        knowledge_path = self.repo_root / "knowledge" / "troubleshooting" / "promoted.md"
        knowledge_path.write_text(
            knowledge_path.read_text(encoding="utf-8").replace(
                "derived_from: [raw/captures/source.md]",
                "derived_from: [raw/captures/promoted.md]",
            ),
            encoding="utf-8",
        )

        app = ForgeApp(self.repo_root)
        receipt = app.review_queue(initiator="codex")

        self.assertEqual(receipt.status, "success")
        self.assertEqual(receipt.queue_name, "raw_to_knowledge")
        self.assertEqual(receipt.total_count, 2)
        self.assertEqual(receipt.pending_count, 1)
        self.assertEqual(receipt.too_short_count, 1)
        self.assertEqual(len(receipt.items), 2)
        self.assertEqual(receipt.items[0]["path"], "raw/captures/pending.md")
        self.assertEqual(receipt.items[0]["action"], "promote_raw")
        self.assertIn("uv run forge promote-raw raw/captures/pending.md", receipt.items[0]["command_hint"])
        self.assertEqual(receipt.items[1]["path"], "raw/captures/short.md")
        self.assertEqual(receipt.items[1]["action"], "expand_or_merge")

    def test_promote_ready_only_processes_ready_queue_items(self):
        from automation.pipeline.app import ForgeApp

        self._write_raw_fixture(
            "raw/captures/pending.md",
            "Pending raw",
            ["network", "dns"],
            "manual note",
            (
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
        )
        self._write_raw_fixture(
            "raw/captures/short.md",
            "Short raw",
            ["workflow"],
            "manual note",
            "Too short.\n",
        )

        app = ForgeApp(self.repo_root)
        receipt = app.promote_ready(initiator="codex")

        self.assertEqual(receipt.status, "success")
        self.assertEqual(receipt.scanned_count, 2)
        self.assertEqual(receipt.ready_count, 1)
        self.assertEqual(receipt.targeted_count, 1)
        self.assertEqual(receipt.success_count, 1)
        self.assertEqual(receipt.failed_count, 0)
        self.assertIsNotNone(receipt.queue_receipt_ref)
        self.assertEqual(len(receipt.results), 1)
        self.assertEqual(receipt.results[0]["raw_ref"], "raw/captures/pending.md")
        self.assertEqual(receipt.results[0]["status"], "success")
        knowledge_files = sorted((self.repo_root / "knowledge").glob("**/*.md"))
        self.assertEqual(len(knowledge_files), 1)
        self.assertIn("derived_from: [raw/captures/pending.md]", knowledge_files[0].read_text(encoding="utf-8"))

    def test_promote_ready_dry_run_previews_without_creating_knowledge(self):
        from automation.pipeline.app import ForgeApp

        self._write_raw_fixture(
            "raw/captures/pending-a.md",
            "Pending raw A",
            ["network", "dns"],
            "manual note",
            (
                "## Context\n\nThe gateway reboot was followed by fake DNS answers.\n\n"
                "## Root Cause\n\nThe upstream resolver injected fake-ip ranges.\n\n"
                "## Fix Steps\n\n- Override the resolver.\n\n"
                "## Verification\n\n- Public domains resolve to public IPs.\n"
            ),
        )
        self._write_raw_fixture(
            "raw/captures/pending-b.md",
            "Pending raw B",
            ["network", "dns"],
            "manual note",
            (
                "## Context\n\nA second host inherited the same resolver issue.\n\n"
                "## Root Cause\n\nThe upstream resolver injected fake-ip ranges.\n\n"
                "## Fix Steps\n\n- Override the resolver.\n\n"
                "## Verification\n\n- Public domains resolve to public IPs.\n"
            ),
        )

        app = ForgeApp(self.repo_root)
        receipt = app.promote_ready(initiator="codex", dry_run=True, limit=1)

        self.assertEqual(receipt.status, "success")
        self.assertTrue(receipt.dry_run)
        self.assertEqual(receipt.limit, 1)
        self.assertEqual(receipt.ready_count, 2)
        self.assertEqual(receipt.targeted_count, 1)
        self.assertEqual(receipt.planned_count, 1)
        self.assertEqual(receipt.success_count, 0)
        self.assertEqual(len(receipt.results), 1)
        self.assertEqual(receipt.results[0]["status"], "planned")
        self.assertEqual(sorted((self.repo_root / "knowledge").glob("**/*.md")), [])

    def test_promote_ready_respects_limit(self):
        from automation.pipeline.app import ForgeApp

        for suffix in ("a", "b"):
            self._write_raw_fixture(
                "raw/captures/pending-{0}.md".format(suffix),
                "Pending raw {0}".format(suffix.upper()),
                ["network", "dns"],
                "manual note",
                (
                    "## Context\n\nThe gateway reboot was followed by fake DNS answers.\n\n"
                    "## Root Cause\n\nThe upstream resolver injected fake-ip ranges.\n\n"
                    "## Fix Steps\n\n- Override the resolver.\n\n"
                    "## Verification\n\n- Public domains resolve to public IPs.\n"
                ),
            )

        app = ForgeApp(self.repo_root)
        receipt = app.promote_ready(initiator="codex", limit=1)

        self.assertEqual(receipt.status, "success")
        self.assertFalse(receipt.dry_run)
        self.assertEqual(receipt.limit, 1)
        self.assertEqual(receipt.ready_count, 2)
        self.assertEqual(receipt.targeted_count, 1)
        self.assertEqual(receipt.success_count, 1)
        knowledge_files = sorted((self.repo_root / "knowledge").glob("**/*.md"))
        self.assertEqual(len(knowledge_files), 1)

    def test_promote_ready_can_confirm_a_dry_run_receipt(self):
        from automation.pipeline.app import ForgeApp

        for suffix in ("a", "b"):
            self._write_raw_fixture(
                "raw/captures/pending-{0}.md".format(suffix),
                "Pending raw {0}".format(suffix.upper()),
                ["network", "dns"],
                "manual note",
                (
                    "## Context\n\nThe gateway reboot was followed by fake DNS answers.\n\n"
                    "## Root Cause\n\nThe upstream resolver injected fake-ip ranges.\n\n"
                    "## Fix Steps\n\n- Override the resolver.\n\n"
                    "## Verification\n\n- Public domains resolve to public IPs.\n"
                ),
            )

        app = ForgeApp(self.repo_root)
        preview = app.promote_ready(initiator="codex", dry_run=True, limit=1)
        receipt = app.promote_ready(initiator="codex", confirm_receipt_ref=preview.receipt_ref)

        self.assertEqual(preview.status, "success")
        self.assertTrue(preview.dry_run)
        self.assertEqual(receipt.status, "success")
        self.assertFalse(receipt.dry_run)
        self.assertEqual(receipt.ready_count, 1)
        self.assertEqual(receipt.targeted_count, 1)
        self.assertEqual(receipt.success_count, 1)
        self.assertEqual(receipt.confirmed_from_receipt_ref, preview.receipt_ref)
        self.assertEqual(receipt.results[0]["raw_ref"], preview.results[0]["raw_ref"])
        knowledge_files = sorted((self.repo_root / "knowledge").glob("**/*.md"))
        self.assertEqual(len(knowledge_files), 1)

    def test_promote_ready_confirm_skips_raw_that_is_no_longer_ready(self):
        from automation.pipeline.app import ForgeApp

        self._write_raw_fixture(
            "raw/captures/pending-a.md",
            "Pending raw A",
            ["network", "dns"],
            "manual note",
            (
                "## Context\n\nThe gateway reboot was followed by fake DNS answers.\n\n"
                "## Root Cause\n\nThe upstream resolver injected fake-ip ranges.\n\n"
                "## Fix Steps\n\n- Override the resolver.\n\n"
                "## Verification\n\n- Public domains resolve to public IPs.\n"
            ),
        )

        app = ForgeApp(self.repo_root)
        preview = app.promote_ready(initiator="codex", dry_run=True)

        raw_path = self.repo_root / "raw" / "captures" / "pending-a.md"
        raw_path.write_text(raw_path.read_text(encoding="utf-8").replace("status: active", "status: archived"), encoding="utf-8")

        receipt = app.promote_ready(initiator="codex", confirm_receipt_ref=preview.receipt_ref)

        self.assertEqual(receipt.status, "success")
        self.assertEqual(receipt.ready_count, 0)
        self.assertEqual(receipt.targeted_count, 1)
        self.assertEqual(receipt.success_count, 0)
        self.assertEqual(receipt.skipped_count, 1)
        self.assertEqual(receipt.results[0]["status"], "skipped")
        self.assertIn("no longer ready", receipt.results[0]["message"])
        self.assertEqual(sorted((self.repo_root / "knowledge").glob("**/*.md")), [])

    def test_promote_raw_creates_knowledge_from_existing_raw_document(self):
        from automation.pipeline.app import ForgeApp

        self._write_raw_fixture(
            "raw/captures/existing.md",
            "Existing raw",
            ["network", "dns"],
            "manual note",
            (
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
        )

        app = ForgeApp(self.repo_root)
        receipt = app.promote_raw("raw/captures/existing.md", initiator="codex")

        self.assertEqual(receipt.status, "success")
        self.assertEqual(receipt.raw_ref, "raw/captures/existing.md")
        self.assertIsNotNone(receipt.knowledge_ref)
        self.assertIsNotNone(receipt.receipt_ref)

        knowledge_text = (self.repo_root / receipt.knowledge_ref).read_text(encoding="utf-8")
        self.assertIn("derived_from: [raw/captures/existing.md]", knowledge_text)
        self.assertIn("# Existing raw", knowledge_text)

    def test_promote_raw_receipt_includes_publication_fields_for_new_promotion(self):
        from automation.pipeline.app import ForgeApp

        self._write_raw_fixture(
            "raw/captures/publication-fields.md",
            "Publication fields raw",
            ["network", "dns"],
            "manual note",
            (
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
        )

        app = ForgeApp(self.repo_root)
        receipt = app.promote_raw("raw/captures/publication-fields.md", initiator="codex")

        self.assertEqual(receipt.status, "success")
        self.assertIn(receipt.publication_status, {"active", "draft"})
        self.assertIsNotNone(receipt.judge_score)
        self.assertIn(receipt.judge_decision, {"publish", "downgrade"})
        self.assertIsInstance(receipt.eligible_for_insights, bool)
        self.assertIsNotNone(receipt.updated_at)
        if receipt.eligible_for_insights:
            self.assertIsNone(receipt.excluded_reason)
        else:
            self.assertIsInstance(receipt.excluded_reason, str)

    def test_promote_raw_already_promoted_reports_current_publication_state(self):
        from automation.pipeline.app import ForgeApp

        self._write_raw_fixture(
            "raw/captures/already-promoted-stateful.md",
            "Already promoted stateful raw",
            ["workflow"],
            "manual note",
            "## Context\n\nA full incident record that already has knowledge.\n",
        )
        self._write_knowledge_fixture(
            "knowledge/workflow/already-promoted-stateful.md",
            "Already promoted stateful knowledge",
            ["workflow"],
            status="active",
            body="Structured knowledge content.\n",
        )
        knowledge_path = self.repo_root / "knowledge" / "workflow" / "already-promoted-stateful.md"
        knowledge_path.write_text(
            knowledge_path.read_text(encoding="utf-8")
            .replace(
                "derived_from: [raw/captures/source.md]",
                "derived_from: [raw/captures/already-promoted-stateful.md]",
            )
            .replace(
                "status: active",
                "status: active\njudge_score: 0.42\njudge_decision: downgrade\nrelease_reason: Legacy decision",
            ),
            encoding="utf-8",
        )

        app = ForgeApp(self.repo_root)
        receipt = app.promote_raw("raw/captures/already-promoted-stateful.md", initiator="codex")

        self.assertEqual(receipt.status, "skipped")
        self.assertEqual(receipt.knowledge_ref, "knowledge/workflow/already-promoted-stateful.md")
        self.assertEqual(receipt.publication_status, "active")
        self.assertAlmostEqual(receipt.judge_score, 0.42, places=2)
        self.assertEqual(receipt.judge_decision, "downgrade")
        self.assertFalse(receipt.eligible_for_insights)
        self.assertEqual(receipt.excluded_reason, "generic_tags_only")
        self.assertEqual(receipt.updated_at, "2026-04-04")

    def test_promote_raw_already_promoted_historical_knowledge_without_judge_metadata_returns_none(self):
        from automation.pipeline.app import ForgeApp

        self._write_raw_fixture(
            "raw/captures/already-promoted-historical.md",
            "Already promoted historical raw",
            ["network"],
            "manual note",
            "## Context\n\nA full incident record that already has knowledge.\n",
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/already-promoted-historical.md",
            "Already promoted historical knowledge",
            ["network"],
            status="active",
            body="Structured knowledge content.\n",
        )
        knowledge_path = self.repo_root / "knowledge" / "troubleshooting" / "already-promoted-historical.md"
        knowledge_path.write_text(
            knowledge_path.read_text(encoding="utf-8").replace(
                "derived_from: [raw/captures/source.md]",
                "derived_from: [raw/captures/already-promoted-historical.md]",
            ),
            encoding="utf-8",
        )

        app = ForgeApp(self.repo_root)
        receipt = app.promote_raw("raw/captures/already-promoted-historical.md", initiator="codex")

        self.assertEqual(receipt.status, "skipped")
        self.assertEqual(receipt.knowledge_ref, "knowledge/troubleshooting/already-promoted-historical.md")
        self.assertEqual(receipt.publication_status, "active")
        self.assertIsNone(receipt.judge_score)
        self.assertIsNone(receipt.judge_decision)
        self.assertTrue(receipt.eligible_for_insights)
        self.assertIsNone(receipt.excluded_reason)
        self.assertEqual(receipt.updated_at, "2026-04-04")

    def test_promote_all_raw_processes_pending_and_skips_non_promotable_documents(self):
        from automation.pipeline.app import ForgeApp

        self._write_raw_fixture(
            "raw/captures/pending.md",
            "Pending raw",
            ["network", "dns"],
            "manual note",
            (
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
        )
        self._write_raw_fixture(
            "raw/captures/already-promoted.md",
            "Already promoted raw",
            ["workflow"],
            "manual note",
            "## Context\n\nA full incident record that already has knowledge.\n",
        )
        self._write_raw_fixture(
            "raw/captures/archived.md",
            "Archived raw",
            ["workflow"],
            "manual note",
            "Historical rollup kept for traceability.\n",
            status="archived",
        )
        self._write_raw_fixture(
            "raw/captures/short.md",
            "Short raw",
            ["workflow"],
            "manual note",
            "Too short.\n",
        )
        self._write_raw_fixture(
            "raw/references/reference.md",
            "Reference raw",
            ["reference"],
            "manual note",
            "External material kept as a reference document.\n",
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/already-promoted.md",
            "Already promoted knowledge",
            ["workflow"],
            body="Structured knowledge content.\n",
        )
        knowledge_path = self.repo_root / "knowledge" / "troubleshooting" / "already-promoted.md"
        knowledge_path.write_text(
            knowledge_path.read_text(encoding="utf-8").replace(
                "derived_from: [raw/captures/source.md]",
                "derived_from: [raw/captures/already-promoted.md]",
            ),
            encoding="utf-8",
        )

        app = ForgeApp(self.repo_root)
        receipt = app.promote_all_raw(initiator="codex")

        self.assertEqual(receipt.status, "success")
        self.assertEqual(receipt.total_count, 5)
        self.assertEqual(receipt.success_count, 1)
        self.assertEqual(receipt.skipped_count, 4)
        self.assertEqual(receipt.failed_count, 0)
        self.assertIsNotNone(receipt.receipt_ref)

        by_path = {item["raw_ref"]: item for item in receipt.results}
        self.assertEqual(by_path["raw/captures/pending.md"]["status"], "success")
        self.assertIsNotNone(by_path["raw/captures/pending.md"]["knowledge_ref"])
        self.assertEqual(by_path["raw/captures/already-promoted.md"]["status"], "skipped")
        self.assertEqual(by_path["raw/captures/archived.md"]["status"], "skipped")
        self.assertEqual(by_path["raw/captures/short.md"]["status"], "skipped")
        self.assertEqual(by_path["raw/references/reference.md"]["status"], "skipped")

        knowledge_text = (
            self.repo_root / by_path["raw/captures/pending.md"]["knowledge_ref"]
        ).read_text(encoding="utf-8")
        self.assertIn("derived_from: [raw/captures/pending.md]", knowledge_text)

    def test_promote_all_raw_prefers_existing_knowledge_link_over_archived_status(self):
        from automation.pipeline.app import ForgeApp

        self._write_raw_fixture(
            "raw/captures/archived-promoted.md",
            "Archived promoted raw",
            ["workflow"],
            "manual note",
            "Historical record already distilled into knowledge.\n",
            status="archived",
        )
        self._write_knowledge_fixture(
            "knowledge/workflow/archived-promoted.md",
            "Archived promoted knowledge",
            ["workflow"],
            body="Structured knowledge content.\n",
        )
        knowledge_path = self.repo_root / "knowledge" / "workflow" / "archived-promoted.md"
        knowledge_path.write_text(
            knowledge_path.read_text(encoding="utf-8").replace(
                "derived_from: [raw/captures/source.md]",
                "derived_from: [raw/captures/archived-promoted.md]",
            ),
            encoding="utf-8",
        )

        app = ForgeApp(self.repo_root)
        receipt = app.promote_all_raw(initiator="codex")

        self.assertEqual(receipt.status, "success")
        self.assertEqual(receipt.total_count, 1)
        self.assertEqual(receipt.skipped_count, 1)
        result = receipt.results[0]
        self.assertEqual(result["raw_ref"], "raw/captures/archived-promoted.md")
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["knowledge_ref"], "knowledge/workflow/archived-promoted.md")
        self.assertEqual(result["message"], "raw document already promoted")

    def test_inject_text_normalizes_initiator_to_supported_value(self):
        from automation.pipeline.app import ForgeApp

        app = ForgeApp(self.repo_root)
        receipt = app.inject_text(
            text="Context:\nA note.\n",
            title="Normalized initiator",
            source="manual note",
            initiator="CoDeX",
        )

        self.assertEqual(receipt.initiator, "codex")
        receipt_payload = json.loads((self.repo_root / receipt.receipt_ref).read_text())
        self.assertEqual(receipt_payload["initiator"], "codex")

    def test_inject_text_rejects_unknown_initiator(self):
        from automation.pipeline.app import ForgeApp

        app = ForgeApp(self.repo_root)

        with self.assertRaisesRegex(ValueError, "invalid initiator"):
            app.inject_text(
                text="Context:\nA note.\n",
                title="Invalid initiator",
                source="manual note",
                initiator="unknown-bot",
            )

    def test_inject_file_promotes_to_active_knowledge_when_content_is_complete(self):
        from automation.pipeline.app import ForgeApp

        source_file = self.repo_root / "gateway-dns.md"
        source_file.write_text(
            "Context:\n"
            "Gateway DNS rewrote public domains to fake-ip.\n\n"
            "Root cause:\n"
            "The local gateway advertised a poisoned DNS resolver.\n\n"
            "Fix steps:\n"
            "- Set resolv.conf to 1.1.1.1.\n"
            "- Restart the gateway service.\n\n"
            "Verification:\n"
            "- dig github.com returns public IPs.\n"
            "- curl https://openai.com succeeds.\n"
        )

        app = ForgeApp(self.repo_root)
        receipt = app.inject_file(
            source_file,
            title="Gateway DNS repair",
            source="local markdown file",
            tags=["network"],
            initiator="claude-code",
            promote_knowledge=True,
        )

        self.assertEqual(receipt.status, "success")
        self.assertIsNotNone(receipt.knowledge_ref)

        knowledge_text = (self.repo_root / receipt.knowledge_ref).read_text()
        self.assertIn("status: active", knowledge_text)
        self.assertIn("reuse_count: 0", knowledge_text)
        self.assertIn("derived_from: [", knowledge_text)
        self.assertIn("The local gateway advertised a poisoned DNS resolver.", knowledge_text)
        self.assertIn("dig github.com returns public IPs.", knowledge_text)

    def test_inject_text_downgrades_knowledge_to_draft_when_sections_are_incomplete(self):
        from automation.pipeline.app import ForgeApp

        app = ForgeApp(self.repo_root)
        receipt = app.inject_text(
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
            initiator="openclaw",
            promote_knowledge=True,
        )

        self.assertEqual(receipt.status, "success")
        self.assertIsNotNone(receipt.knowledge_ref)

        knowledge_text = (self.repo_root / receipt.knowledge_ref).read_text()
        self.assertIn("status: draft", knowledge_text)
        self.assertIn("Verification information is incomplete", knowledge_text)

        failure_cases = sorted((self.repo_root / "state" / "failure_cases" / "knowledge").glob("*.json"))
        self.assertEqual(len(failure_cases), 1)
        failure_payload = json.loads(failure_cases[0].read_text())
        self.assertEqual(failure_payload["stage"], "knowledge")
        self.assertEqual(failure_payload["status"], "draft")
        self.assertEqual(failure_payload["refs"]["receipt_ref"], receipt.receipt_ref)
        self.assertEqual(failure_payload["replay"]["command"], "inject_text")
        self.assertTrue(failure_payload["replay"]["args"]["promote_knowledge"])

    def test_replay_failure_case_replays_archived_knowledge_case(self):
        from automation.pipeline.app import ForgeApp

        app = ForgeApp(self.repo_root)
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

        failure_case = sorted((self.repo_root / "state" / "failure_cases" / "knowledge").glob("*.json"))[0]
        replay_receipt = app.replay_failure_case(failure_case, initiator="codex")

        self.assertEqual(replay_receipt.status, "success")
        self.assertEqual(replay_receipt.replay_command, "inject_text")
        self.assertEqual(replay_receipt.result_status, "success")
        self.assertIsNotNone(replay_receipt.result_receipt_ref)

        replay_payload = json.loads((self.repo_root / replay_receipt.result_receipt_ref).read_text())
        self.assertEqual(replay_payload["title"], "SSH host key mismatch")
        self.assertEqual(replay_payload["status"], "success")

    def test_review_failures_summarizes_archived_cases(self):
        from automation.pipeline.app import ForgeApp
        from automation.pipeline.controller import load_or_create_patch_schema, validate_patch_bundle

        app = ForgeApp(self.repo_root, feishu_fetcher=FakeFeishuFetcher(error="auth required"))
        app.inject_feishu_link(
            "https://example.feishu.cn/docx/abc123",
            source="shared feishu note",
            initiator="codex",
        )
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

        receipt = app.review_failures(initiator="codex", limit=10)

        self.assertEqual(receipt.status, "success")
        self.assertEqual(receipt.case_count, 2)
        self.assertIsNotNone(receipt.summary_ref)

        summary_payload = json.loads((self.repo_root / receipt.summary_ref).read_text())
        self.assertEqual(summary_payload["case_count"], 2)
        self.assertEqual(summary_payload["categories"]["ingest_fetch_failure"], 1)
        self.assertEqual(summary_payload["categories"]["knowledge_draft"], 1)
        recommendation_actions = [item["action"] for item in summary_payload["recommendations"]]
        self.assertIn("repair_feishu_ingestion", recommendation_actions)
        self.assertIn("tighten_knowledge_input_or_prompt", recommendation_actions)

        patch_suggestions = summary_payload["patch_suggestions"]
        self.assertEqual(len(patch_suggestions), 1)
        self.assertEqual(patch_suggestions[0]["action"], "tighten_knowledge_input_or_prompt")
        self.assertEqual(patch_suggestions[0]["patches"][0]["path"], "/prompts/knowledge_writer/domain_appendix/network")

        schema = load_or_create_patch_schema(self.repo_root / "automation" / "schemas" / "patch.schema.json")
        validated = validate_patch_bundle(patch_suggestions[0]["patches"], schema)
        self.assertEqual(validated["version"], 1)

    def test_auto_retune_applies_patch_suggestions_to_runtime_lock(self):
        from automation.pipeline.app import ForgeApp

        app = ForgeApp(self.repo_root)
        lock_path = self.repo_root / "automation" / "compiled" / "runtime.lock.json"
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
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/gateway-dns.md",
            "Gateway DNS repair",
            ["network", "dns"],
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/container-dns.md",
            "Container DNS repair",
            ["network", "dns"],
        )
        app.synthesize_insights()

        receipt = app.auto_retune(initiator="codex", limit=10)

        self.assertEqual(receipt.status, "success")
        self.assertEqual(receipt.applied_actions, ["tighten_knowledge_input_or_prompt", "raise_evidence_supply_or_retune_threshold"])
        self.assertIsNotNone(receipt.review_summary_ref)

        updated_lock = json.loads((self.repo_root / receipt.lock_ref).read_text())
        self.assertEqual(updated_lock["runtime"]["insight"]["min_evidence"], 2)
        self.assertEqual(
            updated_lock["prompts"]["knowledge_writer"]["domain_appendix"]["network"],
            "必须明确 root cause、验证命令和回滚点。",
        )

    def test_inject_feishu_link_records_failure_receipt_when_fetch_fails(self):
        from automation.pipeline.app import ForgeApp

        app = ForgeApp(self.repo_root, feishu_fetcher=FakeFeishuFetcher(error="auth required"))
        receipt = app.inject_feishu_link(
            "https://example.feishu.cn/docx/abc123",
            source="shared feishu note",
            initiator="codex",
        )

        self.assertEqual(receipt.status, "failed")
        self.assertIsNone(receipt.raw_ref)
        self.assertIsNotNone(receipt.failure_ref)

        failure_payload = json.loads((self.repo_root / receipt.failure_ref).read_text())
        self.assertEqual(failure_payload["input_kind"], "feishu_link")
        self.assertIn("auth required", failure_payload["error"])

        archived_cases = sorted((self.repo_root / "state" / "failure_cases" / "inject").glob("*.json"))
        self.assertEqual(len(archived_cases), 1)
        archived_payload = json.loads(archived_cases[0].read_text())
        self.assertEqual(archived_payload["category"], "ingest_fetch_failure")
        self.assertEqual(archived_payload["replay"]["command"], "inject_feishu_link")

    def test_inject_feishu_link_uses_fetcher_payload_when_fetch_succeeds(self):
        from automation.pipeline.app import ForgeApp

        fetcher = FakeFeishuFetcher(
            payload={
                "title": "Feishu Gateway Note",
                "content": (
                    "Context:\n"
                    "The document captured the same DNS outage.\n\n"
                    "Root cause:\n"
                    "The Wi-Fi gateway injected fake-ip DNS replies.\n\n"
                    "Fix steps:\n"
                    "- Change the resolver to 1.1.1.1.\n\n"
                    "Verification:\n"
                    "- Public websites open again.\n"
                ),
                "source_ref": "docx:abc123",
            }
        )
        app = ForgeApp(self.repo_root, feishu_fetcher=fetcher)
        receipt = app.inject_feishu_link(
            "https://example.feishu.cn/docx/abc123",
            source="feishu import",
            initiator="codex",
            promote_knowledge=True,
        )

        self.assertEqual(receipt.status, "success")
        self.assertIsNotNone(receipt.raw_ref)
        self.assertIsNotNone(receipt.knowledge_ref)

        snapshot = json.loads((self.repo_root / receipt.snapshot_ref).read_text())
        self.assertEqual(snapshot["source_ref"], "docx:abc123")
        self.assertIn("The Wi-Fi gateway injected fake-ip DNS replies.", snapshot["content"])

    def test_tune_updates_runtime_lock_from_natural_language(self):
        from automation.pipeline.app import ForgeApp

        app = ForgeApp(self.repo_root)
        receipt = app.tune(
            "把 insight 生成改得更保守：evidence 至少 3 篇 knowledge，judge 改用更强模型。",
            initiator="codex",
        )

        self.assertEqual(receipt.status, "success")
        self.assertTrue(receipt.lock_ref.endswith("automation/compiled/runtime.lock.json"))
        lock_payload = json.loads((self.repo_root / receipt.lock_ref).read_text())
        self.assertEqual(lock_payload["runtime"]["insight"]["min_evidence"], 3)
        self.assertEqual(lock_payload["runtime"]["insight"]["judge_profile"], "judge_strong")

        patch_payload = json.loads((self.repo_root / receipt.receipt_ref).read_text())
        self.assertEqual(len(patch_payload["patches"]), 2)

    def test_runtime_reads_lock_before_promoting_to_knowledge(self):
        from automation.pipeline.app import ForgeApp

        app = ForgeApp(self.repo_root)
        lock_path = self.repo_root / "automation" / "compiled" / "runtime.lock.json"
        lock_payload = json.loads(lock_path.read_text())
        lock_payload["runtime"]["knowledge"]["min_chars"] = 1000
        lock_path.write_text(json.dumps(lock_payload, indent=2) + "\n")

        receipt = app.inject_text(
            text=(
                "Context:\n"
                "This note is intentionally shorter than the tuned threshold.\n\n"
                "Root cause:\n"
                "A configuration default was too optimistic.\n\n"
                "Fix steps:\n"
                "- Raise the threshold.\n\n"
                "Verification:\n"
                "- Observe that promotion is skipped.\n"
            ),
            title="Threshold check",
            source="manual note",
            promote_knowledge=True,
        )

        self.assertIsNone(receipt.knowledge_ref)

    def test_llm_knowledge_pipeline_persists_candidate_review_and_judge_artifacts(self):
        from automation.pipeline.app import ForgeApp

        llm_client = FakeKnowledgeClient(
            candidate={
                "title": "Gateway DNS repair",
                "context": "The incident started after a gateway reboot.",
                "root_cause": "The upstream resolver injected fake-ip ranges.",
                "fix_steps": ["Override resolv.conf to 1.1.1.1", "Restart the affected service"],
                "verification": ["dig github.com returns public IPs", "curl https://openai.com succeeds"],
                "related": ["knowledge/troubleshooting/openclaw-network-dns-fix-2026-04-01.md"],
                "tags": ["network", "dns"],
                "confidence": 0.94,
            },
            critique={
                "issues": [],
                "requires_downgrade": False,
                "summary": "Root cause and verification are explicit.",
            },
            verdict={
                "score": 0.95,
                "decision": "publish",
                "status": "active",
                "reason": "Meets the release bar.",
            },
        )
        app = ForgeApp(self.repo_root, knowledge_client=llm_client)

        receipt = app.inject_text(
            text=(
                "A messy incident note that still needs LLM normalization.\n"
                "Gateway DNS started failing after reboot. dig returned fake-ip ranges.\n"
            ),
            title="Gateway DNS repair",
            source="manual note",
            tags=["network", "dns"],
            initiator="codex",
            promote_knowledge=True,
        )

        self.assertEqual(receipt.pipeline_mode, "llm")
        self.assertIsNotNone(receipt.candidate_ref)
        self.assertIsNotNone(receipt.critic_ref)
        self.assertIsNotNone(receipt.judge_ref)
        self.assertIsNotNone(receipt.llm_trace_ref)
        self.assertEqual(receipt.relay_request_ids, ["relay-write", "relay-critic", "relay-judge"])

        candidate_payload = json.loads((self.repo_root / receipt.candidate_ref).read_text())
        critique_payload = json.loads((self.repo_root / receipt.critic_ref).read_text())
        judge_payload = json.loads((self.repo_root / receipt.judge_ref).read_text())
        llm_trace_payload = json.loads((self.repo_root / receipt.llm_trace_ref).read_text())
        receipt_payload = json.loads((self.repo_root / receipt.receipt_ref).read_text())
        self.assertEqual(candidate_payload["root_cause"], "The upstream resolver injected fake-ip ranges.")
        self.assertEqual(critique_payload["summary"], "Root cause and verification are explicit.")
        self.assertEqual(judge_payload["status"], "active")
        self.assertEqual(receipt_payload["relay_request_ids"], ["relay-write", "relay-critic", "relay-judge"])
        self.assertEqual(llm_trace_payload["schema_version"], "llm_trace/v1")
        self.assertEqual(llm_trace_payload["pipeline_mode"], "llm")
        self.assertEqual([item["stage"] for item in llm_trace_payload["calls"]], ["write", "critique", "judge"])
        self.assertEqual(llm_trace_payload["calls"][0]["provider"], "openai")
        self.assertEqual(llm_trace_payload["calls"][0]["api_base"], "https://relay.example/v1")
        self.assertEqual(llm_trace_payload["calls"][0]["relay_request_id"], "relay-write")
        self.assertEqual(llm_trace_payload["calls"][1]["relay_request_id"], "relay-critic")
        self.assertEqual(llm_trace_payload["calls"][2]["response_id"], "resp-judge")
        self.assertEqual(llm_trace_payload["calls"][2]["relay_request_id"], "relay-judge")

        knowledge_text = (self.repo_root / receipt.knowledge_ref).read_text()
        self.assertIn("status: active", knowledge_text)
        self.assertIn("The upstream resolver injected fake-ip ranges.", knowledge_text)
        self.assertIn("Judge score: `0.95`", knowledge_text)

    def test_knowledge_pipeline_accepts_generic_client_interface(self):
        from automation.pipeline.app import ForgeApp

        app = ForgeApp(self.repo_root, knowledge_client=GenericKnowledgeInterfaceClient())

        receipt = app.inject_text(
            text=(
                "Sparse SSH incident note with enough body to pass the runtime threshold. "
                "The operator replaced the container and the host key drifted."
            ),
            title="SSH host key mismatch",
            source="manual note",
            tags=["ssh"],
            promote_knowledge=True,
        )

        self.assertEqual(receipt.status, "success")
        self.assertEqual(receipt.pipeline_mode, "llm")
        knowledge_text = (self.repo_root / receipt.knowledge_ref).read_text()
        self.assertIn("status: active", knowledge_text)
        self.assertIn("Generic judge passed.", knowledge_text)

    def test_llm_judge_can_downgrade_knowledge_to_draft(self):
        from automation.pipeline.app import ForgeApp

        llm_client = FakeKnowledgeClient(
            candidate={
                "title": "Ambiguous SSH note",
                "context": "The incident note is incomplete.",
                "root_cause": "The evidence is still weak.",
                "fix_steps": ["Collect more logs"],
                "verification": ["Not yet verified"],
                "related": [],
                "tags": ["ssh"],
                "confidence": 0.51,
            },
            critique={
                "issues": ["Verification is too weak."],
                "requires_downgrade": True,
                "summary": "The candidate should stay draft.",
            },
            verdict={
                "score": 0.41,
                "decision": "downgrade",
                "status": "draft",
                "reason": "Below minimum judge threshold.",
            },
        )
        app = ForgeApp(self.repo_root, knowledge_client=llm_client)

        receipt = app.inject_text(
            text=(
                "Sparse SSH incident note with enough body to pass the runtime threshold. "
                "The operator only captured fragments, the evidence was weak, and the system "
                "still needs more logs before this can become active knowledge."
            ),
            title="Ambiguous SSH note",
            source="manual note",
            tags=["ssh"],
            promote_knowledge=True,
        )

        knowledge_text = (self.repo_root / receipt.knowledge_ref).read_text()
        self.assertIn("status: draft", knowledge_text)
        self.assertIn("Below minimum judge threshold.", knowledge_text)

        failure_cases = sorted((self.repo_root / "state" / "failure_cases" / "knowledge").glob("*.json"))
        self.assertEqual(len(failure_cases), 1)
        failure_payload = json.loads(failure_cases[0].read_text())
        self.assertEqual(failure_payload["refs"]["receipt_ref"], receipt.receipt_ref)
        self.assertEqual(failure_payload["refs"]["llm_trace_ref"], receipt.llm_trace_ref)
        self.assertEqual(failure_payload["refs"]["relay_request_ids"], ["relay-write", "relay-critic", "relay-judge"])

    def test_llm_knowledge_fallback_preserves_partial_trace_for_failed_writer(self):
        from automation.pipeline.app import ForgeApp

        app = ForgeApp(self.repo_root, knowledge_client=TraceThenFailKnowledgeClient())

        receipt = app.inject_text(
            text=(
                "A long enough incident note to trigger knowledge promotion. "
                "The gateway DNS became unstable after the reboot and the relay path failed."
            ),
            title="Gateway DNS fallback trace",
            source="manual note",
            tags=["network", "dns"],
            promote_knowledge=True,
        )

        self.assertEqual(receipt.status, "success")
        self.assertEqual(receipt.pipeline_mode, "heuristic-fallback")
        self.assertIsNotNone(receipt.knowledge_ref)
        self.assertIsNotNone(receipt.llm_trace_ref)
        self.assertEqual(receipt.relay_request_ids, ["relay-failed-write"])

        llm_trace_payload = json.loads((self.repo_root / receipt.llm_trace_ref).read_text())
        receipt_payload = json.loads((self.repo_root / receipt.receipt_ref).read_text())
        self.assertEqual(llm_trace_payload["schema_version"], "llm_trace/v1")
        self.assertEqual(llm_trace_payload["pipeline_mode"], "llm")
        self.assertEqual([item["stage"] for item in llm_trace_payload["calls"]], ["write"])
        self.assertEqual(llm_trace_payload["calls"][0]["prompt_name"], "knowledge_writer")
        self.assertEqual(llm_trace_payload["calls"][0]["response_id"], "")
        self.assertEqual(llm_trace_payload["calls"][0]["relay_request_id"], "relay-failed-write")
        self.assertEqual(receipt_payload["relay_request_ids"], ["relay-failed-write"])

    def test_llm_insight_fallback_preserves_partial_trace_for_failed_writer(self):
        from automation.pipeline.app import ForgeApp

        self._write_knowledge_fixture(
            "knowledge/troubleshooting/gateway-dns.md",
            "Gateway DNS repair",
            ["network", "dns"],
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/container-dns.md",
            "Container DNS repair",
            ["network", "dns"],
        )

        app = ForgeApp(self.repo_root, insight_client=TraceThenFailInsightClient())
        receipt = app.synthesize_insights(initiator="codex")

        self.assertEqual(receipt.status, "success")
        self.assertEqual(receipt.pipeline_mode, "heuristic-fallback")
        self.assertIsNotNone(receipt.insight_ref)
        self.assertIsNotNone(receipt.llm_trace_ref)
        self.assertEqual(receipt.relay_request_ids, ["relay-failed-insight-write"])

        llm_trace_payload = json.loads((self.repo_root / receipt.llm_trace_ref).read_text())
        receipt_payload = json.loads((self.repo_root / receipt.receipt_ref).read_text())
        self.assertEqual(llm_trace_payload["schema_version"], "llm_trace/v1")
        self.assertEqual(llm_trace_payload["pipeline_mode"], "llm")
        self.assertEqual([item["stage"] for item in llm_trace_payload["calls"]], ["write"])
        self.assertEqual(llm_trace_payload["calls"][0]["prompt_name"], "insight_writer")
        self.assertEqual(llm_trace_payload["calls"][0]["response_id"], "")
        self.assertEqual(llm_trace_payload["calls"][0]["relay_request_id"], "relay-failed-insight-write")
        self.assertEqual(receipt_payload["relay_request_ids"], ["relay-failed-insight-write"])

    def test_inject_text_returns_failed_receipt_when_llm_and_fallback_both_fail(self):
        from automation.pipeline.app import ForgeApp

        app = ForgeApp(self.repo_root, knowledge_client=TraceThenFailKnowledgeClient())
        app.fallback_knowledge_client = FailingFallbackKnowledgeClient()

        receipt = app.inject_text(
            text=(
                "A long enough incident note to trigger knowledge promotion. "
                "The gateway DNS became unstable after the reboot and both the llm "
                "path and the fallback path failed."
            ),
            title="Gateway DNS double failure",
            source="manual note",
            tags=["network", "dns"],
            promote_knowledge=True,
        )

        self.assertEqual(receipt.status, "failed")
        self.assertIsNotNone(receipt.receipt_ref)
        self.assertIsNotNone(receipt.snapshot_ref)
        self.assertIsNotNone(receipt.raw_ref)
        self.assertIsNotNone(receipt.llm_trace_ref)
        self.assertEqual(receipt.relay_request_ids, ["relay-failed-write"])
        self.assertIn("fallback writer unavailable", receipt.message)

        receipt_payload = json.loads((self.repo_root / receipt.receipt_ref).read_text())
        llm_trace_payload = json.loads((self.repo_root / receipt.llm_trace_ref).read_text())
        self.assertEqual(receipt_payload["status"], "failed")
        self.assertEqual(receipt_payload["relay_request_ids"], ["relay-failed-write"])
        self.assertEqual(llm_trace_payload["calls"][0]["relay_request_id"], "relay-failed-write")

        failure_cases = sorted((self.repo_root / "state" / "failure_cases" / "knowledge").glob("*.json"))
        self.assertEqual(len(failure_cases), 1)
        failure_payload = json.loads(failure_cases[0].read_text())
        self.assertEqual(failure_payload["category"], "knowledge_pipeline_failure")
        self.assertEqual(failure_payload["refs"]["receipt_ref"], receipt.receipt_ref)
        self.assertEqual(failure_payload["refs"]["llm_trace_ref"], receipt.llm_trace_ref)
        self.assertEqual(failure_payload["refs"]["relay_request_ids"], ["relay-failed-write"])

    def test_synthesize_insights_returns_failed_receipt_when_llm_and_fallback_both_fail(self):
        from automation.pipeline.app import ForgeApp

        self._write_knowledge_fixture(
            "knowledge/troubleshooting/gateway-dns.md",
            "Gateway DNS repair",
            ["network", "dns"],
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/container-dns.md",
            "Container DNS repair",
            ["network", "dns"],
        )

        app = ForgeApp(self.repo_root, insight_client=TraceThenFailInsightClient())
        app.fallback_insight_client = FailingFallbackInsightClient()

        receipt = app.synthesize_insights(initiator="codex")

        self.assertEqual(receipt.status, "failed")
        self.assertIsNotNone(receipt.receipt_ref)
        self.assertIsNotNone(receipt.llm_trace_ref)
        self.assertEqual(receipt.relay_request_ids, ["relay-failed-insight-write"])
        self.assertIn("fallback insight writer unavailable", receipt.message)

        receipt_payload = json.loads((self.repo_root / receipt.receipt_ref).read_text())
        llm_trace_payload = json.loads((self.repo_root / receipt.llm_trace_ref).read_text())
        self.assertEqual(receipt_payload["status"], "failed")
        self.assertEqual(receipt_payload["relay_request_ids"], ["relay-failed-insight-write"])
        self.assertEqual(llm_trace_payload["calls"][0]["relay_request_id"], "relay-failed-insight-write")

        failure_cases = sorted((self.repo_root / "state" / "failure_cases" / "insights").glob("*.json"))
        self.assertEqual(len(failure_cases), 1)
        failure_payload = json.loads(failure_cases[0].read_text())
        self.assertEqual(failure_payload["category"], "insight_pipeline_failure")
        self.assertEqual(failure_payload["refs"]["receipt_ref"], receipt.receipt_ref)
        self.assertEqual(failure_payload["refs"]["llm_trace_ref"], receipt.llm_trace_ref)
        self.assertEqual(failure_payload["refs"]["relay_request_ids"], ["relay-failed-insight-write"])

    def test_tune_can_switch_knowledge_writer_profile_and_network_appendix(self):
        from automation.pipeline.app import ForgeApp

        app = ForgeApp(self.repo_root)
        receipt = app.tune(
            "network 类问题提高 root cause 解释权重，raw -> knowledge 继续用便宜模型。",
            initiator="codex",
        )

        self.assertEqual(receipt.status, "success")
        lock_payload = json.loads((self.repo_root / receipt.lock_ref).read_text())
        self.assertEqual(lock_payload["runtime"]["knowledge"]["writer_profile"], "writer_cheap")
        self.assertEqual(
            lock_payload["prompts"]["knowledge_writer"]["domain_appendix"]["network"],
            "必须明确 root cause、验证命令和回滚点。",
        )

    def test_synthesize_insights_creates_artifacts_and_markdown(self):
        from automation.pipeline.app import ForgeApp

        self._write_knowledge_fixture(
            "knowledge/troubleshooting/gateway-dns.md",
            "Gateway DNS repair",
            ["network", "dns"],
            body="The gateway DNS resolver injected fake-ip answers.",
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/container-dns.md",
            "Container DNS repair",
            ["network", "dns"],
            body="The container inherited the poisoned resolver from the gateway.",
        )

        insight_client = FakeInsightClient(
            candidate={
                "title": "容器网络问题中的上游 DNS 失真模式",
                "observation": "Multiple incidents showed fake-ip DNS results upstream.",
                "analysis": "The gateway DNS layer distorted downstream connectivity checks.",
                "application": "Check upstream resolver health before debugging containers.",
                "impact": "high",
                "evidence": [
                    "knowledge/troubleshooting/gateway-dns.md",
                    "knowledge/troubleshooting/container-dns.md",
                ],
                "tags": ["network", "dns", "pattern"],
                "confidence": 0.92,
            }
        )
        app = ForgeApp(self.repo_root, insight_client=insight_client)

        receipt = app.synthesize_insights(initiator="codex")

        self.assertEqual(receipt.status, "success")
        self.assertEqual(receipt.pipeline_mode, "llm")
        self.assertIsNotNone(receipt.insight_ref)
        self.assertIsNotNone(receipt.candidate_ref)
        self.assertIsNotNone(receipt.critic_ref)
        self.assertIsNotNone(receipt.judge_ref)
        self.assertIsNotNone(receipt.llm_trace_ref)
        self.assertIsNotNone(receipt.evidence_trace_ref)
        self.assertEqual(receipt.relay_request_ids, ["relay-insight-write", "relay-insight-critic", "relay-insight-judge"])

        insight_text = (self.repo_root / receipt.insight_ref).read_text()
        llm_trace_payload = json.loads((self.repo_root / receipt.llm_trace_ref).read_text())
        evidence_trace_payload = json.loads((self.repo_root / receipt.evidence_trace_ref).read_text())
        receipt_payload = json.loads((self.repo_root / receipt.receipt_ref).read_text())
        self.assertIn("status: active", insight_text)
        self.assertIn("impact: high", insight_text)
        self.assertIn("knowledge/troubleshooting/gateway-dns.md", insight_text)
        self.assertIn("Judge score: `0.91`", insight_text)
        self.assertEqual(
            set(evidence_trace_payload["selected_paths"]),
            {
                "knowledge/troubleshooting/gateway-dns.md",
                "knowledge/troubleshooting/container-dns.md",
            },
        )
        self.assertEqual(receipt_payload["evidence_trace_ref"], receipt.evidence_trace_ref)
        self.assertEqual(receipt_payload["relay_request_ids"], ["relay-insight-write", "relay-insight-critic", "relay-insight-judge"])
        self.assertEqual(llm_trace_payload["schema_version"], "llm_trace/v1")
        self.assertEqual([item["stage"] for item in llm_trace_payload["calls"]], ["write", "critique", "judge"])
        self.assertEqual(llm_trace_payload["calls"][0]["prompt_name"], "insight_writer")
        self.assertEqual(llm_trace_payload["calls"][0]["relay_request_id"], "relay-insight-write")
        self.assertEqual(llm_trace_payload["calls"][1]["relay_request_id"], "relay-insight-critic")
        self.assertEqual(llm_trace_payload["calls"][2]["relay_request_id"], "relay-insight-judge")

    def test_synthesize_insights_dry_run_writes_preview_without_creating_insight(self):
        from automation.pipeline.app import ForgeApp

        self._write_knowledge_fixture(
            "knowledge/troubleshooting/gateway-dns.md",
            "Gateway DNS repair",
            ["network", "dns"],
            body="The gateway DNS resolver injected fake-ip answers.",
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/container-dns.md",
            "Container DNS repair",
            ["network", "dns"],
            body="The container inherited the poisoned resolver from the gateway.",
        )

        app = ForgeApp(self.repo_root, insight_client=GenericInsightInterfaceClient())
        receipt = app.synthesize_insights(initiator="codex", dry_run=True)

        self.assertEqual(receipt.status, "success")
        self.assertTrue(receipt.dry_run)
        self.assertIsNone(receipt.confirmed_from_receipt_ref)
        self.assertEqual(
            set(receipt.evidence_refs),
            {
                "knowledge/troubleshooting/gateway-dns.md",
                "knowledge/troubleshooting/container-dns.md",
            },
        )
        self.assertEqual(len(receipt.evidence_manifest), 2)
        self.assertIsNotNone(receipt.evidence_trace_ref)
        self.assertIsNone(receipt.insight_ref)
        self.assertIsNone(receipt.candidate_ref)
        self.assertIsNone(receipt.critic_ref)
        self.assertIsNone(receipt.judge_ref)
        self.assertEqual(sorted((self.repo_root / "insights").glob("**/*.md")), [])

        receipt_payload = json.loads((self.repo_root / receipt.receipt_ref).read_text(encoding="utf-8"))
        self.assertTrue(receipt_payload["dry_run"])
        self.assertEqual(receipt_payload["confirmed_from_receipt_ref"], None)
        self.assertEqual(len(receipt_payload["evidence_manifest"]), 2)

    def test_synthesize_insights_can_confirm_a_dry_run_receipt(self):
        from automation.pipeline.app import ForgeApp

        self._write_knowledge_fixture(
            "knowledge/troubleshooting/gateway-dns.md",
            "Gateway DNS repair",
            ["network", "dns"],
            body="The gateway DNS resolver injected fake-ip answers.",
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/container-dns.md",
            "Container DNS repair",
            ["network", "dns"],
            body="The container inherited the poisoned resolver from the gateway.",
        )

        app = ForgeApp(self.repo_root, insight_client=GenericInsightInterfaceClient())
        preview = app.synthesize_insights(initiator="codex", dry_run=True)
        receipt = app.synthesize_insights(initiator="codex", confirm_receipt_ref=preview.receipt_ref)

        self.assertEqual(preview.status, "success")
        self.assertTrue(preview.dry_run)
        self.assertEqual(receipt.status, "success")
        self.assertFalse(receipt.dry_run)
        self.assertEqual(receipt.confirmed_from_receipt_ref, preview.receipt_ref)
        self.assertEqual(set(receipt.evidence_refs), set(preview.evidence_refs))
        self.assertEqual(receipt.evidence_trace_ref, preview.evidence_trace_ref)
        self.assertIsNotNone(receipt.insight_ref)
        self.assertEqual(len(sorted((self.repo_root / "insights").glob("**/*.md"))), 1)

    def test_synthesize_insights_confirm_fails_for_non_preview_receipt(self):
        from automation.pipeline.app import ForgeApp

        self._write_knowledge_fixture(
            "knowledge/troubleshooting/gateway-dns.md",
            "Gateway DNS repair",
            ["network", "dns"],
            body="The gateway DNS resolver injected fake-ip answers.",
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/container-dns.md",
            "Container DNS repair",
            ["network", "dns"],
            body="The container inherited the poisoned resolver from the gateway.",
        )

        app = ForgeApp(self.repo_root, insight_client=GenericInsightInterfaceClient())
        direct = app.synthesize_insights(initiator="codex")
        receipt = app.synthesize_insights(initiator="codex", confirm_receipt_ref=direct.receipt_ref)

        self.assertEqual(direct.status, "success")
        self.assertFalse(getattr(direct, "dry_run", False))
        self.assertEqual(receipt.status, "failed")
        self.assertFalse(receipt.dry_run)
        self.assertEqual(receipt.confirmed_from_receipt_ref, direct.receipt_ref)
        self.assertIn("dry-run insight synthesis receipt", receipt.message)

    def test_synthesize_insights_confirm_fails_when_evidence_drifted(self):
        from automation.pipeline.app import ForgeApp

        self._write_knowledge_fixture(
            "knowledge/troubleshooting/gateway-dns.md",
            "Gateway DNS repair",
            ["network", "dns"],
            body="The gateway DNS resolver injected fake-ip answers.",
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/container-dns.md",
            "Container DNS repair",
            ["network", "dns"],
            body="The container inherited the poisoned resolver from the gateway.",
        )

        app = ForgeApp(self.repo_root, insight_client=GenericInsightInterfaceClient())
        preview = app.synthesize_insights(initiator="codex", dry_run=True)
        drifted_path = self.repo_root / preview.evidence_refs[0]
        drifted_path.write_text(
            drifted_path.read_text(encoding="utf-8") + "\nDrifted after preview.\n",
            encoding="utf-8",
        )

        receipt = app.synthesize_insights(initiator="codex", confirm_receipt_ref=preview.receipt_ref)

        self.assertEqual(receipt.status, "failed")
        self.assertFalse(receipt.dry_run)
        self.assertEqual(receipt.confirmed_from_receipt_ref, preview.receipt_ref)
        self.assertEqual(receipt.evidence_trace_ref, preview.evidence_trace_ref)
        self.assertIn("drift", receipt.message.lower())

    def test_synthesize_insights_renders_pattern_ladder_mitigation_sections(self):
        from automation.pipeline.app import ForgeApp

        self._write_knowledge_fixture(
            "knowledge/troubleshooting/gateway-dns.md",
            "Gateway DNS repair",
            ["network", "dns", "ipv6"],
            body="The gateway DNS resolver injected fake-ip answers.",
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/container-dns.md",
            "Container DNS repair",
            ["network", "dns", "ipv6"],
            body="The container inherited the poisoned resolver from the gateway.",
        )

        insight_client = FakeInsightClient(
            candidate={
                "title": "容器网络问题中的上游 DNS 失真模式",
                "observation": "Multiple incidents showed fake-ip DNS results upstream.",
                "pattern": "Treat upstream DNS distortion as a control-plane pattern.",
                "diagnostic_ladder": [
                    "Check resolvectl status first.",
                    "Validate each upstream DNS independently.",
                ],
                "mitigation": [
                    "Pin a trusted resolver on the client.",
                    "Disable stray RA/RDNSS on secondary routers.",
                ],
                "anti_patterns": [
                    "Do not assume the default gateway is the only source of truth.",
                ],
                "impact": "high",
                "evidence": [
                    "knowledge/troubleshooting/gateway-dns.md",
                    "knowledge/troubleshooting/container-dns.md",
                ],
                "tags": ["network", "dns", "pattern"],
                "confidence": 0.92,
            }
        )
        app = ForgeApp(self.repo_root, insight_client=insight_client)

        receipt = app.synthesize_insights(initiator="codex")

        insight_text = (self.repo_root / receipt.insight_ref).read_text(encoding="utf-8")
        self.assertIn("## Pattern", insight_text)
        self.assertIn("## Diagnostic Ladder", insight_text)
        self.assertIn("## Mitigation Strategy", insight_text)
        self.assertIn("## Anti-Patterns", insight_text)
        self.assertIn("Check resolvectl status first.", insight_text)
        self.assertIn("Pin a trusted resolver on the client.", insight_text)
        self.assertIn("Do not assume the default gateway is the only source of truth.", insight_text)

    def test_llm_judge_can_downgrade_insight_to_draft_and_archive_trace_ref(self):
        from automation.pipeline.app import ForgeApp

        self._write_knowledge_fixture(
            "knowledge/troubleshooting/gateway-dns.md",
            "Gateway DNS repair",
            ["network", "dns"],
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/container-dns.md",
            "Container DNS repair",
            ["network", "dns"],
        )

        insight_client = FakeInsightClient(
            candidate={
                "title": "DNS pattern draft",
                "observation": "The pattern is still weak.",
                "analysis": "We need more evidence before publishing.",
                "application": "Collect more incidents first.",
                "impact": "medium",
                "evidence": [
                    "knowledge/troubleshooting/gateway-dns.md",
                    "knowledge/troubleshooting/container-dns.md",
                ],
                "tags": ["network", "dns", "pattern"],
                "confidence": 0.62,
            },
            critique={
                "issues": ["The evidence is still too weak."],
                "requires_downgrade": True,
                "summary": "Keep this insight in draft.",
            },
            verdict={
                "score": 0.45,
                "decision": "downgrade",
                "status": "draft",
                "reason": "Below minimum judge threshold.",
            },
        )
        app = ForgeApp(self.repo_root, insight_client=insight_client)

        receipt = app.synthesize_insights(initiator="codex")

        self.assertEqual(receipt.status, "success")
        self.assertEqual(receipt.pipeline_mode, "llm")
        self.assertIsNotNone(receipt.llm_trace_ref)

        insight_text = (self.repo_root / receipt.insight_ref).read_text()
        self.assertIn("status: draft", insight_text)
        self.assertIn("Below minimum judge threshold.", insight_text)

        failure_cases = sorted((self.repo_root / "state" / "failure_cases" / "insights").glob("*.json"))
        self.assertEqual(len(failure_cases), 1)
        failure_payload = json.loads(failure_cases[0].read_text())
        self.assertEqual(failure_payload["refs"]["receipt_ref"], receipt.receipt_ref)
        self.assertEqual(failure_payload["refs"]["evidence_trace_ref"], receipt.evidence_trace_ref)
        self.assertEqual(failure_payload["refs"]["llm_trace_ref"], receipt.llm_trace_ref)
        self.assertEqual(failure_payload["refs"]["relay_request_ids"], ["relay-insight-write", "relay-insight-critic", "relay-insight-judge"])

    def test_insight_pipeline_accepts_generic_client_interface(self):
        from automation.pipeline.app import ForgeApp

        self._write_knowledge_fixture(
            "knowledge/troubleshooting/gateway-dns.md",
            "Gateway DNS repair",
            ["network", "dns"],
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/container-dns.md",
            "Container DNS repair",
            ["network", "dns"],
        )

        app = ForgeApp(self.repo_root, insight_client=GenericInsightInterfaceClient())
        receipt = app.synthesize_insights(initiator="codex")

        self.assertEqual(receipt.status, "success")
        self.assertEqual(receipt.pipeline_mode, "llm")
        insight_text = (self.repo_root / receipt.insight_ref).read_text()
        self.assertIn("Generic insight judge passed.", insight_text)

    def test_synthesize_insights_skips_when_evidence_is_below_lock_threshold(self):
        from automation.pipeline.app import ForgeApp

        self._write_knowledge_fixture(
            "knowledge/troubleshooting/gateway-dns.md",
            "Gateway DNS repair",
            ["network", "dns"],
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/container-dns.md",
            "Container DNS repair",
            ["network", "dns"],
        )

        app = ForgeApp(self.repo_root)
        lock_path = self.repo_root / "automation" / "compiled" / "runtime.lock.json"
        lock_payload = json.loads(lock_path.read_text())
        lock_payload["runtime"]["insight"]["min_evidence"] = 3
        lock_path.write_text(json.dumps(lock_payload, indent=2) + "\n")

        receipt = app.synthesize_insights()

        self.assertEqual(receipt.status, "skipped")
        self.assertIsNone(receipt.insight_ref)
        self.assertIn("min_evidence", receipt.message)

        failure_cases = sorted((self.repo_root / "state" / "failure_cases" / "insights").glob("*.json"))
        self.assertEqual(len(failure_cases), 1)
        failure_payload = json.loads(failure_cases[0].read_text())
        self.assertEqual(failure_payload["status"], "skipped")
        self.assertEqual(failure_payload["refs"]["evidence_trace_ref"], receipt.evidence_trace_ref)
        self.assertEqual(failure_payload["replay"]["command"], "synthesize_insights")

    def test_synthesize_insights_skips_when_only_generic_tags_overlap(self):
        from automation.pipeline.app import ForgeApp

        self._write_knowledge_fixture(
            "knowledge/workflow/note-a.md",
            "Workflow note A",
            ["workflow"],
            body="Generic workflow note.",
        )
        self._write_knowledge_fixture(
            "knowledge/workflow/note-b.md",
            "Workflow note B",
            ["workflow"],
            body="Another generic workflow note.",
        )

        app = ForgeApp(self.repo_root)
        receipt = app.synthesize_insights()

        self.assertEqual(receipt.status, "skipped")
        self.assertIsNotNone(receipt.evidence_trace_ref)
        self.assertIn("no evidence cluster", receipt.message)
        trace_payload = json.loads((self.repo_root / receipt.evidence_trace_ref).read_text())
        self.assertEqual(trace_payload["selected_paths"], [])

    def test_synthesize_insights_ignores_correction_like_knowledge(self):
        from automation.pipeline.app import ForgeApp

        self._write_knowledge_fixture(
            "knowledge/troubleshooting/active-dns.md",
            "Active DNS note",
            ["dns", "network"],
            body="A stable DNS troubleshooting note.",
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/corrected-dns.md",
            "Corrected DNS note",
            ["dns", "network", "corrected"],
            body="A corrected conclusion that should not be used as pattern evidence.",
        )

        app = ForgeApp(self.repo_root)
        receipt = app.synthesize_insights()

        self.assertEqual(receipt.status, "skipped")
        self.assertIn("no evidence cluster", receipt.message)

    def test_synthesize_insights_can_select_retrieval_cohesive_docs_without_shared_specific_tags(self):
        from automation.pipeline.app import ForgeApp

        self._write_knowledge_fixture(
            "knowledge/troubleshooting/gateway-relay.md",
            "Gateway relay rewrite",
            ["gateway", "relay"],
            body=(
                "## Context\n\nThe gateway reboot was followed by github.com resolving to fake-ip answers.\n\n"
                "## Root Cause\n\nBecause the upstream relay rewrote github answers into fake-ip ranges.\n\n"
                "## Verification\n\nThe same fake-ip answers appeared in container traffic.\n"
            ),
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/container-resolver.md",
            "Container resolver fake-ip",
            ["container", "resolver"],
            body=(
                "## Context\n\nContainer traffic failed after github.com started resolving to fake-ip answers.\n\n"
                "## Root Cause\n\nBecause the upstream relay rewrote github answers into fake-ip ranges.\n\n"
                "## Verification\n\nThe same fake-ip answers appeared in pod traffic.\n"
            ),
        )

        app = ForgeApp(self.repo_root, insight_client=GenericInsightInterfaceClient())
        receipt = app.synthesize_insights(initiator="codex")

        self.assertEqual(receipt.status, "success")
        self.assertEqual(
            set(receipt.evidence_refs),
            {
                "knowledge/troubleshooting/gateway-relay.md",
                "knowledge/troubleshooting/container-resolver.md",
            },
        )
        trace_payload = json.loads((self.repo_root / receipt.evidence_trace_ref).read_text())
        self.assertIn("retrieval_graph", trace_payload["candidate_generation_modes"])
        self.assertEqual(
            set(trace_payload["selected_paths"]),
            {
                "knowledge/troubleshooting/gateway-relay.md",
                "knowledge/troubleshooting/container-resolver.md",
            },
        )

    def test_synthesize_insights_prefers_cohesive_component_over_broader_tag_overlap(self):
        from automation.pipeline.app import ForgeApp

        self._write_knowledge_fixture(
            "knowledge/troubleshooting/gateway-fake-ip-a.md",
            "Gateway fake-ip incident A",
            ["network", "dns", "gateway"],
            body=(
                "The gateway resolver injected fake-ip answers after the router reboot.\n"
                "Root cause was upstream resolver poisoning on the gateway path.\n"
            ),
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/gateway-fake-ip-b.md",
            "Gateway fake-ip incident B",
            ["network", "dns", "gateway"],
            body=(
                "The gateway resolver kept returning fake-ip answers to all clients.\n"
                "Root cause again pointed to gateway-side resolver poisoning.\n"
            ),
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/ssh-reverse-lookup.md",
            "SSH reverse lookup slowdown",
            ["network", "dns", "ssh"],
            body=(
                "SSH login stalled because reverse lookup blocked banner rendering.\n"
                "Fix by disabling slow reverse lookup on the remote path.\n"
            ),
        )

        app = ForgeApp(self.repo_root)
        receipt = app.synthesize_insights(initiator="codex")

        self.assertEqual(receipt.status, "success")
        self.assertEqual(
            set(receipt.evidence_refs),
            {
                "knowledge/troubleshooting/gateway-fake-ip-a.md",
                "knowledge/troubleshooting/gateway-fake-ip-b.md",
            },
        )

    def test_synthesize_insights_skips_when_shared_tags_lack_signal_cohesion(self):
        from automation.pipeline.app import ForgeApp

        self._write_knowledge_fixture(
            "knowledge/troubleshooting/router-dns.md",
            "Router DNS repair",
            ["network", "dns", "router"],
            body=(
                "The router injected forged answers after reboot.\n"
                "The fix was to pin the resolver away from the router.\n"
            ),
        )
        self._write_knowledge_fixture(
            "knowledge/troubleshooting/ssh-banner.md",
            "SSH banner slowdown",
            ["network", "dns", "ssh"],
            body=(
                "SSH banner rendering stalled because remote reverse lookup timed out.\n"
                "Disable banner-time reverse lookup on the SSH path.\n"
            ),
        )

        app = ForgeApp(self.repo_root)
        receipt = app.synthesize_insights(initiator="codex")

        self.assertEqual(receipt.status, "skipped")
        self.assertIn("no evidence cluster", receipt.message)


if __name__ == "__main__":
    unittest.main()
