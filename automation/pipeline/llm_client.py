from __future__ import annotations

import json
import re
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from .repo_env import build_litellm_credentials, resolve_provider_runtime_config, resolve_repo_setting


class PipelineClient(Protocol):
    mode: str

    def write_candidate(self, **kwargs) -> Dict[str, Any]:
        ...

    def critique_candidate(self, **kwargs) -> Dict[str, Any]:
        ...

    def judge_candidate(self, **kwargs) -> Dict[str, Any]:
        ...


class HeuristicJudgeMixin:
    mode = "heuristic"

    def judge_candidate(self, **kwargs) -> Dict[str, Any]:
        candidate = kwargs["candidate"]
        critique = kwargs["critique"]
        min_judge_score = float(kwargs["min_judge_score"])
        issues = len(critique.get("issues", []))
        base_score = candidate.get("confidence", 0.0) or 0.0
        score = max(0.0, round(base_score - (issues * 0.2), 2))
        decision = "publish" if (not critique.get("requires_downgrade") and score >= min_judge_score) else "downgrade"
        status = "active" if decision == "publish" else "draft"
        reason = "Meets the release bar." if decision == "publish" else critique["summary"]
        return {
            "score": score,
            "decision": decision,
            "status": status,
            "reason": reason,
        }


class LiteLLMStructuredClient:
    mode = "llm"

    def __init__(self, repo_root: Path, app_root: Path | None = None):
        try:
            from litellm.responses.main import responses
        except ImportError as exc:
            if getattr(exc, "name", "") in {"litellm", "litellm.responses", "litellm.responses.main"}:
                raise RuntimeError("litellm is not installed") from exc
            raise RuntimeError("litellm import failed: {0}".format(exc)) from exc

        self.repo_root = Path(repo_root)
        self.app_root = Path(app_root) if app_root is not None else self.repo_root
        self._responses = responses
        self._last_call_trace: Optional[Dict[str, Any]] = None

    def _call_json(self, prompt_name: str, profile: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self._load_prompt(prompt_name)
        provider = _provider_for_model(profile["model"])
        runtime_config = resolve_provider_runtime_config(provider, self.repo_root)
        correlation_context = _build_correlation_context(prompt_name)
        response_kwargs = {
            "model": profile["model"],
            "temperature": profile.get("temperature", 0.0),
            "input": self._build_input_text(prompt, payload),
            "text": {"format": {"type": "json_object"}},
            "store": False,
            "extra_headers": {
                correlation_context["header_name"]: correlation_context["correlation_id"],
            },
        }
        response_kwargs.update(build_litellm_credentials(profile["model"], self.repo_root))
        trace_payload = {
            "prompt_name": prompt_name,
            "model": profile["model"],
            "provider": provider,
            "api_base": response_kwargs.get("api_base", ""),
            "api_base_source": runtime_config.get("api_base_source", ""),
            "api_key_source": runtime_config.get("api_key_source", ""),
            "response_id": "",
            "relay_request_id": "",
            "output_text_present": False,
            "request_correlation_id": correlation_context["correlation_id"],
            "request_header_name": correlation_context["header_name"],
            "request_metadata": dict(correlation_context["metadata"]),
        }
        try:
            response = self._responses(**response_kwargs)
            trace_payload["response_id"] = str(getattr(response, "id", "") or "")
            trace_payload["relay_request_id"] = self._extract_relay_request_id(response)
            content = self._extract_output_text(response)
            trace_payload["output_text_present"] = bool(content.strip())
            return json.loads(content)
        except Exception as exc:
            if not trace_payload["relay_request_id"]:
                trace_payload["relay_request_id"] = self._extract_relay_request_id(exc)
            raise
        finally:
            self._last_call_trace = trace_payload

    def consume_last_call_trace(self) -> Optional[Dict[str, Any]]:
        payload = self._last_call_trace
        self._last_call_trace = None
        return payload

    def _load_prompt(self, prompt_name: str) -> str:
        prompt_path = self.app_root / "automation" / "prompts" / "{0}.md".format(prompt_name)
        return prompt_path.read_text(encoding="utf-8")

    def _build_input_text(self, prompt: str, payload: Dict[str, Any]) -> str:
        return "{0}\n\nPayload JSON:\n{1}".format(
            prompt.strip(),
            json.dumps(payload, ensure_ascii=False),
        )

    def _extract_output_text(self, response: Any) -> str:
        direct_text = getattr(response, "output_text", "")
        if direct_text:
            return direct_text

        chunks: List[str] = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", "") != "message":
                continue
            for content in getattr(item, "content", []) or []:
                if getattr(content, "type", "") == "output_text":
                    chunks.append(getattr(content, "text", ""))

        text = "".join(chunks).strip()
        if text:
            return text
        raise RuntimeError("LiteLLM responses() did not return output text")

    def _extract_relay_request_id(self, payload: Any) -> str:
        for headers in self._iter_response_header_maps(payload):
            request_id = self._find_header_value(
                headers,
                (
                    "x-oneapi-request-id",
                    "x-request-id",
                    "request-id",
                    "x-openai-request-id",
                    "openai-request-id",
                    "llm_provider-x-oneapi-request-id",
                    "llm_provider-x-request-id",
                    "llm_provider-request-id",
                    "llm_provider-x-openai-request-id",
                    "llm_provider-openai-request-id",
                ),
            )
            if request_id:
                return request_id
        return ""

    def _iter_response_header_maps(self, payload: Any) -> List[Mapping[str, Any]]:
        maps: List[Mapping[str, Any]] = []
        if payload is None:
            return maps

        direct_headers = getattr(payload, "headers", None)
        if isinstance(direct_headers, Mapping):
            maps.append(direct_headers)

        private_response_headers = getattr(payload, "_response_headers", None)
        if isinstance(private_response_headers, Mapping):
            maps.append(private_response_headers)

        litellm_response_headers = getattr(payload, "litellm_response_headers", None)
        if isinstance(litellm_response_headers, Mapping):
            maps.append(litellm_response_headers)

        hidden_params = getattr(payload, "_hidden_params", None)
        if isinstance(hidden_params, Mapping):
            for key in ("additional_headers", "headers", "response_headers"):
                candidate = hidden_params.get(key)
                if isinstance(candidate, Mapping):
                    maps.append(candidate)

        response = getattr(payload, "response", None)
        if response is not None:
            response_headers = getattr(response, "headers", None)
            if isinstance(response_headers, Mapping):
                maps.append(response_headers)
            nested_private_headers = getattr(response, "_response_headers", None)
            if isinstance(nested_private_headers, Mapping):
                maps.append(nested_private_headers)

        return maps

    def _find_header_value(self, headers: Mapping[str, Any], names: tuple[str, ...]) -> str:
        normalized = {str(key).lower(): str(value).strip() for key, value in headers.items() if str(value).strip()}
        for name in names:
            value = normalized.get(name)
            if value:
                return value
        return ""


class HeuristicKnowledgeClient(HeuristicJudgeMixin):
    def write_candidate(self, **kwargs) -> Dict[str, Any]:
        content = kwargs["content"]
        title = kwargs["title"]
        tags = list(kwargs.get("tags") or [])
        sections = _extract_sections(content)
        completeness = sum(
            1
            for value in (
                sections["context"],
                sections["root_cause"],
                sections["fix_steps"],
                sections["verification"],
            )
            if value
        )
        confidence = min(0.95, round(0.45 + (0.12 * completeness), 2))
        return {
            "title": title,
            "context": sections["context"] or "Imported from runtime snapshot.",
            "observation": sections["context"] or sections["root_cause"] or "Imported from runtime snapshot.",
            "root_cause": sections["root_cause"],
            "evidence": [item for item in (sections["context"], sections["root_cause"]) if item],
            "fix_steps": _split_lines(sections["fix_steps"]),
            "verification": _split_lines(sections["verification"]),
            "verified_results": _split_lines(sections["verification"]),
            "scope_limits": ["Applies only to the systems, inputs, and environment described in the source material."],
            "confidence_basis": "Confidence is based on captured evidence, recorded verification results, and a stated root cause.",
            "related": [],
            "tags": tags,
            "confidence": confidence,
        }

    def write_knowledge_candidate(self, **kwargs) -> Dict[str, Any]:
        return self.write_candidate(**kwargs)

    def critique_candidate(self, **kwargs) -> Dict[str, Any]:
        candidate = kwargs["candidate"]
        issues = []
        if not candidate["root_cause"]:
            issues.append("Root cause information is incomplete.")
        if not candidate["fix_steps"]:
            issues.append("Fix steps are incomplete.")
        if not candidate["verification"]:
            issues.append("Verification information is incomplete.")
        return {
            "issues": issues,
            "requires_downgrade": bool(issues),
            "summary": "Candidate passes deterministic checks." if not issues else "; ".join(issues),
        }

    def critique_knowledge_candidate(self, **kwargs) -> Dict[str, Any]:
        return self.critique_candidate(**kwargs)

    def judge_knowledge_candidate(self, **kwargs) -> Dict[str, Any]:
        return self.judge_candidate(**kwargs)


class LiteLLMKnowledgeClient(LiteLLMStructuredClient):
    def write_candidate(self, **kwargs) -> Dict[str, Any]:
        return self._call_json(
            prompt_name="knowledge_writer",
            profile=kwargs["profile"],
            payload={
                "title": kwargs["title"],
                "content": kwargs["content"],
                "tags": kwargs.get("tags") or [],
                "raw_ref": kwargs["raw_ref"],
                "source_ref": kwargs["source_ref"],
                "domain_appendix": kwargs.get("domain_appendix", ""),
            },
        )

    def critique_candidate(self, **kwargs) -> Dict[str, Any]:
        return self._call_json(
            prompt_name="critic",
            profile=kwargs["profile"],
            payload={
                "candidate": kwargs["candidate"],
                "deterministic_issues": list(kwargs.get("deterministic_issues") or []),
            },
        )

    def judge_candidate(self, **kwargs) -> Dict[str, Any]:
        return self._call_json(
            prompt_name="judge",
            profile=kwargs["profile"],
            payload={
                "candidate": kwargs["candidate"],
                "critique": kwargs["critique"],
                "min_judge_score": kwargs["min_judge_score"],
            },
        )

    def write_knowledge_candidate(self, **kwargs) -> Dict[str, Any]:
        return self.write_candidate(**kwargs)

    def critique_knowledge_candidate(self, **kwargs) -> Dict[str, Any]:
        return self.critique_candidate(**kwargs)

    def judge_knowledge_candidate(self, **kwargs) -> Dict[str, Any]:
        return self.judge_candidate(**kwargs)


def build_default_knowledge_client(repo_root: Path, app_root: Path | None = None) -> PipelineClient:
    client_name, _ = resolve_repo_setting("FORGE_KNOWLEDGE_CLIENT", Path(repo_root))
    client_name = client_name.strip().lower()
    if client_name == "litellm":
        return LiteLLMKnowledgeClient(repo_root, app_root=app_root)
    return HeuristicKnowledgeClient()


class HeuristicInsightClient(HeuristicJudgeMixin):
    def write_candidate(self, **kwargs) -> Dict[str, Any]:
        evidence_docs = list(kwargs["evidence_docs"])
        min_evidence = int(kwargs["min_evidence"])
        tag_counts = {}
        for doc in evidence_docs:
            for tag in doc["tags"]:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        dominant_tag = sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
        titles = [doc["title"] for doc in evidence_docs]
        confidence = min(0.97, round(0.5 + (0.1 * len(evidence_docs)), 2))
        impact = "high" if len(evidence_docs) >= max(3, min_evidence) else "medium"
        return {
            "title": "Pattern: {0} recurring incidents".format(dominant_tag),
            "observation": "Repeated incidents mention {0}: {1}".format(
                dominant_tag,
                "; ".join(titles[:3]),
            ),
            "analysis": "The same upstream pattern appears across multiple knowledge articles.",
            "application": "Use the dominant tag as an early diagnostic pivot during triage.",
            "pattern": "Treat {0} as the shared control-plane pattern before debugging downstream symptoms.".format(
                dominant_tag
            ),
            "diagnostic_ladder": [
                "Confirm the effective runtime state before changing configuration.",
                "Compare evidence across the selected knowledge documents.",
            ],
            "mitigation": [
                "Apply the lowest-cost mitigation that neutralizes the shared upstream cause.",
                "Persist the fix at the control-plane layer instead of relying on one-off client overrides.",
            ],
            "anti_patterns": [
                "Do not debug each symptom in isolation before checking the shared upstream pattern.",
            ],
            "impact": impact,
            "evidence": [doc["path"] for doc in evidence_docs],
            "tags": [dominant_tag, "pattern"],
            "confidence": confidence,
        }

    def write_insight_candidate(self, **kwargs) -> Dict[str, Any]:
        return self.write_candidate(**kwargs)

    def critique_candidate(self, **kwargs) -> Dict[str, Any]:
        candidate = kwargs["candidate"]
        min_evidence = int(kwargs["min_evidence"])
        issues = []
        if len(candidate["evidence"]) < min_evidence:
            issues.append("Insight evidence is below the minimum threshold.")
        if not candidate.get("pattern"):
            issues.append("Insight pattern is incomplete.")
        if not candidate.get("diagnostic_ladder"):
            issues.append("Insight diagnostic ladder is incomplete.")
        if not candidate.get("mitigation"):
            issues.append("Insight mitigation is incomplete.")
        return {
            "issues": issues,
            "requires_downgrade": bool(issues),
            "summary": "Insight passes deterministic checks." if not issues else "; ".join(issues),
        }

    def critique_insight_candidate(self, **kwargs) -> Dict[str, Any]:
        return self.critique_candidate(**kwargs)

    def judge_insight_candidate(self, **kwargs) -> Dict[str, Any]:
        return self.judge_candidate(**kwargs)


class LiteLLMInsightClient(LiteLLMStructuredClient):
    def write_candidate(self, **kwargs) -> Dict[str, Any]:
        return self._call_json(
            prompt_name="insight_writer",
            profile=kwargs["profile"],
            payload={
                "evidence_docs": kwargs["evidence_docs"],
                "min_evidence": kwargs["min_evidence"],
            },
        )

    def write_insight_candidate(self, **kwargs) -> Dict[str, Any]:
        return self.write_candidate(**kwargs)

    def critique_candidate(self, **kwargs) -> Dict[str, Any]:
        return self._call_json(
            prompt_name="critic",
            profile=kwargs["profile"],
            payload={
                "candidate": kwargs["candidate"],
                "deterministic_issues": list(kwargs.get("deterministic_issues") or []),
            },
        )

    def critique_insight_candidate(self, **kwargs) -> Dict[str, Any]:
        return self.critique_candidate(**kwargs)

    def judge_candidate(self, **kwargs) -> Dict[str, Any]:
        return self._call_json(
            prompt_name="judge",
            profile=kwargs["profile"],
            payload={
                "candidate": kwargs["candidate"],
                "critique": kwargs["critique"],
                "min_judge_score": kwargs["min_judge_score"],
            },
        )

    def judge_insight_candidate(self, **kwargs) -> Dict[str, Any]:
        return self.judge_candidate(**kwargs)


def build_default_insight_client(repo_root: Path, app_root: Path | None = None) -> PipelineClient:
    repo_root = Path(repo_root)
    client_name, _ = resolve_repo_setting("FORGE_INSIGHT_CLIENT", repo_root)
    client_name = client_name.strip().lower()
    if not client_name:
        client_name, _ = resolve_repo_setting("FORGE_KNOWLEDGE_CLIENT", repo_root)
        client_name = client_name.strip().lower()
    if client_name == "litellm":
        return LiteLLMInsightClient(repo_root, app_root=app_root)
    return HeuristicInsightClient()


def _extract_sections(content: str) -> Dict[str, str]:
    heading_map = {
        "context": "context",
        "背景": "context",
        "signals": "signals",
        "现象": "signals",
        "root cause": "root_cause",
        "根因": "root_cause",
        "原因": "root_cause",
        "fix steps": "fix_steps",
        "修复": "fix_steps",
        "处理步骤": "fix_steps",
        "verification": "verification",
        "验证": "verification",
    }
    current = "context"
    buckets = {
        "context": [],
        "signals": [],
        "root_cause": [],
        "fix_steps": [],
        "verification": [],
    }

    for raw_line in content.splitlines():
        line = raw_line.strip()
        matched = False
        for heading, bucket in heading_map.items():
            if re.match(r"^{0}\s*:$".format(re.escape(heading)), line, re.IGNORECASE):
                current = bucket
                matched = True
                break
        if matched:
            continue
        if line:
            buckets[current].append(line)

    return {key: "\n".join(value).strip() for key, value in buckets.items()}


def _split_lines(value: str) -> List[str]:
    items = []
    for line in value.splitlines():
        cleaned = line.strip().lstrip("-").strip()
        if cleaned:
            items.append(cleaned)
    return items


def _provider_for_model(model: str) -> str:
    if "/" not in model:
        return "unknown"
    return model.split("/", 1)[0].strip().lower()


def _build_correlation_context(prompt_name: str) -> Dict[str, Any]:
    correlation_id = "forge-{0}".format(uuid.uuid4().hex[:12])
    return {
        "correlation_id": correlation_id,
        "header_name": "x-forge-trace-id",
        "metadata": {
            "forge_trace_id": correlation_id,
            "forge_prompt_name": prompt_name,
        },
    }
