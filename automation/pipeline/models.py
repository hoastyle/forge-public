from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class IngestReceipt:
    id: str
    status: str
    title: str
    input_kind: str
    initiator: str
    source_ref: str
    snapshot_ref: Optional[str] = None
    raw_ref: Optional[str] = None
    knowledge_ref: Optional[str] = None
    failure_ref: Optional[str] = None
    receipt_ref: Optional[str] = None
    pipeline_mode: Optional[str] = None
    candidate_ref: Optional[str] = None
    critic_ref: Optional[str] = None
    judge_ref: Optional[str] = None
    llm_trace_ref: Optional[str] = None
    relay_request_ids: Optional[List[str]] = None
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Patch:
    op: str
    path: str
    value: Any
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TuneReceipt:
    id: str
    status: str
    initiator: str
    intent: str
    patches: List[Patch]
    lock_ref: str
    receipt_ref: Optional[str] = None
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["patches"] = [patch.to_dict() for patch in self.patches]
        return payload


@dataclass
class InsightSynthesisReceipt:
    id: str
    status: str
    initiator: str
    dry_run: bool = False
    confirmed_from_receipt_ref: Optional[str] = None
    evidence_refs: List[str] = field(default_factory=list)
    evidence_manifest: List[Dict[str, str]] = field(default_factory=list)
    evidence_trace_ref: Optional[str] = None
    insight_ref: Optional[str] = None
    candidate_ref: Optional[str] = None
    critic_ref: Optional[str] = None
    judge_ref: Optional[str] = None
    pipeline_mode: Optional[str] = None
    llm_trace_ref: Optional[str] = None
    relay_request_ids: Optional[List[str]] = None
    receipt_ref: Optional[str] = None
    error_code: Optional[str] = None
    next_step: Optional[str] = None
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReplayReceipt:
    id: str
    status: str
    initiator: str
    case_ref: str
    replay_command: str
    result_status: str
    result_receipt_ref: Optional[str] = None
    receipt_ref: Optional[str] = None
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FailureReviewReceipt:
    id: str
    status: str
    initiator: str
    case_count: int
    summary_ref: Optional[str] = None
    receipt_ref: Optional[str] = None
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AutoRetuneReceipt:
    id: str
    status: str
    initiator: str
    applied_actions: List[str]
    patches: List[Patch]
    lock_ref: Optional[str] = None
    review_summary_ref: Optional[str] = None
    review_receipt_ref: Optional[str] = None
    receipt_ref: Optional[str] = None
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["patches"] = [patch.to_dict() for patch in self.patches]
        return payload


@dataclass
class RawReviewReceipt:
    id: str
    status: str
    initiator: str
    total_count: int
    promoted_count: int
    pending_count: int
    too_short_count: int
    documents: List[Dict[str, Any]] = field(default_factory=list)
    receipt_ref: Optional[str] = None
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewQueueReceipt:
    id: str
    status: str
    initiator: str
    queue_name: str
    scanned_count: int
    queue_count: int
    ready_count: int
    blocked_count: int
    total_count: int
    pending_count: int
    too_short_count: int
    documents: List[Dict[str, Any]] = field(default_factory=list)
    items: List[Dict[str, Any]] = field(default_factory=list)
    receipt_ref: Optional[str] = None
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RawPromotionReceipt:
    id: str
    status: str
    initiator: str
    raw_ref: str
    knowledge_ref: Optional[str] = None
    knowledge_kind: Optional[str] = None
    candidate_ref: Optional[str] = None
    critic_ref: Optional[str] = None
    judge_ref: Optional[str] = None
    pipeline_mode: Optional[str] = None
    llm_trace_ref: Optional[str] = None
    relay_request_ids: Optional[List[str]] = None
    receipt_ref: Optional[str] = None
    message: Optional[str] = None
    publication_status: Optional[str] = None
    judge_score: Optional[float] = None
    judge_decision: Optional[str] = None
    eligible_for_insights: Optional[bool] = None
    excluded_reason: Optional[str] = None
    updated_at: Optional[str] = None
    last_receipt_ref: Optional[str] = None
    error_code: Optional[str] = None
    next_step: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RawPromotionBatchReceipt:
    id: str
    status: str
    initiator: str
    total_count: int
    success_count: int
    skipped_count: int
    failed_count: int
    results: List[Dict[str, Any]] = field(default_factory=list)
    receipt_ref: Optional[str] = None
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReadyPromotionBatchReceipt:
    id: str
    status: str
    initiator: str
    queue_receipt_ref: Optional[str]
    confirmed_from_receipt_ref: Optional[str]
    dry_run: bool
    limit: Optional[int]
    scanned_count: int
    ready_count: int
    targeted_count: int
    planned_count: int
    success_count: int
    skipped_count: int
    failed_count: int
    results: List[Dict[str, Any]] = field(default_factory=list)
    receipt_ref: Optional[str] = None
    error_code: Optional[str] = None
    next_step: Optional[str] = None
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
