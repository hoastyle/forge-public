from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Union

from .controller import (
    apply_patches,
    compile_intent_to_patches,
    load_or_create_golden_cases,
    load_or_create_patch_schema,
    load_or_create_runtime_lock,
    run_replay_evals,
    validate_patch_bundle,
)
from .documents import load_knowledge_documents, load_raw_documents
from .errors import ForgeOperatorError
from .explain import build_insight_explanation
from .fetchers import LarkCliFeishuFetcher
from .initiators import normalize_initiator
from .knowledge_status import KnowledgePublicationStatus, build_knowledge_publication_status
from .llm_client import (
    HeuristicInsightClient,
    HeuristicKnowledgeClient,
    build_default_insight_client,
    build_default_knowledge_client,
)
from .models import (
    AutoRetuneReceipt,
    FailureReviewReceipt,
    IngestReceipt,
    InsightSynthesisReceipt,
    Patch,
    RawPromotionBatchReceipt,
    RawPromotionReceipt,
    RawReviewReceipt,
    ReadyPromotionBatchReceipt,
    ReviewQueueReceipt,
    ReplayReceipt,
    TuneReceipt,
)
from .validators import (
    determine_status,
    deterministic_candidate_issues,
    deterministic_insight_issues,
    normalize_candidate,
    normalize_critique,
    normalize_insight_candidate,
    normalize_judge,
)


class _PipelineTraceCaptureError(RuntimeError):
    def __init__(self, trace_ref: str, message: str = "partial llm trace captured"):
        super().__init__(message)
        self.trace_ref = trace_ref


class ForgeApp:
    def __init__(
        self,
        repo_root: Path,
        state_root: Optional[Path] = None,
        app_root: Optional[Path] = None,
        feishu_fetcher=None,
        knowledge_client=None,
        insight_client=None,
        clock: Optional[Callable[[], date]] = None,
    ):
        self.repo_root = Path(repo_root)
        self.state_root = Path(state_root) if state_root is not None else self.repo_root / "state"
        self.app_root = Path(app_root) if app_root is not None else self.repo_root
        self.feishu_fetcher = feishu_fetcher or LarkCliFeishuFetcher()
        self._knowledge_client = knowledge_client
        self._insight_client = insight_client
        self._fallback_knowledge_client = HeuristicKnowledgeClient()
        self._fallback_insight_client = HeuristicInsightClient()
        self.clock = clock or date.today
        self._bootstrap()

    @property
    def knowledge_client(self):
        if self._knowledge_client is None:
            self._knowledge_client = build_default_knowledge_client(self.repo_root, app_root=self.app_root)
        return self._knowledge_client

    @property
    def insight_client(self):
        if self._insight_client is None:
            self._insight_client = build_default_insight_client(self.repo_root, app_root=self.app_root)
        return self._insight_client

    @property
    def fallback_knowledge_client(self):
        return self._fallback_knowledge_client

    @fallback_knowledge_client.setter
    def fallback_knowledge_client(self, value):
        self._fallback_knowledge_client = value

    @property
    def fallback_insight_client(self):
        return self._fallback_insight_client

    @fallback_insight_client.setter
    def fallback_insight_client(self, value):
        self._fallback_insight_client = value

    def inject_text(
        self,
        text: str,
        title: Optional[str] = None,
        source: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        initiator: str = "manual",
        promote_knowledge: bool = False,
    ) -> IngestReceipt:
        return self.inject_content(
            input_kind="text",
            content=text,
            source_ref="inline:text",
            title=title,
            source=source or "inline text injection",
            tags=list(tags or []),
            initiator=initiator,
            promote_knowledge=promote_knowledge,
        )

    def inject_content(
        self,
        input_kind: str,
        content: str,
        source_ref: str,
        title: Optional[str] = None,
        source: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        initiator: str = "manual",
        promote_knowledge: bool = False,
    ) -> IngestReceipt:
        initiator = normalize_initiator(initiator)
        normalized_title = title or self._derive_title(content)
        if input_kind == "file" and not normalized_title:
            normalized_title = Path(source_ref).stem
        if not normalized_title:
            normalized_title = "Untitled capture"
        return self._ingest_content(
            input_kind=input_kind,
            content=content,
            source_ref=source_ref,
            title=normalized_title,
            source=source or "{0} injection".format(input_kind),
            tags=list(tags or []),
            initiator=initiator,
            promote_knowledge=promote_knowledge,
        )

    def inject_file(
        self,
        file_path: Path,
        title: Optional[str] = None,
        source: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        initiator: str = "manual",
        promote_knowledge: bool = False,
    ) -> IngestReceipt:
        file_path = Path(file_path)
        content = file_path.read_text(encoding="utf-8")
        return self.inject_content(
            input_kind="file",
            content=content,
            source_ref=str(file_path),
            title=title or file_path.stem,
            source=source or "file import: {0}".format(file_path),
            tags=list(tags or []),
            initiator=initiator,
            promote_knowledge=promote_knowledge,
        )

    def inject_feishu_link(
        self,
        link: str,
        title: Optional[str] = None,
        source: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        initiator: str = "manual",
        promote_knowledge: bool = False,
    ) -> IngestReceipt:
        initiator = normalize_initiator(initiator)
        ingest_id = self._new_id()
        try:
            payload = self.feishu_fetcher.fetch(link)
        except Exception as exc:
            return self._write_failure_receipt(
                ingest_id=ingest_id,
                input_kind="feishu_link",
                title=title or "Feishu import failed",
                source_ref=link,
                initiator=initiator,
                error=str(exc),
                source=source or "feishu import: {0}".format(link),
                tags=list(tags or []),
                promote_knowledge=promote_knowledge,
            )

        return self._ingest_content(
            input_kind="feishu_link",
            content=payload["content"],
            source_ref=payload.get("source_ref", link),
            title=title or payload.get("title") or self._derive_title(payload["content"]),
            source=source or "feishu import: {0}".format(link),
            tags=list(tags or []),
            initiator=initiator,
            promote_knowledge=promote_knowledge,
            ingest_id=ingest_id,
        )

    def replay_failure_case(self, case_ref: Union[str, Path], initiator: str = "manual") -> ReplayReceipt:
        initiator = normalize_initiator(initiator)
        replay_id = self._new_id()
        case_path = self._resolve_repo_path(case_ref)
        replay_command = "unknown"

        try:
            case_payload = json.loads(case_path.read_text(encoding="utf-8"))
            replay_payload = dict(case_payload.get("replay") or {})
            replay_command = str(replay_payload.get("command") or "unknown")
            replay_args = dict(replay_payload.get("args") or {})
            replay_args["initiator"] = initiator

            if replay_command == "inject_text":
                result = self.inject_text(**replay_args)
            elif replay_command == "inject_feishu_link":
                link = replay_args.pop("link")
                result = self.inject_feishu_link(link, **replay_args)
            elif replay_command == "synthesize_insights":
                result = self.synthesize_insights(initiator=initiator)
            else:
                raise ValueError("unsupported replay command: {0}".format(replay_command))

            receipt = ReplayReceipt(
                id=replay_id,
                status="success",
                initiator=initiator,
                case_ref=self._display_path(case_path),
                replay_command=replay_command,
                result_status=result.status,
                result_receipt_ref=result.receipt_ref,
                receipt_ref=None,
                message="replay executed",
            )
        except Exception as exc:
            receipt = ReplayReceipt(
                id=replay_id,
                status="failed",
                initiator=initiator,
                case_ref=self._display_path(case_path),
                replay_command=replay_command,
                result_status="failed",
                result_receipt_ref=None,
                receipt_ref=None,
                message=str(exc),
            )

        receipt_path = self.state_root / "receipts" / "replays" / "{0}.json".format(replay_id)
        self._write_json(receipt_path, receipt.to_dict())
        receipt.receipt_ref = self._relative(receipt_path)
        self._write_json(receipt_path, receipt.to_dict())
        return receipt

    def review_failures(self, initiator: str = "manual", limit: int = 20) -> FailureReviewReceipt:
        initiator = normalize_initiator(initiator)
        review_id = self._new_id()
        failure_cases = self._load_failure_cases(limit=limit)

        if not failure_cases:
            receipt = FailureReviewReceipt(
                id=review_id,
                status="skipped",
                initiator=initiator,
                case_count=0,
                summary_ref=None,
                receipt_ref=None,
                message="no failure cases archived",
            )
            receipt_path = self.state_root / "receipts" / "replays" / "{0}-review.json".format(review_id)
            self._write_json(receipt_path, receipt.to_dict())
            receipt.receipt_ref = self._relative(receipt_path)
            self._write_json(receipt_path, receipt.to_dict())
            return receipt

        summary_payload = {
            "generated_at": self._now_iso(),
            "limit": limit,
            "case_count": len(failure_cases),
            "stages": self._count_by_key(failure_cases, "stage"),
            "categories": self._count_by_key(failure_cases, "category"),
            "latest_cases": [
                {
                    "case_ref": case["case_ref"],
                    "stage": case["stage"],
                    "category": case["category"],
                    "status": case["status"],
                    "reason": case["reason"],
                }
                for case in failure_cases
            ],
            "recommendations": self._suggest_failure_actions(failure_cases),
            "patch_suggestions": self._suggest_failure_patches(failure_cases),
        }

        summary_path = self.state_root / "reviews" / "failures" / "{0}.json".format(review_id)
        self._write_json(summary_path, summary_payload)

        receipt = FailureReviewReceipt(
            id=review_id,
            status="success",
            initiator=initiator,
            case_count=len(failure_cases),
            summary_ref=self._relative(summary_path),
            receipt_ref=None,
            message="failure cases reviewed",
        )
        receipt_path = self.state_root / "receipts" / "replays" / "{0}-review.json".format(review_id)
        self._write_json(receipt_path, receipt.to_dict())
        receipt.receipt_ref = self._relative(receipt_path)
        self._write_json(receipt_path, receipt.to_dict())
        return receipt

    def auto_retune(self, initiator: str = "manual", limit: int = 20) -> AutoRetuneReceipt:
        initiator = normalize_initiator(initiator)
        retune_id = self._new_id()
        lock_path = self.app_root / "automation" / "compiled" / "runtime.lock.json"
        cases_path = self.app_root / "automation" / "evals" / "golden_cases.json"
        schema_path = self.app_root / "automation" / "schemas" / "patch.schema.json"

        review_receipt = self.review_failures(initiator=initiator, limit=limit)
        summary_ref = review_receipt.summary_ref
        if review_receipt.status != "success" or not summary_ref:
            receipt = AutoRetuneReceipt(
                id=retune_id,
                status="skipped",
                initiator=initiator,
                applied_actions=[],
                patches=[],
                lock_ref=self._relative(lock_path),
                review_summary_ref=summary_ref,
                review_receipt_ref=review_receipt.receipt_ref,
                receipt_ref=None,
                message="no failure review summary available for auto retune",
            )
            receipt_path = self.state_root / "receipts" / "auto_retune" / "{0}.json".format(retune_id)
            self._write_json(receipt_path, receipt.to_dict())
            receipt.receipt_ref = self._relative(receipt_path)
            self._write_json(receipt_path, receipt.to_dict())
            return receipt

        summary_payload = json.loads((self.repo_root / summary_ref).read_text(encoding="utf-8"))
        patch_suggestions = list(summary_payload.get("patch_suggestions") or [])
        if not patch_suggestions:
            receipt = AutoRetuneReceipt(
                id=retune_id,
                status="skipped",
                initiator=initiator,
                applied_actions=[],
                patches=[],
                lock_ref=self._relative(lock_path),
                review_summary_ref=summary_ref,
                review_receipt_ref=review_receipt.receipt_ref,
                receipt_ref=None,
                message="failure review did not produce any patch suggestions",
            )
            receipt_path = self.state_root / "receipts" / "auto_retune" / "{0}.json".format(retune_id)
            self._write_json(receipt_path, receipt.to_dict())
            receipt.receipt_ref = self._relative(receipt_path)
            self._write_json(receipt_path, receipt.to_dict())
            return receipt

        patch_schema = load_or_create_patch_schema(schema_path)
        current_lock = load_or_create_runtime_lock(lock_path)
        golden_cases = load_or_create_golden_cases(cases_path)

        patches: List[Patch] = []
        applied_actions: List[str] = []
        for suggestion in patch_suggestions:
            applied_actions.append(str(suggestion["action"]))
            for payload in suggestion["patches"]:
                patches.append(Patch(**payload))

        validate_patch_bundle(patches, patch_schema)
        updated_lock = apply_patches(current_lock, patches, patch_schema)
        run_replay_evals(updated_lock, golden_cases)
        lock_path.write_text(
            json.dumps(updated_lock, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        receipt = AutoRetuneReceipt(
            id=retune_id,
            status="success",
            initiator=initiator,
            applied_actions=applied_actions,
            patches=patches,
            lock_ref=self._relative(lock_path),
            review_summary_ref=summary_ref,
            review_receipt_ref=review_receipt.receipt_ref,
            receipt_ref=None,
            message="runtime lock updated from failure review patch suggestions",
        )
        receipt_path = self.state_root / "receipts" / "auto_retune" / "{0}.json".format(retune_id)
        self._write_json(receipt_path, receipt.to_dict())
        receipt.receipt_ref = self._relative(receipt_path)
        self._write_json(receipt_path, receipt.to_dict())
        return receipt

    def tune(self, intent: str, initiator: str = "manual") -> TuneReceipt:
        initiator = normalize_initiator(initiator)
        tune_id = self._new_id()
        lock_path = self.app_root / "automation" / "compiled" / "runtime.lock.json"
        cases_path = self.app_root / "automation" / "evals" / "golden_cases.json"
        schema_path = self.app_root / "automation" / "schemas" / "patch.schema.json"

        current_lock = load_or_create_runtime_lock(lock_path)
        golden_cases = load_or_create_golden_cases(cases_path)
        patch_schema = load_or_create_patch_schema(schema_path)
        patches = compile_intent_to_patches(intent)
        validate_patch_bundle(patches, patch_schema)
        updated_lock = apply_patches(current_lock, patches, patch_schema)
        run_replay_evals(updated_lock, golden_cases)

        lock_path.write_text(
            json.dumps(updated_lock, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        receipt = TuneReceipt(
            id=tune_id,
            status="success",
            initiator=initiator,
            intent=intent,
            patches=patches,
            lock_ref=self._relative(lock_path),
            receipt_ref=None,
            message="runtime lock updated after replay evals",
        )
        receipt_path = self.state_root / "receipts" / "tune" / "{0}.json".format(tune_id)
        self._write_json(receipt_path, receipt.to_dict())
        receipt.receipt_ref = self._relative(receipt_path)
        self._write_json(receipt_path, receipt.to_dict())
        return receipt

    def synthesize_insights(
        self,
        initiator: str = "manual",
        dry_run: bool = False,
        confirm_receipt_ref: Optional[str] = None,
    ) -> InsightSynthesisReceipt:
        initiator = normalize_initiator(initiator)
        synthesis_id = self._new_id()
        if confirm_receipt_ref:
            return self._confirm_insight_synthesis(
                synthesis_id=synthesis_id,
                initiator=initiator,
                confirm_receipt_ref=confirm_receipt_ref,
            )
        runtime_lock = load_or_create_runtime_lock(self.app_root / "automation" / "compiled" / "runtime.lock.json")
        knowledge_docs = [doc for doc in load_knowledge_documents(self.repo_root) if doc["status"] != "draft"]
        evidence_docs, evidence_trace_ref = self._select_insight_evidence_with_trace(
            synthesis_id=synthesis_id,
            knowledge_docs=knowledge_docs,
            min_evidence=runtime_lock["runtime"]["insight"]["min_evidence"],
        )
        evidence_manifest = self._build_insight_evidence_manifest(evidence_docs)

        if not evidence_docs:
            receipt = InsightSynthesisReceipt(
                id=synthesis_id,
                status="skipped",
                initiator=initiator,
                dry_run=dry_run,
                evidence_refs=[],
                evidence_manifest=[],
                evidence_trace_ref=evidence_trace_ref,
                message="no evidence cluster met min_evidence",
            )
            receipt = self._write_insight_receipt(receipt)
            if not dry_run:
                self._archive_failure_case(
                    stage="insights",
                    category="insight_skipped",
                    status=receipt.status,
                    reason=receipt.message or "insight synthesis skipped",
                    initiator=initiator,
                    refs={
                        "receipt_ref": receipt.receipt_ref,
                        "evidence_trace_ref": receipt.evidence_trace_ref,
                    },
                    replay_command="synthesize_insights",
                    replay_args={},
                )
            return receipt

        if dry_run:
            return self._write_insight_receipt(
                InsightSynthesisReceipt(
                    id=synthesis_id,
                    status="success",
                    initiator=initiator,
                    dry_run=True,
                    evidence_refs=[str(doc["path"]) for doc in evidence_docs],
                    evidence_manifest=evidence_manifest,
                    evidence_trace_ref=evidence_trace_ref,
                    receipt_ref=None,
                    message="insight synthesis dry run completed",
                )
            )

        try:
            result = self._run_insight_pipeline(
                synthesis_id=synthesis_id,
                runtime_lock=runtime_lock,
                evidence_docs=evidence_docs,
            )
        except Exception as exc:
            partial_trace_ref = self._extract_trace_ref(exc)
            if partial_trace_ref:
                return self._write_insight_pipeline_failure_receipt(
                    synthesis_id=synthesis_id,
                    initiator=initiator,
                    evidence_refs=[doc["path"] for doc in evidence_docs],
                    evidence_manifest=evidence_manifest,
                    error=str(exc),
                    evidence_trace_ref=evidence_trace_ref,
                    llm_trace_ref=partial_trace_ref,
                    pipeline_mode="heuristic-fallback",
                )
            raise
        receipt = InsightSynthesisReceipt(
            id=synthesis_id,
            status="success",
            initiator=initiator,
            evidence_refs=[doc["path"] for doc in evidence_docs],
            evidence_manifest=evidence_manifest,
            evidence_trace_ref=evidence_trace_ref,
            insight_ref=result["insight_ref"],
            candidate_ref=result["candidate_ref"],
            critic_ref=result["critic_ref"],
            judge_ref=result["judge_ref"],
            pipeline_mode=result["pipeline_mode"],
            llm_trace_ref=result["llm_trace_ref"],
            relay_request_ids=result["relay_request_ids"],
            receipt_ref=None,
            message="insight synthesis completed",
        )
        receipt = self._write_insight_receipt(receipt)
        if result["insight_status"] != "active":
            self._archive_failure_case(
                stage="insights",
                category="insight_draft",
                status=result["insight_status"],
                reason=result["failure_reason"],
                initiator=initiator,
                pipeline_mode=result["pipeline_mode"],
                refs={
                    "receipt_ref": receipt.receipt_ref,
                    "insight_ref": result["insight_ref"],
                    "candidate_ref": result["candidate_ref"],
                    "critic_ref": result["critic_ref"],
                    "judge_ref": result["judge_ref"],
                    "evidence_trace_ref": receipt.evidence_trace_ref,
                    "llm_trace_ref": result["llm_trace_ref"],
                    "relay_request_ids": result["relay_request_ids"],
                },
                replay_command="synthesize_insights",
                replay_args={},
            )
        return receipt

    def _confirm_insight_synthesis(
        self,
        synthesis_id: str,
        initiator: str,
        confirm_receipt_ref: str,
    ) -> InsightSynthesisReceipt:
        try:
            preview_payload = self.read_receipt(confirm_receipt_ref)
        except FileNotFoundError:
            return self._write_insight_receipt(
                InsightSynthesisReceipt(
                    id=synthesis_id,
                    status="failed",
                    initiator=initiator,
                    dry_run=False,
                    confirmed_from_receipt_ref=confirm_receipt_ref,
                    receipt_ref=None,
                    error_code="INSIGHT_CONFIRM_NOT_FOUND",
                    next_step="Run `forge synthesize-insights --dry-run` first, then pass the preview receipt to `--confirm-receipt`.",
                    message="confirm receipt not found",
                )
            )
        evidence_trace_ref = str(preview_payload.get("evidence_trace_ref") or "").strip() or None
        if not preview_payload.get("dry_run"):
            return self._write_insight_receipt(
                InsightSynthesisReceipt(
                    id=synthesis_id,
                    status="failed",
                    initiator=initiator,
                    dry_run=False,
                    confirmed_from_receipt_ref=confirm_receipt_ref,
                    evidence_refs=list(preview_payload.get("evidence_refs") or []),
                    evidence_manifest=list(preview_payload.get("evidence_manifest") or []),
                    evidence_trace_ref=evidence_trace_ref,
                    receipt_ref=None,
                    error_code="INSIGHT_CONFIRM_INVALID_TYPE",
                    next_step="Use an insight dry-run receipt from `state/receipts/insights/...json`.",
                    message="confirm receipt must reference a dry-run insight synthesis receipt",
                )
            )

        manifest = list(preview_payload.get("evidence_manifest") or [])
        if not manifest:
            return self._write_insight_receipt(
                InsightSynthesisReceipt(
                    id=synthesis_id,
                    status="failed",
                    initiator=initiator,
                    dry_run=False,
                    confirmed_from_receipt_ref=confirm_receipt_ref,
                    evidence_refs=list(preview_payload.get("evidence_refs") or []),
                    evidence_manifest=[],
                    evidence_trace_ref=evidence_trace_ref,
                    receipt_ref=None,
                    error_code="INSIGHT_CONFIRM_MISSING_MANIFEST",
                    next_step="Rerun `forge synthesize-insights --dry-run` to generate a fresh preview receipt before confirming.",
                    message="confirm receipt is missing evidence manifest",
                )
            )

        evidence_docs, failure_message = self._resolve_confirmed_insight_evidence(manifest)
        if failure_message is not None:
            return self._write_insight_receipt(
                InsightSynthesisReceipt(
                    id=synthesis_id,
                    status="failed",
                    initiator=initiator,
                    dry_run=False,
                    confirmed_from_receipt_ref=confirm_receipt_ref,
                    evidence_refs=[str(item.get("knowledge_ref") or "") for item in manifest if item.get("knowledge_ref")],
                    evidence_manifest=manifest,
                    evidence_trace_ref=evidence_trace_ref,
                    receipt_ref=None,
                    error_code="INSIGHT_CONFIRM_EVIDENCE_DRIFT",
                    next_step="Rerun `forge synthesize-insights --dry-run` to refresh the evidence set, then confirm again.",
                    message=failure_message,
                )
            )

        runtime_lock = load_or_create_runtime_lock(self.app_root / "automation" / "compiled" / "runtime.lock.json")
        try:
            result = self._run_insight_pipeline(
                synthesis_id=synthesis_id,
                runtime_lock=runtime_lock,
                evidence_docs=evidence_docs,
            )
        except Exception as exc:
            partial_trace_ref = self._extract_trace_ref(exc)
            if partial_trace_ref:
                failed = self._write_insight_pipeline_failure_receipt(
                    synthesis_id=synthesis_id,
                    initiator=initiator,
                    evidence_refs=[str(doc["path"]) for doc in evidence_docs],
                    evidence_manifest=manifest,
                    error=str(exc),
                    evidence_trace_ref=evidence_trace_ref,
                    llm_trace_ref=partial_trace_ref,
                    pipeline_mode="heuristic-fallback",
                )
                failed.confirmed_from_receipt_ref = confirm_receipt_ref
                return self._write_insight_receipt(failed)
            raise
        receipt = InsightSynthesisReceipt(
            id=synthesis_id,
            status="success",
            initiator=initiator,
            dry_run=False,
            confirmed_from_receipt_ref=confirm_receipt_ref,
            evidence_refs=[str(doc["path"]) for doc in evidence_docs],
            evidence_manifest=manifest,
            evidence_trace_ref=evidence_trace_ref,
            insight_ref=result["insight_ref"],
            candidate_ref=result["candidate_ref"],
            critic_ref=result["critic_ref"],
            judge_ref=result["judge_ref"],
            pipeline_mode=result["pipeline_mode"],
            llm_trace_ref=result["llm_trace_ref"],
            relay_request_ids=result["relay_request_ids"],
            receipt_ref=None,
            message="insight synthesis confirmed from dry-run receipt",
        )
        receipt = self._write_insight_receipt(receipt)
        if result["insight_status"] != "active":
            self._archive_failure_case(
                stage="insights",
                category="insight_draft",
                status=result["insight_status"],
                reason=result["failure_reason"],
                initiator=initiator,
                pipeline_mode=result["pipeline_mode"],
                refs={
                    "receipt_ref": receipt.receipt_ref,
                    "insight_ref": result["insight_ref"],
                    "candidate_ref": result["candidate_ref"],
                    "critic_ref": result["critic_ref"],
                    "judge_ref": result["judge_ref"],
                    "evidence_trace_ref": receipt.evidence_trace_ref,
                    "llm_trace_ref": result["llm_trace_ref"],
                    "relay_request_ids": result["relay_request_ids"],
                },
                replay_command="synthesize_insights",
                replay_args={},
            )
        return receipt

    def review_raw(self, initiator: str = "manual") -> RawReviewReceipt:
        initiator = normalize_initiator(initiator)
        review_id = self._new_id()
        runtime_lock = load_or_create_runtime_lock(self.app_root / "automation" / "compiled" / "runtime.lock.json")
        min_chars = int(runtime_lock["runtime"]["knowledge"]["min_chars"])
        raw_docs = load_raw_documents(self.repo_root)
        derived_map = self._build_raw_to_knowledge_map()

        documents: List[Dict[str, Any]] = []
        promoted_count = 0
        pending_count = 0
        too_short_count = 0

        for doc in raw_docs:
            knowledge_refs = sorted(derived_map.get(str(doc["path"]), []))
            qualifies = bool(int(doc["content_chars"]) >= min_chars)
            disposition = self._classify_raw_document(
                str(doc["raw_kind"]),
                str(doc["status"]),
                knowledge_refs,
                qualifies,
            )
            if disposition == "promoted":
                promoted_count += 1
            elif disposition == "pending":
                pending_count += 1
            elif disposition == "too_short":
                too_short_count += 1
            documents.append(
                {
                    "path": doc["path"],
                    "title": doc["title"],
                    "status": doc["status"],
                    "source": doc["source"],
                    "raw_kind": doc["raw_kind"],
                    "content_chars": doc["content_chars"],
                    "qualifies_for_knowledge": qualifies,
                    "knowledge_refs": knowledge_refs,
                    "disposition": disposition,
                    "reason": self._raw_disposition_reason(disposition, min_chars),
                }
            )

        receipt = RawReviewReceipt(
            id=review_id,
            status="success",
            initiator=initiator,
            total_count=len(documents),
            promoted_count=promoted_count,
            pending_count=pending_count,
            too_short_count=too_short_count,
            documents=documents,
            receipt_ref=None,
            message="raw documents reviewed",
        )
        receipt_path = self.state_root / "receipts" / "raw_review" / "{0}.json".format(review_id)
        self._write_json(receipt_path, receipt.to_dict())
        receipt.receipt_ref = self._relative(receipt_path)
        self._write_json(receipt_path, receipt.to_dict())
        return receipt

    def review_queue(self, initiator: str = "manual") -> ReviewQueueReceipt:
        initiator = normalize_initiator(initiator)
        queue_id = self._new_id()
        review = self.review_raw(initiator=initiator)
        items: List[Dict[str, Any]] = []

        for doc in review.documents:
            disposition = str(doc["disposition"])
            if disposition not in {"pending", "too_short"}:
                continue
            queue_status = "ready" if disposition == "pending" else "blocked"
            action = "promote_raw" if disposition == "pending" else "expand_or_merge"
            command_hint = (
                "uv run forge promote-raw {0} --initiator {1}".format(doc["path"], initiator)
                if disposition == "pending"
                else "expand or merge the raw content, then rerun inject or promote-raw"
            )
            items.append(
                {
                    "path": doc["path"],
                    "title": doc["title"],
                    "disposition": disposition,
                    "queue_status": queue_status,
                    "action": action,
                    "command_hint": command_hint,
                    "suggested_command": command_hint if disposition == "pending" else "",
                    "reason": doc["reason"],
                    "content_chars": doc["content_chars"],
                }
            )

        items.sort(key=lambda item: (0 if item["disposition"] == "pending" else 1, item["path"]))
        receipt = ReviewQueueReceipt(
            id=queue_id,
            status="success",
            initiator=initiator,
            queue_name="raw_to_knowledge",
            scanned_count=review.total_count,
            queue_count=len(items),
            ready_count=sum(1 for item in items if item["queue_status"] == "ready"),
            blocked_count=sum(1 for item in items if item["queue_status"] == "blocked"),
            total_count=len(items),
            pending_count=sum(1 for item in items if item["disposition"] == "pending"),
            too_short_count=sum(1 for item in items if item["disposition"] == "too_short"),
            documents=items,
            items=items,
            receipt_ref=None,
            message="review queue prepared",
        )
        receipt_path = self.state_root / "receipts" / "review_queue" / "{0}.json".format(queue_id)
        self._write_json(receipt_path, receipt.to_dict())
        receipt.receipt_ref = self._relative(receipt_path)
        self._write_json(receipt_path, receipt.to_dict())
        return receipt

    def read_receipt(self, selector: Union[str, Path]) -> Dict[str, Any]:
        selector_text = str(selector).strip()
        if not selector_text:
            raise ForgeOperatorError(
                "receipt selector is empty",
                error_code="RECEIPT_SELECTOR_EMPTY",
                next_step="Pass a receipt id or a full `state/receipts/...json` path to `forge receipt get`.",
                status_code=400,
            )

        direct_path = self._resolve_repo_path(selector_text)
        if direct_path.exists():
            return json.loads(direct_path.read_text(encoding="utf-8"))

        state_path = self._resolve_state_path(selector_text)
        if state_path.exists():
            return json.loads(state_path.read_text(encoding="utf-8"))

        normalized_selector = selector_text
        if normalized_selector.endswith(".json"):
            normalized_selector = normalized_selector[:-5]

        matches: List[Path] = []
        for path in sorted(self.state_root.glob("receipts/**/*.json")):
            if path.stem == normalized_selector:
                matches.append(path)
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if str(payload.get("id") or "").strip() == normalized_selector:
                matches.append(path)

        if not matches:
            raise ForgeOperatorError(
                "receipt not found: {0}".format(selector_text),
                error_code="RECEIPT_NOT_FOUND",
                next_step="Run `forge job get <job_id>` to discover `receipt_ref`, or pass a full `state/receipts/...json` path.",
                status_code=404,
            )
        if len(matches) > 1:
            raise ForgeOperatorError(
                "receipt selector is ambiguous: {0}".format(selector_text),
                error_code="RECEIPT_SELECTOR_AMBIGUOUS",
                next_step="Pass the full `state/receipts/...json` path instead of a short selector.",
                status_code=400,
            )
        return json.loads(matches[0].read_text(encoding="utf-8"))

    def read_knowledge_status(self, selector: Union[str, Path]) -> Dict[str, Any]:
        knowledge_ref = str(selector).strip()
        doc = self._find_knowledge_document(knowledge_ref)
        if doc is None:
            raise ForgeOperatorError(
                "knowledge not found: {0}".format(knowledge_ref),
                error_code="KNOWLEDGE_NOT_FOUND",
                next_step="Pass a full `knowledge/...md` path or inspect the available documents before retrying `forge knowledge get`.",
                status_code=404,
            )
        publication = self._resolve_knowledge_publication_status(knowledge_ref)
        if publication is None:
            raise ForgeOperatorError(
                "knowledge not found: {0}".format(knowledge_ref),
                error_code="KNOWLEDGE_NOT_FOUND",
                next_step="Pass a full `knowledge/...md` path or inspect the available documents before retrying `forge knowledge get`.",
                status_code=404,
            )
        return {
            "status": "success",
            "knowledge_ref": knowledge_ref,
            "title": str(doc.get("title") or Path(knowledge_ref).stem),
            "tags": list(doc.get("tags") or []),
            "publication_status": publication.publication_status,
            "judge_score": publication.judge_score,
            "judge_decision": publication.judge_decision,
            "release_reason": publication.release_reason,
            "eligible_for_insights": publication.eligible_for_insights,
            "excluded_reason": publication.excluded_reason,
            "updated_at": publication.updated_at,
            "last_receipt_ref": publication.last_receipt_ref,
        }

    def explain_insight_receipt(self, receipt_ref: Union[str, Path]) -> Dict[str, Any]:
        normalized_receipt_ref = str(receipt_ref).strip()
        receipt = self.read_receipt(normalized_receipt_ref)
        evidence_trace_ref = str(receipt.get("evidence_trace_ref") or "").strip()
        if evidence_trace_ref == "":
            raise ForgeOperatorError(
                "insight receipt missing evidence trace: {0}".format(normalized_receipt_ref),
                error_code="INSIGHT_RECEIPT_MISSING_TRACE",
                next_step="Use an insight synthesis receipt that includes `evidence_trace_ref`, or rerun insight synthesis before calling `forge explain insight`.",
                status_code=400,
            )
        trace_path = self._resolve_state_path(evidence_trace_ref)
        if not trace_path.exists():
            raise ForgeOperatorError(
                "evidence trace not found: {0}".format(evidence_trace_ref),
                error_code="EVIDENCE_TRACE_NOT_FOUND",
                next_step="Rerun insight synthesis to regenerate the evidence trace, then retry `forge explain insight`.",
                status_code=404,
            )
        trace_payload = json.loads(trace_path.read_text(encoding="utf-8"))
        return build_insight_explanation(
            receipt_ref=normalized_receipt_ref,
            evidence_trace_ref=evidence_trace_ref,
            trace_payload=trace_payload,
        )

    def promote_raw(self, raw_ref: Union[str, Path], initiator: str = "manual") -> RawPromotionReceipt:
        initiator = normalize_initiator(initiator)
        promotion_id = self._new_id()
        runtime_lock = load_or_create_runtime_lock(self.app_root / "automation" / "compiled" / "runtime.lock.json")
        relative_raw_ref = self._normalize_raw_ref(raw_ref)
        raw_doc = self._find_raw_document(relative_raw_ref)

        if raw_doc is None:
            return self._write_raw_promotion_receipt(
                RawPromotionReceipt(
                    id=promotion_id,
                    status="failed",
                    initiator=initiator,
                    raw_ref=relative_raw_ref,
                    error_code="RAW_NOT_FOUND",
                    next_step="Use `forge review-queue` or verify the exact `raw/...md` path before retrying promotion.",
                    message="raw document not found",
                )
            )

        existing_knowledge_refs = sorted(self._build_raw_to_knowledge_map().get(relative_raw_ref, []))
        if existing_knowledge_refs:
            publication = self._resolve_knowledge_publication_status(existing_knowledge_refs[0])
            return self._write_raw_promotion_receipt(
                RawPromotionReceipt(
                    id=promotion_id,
                    status="skipped",
                    initiator=initiator,
                    raw_ref=relative_raw_ref,
                    knowledge_ref=existing_knowledge_refs[0],
                    publication_status=publication.publication_status if publication else None,
                    judge_score=publication.judge_score if publication else None,
                    judge_decision=publication.judge_decision if publication else None,
                    eligible_for_insights=publication.eligible_for_insights if publication else None,
                    excluded_reason=publication.excluded_reason if publication else None,
                    updated_at=publication.updated_at if publication else None,
                    last_receipt_ref=self._find_latest_receipt_ref_for_knowledge(existing_knowledge_refs[0]),
                    message="raw document already promoted",
                )
            )

        content = str(raw_doc["promotion_content"])
        if not self._qualifies_for_knowledge(content, runtime_lock):
            return self._write_raw_promotion_receipt(
                RawPromotionReceipt(
                    id=promotion_id,
                    status="skipped",
                    initiator=initiator,
                    raw_ref=relative_raw_ref,
                    error_code="RAW_BELOW_PROMOTION_THRESHOLD",
                    next_step="Expand the raw content or merge it with related material, then retry `forge promote-raw`.",
                    message="raw content is below the knowledge promotion threshold",
                )
            )

        try:
            result = self._run_knowledge_pipeline(
                ingest_id=promotion_id,
                runtime_lock=runtime_lock,
                title=str(raw_doc["title"]),
                content=content,
                raw_ref=relative_raw_ref,
                tags=list(raw_doc["tags"] or []),
                input_kind="raw-backfill",
                source_ref=relative_raw_ref,
            )
        except Exception as exc:
            return self._write_raw_promotion_receipt(
                RawPromotionReceipt(
                    id=promotion_id,
                    status="failed",
                    initiator=initiator,
                    raw_ref=relative_raw_ref,
                    llm_trace_ref=self._extract_trace_ref(exc),
                    error_code="RAW_PROMOTION_PIPELINE_FAILED",
                    next_step="Inspect the attached trace fields and retry the same raw path once the upstream issue is resolved.",
                    message=str(exc),
                )
            )

        self._annotate_raw_distillation(relative_raw_ref, str(result["knowledge_ref"]))
        publication = self._resolve_knowledge_publication_status(str(result["knowledge_ref"]))
        return self._write_raw_promotion_receipt(
            RawPromotionReceipt(
                id=promotion_id,
                status="success",
                initiator=initiator,
                raw_ref=relative_raw_ref,
                knowledge_ref=result["knowledge_ref"],
                candidate_ref=result["candidate_ref"],
                critic_ref=result["critic_ref"],
                judge_ref=result["judge_ref"],
                pipeline_mode=result["pipeline_mode"],
                llm_trace_ref=result["llm_trace_ref"],
                relay_request_ids=result["relay_request_ids"],
                publication_status=(
                    publication.publication_status if publication else result.get("knowledge_status")
                ),
                judge_score=publication.judge_score if publication else result.get("judge_score"),
                judge_decision=publication.judge_decision if publication else result.get("judge_decision"),
                eligible_for_insights=publication.eligible_for_insights if publication else None,
                excluded_reason=publication.excluded_reason if publication else None,
                updated_at=publication.updated_at if publication else self.clock().isoformat(),
                message="raw promotion completed",
            )
        )

    def promote_all_raw(self, initiator: str = "manual") -> RawPromotionBatchReceipt:
        initiator = normalize_initiator(initiator)
        batch_id = self._new_id()
        results: List[RawPromotionReceipt] = []
        derived_map = self._build_raw_to_knowledge_map()

        for doc in load_raw_documents(self.repo_root):
            raw_ref = str(doc["path"])
            raw_kind = str(doc["raw_kind"])
            raw_status = str(doc["status"]).strip().lower()
            existing_knowledge_refs = sorted(derived_map.get(raw_ref, []))
            if existing_knowledge_refs:
                publication = self._resolve_knowledge_publication_status(existing_knowledge_refs[0])
                results.append(
                    self._write_raw_promotion_receipt(
                        RawPromotionReceipt(
                            id=self._new_id(),
                            status="skipped",
                            initiator=initiator,
                            raw_ref=raw_ref,
                            knowledge_ref=existing_knowledge_refs[0],
                            publication_status=publication.publication_status if publication else None,
                            judge_score=publication.judge_score if publication else None,
                            judge_decision=publication.judge_decision if publication else None,
                            eligible_for_insights=publication.eligible_for_insights if publication else None,
                            excluded_reason=publication.excluded_reason if publication else None,
                            updated_at=publication.updated_at if publication else None,
                            last_receipt_ref=self._find_latest_receipt_ref_for_knowledge(existing_knowledge_refs[0]),
                            message="raw document already promoted",
                        )
                    )
                )
                continue
            if raw_kind == "references":
                results.append(
                    self._write_raw_promotion_receipt(
                        RawPromotionReceipt(
                            id=self._new_id(),
                            status="skipped",
                            initiator=initiator,
                            raw_ref=raw_ref,
                            message="reference raw requires manual distillation",
                        )
                    )
                )
                continue
            if raw_status == "archived":
                results.append(
                    self._write_raw_promotion_receipt(
                        RawPromotionReceipt(
                            id=self._new_id(),
                            status="skipped",
                            initiator=initiator,
                            raw_ref=raw_ref,
                            message="archived raw kept for traceability",
                        )
                    )
                )
                continue
            results.append(self.promote_raw(raw_ref, initiator=initiator))

        success_count = sum(1 for item in results if item.status == "success")
        skipped_count = sum(1 for item in results if item.status == "skipped")
        failed_count = sum(1 for item in results if item.status == "failed")
        receipt = RawPromotionBatchReceipt(
            id=batch_id,
            status="failed" if failed_count else "success",
            initiator=initiator,
            total_count=len(results),
            success_count=success_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            results=[item.to_dict() for item in results],
            receipt_ref=None,
            message="bulk raw promotion completed",
        )
        return self._write_raw_promotion_batch_receipt(receipt)

    def promote_ready(
        self,
        initiator: str = "manual",
        dry_run: bool = False,
        limit: Optional[int] = None,
        confirm_receipt_ref: Optional[str] = None,
    ) -> ReadyPromotionBatchReceipt:
        initiator = normalize_initiator(initiator)
        batch_id = self._new_id()
        if confirm_receipt_ref:
            return self._confirm_ready_promotion(
                batch_id=batch_id,
                initiator=initiator,
                confirm_receipt_ref=confirm_receipt_ref,
            )

        queue = self.review_queue(initiator=initiator)
        ready_items = [item for item in queue.documents if item["queue_status"] == "ready"]
        normalized_limit = None if limit is None else max(0, int(limit))
        if normalized_limit is not None:
            ready_items = ready_items[:normalized_limit]
        planned_count = len(ready_items) if dry_run else 0
        if dry_run:
            results = [
                {
                    "raw_ref": item["path"],
                    "status": "planned",
                    "action": item["action"],
                    "suggested_command": item["suggested_command"],
                    "message": "dry run: ready item not promoted",
                }
                for item in ready_items
            ]
            success_count = 0
            skipped_count = 0
            failed_count = 0
        else:
            receipts = [self.promote_raw(item["path"], initiator=initiator) for item in ready_items]
            results = [item.to_dict() for item in receipts]
            success_count = sum(1 for item in receipts if item.status == "success")
            skipped_count = sum(1 for item in receipts if item.status == "skipped")
            failed_count = sum(1 for item in receipts if item.status == "failed")
        receipt = ReadyPromotionBatchReceipt(
            id=batch_id,
            status="failed" if failed_count else "success",
            initiator=initiator,
            queue_receipt_ref=queue.receipt_ref,
            confirmed_from_receipt_ref=None,
            dry_run=dry_run,
            limit=normalized_limit,
            scanned_count=queue.scanned_count,
            ready_count=queue.ready_count,
            targeted_count=len(ready_items),
            planned_count=planned_count,
            success_count=success_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            results=results,
            receipt_ref=None,
            message="ready raw promotion dry run completed" if dry_run else "ready raw promotion completed",
        )
        return self._write_ready_promotion_batch_receipt(receipt)

    def _confirm_ready_promotion(
        self,
        batch_id: str,
        initiator: str,
        confirm_receipt_ref: str,
    ) -> ReadyPromotionBatchReceipt:
        receipt_path = self.repo_root / confirm_receipt_ref
        if not receipt_path.exists():
            receipt = ReadyPromotionBatchReceipt(
                id=batch_id,
                status="failed",
                initiator=initiator,
                queue_receipt_ref=None,
                confirmed_from_receipt_ref=confirm_receipt_ref,
                dry_run=False,
                limit=None,
                scanned_count=0,
                ready_count=0,
                targeted_count=0,
                planned_count=0,
                success_count=0,
                skipped_count=0,
                failed_count=1,
                results=[],
                receipt_ref=None,
                error_code="READY_CONFIRM_NOT_FOUND",
                next_step="Run `forge promote-ready --dry-run` first, then pass the preview receipt to `--confirm-receipt`.",
                message="confirm receipt not found",
            )
            return self._write_ready_promotion_batch_receipt(receipt)

        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        if not payload.get("dry_run"):
            receipt = ReadyPromotionBatchReceipt(
                id=batch_id,
                status="failed",
                initiator=initiator,
                queue_receipt_ref=payload.get("queue_receipt_ref"),
                confirmed_from_receipt_ref=confirm_receipt_ref,
                dry_run=False,
                limit=None,
                scanned_count=0,
                ready_count=0,
                targeted_count=0,
                planned_count=0,
                success_count=0,
                skipped_count=0,
                failed_count=1,
                results=[],
                receipt_ref=None,
                error_code="READY_CONFIRM_INVALID_TYPE",
                next_step="Use a ready-promotion dry-run receipt from `state/receipts/ready_promote/...json`.",
                message="confirm receipt must reference a dry-run ready promotion batch",
            )
            return self._write_ready_promotion_batch_receipt(receipt)

        planned_raw_refs = []
        for item in payload.get("results") or []:
            if not isinstance(item, dict):
                continue
            raw_ref = str(item.get("raw_ref") or "").strip()
            if raw_ref:
                planned_raw_refs.append(raw_ref)

        queue = self.review_queue(initiator=initiator)
        ready_paths = {
            str(item["path"])
            for item in queue.documents
            if str(item.get("queue_status") or "").strip().lower() == "ready"
        }
        results = []
        success_count = 0
        skipped_count = 0
        failed_count = 0
        ready_count = 0
        for raw_ref in planned_raw_refs:
            if raw_ref not in ready_paths:
                skipped_count += 1
                results.append(
                    {
                        "raw_ref": raw_ref,
                        "status": "skipped",
                        "message": "planned raw is no longer ready",
                    }
                )
                continue
            ready_count += 1
            item = self.promote_raw(raw_ref, initiator=initiator)
            results.append(item.to_dict())
            if item.status == "success":
                success_count += 1
            elif item.status == "skipped":
                skipped_count += 1
            else:
                failed_count += 1
        receipt = ReadyPromotionBatchReceipt(
            id=batch_id,
            status="failed" if failed_count else "success",
            initiator=initiator,
            queue_receipt_ref=queue.receipt_ref,
            confirmed_from_receipt_ref=confirm_receipt_ref,
            dry_run=False,
            limit=payload.get("limit"),
            scanned_count=queue.scanned_count,
            ready_count=ready_count,
            targeted_count=len(planned_raw_refs),
            planned_count=0,
            success_count=success_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            results=results,
            receipt_ref=None,
            message="ready raw promotion confirmed from dry-run receipt",
        )
        return self._write_ready_promotion_batch_receipt(receipt)

    def _bootstrap(self) -> None:
        self._ensure_dir(self.repo_root / "raw" / "captures")
        self._ensure_dir(self.repo_root / "knowledge" / "troubleshooting")
        self._ensure_dir(self.repo_root / "knowledge" / "workflow")
        self._ensure_dir(self.repo_root / "knowledge" / "tools")
        self._ensure_dir(self.repo_root / "insights" / "patterns")
        self._ensure_dir(self.state_root / "snapshots")
        self._ensure_dir(self.state_root / "receipts" / "inject")
        self._ensure_dir(self.state_root / "receipts" / "failures")
        self._ensure_dir(self.state_root / "receipts" / "tune")
        self._ensure_dir(self.state_root / "receipts" / "insights")
        self._ensure_dir(self.state_root / "receipts" / "replays")
        self._ensure_dir(self.state_root / "receipts" / "auto_retune")
        self._ensure_dir(self.state_root / "receipts" / "raw_review")
        self._ensure_dir(self.state_root / "receipts" / "review_queue")
        self._ensure_dir(self.state_root / "receipts" / "raw_promote")
        self._ensure_dir(self.state_root / "receipts" / "ready_promote")
        self._ensure_dir(self.state_root / "failure_cases" / "inject")
        self._ensure_dir(self.state_root / "failure_cases" / "knowledge")
        self._ensure_dir(self.state_root / "failure_cases" / "insights")
        self._ensure_dir(self.state_root / "candidates" / "knowledge")
        self._ensure_dir(self.state_root / "candidates" / "insights")
        self._ensure_dir(self.state_root / "reviews" / "knowledge")
        self._ensure_dir(self.state_root / "reviews" / "insights")
        self._ensure_dir(self.state_root / "reviews" / "failures")
        self._ensure_dir(self.state_root / "traces" / "knowledge")
        self._ensure_dir(self.state_root / "traces" / "insights")
        load_or_create_runtime_lock(self.app_root / "automation" / "compiled" / "runtime.lock.json")
        load_or_create_golden_cases(self.app_root / "automation" / "evals" / "golden_cases.json")
        load_or_create_patch_schema(self.app_root / "automation" / "schemas" / "patch.schema.json")

    def _ingest_content(
        self,
        input_kind: str,
        content: str,
        source_ref: str,
        title: str,
        source: str,
        tags: List[str],
        initiator: str,
        promote_knowledge: bool,
        ingest_id: Optional[str] = None,
    ) -> IngestReceipt:
        ingest_id = ingest_id or self._new_id()
        runtime_lock = load_or_create_runtime_lock(self.app_root / "automation" / "compiled" / "runtime.lock.json")
        snapshot_path = self.state_root / "snapshots" / "{0}.json".format(ingest_id)
        raw_rel = self._allocate_raw_path(title, content)
        raw_path = self.repo_root / raw_rel

        snapshot_payload = {
            "id": ingest_id,
            "title": title,
            "input_kind": input_kind,
            "source_ref": source_ref,
            "captured_at": self._now_iso(),
            "content_digest": self._content_digest(content),
            "content": content,
        }
        self._write_json(snapshot_path, snapshot_payload)

        knowledge_result = {
            "knowledge_ref": None,
            "candidate_ref": None,
            "critic_ref": None,
            "judge_ref": None,
            "llm_trace_ref": None,
            "relay_request_ids": None,
            "pipeline_mode": None,
            "knowledge_status": None,
            "failure_reason": None,
        }
        if promote_knowledge and self._qualifies_for_knowledge(content, runtime_lock):
            try:
                knowledge_result = self._run_knowledge_pipeline(
                    ingest_id=ingest_id,
                    runtime_lock=runtime_lock,
                    title=title,
                    content=content,
                    raw_ref=raw_rel,
                    tags=tags,
                    input_kind=input_kind,
                    source_ref=source_ref,
                )
            except Exception as exc:
                partial_trace_ref = self._extract_trace_ref(exc)
                if partial_trace_ref:
                    raw_document = self._render_raw_document(
                        title=title,
                        source=source,
                        tags=tags,
                        input_kind=input_kind,
                        source_ref=source_ref,
                        content=content,
                        knowledge_ref=None,
                    )
                    self._write_text(raw_path, raw_document)
                    return self._write_ingest_pipeline_failure_receipt(
                        ingest_id=ingest_id,
                        input_kind=input_kind,
                        title=title,
                        source_ref=source_ref,
                        initiator=initiator,
                        snapshot_ref=self._relative(snapshot_path),
                        raw_ref=raw_rel,
                        error=str(exc),
                        llm_trace_ref=partial_trace_ref,
                        pipeline_mode="heuristic-fallback",
                        source=source,
                        content=content,
                        tags=tags,
                    )
                raise

        raw_document = self._render_raw_document(
            title=title,
            source=source,
            tags=tags,
            input_kind=input_kind,
            source_ref=source_ref,
            content=content,
            knowledge_ref=knowledge_result["knowledge_ref"],
        )
        self._write_text(raw_path, raw_document)

        receipt = IngestReceipt(
            id=ingest_id,
            status="success",
            title=title,
            input_kind=input_kind,
            initiator=initiator,
            source_ref=source_ref,
            snapshot_ref=self._relative(snapshot_path),
            raw_ref=raw_rel,
            knowledge_ref=knowledge_result["knowledge_ref"],
            receipt_ref=None,
            pipeline_mode=knowledge_result["pipeline_mode"],
            candidate_ref=knowledge_result["candidate_ref"],
            critic_ref=knowledge_result["critic_ref"],
            judge_ref=knowledge_result["judge_ref"],
            llm_trace_ref=knowledge_result["llm_trace_ref"],
            relay_request_ids=knowledge_result["relay_request_ids"],
            message="ingest completed",
        )
        receipt_path = self.state_root / "receipts" / "inject" / "{0}.json".format(ingest_id)
        self._write_json(receipt_path, receipt.to_dict())
        receipt.receipt_ref = self._relative(receipt_path)
        self._write_json(receipt_path, receipt.to_dict())
        if knowledge_result["knowledge_status"] and knowledge_result["knowledge_status"] != "active":
            self._archive_failure_case(
                stage="knowledge",
                category="knowledge_draft",
                status=knowledge_result["knowledge_status"],
                reason=knowledge_result["failure_reason"],
                initiator=initiator,
                pipeline_mode=knowledge_result["pipeline_mode"],
                refs={
                    "receipt_ref": receipt.receipt_ref,
                    "snapshot_ref": receipt.snapshot_ref,
                    "raw_ref": receipt.raw_ref,
                    "knowledge_ref": receipt.knowledge_ref,
                    "candidate_ref": receipt.candidate_ref,
                    "critic_ref": receipt.critic_ref,
                    "judge_ref": receipt.judge_ref,
                    "llm_trace_ref": receipt.llm_trace_ref,
                    "relay_request_ids": receipt.relay_request_ids,
                },
                replay_command="inject_text",
                replay_args={
                    "text": content,
                    "title": title,
                    "source": source,
                    "tags": tags,
                    "promote_knowledge": True,
                },
            )
        return receipt

    def _run_knowledge_pipeline(
        self,
        ingest_id: str,
        runtime_lock: Dict[str, Any],
        title: str,
        content: str,
        raw_ref: str,
        tags: List[str],
        input_kind: str,
        source_ref: str,
    ) -> Dict[str, Any]:
        selected_client = self.knowledge_client
        selected_mode = getattr(selected_client, "mode", "unknown")
        try:
            return self._generate_knowledge_with_client(
                client=selected_client,
                pipeline_mode=selected_mode,
                ingest_id=ingest_id,
                runtime_lock=runtime_lock,
                title=title,
                content=content,
                raw_ref=raw_ref,
                tags=tags,
                input_kind=input_kind,
                source_ref=source_ref,
            )
        except Exception as exc:
            if selected_mode == "heuristic":
                raise
            partial_trace_ref = self._extract_trace_ref(exc)
            try:
                result = self._generate_knowledge_with_client(
                    client=self.fallback_knowledge_client,
                    pipeline_mode="heuristic-fallback",
                    ingest_id=ingest_id,
                    runtime_lock=runtime_lock,
                    title=title,
                    content=content,
                    raw_ref=raw_ref,
                    tags=tags,
                    input_kind=input_kind,
                    source_ref=source_ref,
                )
            except Exception as fallback_exc:
                if partial_trace_ref:
                    raise _PipelineTraceCaptureError(partial_trace_ref, str(fallback_exc)) from fallback_exc
                raise
            if partial_trace_ref and not result.get("llm_trace_ref"):
                result["llm_trace_ref"] = partial_trace_ref
            if partial_trace_ref and not result.get("relay_request_ids"):
                result["relay_request_ids"] = self._read_relay_request_ids_from_trace_ref(partial_trace_ref)
            return result

    def _generate_knowledge_with_client(
        self,
        client,
        pipeline_mode: str,
        ingest_id: str,
        runtime_lock: Dict[str, Any],
        title: str,
        content: str,
        raw_ref: str,
        tags: List[str],
        input_kind: str,
        source_ref: str,
    ) -> Dict[str, Any]:
        runtime_knowledge = runtime_lock["runtime"]["knowledge"]
        profiles = runtime_lock["profiles"]
        writer_profile = profiles[runtime_knowledge["writer_profile"]]
        critic_profile_name = runtime_knowledge.get("critic_profile", runtime_knowledge["judge_profile"])
        critic_profile = profiles[critic_profile_name]
        judge_profile = profiles[runtime_knowledge["judge_profile"]]
        domain_appendix = runtime_lock["prompts"]["knowledge_writer"]["domain_appendix"].get("network", "")
        llm_calls: List[Dict[str, Any]] = []

        try:
            candidate = self._invoke_client_method(
                client,
                preferred_name="write_candidate",
                legacy_name="write_knowledge_candidate",
                trace_calls=llm_calls,
                trace_stage="write",
                title=title,
                content=content,
                tags=tags,
                raw_ref=raw_ref,
                source_ref=source_ref,
                profile=writer_profile,
                domain_appendix=domain_appendix,
            )
            candidate = normalize_candidate(candidate, fallback_title=title, fallback_tags=tags)
            deterministic_issues = deterministic_candidate_issues(candidate)

            critique = self._invoke_client_method(
                client,
                preferred_name="critique_candidate",
                legacy_name="critique_knowledge_candidate",
                trace_calls=llm_calls,
                trace_stage="critique",
                candidate=candidate,
                deterministic_issues=deterministic_issues,
                profile=critic_profile,
            )
            critique = normalize_critique(critique, deterministic_issues)

            judge = self._invoke_client_method(
                client,
                preferred_name="judge_candidate",
                legacy_name="judge_knowledge_candidate",
                trace_calls=llm_calls,
                trace_stage="judge",
                candidate=candidate,
                critique=critique,
                profile=judge_profile,
                min_judge_score=runtime_knowledge["min_judge_score"],
            )
            judge = normalize_judge(judge, min_score=runtime_knowledge["min_judge_score"])
        except Exception as exc:
            partial_trace_ref = self._write_llm_trace(
                domain="knowledge",
                trace_id=ingest_id,
                pipeline_mode=pipeline_mode,
                calls=llm_calls,
            )
            if partial_trace_ref:
                raise _PipelineTraceCaptureError(partial_trace_ref) from exc
            raise

        status = determine_status(
            candidate=candidate,
            critique=critique,
            judge=judge,
            min_score=runtime_knowledge["min_judge_score"],
            status_on_fail=runtime_knowledge["status_on_fail"],
            structural_issues=deterministic_issues,
        )

        candidate_path = self.state_root / "candidates" / "knowledge" / "{0}.json".format(ingest_id)
        critic_path = self.state_root / "reviews" / "knowledge" / "{0}-critic.json".format(ingest_id)
        judge_path = self.state_root / "reviews" / "knowledge" / "{0}-judge.json".format(ingest_id)
        llm_trace_ref = self._write_llm_trace(
            domain="knowledge",
            trace_id=ingest_id,
            pipeline_mode=pipeline_mode,
            calls=llm_calls,
        )
        self._write_json(candidate_path, candidate)
        self._write_json(critic_path, critique)
        self._write_json(judge_path, judge)

        category = self._pick_knowledge_category(candidate["tags"] or tags)
        knowledge_rel = self._allocate_knowledge_path(candidate["title"], category)
        knowledge_doc = self._render_knowledge_document(
            candidate=candidate,
            critique=critique,
            judge=judge,
            status=status,
            raw_ref=raw_ref,
            input_kind=input_kind,
            source_ref=source_ref,
        )
        self._write_text(self.repo_root / knowledge_rel, knowledge_doc)

        return {
            "knowledge_ref": knowledge_rel,
            "candidate_ref": self._relative(candidate_path),
            "critic_ref": self._relative(critic_path),
            "judge_ref": self._relative(judge_path),
            "llm_trace_ref": llm_trace_ref,
            "relay_request_ids": self._collect_relay_request_ids(llm_calls),
            "pipeline_mode": pipeline_mode,
            "knowledge_status": status,
            "judge_score": judge["score"],
            "judge_decision": judge["decision"],
            "release_reason": judge["reason"],
            "failure_reason": judge["reason"],
        }

    def _write_failure_receipt(
        self,
        ingest_id: str,
        input_kind: str,
        title: str,
        source_ref: str,
        initiator: str,
        error: str,
        source: Optional[str] = None,
        tags: Optional[List[str]] = None,
        promote_knowledge: bool = False,
    ) -> IngestReceipt:
        failure_path = self.state_root / "receipts" / "failures" / "{0}.json".format(ingest_id)
        receipt = IngestReceipt(
            id=ingest_id,
            status="failed",
            title=title,
            input_kind=input_kind,
            initiator=initiator,
            source_ref=source_ref,
            failure_ref=self._relative(failure_path),
            message=error,
        )
        payload = receipt.to_dict()
        payload["error"] = error
        self._write_json(failure_path, payload)
        self._archive_failure_case(
            stage="inject",
            category="ingest_fetch_failure",
            status="failed",
            reason=error,
            initiator=initiator,
            refs={
                "failure_ref": self._relative(failure_path),
                "source_ref": source_ref,
            },
            replay_command="inject_feishu_link",
            replay_args={
                "link": source_ref,
                "title": title,
                "source": source or "feishu import: {0}".format(source_ref),
                "tags": list(tags or []),
                "promote_knowledge": promote_knowledge,
            },
        )
        return receipt

    def _write_ingest_pipeline_failure_receipt(
        self,
        ingest_id: str,
        input_kind: str,
        title: str,
        source_ref: str,
        initiator: str,
        snapshot_ref: str,
        raw_ref: str,
        error: str,
        llm_trace_ref: str,
        pipeline_mode: Optional[str],
        source: str,
        content: str,
        tags: List[str],
    ) -> IngestReceipt:
        receipt = IngestReceipt(
            id=ingest_id,
            status="failed",
            title=title,
            input_kind=input_kind,
            initiator=initiator,
            source_ref=source_ref,
            snapshot_ref=snapshot_ref,
            raw_ref=raw_ref,
            pipeline_mode=pipeline_mode,
            llm_trace_ref=llm_trace_ref,
            relay_request_ids=self._read_relay_request_ids_from_trace_ref(llm_trace_ref),
            receipt_ref=None,
            message=error,
        )
        receipt_path = self.state_root / "receipts" / "inject" / "{0}.json".format(ingest_id)
        self._write_json(receipt_path, receipt.to_dict())
        receipt.receipt_ref = self._relative(receipt_path)
        self._write_json(receipt_path, receipt.to_dict())
        self._archive_failure_case(
            stage="knowledge",
            category="knowledge_pipeline_failure",
            status=receipt.status,
            reason=error,
            initiator=initiator,
            pipeline_mode=pipeline_mode,
            refs={
                "receipt_ref": receipt.receipt_ref,
                "snapshot_ref": receipt.snapshot_ref,
                "raw_ref": receipt.raw_ref,
                "llm_trace_ref": receipt.llm_trace_ref,
                "relay_request_ids": receipt.relay_request_ids,
            },
            replay_command="inject_text",
            replay_args={
                "text": content,
                "title": title,
                "source": source,
                "tags": tags,
                "promote_knowledge": True,
            },
        )
        return receipt

    def _write_insight_pipeline_failure_receipt(
        self,
        synthesis_id: str,
        initiator: str,
        evidence_refs: List[str],
        evidence_manifest: Optional[List[Dict[str, str]]],
        error: str,
        evidence_trace_ref: Optional[str],
        llm_trace_ref: str,
        pipeline_mode: Optional[str],
    ) -> InsightSynthesisReceipt:
        receipt = InsightSynthesisReceipt(
            id=synthesis_id,
            status="failed",
            initiator=initiator,
            evidence_refs=evidence_refs,
            evidence_manifest=list(evidence_manifest or []),
            evidence_trace_ref=evidence_trace_ref,
            pipeline_mode=pipeline_mode,
            llm_trace_ref=llm_trace_ref,
            relay_request_ids=self._read_relay_request_ids_from_trace_ref(llm_trace_ref),
            receipt_ref=None,
            message=error,
        )
        receipt = self._write_insight_receipt(receipt)
        self._archive_failure_case(
            stage="insights",
            category="insight_pipeline_failure",
            status=receipt.status,
            reason=error,
            initiator=initiator,
            pipeline_mode=pipeline_mode,
            refs={
                "receipt_ref": receipt.receipt_ref,
                "evidence_trace_ref": receipt.evidence_trace_ref,
                "llm_trace_ref": receipt.llm_trace_ref,
                "relay_request_ids": receipt.relay_request_ids,
            },
            replay_command="synthesize_insights",
            replay_args={},
        )
        return receipt

    def _run_insight_pipeline(
        self,
        synthesis_id: str,
        runtime_lock: Dict[str, Any],
        evidence_docs: List[Dict[str, object]],
    ) -> Dict[str, Any]:
        selected_client = self.insight_client
        selected_mode = getattr(selected_client, "mode", "unknown")
        try:
            return self._generate_insight_with_client(
                client=selected_client,
                pipeline_mode=selected_mode,
                synthesis_id=synthesis_id,
                runtime_lock=runtime_lock,
                evidence_docs=evidence_docs,
            )
        except Exception as exc:
            if selected_mode == "heuristic":
                raise
            partial_trace_ref = self._extract_trace_ref(exc)
            try:
                result = self._generate_insight_with_client(
                    client=self.fallback_insight_client,
                    pipeline_mode="heuristic-fallback",
                    synthesis_id=synthesis_id,
                    runtime_lock=runtime_lock,
                    evidence_docs=evidence_docs,
                )
            except Exception as fallback_exc:
                if partial_trace_ref:
                    raise _PipelineTraceCaptureError(partial_trace_ref, str(fallback_exc)) from fallback_exc
                raise
            if partial_trace_ref and not result.get("llm_trace_ref"):
                result["llm_trace_ref"] = partial_trace_ref
            if partial_trace_ref and not result.get("relay_request_ids"):
                result["relay_request_ids"] = self._read_relay_request_ids_from_trace_ref(partial_trace_ref)
            return result

    def _generate_insight_with_client(
        self,
        client,
        pipeline_mode: str,
        synthesis_id: str,
        runtime_lock: Dict[str, Any],
        evidence_docs: List[Dict[str, object]],
    ) -> Dict[str, Any]:
        runtime_insight = runtime_lock["runtime"]["insight"]
        profiles = runtime_lock["profiles"]
        writer_profile = profiles[runtime_insight["writer_profile"]]
        critic_profile = profiles[runtime_insight["critic_profile"]]
        judge_profile = profiles[runtime_insight["judge_profile"]]
        evidence_refs = [doc["path"] for doc in evidence_docs]
        llm_calls: List[Dict[str, Any]] = []

        try:
            candidate = self._invoke_client_method(
                client,
                preferred_name="write_candidate",
                legacy_name="write_insight_candidate",
                trace_calls=llm_calls,
                trace_stage="write",
                evidence_docs=evidence_docs,
                profile=writer_profile,
                min_evidence=runtime_insight["min_evidence"],
            )
            candidate = normalize_insight_candidate(
                candidate,
                fallback_title="Pattern: recurring evidence cluster",
                evidence=evidence_refs,
            )
            deterministic_issues = deterministic_insight_issues(candidate, runtime_insight["min_evidence"])

            critique = self._invoke_client_method(
                client,
                preferred_name="critique_candidate",
                legacy_name="critique_insight_candidate",
                trace_calls=llm_calls,
                trace_stage="critique",
                candidate=candidate,
                deterministic_issues=deterministic_issues,
                min_evidence=runtime_insight["min_evidence"],
                profile=critic_profile,
            )
            critique = normalize_critique(critique, deterministic_issues)

            judge = self._invoke_client_method(
                client,
                preferred_name="judge_candidate",
                legacy_name="judge_insight_candidate",
                trace_calls=llm_calls,
                trace_stage="judge",
                candidate=candidate,
                critique=critique,
                profile=judge_profile,
                min_judge_score=runtime_insight["min_judge_score"],
            )
            judge = normalize_judge(judge, min_score=runtime_insight["min_judge_score"])
        except Exception as exc:
            partial_trace_ref = self._write_llm_trace(
                domain="insights",
                trace_id=synthesis_id,
                pipeline_mode=pipeline_mode,
                calls=llm_calls,
            )
            if partial_trace_ref:
                raise _PipelineTraceCaptureError(partial_trace_ref) from exc
            raise

        status = determine_status(
            candidate=candidate,
            critique=critique,
            judge=judge,
            min_score=runtime_insight["min_judge_score"],
            status_on_fail=runtime_insight["status_on_fail"],
            structural_issues=deterministic_issues,
        )

        candidate_path = self.state_root / "candidates" / "insights" / "{0}.json".format(synthesis_id)
        critic_path = self.state_root / "reviews" / "insights" / "{0}-critic.json".format(synthesis_id)
        judge_path = self.state_root / "reviews" / "insights" / "{0}-judge.json".format(synthesis_id)
        llm_trace_ref = self._write_llm_trace(
            domain="insights",
            trace_id=synthesis_id,
            pipeline_mode=pipeline_mode,
            calls=llm_calls,
        )
        self._write_json(candidate_path, candidate)
        self._write_json(critic_path, critique)
        self._write_json(judge_path, judge)

        insight_rel = self._allocate_insight_path(candidate["title"])
        insight_doc = self._render_insight_document(candidate, critique, judge, status)
        self._write_text(self.repo_root / insight_rel, insight_doc)
        return {
            "insight_ref": insight_rel,
            "candidate_ref": self._relative(candidate_path),
            "critic_ref": self._relative(critic_path),
            "judge_ref": self._relative(judge_path),
            "llm_trace_ref": llm_trace_ref,
            "relay_request_ids": self._collect_relay_request_ids(llm_calls),
            "pipeline_mode": pipeline_mode,
            "insight_status": status,
            "failure_reason": judge["reason"],
        }

    def _render_raw_document(
        self,
        title: str,
        source: str,
        tags: List[str],
        input_kind: str,
        source_ref: str,
        content: str,
        knowledge_ref: Optional[str],
    ) -> str:
        lines = [
            "---",
            "title: {0}".format(title),
            "created: {0}".format(self.clock().isoformat()),
            "updated: {0}".format(self.clock().isoformat()),
            "tags: {0}".format(self._yaml_list(tags)),
            "status: active",
            "source: {0}".format(source),
            "---",
            "",
            "# {0}".format(title),
            "",
            "## Context",
            "",
            "- Input kind: `{0}`".format(input_kind),
            "- Source reference: `{0}`".format(source_ref),
            "",
            "## Content",
            "",
            content.rstrip(),
            "",
            "## Distillation",
            "",
        ]
        if knowledge_ref:
            lines.append("- Promoted to `{0}`".format(knowledge_ref))
        else:
            lines.append("- Awaiting knowledge promotion.")
        lines.append("")
        return "\n".join(lines)

    def _render_knowledge_document(
        self,
        candidate: Dict[str, Any],
        critique: Dict[str, Any],
        judge: Dict[str, Any],
        status: str,
        raw_ref: str,
        input_kind: str,
        source_ref: str,
    ) -> str:
        tags = candidate["tags"]
        key_takeaways = [
            "- Derived from `{0}`".format(raw_ref),
            "- Input kind: `{0}`".format(input_kind),
            "- Source reference: `{0}`".format(source_ref),
            "- Judge score: `{0:.2f}`".format(judge["score"]),
            "- Judge decision: `{0}`".format(judge["decision"]),
            "- Release reason: {0}".format(judge["reason"]),
        ]
        for issue in critique["issues"]:
            key_takeaways.append("- {0}".format(issue))

        lines = [
            "---",
            "title: {0}".format(candidate["title"]),
            "created: {0}".format(self.clock().isoformat()),
            "updated: {0}".format(self.clock().isoformat()),
            "tags: {0}".format(self._yaml_list(tags)),
            "status: {0}".format(status),
            "judge_score: {0:.2f}".format(judge["score"]),
            "judge_decision: {0}".format(judge["decision"]),
            "release_reason: {0}".format(judge["reason"]),
            "reuse_count: 0",
            "derived_from: [{0}]".format(raw_ref),
            "---",
            "",
            "# {0}".format(candidate["title"]),
            "",
            "## Context",
            "",
            candidate["context"] or "Imported from runtime snapshot.",
            "",
            "## Content",
            "",
            "### Root Cause",
            "",
            candidate["root_cause"] or "Root cause information is incomplete.",
            "",
            "### Fix Steps",
            "",
        ]
        lines.extend(self._render_markdown_list(candidate["fix_steps"], "Fix steps are incomplete."))
        lines.extend(
            [
                "",
                "### Verification",
                "",
            ]
        )
        lines.extend(self._render_markdown_list(candidate["verification"], "Verification information is incomplete."))
        lines.extend(
            [
                "",
                "## Key Takeaways",
                "",
            ]
        )
        lines.extend(key_takeaways)
        lines.extend(
            [
                "",
                "## Related",
                "",
                "- Raw source: `{0}`".format(raw_ref),
            ]
        )
        for related in candidate["related"]:
            lines.append("- Related knowledge: `{0}`".format(related))
        lines.append("")
        return "\n".join(lines)

    def _render_insight_document(
        self,
        candidate: Dict[str, Any],
        critique: Dict[str, Any],
        judge: Dict[str, Any],
        status: str,
    ) -> str:
        lines = [
            "---",
            "title: {0}".format(candidate["title"]),
            "created: {0}".format(self.clock().isoformat()),
            "updated: {0}".format(self.clock().isoformat()),
            "tags: {0}".format(self._yaml_list(candidate["tags"])),
            "status: {0}".format(status),
            "impact: {0}".format(candidate["impact"]),
            "evidence: [{0}]".format(", ".join(candidate["evidence"])),
            "---",
            "",
            "# {0}".format(candidate["title"]),
            "",
            "## Observation",
            "",
            candidate["observation"] or "Observation is incomplete.",
            "",
            "## Pattern",
            "",
            candidate["pattern"] or candidate["analysis"] or "Pattern is incomplete.",
            "",
            "## Diagnostic Ladder",
            "",
        ]
        lines.extend(
            self._render_markdown_list(
                candidate["diagnostic_ladder"],
                "Diagnostic ladder is incomplete.",
            )
        )
        lines.extend(
            [
                "",
                "## Mitigation Strategy",
                "",
            ]
        )
        lines.extend(
            self._render_markdown_list(
                candidate["mitigation"],
                candidate["application"] or "Mitigation guidance is incomplete.",
            )
        )
        lines.extend(
            [
                "",
                "## Anti-Patterns",
                "",
            ]
        )
        lines.extend(
            self._render_markdown_list(
                candidate["anti_patterns"],
                "Anti-pattern guidance is incomplete.",
            )
        )
        lines.extend(
            [
                "",
                "## Analysis",
                "",
                candidate["analysis"] or "Analysis is incomplete.",
                "",
                "## Evidence",
                "",
            ]
        )
        for ref in candidate["evidence"]:
            lines.append("- `{0}`".format(ref))
        lines.extend(
            [
                "",
                "## Key Takeaways",
                "",
                "- Judge score: `{0:.2f}`".format(judge["score"]),
                "- Judge decision: `{0}`".format(judge["decision"]),
                "- Release reason: {0}".format(judge["reason"]),
            ]
        )
        for issue in critique["issues"]:
            lines.append("- {0}".format(issue))
        lines.append("")
        return "\n".join(lines)

    def _pick_knowledge_category(self, tags: List[str]) -> str:
        tag_set = set(tags)
        if tag_set.intersection({"network", "dns", "ssh", "auth", "proxy", "incident"}):
            return "troubleshooting"
        if tag_set.intersection({"tool", "tools", "cli", "automation"}):
            return "tools"
        return "workflow"

    def _qualifies_for_knowledge(self, content: str, runtime_lock: Dict[str, Dict]) -> bool:
        min_chars = runtime_lock["runtime"]["knowledge"]["min_chars"]
        return len(content.strip()) >= int(min_chars)

    def _build_raw_to_knowledge_map(self) -> Dict[str, List[str]]:
        mapping: Dict[str, List[str]] = {}
        for doc in load_knowledge_documents(self.repo_root):
            for raw_ref in doc.get("derived_from") or []:
                key = str(raw_ref)
                mapping.setdefault(key, []).append(str(doc["path"]))
        return mapping

    def _classify_raw_document(self, raw_kind: str, status: str, knowledge_refs: List[str], qualifies: bool) -> str:
        if knowledge_refs:
            return "promoted"
        if raw_kind == "references":
            return "reference"
        if status.strip().lower() == "archived":
            return "archived"
        if qualifies:
            return "pending"
        return "too_short"

    def _raw_disposition_reason(self, disposition: str, min_chars: int) -> str:
        if disposition == "promoted":
            return "already referenced by at least one knowledge document"
        if disposition == "reference":
            return "reference material kept in raw/references; manual distillation only"
        if disposition == "archived":
            return "historical raw kept for traceability; not queued for promotion"
        if disposition == "pending":
            return "eligible for explicit promotion"
        return "content is below runtime.knowledge.min_chars={0}".format(min_chars)

    def _find_raw_document(self, raw_ref: str) -> Optional[Dict[str, object]]:
        for doc in load_raw_documents(self.repo_root):
            if str(doc["path"]) == raw_ref:
                return doc
        return None

    def _find_knowledge_document(self, knowledge_ref: str) -> Optional[Dict[str, object]]:
        for doc in load_knowledge_documents(self.repo_root):
            if str(doc["path"]) == knowledge_ref:
                return doc
        return None

    def _resolve_knowledge_publication_status(self, knowledge_ref: str) -> Optional[KnowledgePublicationStatus]:
        doc = self._find_knowledge_document(knowledge_ref)
        if doc is None:
            return None
        evaluation = self._evaluate_knowledge_doc_for_insights(doc)
        return build_knowledge_publication_status(
            knowledge_ref=knowledge_ref,
            document=doc,
            excluded_reason=evaluation["excluded_reason"],
            last_receipt_ref=self._find_latest_receipt_ref_for_knowledge(knowledge_ref),
        )

    def _find_latest_receipt_ref_for_knowledge(self, knowledge_ref: str) -> Optional[str]:
        matches: List[Path] = []
        for path in sorted(self.state_root.glob("receipts/**/*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if str(payload.get("knowledge_ref") or "").strip() == knowledge_ref:
                matches.append(path)
        if not matches:
            return None
        latest = max(matches, key=lambda path: (path.stat().st_mtime_ns, str(path)))
        return self._relative(latest)

    def _evaluate_knowledge_doc_for_insights(self, doc: Dict[str, object]) -> Dict[str, Any]:
        status = str(doc.get("status") or "").strip().lower()
        excluded_reason = None
        if status != "active":
            excluded_reason = "status_not_active"
        elif doc.get("superseded_by"):
            excluded_reason = "superseded"
        elif self._is_correction_like_knowledge(doc):
            excluded_reason = "correction_like"

        eligible_tags = []
        if excluded_reason is None:
            for tag in doc.get("tags") or []:
                normalized_tag = str(tag).strip().lower()
                if self._is_generic_insight_tag(normalized_tag):
                    continue
                eligible_tags.append(normalized_tag)
            if not eligible_tags:
                excluded_reason = "generic_tags_only"
        return {"eligible_tags": eligible_tags, "excluded_reason": excluded_reason}

    def _build_insight_evidence_manifest(self, evidence_docs: List[Dict[str, object]]) -> List[Dict[str, str]]:
        manifest: List[Dict[str, str]] = []
        for doc in evidence_docs:
            knowledge_ref = str(doc["path"])
            path = self.repo_root / knowledge_ref
            manifest.append(
                {
                    "knowledge_ref": knowledge_ref,
                    "fingerprint": self._content_digest(path.read_text(encoding="utf-8")),
                }
            )
        return manifest

    def _resolve_confirmed_insight_evidence(
        self,
        manifest: List[Dict[str, str]],
    ) -> tuple[List[Dict[str, object]], Optional[str]]:
        evidence_docs: List[Dict[str, object]] = []
        for item in manifest:
            knowledge_ref = str(item.get("knowledge_ref") or "").strip()
            fingerprint = str(item.get("fingerprint") or "").strip()
            if not knowledge_ref or not fingerprint:
                return [], "confirm receipt is missing evidence manifest"

            path = self.repo_root / knowledge_ref
            if not path.exists():
                return [], "knowledge evidence missing since preview: {0}".format(knowledge_ref)

            doc = self._find_knowledge_document(knowledge_ref)
            if doc is None:
                return [], "knowledge evidence missing since preview: {0}".format(knowledge_ref)

            evaluation = self._evaluate_knowledge_doc_for_insights(doc)
            if evaluation["excluded_reason"] is not None:
                return [], "knowledge evidence is no longer eligible: {0}".format(knowledge_ref)

            current_fingerprint = self._content_digest(path.read_text(encoding="utf-8"))
            if current_fingerprint != fingerprint:
                return [], "knowledge evidence drifted since preview: {0}".format(knowledge_ref)

            evidence_docs.append(doc)
        return evidence_docs, None

    def _annotate_raw_distillation(self, raw_ref: str, knowledge_ref: str) -> None:
        raw_path = self.repo_root / raw_ref
        text = raw_path.read_text(encoding="utf-8")
        note = "- Promoted to `{0}`".format(knowledge_ref)
        if note in text or "## Distillation" not in text:
            return
        if "- Awaiting knowledge promotion." in text:
            text = text.replace("- Awaiting knowledge promotion.", note, 1)
            self._write_text(raw_path, text)
            return

        match = re.search(r"(^##\s+Distillation\s*$)(?P<section>.*)\Z", text, flags=re.MULTILINE | re.DOTALL)
        if not match:
            return
        section = match.group("section")
        if not section.strip():
            replacement = "\n\n{0}\n".format(note)
        else:
            replacement = section.rstrip() + "\n" + note + "\n"
        updated = text[: match.start("section")] + replacement
        self._write_text(raw_path, updated)

    def _derive_title(self, content: str) -> str:
        for line in content.splitlines():
            stripped = line.strip().lstrip("#").strip()
            if stripped and not stripped.endswith(":"):
                return stripped[:80]
        return "Untitled Injection"

    def _allocate_raw_path(self, title: str, content: str) -> str:
        today = self.clock().isoformat()
        slug = self._slugify(title, content)
        path = Path("raw") / "captures" / "{0}-{1}.md".format(today, slug)
        return self._allocate_unique_relative_path(path)

    def _allocate_knowledge_path(self, title: str, category: str) -> str:
        slug = self._slugify(title, title)
        path = Path("knowledge") / category / "{0}.md".format(slug)
        return self._allocate_unique_relative_path(path)

    def _allocate_insight_path(self, title: str) -> str:
        slug = self._slugify(title, title)
        path = Path("insights") / "patterns" / "{0}.md".format(slug)
        return self._allocate_unique_relative_path(path)

    def _select_insight_evidence_with_trace(
        self,
        synthesis_id: str,
        knowledge_docs: List[Dict[str, object]],
        min_evidence: int,
    ) -> tuple[List[Dict[str, object]], str]:
        clusters: Dict[str, List[Dict[str, object]]] = {}
        document_evaluations = []
        eligible_docs = []
        for doc in knowledge_docs:
            evaluation = self._evaluate_knowledge_doc_for_insights(doc)
            eligible_tags = list(evaluation["eligible_tags"])
            excluded_reason = evaluation["excluded_reason"]
            if excluded_reason is None:
                for normalized_tag in eligible_tags:
                    clusters.setdefault(normalized_tag, []).append(doc)
                eligible_docs.append(doc)

            document_evaluations.append(
                {
                    "path": doc["path"],
                    "status": doc.get("status"),
                    "tags": list(doc.get("tags") or []),
                    "eligible_tags": eligible_tags,
                    "excluded_reason": excluded_reason or "",
                }
            )

        best_cluster: List[Dict[str, object]] = []
        best_score = -1
        seen_components = set()
        candidate_clusters = []
        cluster_inputs: List[Dict[str, Any]] = [
            {
                "generation_strategy": "tag_seed",
                "seed_tag": seed_tag,
                "docs": docs,
            }
            for seed_tag, docs in sorted(clusters.items(), key=lambda item: (-len(item[1]), item[0]))
        ]
        if eligible_docs:
            cluster_inputs.append(
                {
                    "generation_strategy": "retrieval_graph",
                    "seed_tag": "__retrieval__",
                    "docs": eligible_docs,
                }
            )

        for cluster_input in cluster_inputs:
            seed_tag = str(cluster_input["seed_tag"])
            generation_strategy = str(cluster_input["generation_strategy"])
            docs = list(cluster_input["docs"])
            unique_docs = []
            seen = set()
            for doc in docs:
                if doc["path"] in seen:
                    continue
                seen.add(doc["path"])
                unique_docs.append(doc)

            component_payloads = []
            for component in self._split_cluster_by_signal_cohesion(unique_docs):
                identity = tuple(sorted(str(doc["path"]) for doc in component))
                if identity in seen_components:
                    continue
                seen_components.add(identity)
                score = self._score_evidence_component(component)
                eligible = len(component) >= int(min_evidence)
                component_payloads.append(
                    {
                        "paths": list(identity),
                        "score": score,
                        "eligible": eligible,
                    }
                )
                if not eligible:
                    continue
                if score > best_score or (score == best_score and len(component) > len(best_cluster)):
                    best_cluster = component
                    best_score = score
            if component_payloads:
                candidate_clusters.append(
                    {
                        "generation_strategy": generation_strategy,
                        "seed_tag": seed_tag,
                        "paths": [str(doc["path"]) for doc in unique_docs],
                        "components": component_payloads,
                    }
                )

        trace_payload = {
            "schema_version": "insight_evidence_trace/v1",
            "selection_mode": "filtered_candidate_generation_plus_retrieval_signal_causal_reranking",
            "candidate_generation_modes": ["tag_seed", "retrieval_graph"],
            "min_evidence": int(min_evidence),
            "documents": document_evaluations,
            "candidate_clusters": candidate_clusters,
            "selected_paths": [str(doc["path"]) for doc in best_cluster],
            "selected_score": best_score if best_cluster else None,
        }
        return best_cluster, self._write_insight_evidence_trace(synthesis_id, trace_payload)

    def _is_correction_like_knowledge(self, doc: Dict[str, object]) -> bool:
        if str(doc.get("knowledge_kind") or "").strip().lower() == "correction":
            return True
        tags = {str(tag).strip().lower() for tag in (doc.get("tags") or [])}
        correction_tags = {"corrected", "correction", "superseded", "obsolete", "retracted"}
        if tags.intersection(correction_tags):
            return True
        title = str(doc.get("title") or "").strip().lower()
        body = str(doc.get("body") or "").strip().lower()
        correction_markers = ("corrected", "correction", "superseded", "obsolete", "retracted")
        return any(marker in title or marker in body for marker in correction_markers)

    def _is_generic_insight_tag(self, tag: str) -> bool:
        return tag in {
            "automation",
            "general",
            "misc",
            "note",
            "notes",
            "pattern",
            "patterns",
            "tool",
            "tools",
            "troubleshooting",
            "workflow",
        }

    def _split_cluster_by_signal_cohesion(self, docs: List[Dict[str, object]]) -> List[List[Dict[str, object]]]:
        if not docs:
            return []
        by_path = {str(doc["path"]): doc for doc in docs}
        adjacency = {path: set() for path in by_path}
        for index, left in enumerate(docs):
            left_path = str(left["path"])
            for right in docs[index + 1 :]:
                right_path = str(right["path"])
                if not self._evidence_pair_is_cohesive(left, right):
                    continue
                adjacency[left_path].add(right_path)
                adjacency[right_path].add(left_path)

        components: List[List[Dict[str, object]]] = []
        visited = set()
        for path in sorted(by_path):
            if path in visited:
                continue
            stack = [path]
            component_paths = []
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                component_paths.append(current)
                stack.extend(sorted(adjacency[current] - visited))
            if len(component_paths) < 2:
                continue
            components.append([by_path[item] for item in sorted(component_paths)])
        return components

    def _score_evidence_component(self, docs: List[Dict[str, object]]) -> int:
        score = len(docs) * 3
        for index, left in enumerate(docs):
            for right in docs[index + 1 :]:
                score += self._score_evidence_pair(left, right)
        return score

    def _score_evidence_pair(self, left: Dict[str, object], right: Dict[str, object]) -> int:
        shared_specific_tags = self._shared_specific_insight_tags(left, right)
        shared_signal_terms = self._extract_signal_terms(left).intersection(self._extract_signal_terms(right))
        shared_causal_terms = self._extract_causal_terms(left).intersection(self._extract_causal_terms(right))
        return (len(shared_specific_tags) * 2) + len(shared_signal_terms) + (len(shared_causal_terms) * 2)

    def _evidence_pair_is_cohesive(self, left: Dict[str, object], right: Dict[str, object]) -> bool:
        shared_specific_tags = self._shared_specific_insight_tags(left, right)
        shared_signal_terms = self._extract_signal_terms(left).intersection(self._extract_signal_terms(right))
        shared_causal_terms = self._extract_causal_terms(left).intersection(self._extract_causal_terms(right))
        if shared_causal_terms:
            return True
        if len(shared_specific_tags) >= 2 and len(shared_signal_terms) >= 1:
            return True
        if len(shared_specific_tags) >= 1 and len(shared_signal_terms) >= 2:
            return True
        return False

    def _shared_specific_insight_tags(self, left: Dict[str, object], right: Dict[str, object]) -> set[str]:
        left_tags = {
            str(tag).strip().lower()
            for tag in (left.get("tags") or [])
            if not self._is_generic_insight_tag(str(tag).strip().lower())
        }
        right_tags = {
            str(tag).strip().lower()
            for tag in (right.get("tags") or [])
            if not self._is_generic_insight_tag(str(tag).strip().lower())
        }
        return left_tags.intersection(right_tags)

    def _extract_signal_terms(self, doc: Dict[str, object]) -> set[str]:
        text = "{0}\n{1}".format(doc.get("title") or "", doc.get("body") or "")
        return self._tokenize_signal_terms(text)

    def _extract_causal_terms(self, doc: Dict[str, object]) -> set[str]:
        body = str(doc.get("body") or "")
        causal_lines = []
        for line in body.splitlines():
            lowered = line.strip().lower()
            if any(marker in lowered for marker in ("root cause", "caused", "causing", "because", "due to", "upstream")):
                causal_lines.append(line)
        if not causal_lines:
            return set()
        return self._tokenize_signal_terms("\n".join(causal_lines))

    def _tokenize_signal_terms(self, text: str) -> set[str]:
        stopwords = {
            "all",
            "and",
            "are",
            "away",
            "before",
            "been",
            "being",
            "but",
            "by",
            "active",
            "after",
            "analysis",
            "again",
            "an",
            "any",
            "as",
            "at",
            "be",
            "because",
            "between",
            "can",
            "could",
            "content",
            "context",
            "created",
            "diagnostic",
            "draft",
            "evidence",
            "for",
            "from",
            "fix",
            "guide",
            "into",
            "is",
            "incident",
            "issue",
            "knowledge",
            "keep",
            "kept",
            "mitigation",
            "note",
            "notes",
            "observation",
            "of",
            "on",
            "or",
            "out",
            "path",
            "pattern",
            "pointed",
            "repair",
            "root",
            "cause",
            "return",
            "returning",
            "steps",
            "structured",
            "that",
            "the",
            "their",
            "them",
            "there",
            "these",
            "this",
            "those",
            "through",
            "title",
            "to",
            "too",
            "troubleshooting",
            "updated",
            "via",
            "verification",
            "was",
            "were",
            "with",
            "without",
            "workflow",
        }
        terms = set()
        for token in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", text.lower()):
            if token.isdigit() or token in stopwords:
                continue
            terms.add(token)
        return terms

    def _allocate_unique_relative_path(self, path: Path) -> str:
        candidate = self.repo_root / path
        if not candidate.exists():
            return self._relative(candidate)
        digest = self._content_digest(str(path))[:8]
        suffixed = path.with_name("{0}-{1}{2}".format(path.stem, digest, path.suffix))
        return self._relative(self.repo_root / suffixed)

    def _slugify(self, text: str, fallback_seed: str) -> str:
        normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
        if slug:
            return slug
        return "entry-{0}".format(self._content_digest(fallback_seed)[:8])

    def _new_id(self) -> str:
        return "{0}-{1}".format(datetime.now(UTC).strftime("%Y%m%d%H%M%S"), uuid.uuid4().hex[:8])

    def _content_digest(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _yaml_list(self, items: Iterable[str]) -> str:
        values = [item for item in items if item]
        return "[{0}]".format(", ".join(values))

    def _render_markdown_list(self, items: Iterable[str], fallback: str) -> List[str]:
        values = [item for item in items if item]
        if not values:
            return [fallback]
        return ["- {0}".format(item) for item in values]

    def _invoke_client_method(
        self,
        client: Any,
        preferred_name: str,
        legacy_name: str,
        trace_calls: Optional[List[Dict[str, Any]]] = None,
        trace_stage: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        method = getattr(client, preferred_name, None)
        if method is None:
            method = getattr(client, legacy_name, None)
        if method is None:
            raise AttributeError(
                "client must implement `{0}` or `{1}`".format(
                    preferred_name,
                    legacy_name,
                )
            )
        try:
            return method(**kwargs)
        finally:
            if trace_calls is not None and trace_stage:
                self._append_llm_trace_call(client, trace_calls, stage=trace_stage)

    def _append_llm_trace_call(self, client: Any, calls: List[Dict[str, Any]], stage: str) -> None:
        trace = self._consume_client_call_trace(client)
        if not trace:
            return
        calls.append({"stage": stage, **trace})

    def _collect_relay_request_ids(self, calls: List[Dict[str, Any]]) -> Optional[List[str]]:
        request_ids: List[str] = []
        for call in calls:
            request_id = str(call.get("relay_request_id") or "").strip()
            if request_id and request_id not in request_ids:
                request_ids.append(request_id)
        return request_ids or None

    def _read_relay_request_ids_from_trace_ref(self, trace_ref: str) -> Optional[List[str]]:
        trace_path = self._resolve_state_path(trace_ref)
        if not trace_path.exists():
            return None
        payload = json.loads(trace_path.read_text(encoding="utf-8"))
        calls = payload.get("calls")
        if not isinstance(calls, list):
            return None
        request_ids: List[str] = []
        for call in calls:
            if not isinstance(call, dict):
                continue
            request_id = str(call.get("relay_request_id") or "").strip()
            if request_id and request_id not in request_ids:
                request_ids.append(request_id)
        return request_ids or None

    def _consume_client_call_trace(self, client: Any) -> Optional[Dict[str, Any]]:
        consumer = getattr(client, "consume_last_call_trace", None)
        if consumer is None:
            return None
        trace = consumer()
        if not trace:
            return None
        return dict(trace)

    def _write_llm_trace(
        self,
        domain: str,
        trace_id: str,
        pipeline_mode: str,
        calls: List[Dict[str, Any]],
    ) -> Optional[str]:
        if not calls:
            return None
        trace_path = self.state_root / "traces" / domain / "{0}.json".format(trace_id)
        payload = {
            "schema_version": "llm_trace/v1",
            "id": trace_id,
            "generated_at": self._now_iso(),
            "pipeline_mode": pipeline_mode,
            "calls": calls,
        }
        self._write_json(trace_path, payload)
        return self._relative(trace_path)

    def _write_insight_evidence_trace(self, synthesis_id: str, payload: Dict[str, Any]) -> str:
        trace_path = self.state_root / "traces" / "insights" / "{0}-evidence.json".format(synthesis_id)
        self._write_json(trace_path, payload)
        return self._relative(trace_path)

    def _extract_trace_ref(self, exc: Exception) -> Optional[str]:
        if isinstance(exc, _PipelineTraceCaptureError):
            return exc.trace_ref
        return None

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        self._ensure_dir(path.parent)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _write_raw_promotion_receipt(self, receipt: RawPromotionReceipt) -> RawPromotionReceipt:
        receipt_path = self.state_root / "receipts" / "raw_promote" / "{0}.json".format(receipt.id)
        self._write_json(receipt_path, receipt.to_dict())
        receipt.receipt_ref = self._relative(receipt_path)
        if receipt.knowledge_ref and receipt.last_receipt_ref is None:
            receipt.last_receipt_ref = receipt.receipt_ref
        self._write_json(receipt_path, receipt.to_dict())
        return receipt

    def _write_raw_promotion_batch_receipt(self, receipt: RawPromotionBatchReceipt) -> RawPromotionBatchReceipt:
        receipt_path = self.state_root / "receipts" / "raw_promote" / "{0}-batch.json".format(receipt.id)
        self._write_json(receipt_path, receipt.to_dict())
        receipt.receipt_ref = self._relative(receipt_path)
        self._write_json(receipt_path, receipt.to_dict())
        return receipt

    def _write_ready_promotion_batch_receipt(self, receipt: ReadyPromotionBatchReceipt) -> ReadyPromotionBatchReceipt:
        receipt_path = self.state_root / "receipts" / "ready_promote" / "{0}.json".format(receipt.id)
        self._write_json(receipt_path, receipt.to_dict())
        receipt.receipt_ref = self._relative(receipt_path)
        self._write_json(receipt_path, receipt.to_dict())
        return receipt

    def _write_insight_receipt(self, receipt: InsightSynthesisReceipt) -> InsightSynthesisReceipt:
        receipt_path = self.state_root / "receipts" / "insights" / "{0}.json".format(receipt.id)
        self._write_json(receipt_path, receipt.to_dict())
        receipt.receipt_ref = self._relative(receipt_path)
        self._write_json(receipt_path, receipt.to_dict())
        return receipt

    def _load_failure_cases(self, limit: int) -> List[Dict[str, Any]]:
        case_paths = sorted(
            (self.state_root / "failure_cases").glob("*/*.json"),
            key=lambda item: item.name,
            reverse=True,
        )
        cases: List[Dict[str, Any]] = []
        for path in case_paths[: max(0, int(limit))]:
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["case_ref"] = self._relative(path)
            cases.append(payload)
        return cases

    def _count_by_key(self, items: List[Dict[str, Any]], key: str) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for item in items:
            name = str(item.get(key) or "unknown")
            counts[name] = counts.get(name, 0) + 1
        return counts

    def _suggest_failure_actions(self, failure_cases: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        recommendations: List[Dict[str, str]] = []
        seen_actions = set()

        for case in failure_cases:
            category = str(case.get("category") or "")
            reason = str(case.get("reason") or "")

            if category == "ingest_fetch_failure":
                self._append_recommendation(
                    recommendations,
                    seen_actions,
                    action="repair_feishu_ingestion",
                    reason=reason,
                    suggestion="恢复 `lark-cli` 认证或权限，再重放 Feishu 导入失败样本。",
                )
                continue

            if category == "knowledge_draft":
                self._append_recommendation(
                    recommendations,
                    seen_actions,
                    action="tighten_knowledge_input_or_prompt",
                    reason=reason,
                    suggestion="补齐 root cause / fix steps / verification，或调整 knowledge writer prompt 强化这些字段。",
                )
                continue

            if category == "insight_skipped":
                self._append_recommendation(
                    recommendations,
                    seen_actions,
                    action="raise_evidence_supply_or_retune_threshold",
                    reason=reason,
                    suggestion="补充更多 active knowledge，或通过 `forge tune` 下调 insight `min_evidence`。",
                )
                continue

            if category == "insight_draft":
                self._append_recommendation(
                    recommendations,
                    seen_actions,
                    action="strengthen_insight_analysis",
                    reason=reason,
                    suggestion="增强 insight 分析与应用部分，必要时提高 evidence 质量后再重放。",
                )

        return recommendations

    def _suggest_failure_patches(self, failure_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        schema = load_or_create_patch_schema(self.app_root / "automation" / "schemas" / "patch.schema.json")
        runtime_lock = load_or_create_runtime_lock(self.app_root / "automation" / "compiled" / "runtime.lock.json")
        suggestions: List[Dict[str, Any]] = []
        seen_actions = set()
        categories = {str(case.get("category") or "") for case in failure_cases}

        if "knowledge_draft" in categories:
            patches = [
                {
                    "op": "add",
                    "path": "/prompts/knowledge_writer/domain_appendix/network",
                    "value": "必须明确 root cause、验证命令和回滚点。",
                    "reason": "Failure review observed recurring draft knowledge caused by incomplete root cause or verification sections.",
                }
            ]
            bundle = validate_patch_bundle(patches, schema)
            self._append_patch_suggestion(
                suggestions,
                seen_actions,
                action="tighten_knowledge_input_or_prompt",
                rationale="Knowledge draft cases indicate the writer guidance should force clearer root cause and verification output.",
                bundle=bundle,
            )

        current_min_evidence = int(runtime_lock["runtime"]["insight"]["min_evidence"])
        if "insight_skipped" in categories and current_min_evidence > 2:
            target_min_evidence = max(2, current_min_evidence - 1)
            patches = [
                {
                    "op": "replace",
                    "path": "/runtime/insight/min_evidence",
                    "value": target_min_evidence,
                    "reason": "Failure review observed skipped insight synthesis because the current evidence threshold is too strict.",
                }
            ]
            bundle = validate_patch_bundle(patches, schema)
            self._append_patch_suggestion(
                suggestions,
                seen_actions,
                action="raise_evidence_supply_or_retune_threshold",
                rationale="Lower the insight evidence floor by one step before replaying skipped insight cases.",
                bundle=bundle,
            )

        return suggestions

    def _append_recommendation(
        self,
        recommendations: List[Dict[str, str]],
        seen_actions: set,
        action: str,
        reason: str,
        suggestion: str,
    ) -> None:
        if action in seen_actions:
            return
        recommendations.append(
            {
                "action": action,
                "reason": reason,
                "suggestion": suggestion,
            }
        )
        seen_actions.add(action)

    def _append_patch_suggestion(
        self,
        suggestions: List[Dict[str, Any]],
        seen_actions: set,
        action: str,
        rationale: str,
        bundle: Dict[str, Any],
    ) -> None:
        if action in seen_actions:
            return
        suggestions.append(
            {
                "action": action,
                "rationale": rationale,
                "schema_version": bundle["version"],
                "patches": bundle["patches"],
            }
        )
        seen_actions.add(action)

    def _archive_failure_case(
        self,
        stage: str,
        category: str,
        status: str,
        reason: str,
        initiator: str,
        refs: Dict[str, Any],
        replay_command: str,
        replay_args: Dict[str, Any],
        pipeline_mode: Optional[str] = None,
    ) -> str:
        case_id = self._new_id()
        case_path = self.state_root / "failure_cases" / stage / "{0}.json".format(case_id)
        payload = {
            "id": case_id,
            "archived_at": self._now_iso(),
            "stage": stage,
            "category": category,
            "status": status,
            "reason": reason,
            "initiator": initiator,
            "pipeline_mode": pipeline_mode,
            "refs": refs,
            "replay": {
                "command": replay_command,
                "args": replay_args,
            },
        }
        self._write_json(case_path, payload)
        return self._relative(case_path)

    def _write_text(self, path: Path, content: str) -> None:
        self._ensure_dir(path.parent)
        path.write_text(content, encoding="utf-8")

    def _ensure_dir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def _relative(self, path: Path) -> str:
        if self._is_under(path, self.state_root):
            return str(Path("state") / path.relative_to(self.state_root))
        if self._is_under(path, self.repo_root):
            return str(path.relative_to(self.repo_root))
        if self._is_under(path, self.app_root):
            return str(path.relative_to(self.app_root))
        return str(path)

    def _is_under(self, path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
        except ValueError:
            return False
        return True

    def _resolve_repo_path(self, path: Union[str, Path]) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return self.repo_root / candidate

    def _resolve_state_path(self, path: Union[str, Path]) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        parts = candidate.parts
        if parts and parts[0] == "state":
            candidate = Path(*parts[1:]) if len(parts) > 1 else Path()
        return self.state_root / candidate

    def _normalize_raw_ref(self, raw_ref: Union[str, Path]) -> str:
        path = self._resolve_repo_path(raw_ref)
        try:
            relative = self._relative(path)
        except ValueError:
            return str(Path(raw_ref))
        return relative

    def _display_path(self, path: Path) -> str:
        try:
            return self._relative(path)
        except ValueError:
            return str(path)

    def _now_iso(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
