from __future__ import annotations

from typing import Any, Dict, Iterable, List


def normalize_text_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip().lstrip("-").strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        items = []
        for line in value.splitlines():
            cleaned = line.strip().lstrip("-").strip()
            if cleaned:
                items.append(cleaned)
        return items
    return [str(value).strip()]


def normalize_candidate(payload: Dict[str, Any], fallback_title: str, fallback_tags: Iterable[str]) -> Dict[str, Any]:
    fallback_tags = list(fallback_tags)
    candidate = {
        "title": str(payload.get("title") or fallback_title).strip(),
        "context": str(payload.get("context") or "").strip(),
        "root_cause": str(payload.get("root_cause") or "").strip(),
        "fix_steps": normalize_text_list(payload.get("fix_steps")),
        "verification": normalize_text_list(payload.get("verification")),
        "related": normalize_text_list(payload.get("related")),
        "tags": normalize_text_list(payload.get("tags")) or fallback_tags,
        "confidence": _normalize_confidence(payload.get("confidence")),
    }
    return candidate


def normalize_critique(payload: Dict[str, Any], deterministic_issues: Iterable[str]) -> Dict[str, Any]:
    merged_issues = []
    for item in list(deterministic_issues) + normalize_text_list(payload.get("issues")):
        if item not in merged_issues:
            merged_issues.append(item)

    summary = str(payload.get("summary") or "").strip()
    if not summary:
        summary = "Candidate passes deterministic checks." if not merged_issues else "; ".join(merged_issues)

    return {
        "issues": merged_issues,
        "requires_downgrade": bool(payload.get("requires_downgrade")) or bool(merged_issues),
        "summary": summary,
    }


def normalize_judge(payload: Dict[str, Any], min_score: float) -> Dict[str, Any]:
    score = _normalize_confidence(payload.get("score"))
    decision = str(payload.get("decision") or "").strip() or ("publish" if score >= min_score else "downgrade")
    status = str(payload.get("status") or "").strip() or ("active" if decision == "publish" else "draft")
    reason = str(payload.get("reason") or "").strip() or (
        "Meets the release bar." if decision == "publish" else "Below minimum judge threshold."
    )
    return {
        "score": score,
        "decision": decision,
        "status": status,
        "reason": reason,
    }


def deterministic_candidate_issues(candidate: Dict[str, Any]) -> List[str]:
    issues = []
    if not candidate["root_cause"]:
        issues.append("Root cause information is incomplete.")
    if not candidate["fix_steps"]:
        issues.append("Fix steps are incomplete.")
    if not candidate["verification"]:
        issues.append("Verification information is incomplete.")
    return issues


def determine_status(
    candidate: Dict[str, Any],
    critique: Dict[str, Any],
    judge: Dict[str, Any],
    min_score: float,
    status_on_fail: str,
    structural_issues: Iterable[str] = (),
) -> str:
    issues = list(structural_issues)
    if not issues and "root_cause" in candidate:
        issues = deterministic_candidate_issues(candidate)
    if issues:
        return status_on_fail
    if critique["requires_downgrade"]:
        return status_on_fail
    if judge["decision"] != "publish":
        return status_on_fail
    if judge["score"] < min_score:
        return status_on_fail
    return judge["status"] or "active"


def normalize_insight_candidate(payload: Dict[str, Any], fallback_title: str, evidence: Iterable[str]) -> Dict[str, Any]:
    evidence = list(evidence)
    analysis = str(payload.get("analysis") or "").strip()
    application = str(payload.get("application") or "").strip()
    candidate = {
        "title": str(payload.get("title") or fallback_title).strip(),
        "observation": str(payload.get("observation") or "").strip(),
        "analysis": analysis,
        "application": application,
        "pattern": str(payload.get("pattern") or analysis).strip(),
        "diagnostic_ladder": normalize_text_list(payload.get("diagnostic_ladder")) or normalize_text_list(application),
        "mitigation": normalize_text_list(payload.get("mitigation")) or normalize_text_list(application),
        "anti_patterns": normalize_text_list(payload.get("anti_patterns")),
        "impact": str(payload.get("impact") or "medium").strip() or "medium",
        "evidence": normalize_text_list(payload.get("evidence")) or evidence,
        "tags": normalize_text_list(payload.get("tags")),
        "confidence": _normalize_confidence(payload.get("confidence")),
    }
    return candidate


def deterministic_insight_issues(candidate: Dict[str, Any], min_evidence: int) -> List[str]:
    issues = []
    if len(candidate["evidence"]) < min_evidence:
        issues.append("Insight evidence is below the minimum threshold.")
    if not candidate["observation"]:
        issues.append("Insight observation is incomplete.")
    if not candidate["pattern"]:
        issues.append("Insight pattern is incomplete.")
    if not candidate["diagnostic_ladder"]:
        issues.append("Insight diagnostic ladder is incomplete.")
    if not candidate["mitigation"]:
        issues.append("Insight mitigation is incomplete.")
    return issues


def _normalize_confidence(value: Any) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0
