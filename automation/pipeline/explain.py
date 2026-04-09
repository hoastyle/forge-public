from __future__ import annotations

from typing import Any, Dict, List


def build_insight_explanation(
    *,
    receipt_ref: str,
    evidence_trace_ref: str,
    trace_payload: Dict[str, Any],
) -> Dict[str, Any]:
    documents = list(trace_payload.get("documents") or [])
    excluded_documents: List[Dict[str, Any]] = []
    for document in documents:
        if not isinstance(document, dict):
            continue
        if str(document.get("excluded_reason") or "").strip():
            excluded_documents.append(document)

    return {
        "status": "success",
        "receipt_ref": receipt_ref,
        "evidence_trace_ref": evidence_trace_ref,
        "selected_paths": list(trace_payload.get("selected_paths") or []),
        "candidate_clusters": list(trace_payload.get("candidate_clusters") or []),
        "excluded_documents": excluded_documents,
    }
