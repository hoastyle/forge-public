from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional


@dataclass
class KnowledgePublicationStatus:
    knowledge_ref: str
    publication_status: Optional[str]
    judge_score: Optional[float]
    judge_decision: Optional[str]
    release_reason: Optional[str]
    eligible_for_insights: bool
    excluded_reason: Optional[str]
    updated_at: Optional[str]
    last_receipt_ref: Optional[str]


def build_knowledge_publication_status(
    *,
    knowledge_ref: str,
    document: Mapping[str, object],
    excluded_reason: Optional[str],
    last_receipt_ref: Optional[str],
) -> KnowledgePublicationStatus:
    publication_status = _normalize_optional_text(document.get("status"))
    judge_decision = _normalize_optional_text(document.get("judge_decision"))
    release_reason = _normalize_optional_text(document.get("release_reason"))
    updated_at = _normalize_optional_text(document.get("updated_at"))
    return KnowledgePublicationStatus(
        knowledge_ref=knowledge_ref,
        publication_status=publication_status,
        judge_score=_parse_optional_float(document.get("judge_score")),
        judge_decision=judge_decision,
        release_reason=release_reason,
        eligible_for_insights=excluded_reason is None,
        excluded_reason=excluded_reason,
        updated_at=updated_at,
        last_receipt_ref=last_receipt_ref,
    )


def _normalize_optional_text(value: object) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _parse_optional_float(value: object) -> Optional[float]:
    text = _normalize_optional_text(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None
