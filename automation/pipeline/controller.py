from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from .models import Patch

PATCH_SCHEMA_VERSION = 1

DEFAULT_PATCH_SCHEMA = {
    "version": PATCH_SCHEMA_VERSION,
    "allowed_ops": ["add", "replace"],
    "required_fields": ["op", "path", "value", "reason"],
    "paths": {
        "/runtime/insight/min_evidence": {
            "type": "integer",
            "ops": ["replace"],
            "minimum": 2,
        },
        "/runtime/insight/judge_profile": {
            "type": "string",
            "ops": ["replace"],
            "minLength": 1,
        },
        "/runtime/knowledge/writer_profile": {
            "type": "string",
            "ops": ["replace"],
            "minLength": 1,
        },
        "/prompts/knowledge_writer/domain_appendix/network": {
            "type": "string",
            "ops": ["add", "replace"],
            "minLength": 1,
        },
    },
}

ALLOWED_PATCH_PATHS = set(DEFAULT_PATCH_SCHEMA["paths"].keys())

DEFAULT_RUNTIME_LOCK = {
    "version": 1,
    "profiles": {
        "writer_cheap": {"model": "openai/gpt-5.4", "temperature": 0.1},
        "writer_mid": {"model": "openai/gpt-5.4", "temperature": 0.2},
        "judge_mid": {"model": "openai/gpt-5.4", "temperature": 0.0},
        "judge_strong": {"model": "openai/gpt-5.4", "temperature": 0.0},
    },
    "runtime": {
        "knowledge": {
            "writer_profile": "writer_cheap",
            "critic_profile": "judge_mid",
            "judge_profile": "judge_mid",
            "min_chars": 80,
            "min_judge_score": 0.82,
            "status_on_fail": "draft",
        },
        "insight": {
            "writer_profile": "writer_cheap",
            "critic_profile": "judge_mid",
            "judge_profile": "judge_mid",
            "min_evidence": 2,
            "min_judge_score": 0.88,
            "status_on_fail": "draft",
        },
    },
    "prompts": {
        "knowledge_writer": {
            "domain_appendix": {
                "network": "",
            }
        }
    },
}

DEFAULT_GOLDEN_CASES = [
    {
        "name": "insight-min-evidence-floor",
        "type": "minimum",
        "path": "/runtime/insight/min_evidence",
        "min": 2,
    },
    {
        "name": "insight-judge-profile-valid",
        "type": "profile_exists",
        "path": "/runtime/insight/judge_profile",
    },
    {
        "name": "knowledge-writer-profile-valid",
        "type": "profile_exists",
        "path": "/runtime/knowledge/writer_profile",
    },
]


def compile_intent_to_patches(intent: str) -> List[Patch]:
    text = intent.strip()
    patches: List[Patch] = []

    evidence_match = re.search(r"(evidence|证据).{0,12}(至少|at least)\s*(\d+)", text, re.IGNORECASE)
    if evidence_match:
        patches.append(
            Patch(
                op="replace",
                path="/runtime/insight/min_evidence",
                value=int(evidence_match.group(3)),
                reason="Raise insight evidence floor from natural-language tuning intent.",
            )
        )

    if re.search(r"judge.{0,12}(更强|strong)", text, re.IGNORECASE):
        patches.append(
            Patch(
                op="replace",
                path="/runtime/insight/judge_profile",
                value="judge_strong",
                reason="Use the stronger judge profile when the intent explicitly asks for it.",
            )
        )

    if re.search(r"(raw\s*->\s*knowledge|knowledge).{0,16}(便宜|cheap)", text, re.IGNORECASE):
        patches.append(
            Patch(
                op="replace",
                path="/runtime/knowledge/writer_profile",
                value="writer_cheap",
                reason="Switch the knowledge writer to the cheaper profile on request.",
            )
        )

    if re.search(r"(network|网络).{0,20}(root cause|根因).{0,12}(权重|强调|weight)", text, re.IGNORECASE):
        patches.append(
            Patch(
                op="add",
                path="/prompts/knowledge_writer/domain_appendix/network",
                value="必须明确 root cause、验证命令和回滚点。",
                reason="Strengthen network-domain writing guidance when requested.",
            )
        )

    if not patches:
        raise ValueError("could not compile any allowed patch from the provided intent")

    return patches


def load_or_create_patch_schema(schema_path: Path) -> Dict[str, Any]:
    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        _validate_patch_schema_definition(schema)
        return schema
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(
        json.dumps(DEFAULT_PATCH_SCHEMA, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return copy.deepcopy(DEFAULT_PATCH_SCHEMA)


def load_or_create_runtime_lock(lock_path: Path) -> Dict[str, Any]:
    if lock_path.exists():
        return json.loads(lock_path.read_text(encoding="utf-8"))
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps(DEFAULT_RUNTIME_LOCK, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return copy.deepcopy(DEFAULT_RUNTIME_LOCK)


def load_or_create_golden_cases(cases_path: Path) -> List[Dict[str, Any]]:
    if cases_path.exists():
        return json.loads(cases_path.read_text(encoding="utf-8"))
    cases_path.parent.mkdir(parents=True, exist_ok=True)
    cases_path.write_text(
        json.dumps(DEFAULT_GOLDEN_CASES, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return copy.deepcopy(DEFAULT_GOLDEN_CASES)


def validate_patch_bundle(patches: Iterable[Patch], schema: Dict[str, Any]) -> Dict[str, Any]:
    _validate_patch_schema_definition(schema)

    normalized_patches = [_normalize_patch(patch) for patch in patches]
    if not normalized_patches:
        raise ValueError("patch bundle cannot be empty")

    required_fields = set(schema["required_fields"])
    allowed_ops = set(schema["allowed_ops"])
    path_rules = schema["paths"]

    for payload in normalized_patches:
        if set(payload.keys()) != required_fields:
            raise ValueError("patch fields mismatch schema")

        reason = payload["reason"]
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("patch reason must be a non-empty string")

        path = payload["path"]
        if path not in path_rules:
            raise ValueError("patch path is not allowed: {0}".format(path))

        op = payload["op"]
        if op not in allowed_ops:
            raise ValueError("patch op is not allowed: {0}".format(op))

        rule = path_rules[path]
        if op not in set(rule["ops"]):
            raise ValueError("patch op is not allowed for path: {0}".format(path))

        _validate_patch_value(payload["value"], rule)

    return {"version": schema["version"], "patches": normalized_patches}


def apply_patches(
    lock_payload: Dict[str, Any],
    patches: Iterable[Patch],
    schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    bundle = validate_patch_bundle(patches, schema or DEFAULT_PATCH_SCHEMA)
    updated = copy.deepcopy(lock_payload)
    for patch in bundle["patches"]:
        pointer = updated
        parts = [part for part in patch["path"].split("/") if part]
        for key in parts[:-1]:
            pointer = pointer[key]
        pointer[parts[-1]] = patch["value"]
    return updated


def run_replay_evals(lock_payload: Dict[str, Any], golden_cases: Iterable[Dict[str, Any]]) -> None:
    for case in golden_cases:
        value = _get_value(lock_payload, case["path"])
        if case["type"] == "minimum":
            if value < case["min"]:
                raise ValueError("replay eval failed: {0}".format(case["name"]))
        elif case["type"] == "profile_exists":
            profiles = lock_payload["profiles"]
            if value not in profiles:
                raise ValueError("replay eval failed: {0}".format(case["name"]))
        else:
            raise ValueError("unsupported golden case type: {0}".format(case["type"]))


def _get_value(payload: Dict[str, Any], pointer: str) -> Any:
    current: Any = payload
    for part in [item for item in pointer.split("/") if item]:
        current = current[part]
    return current


def _normalize_patch(patch: Union[Patch, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(patch, Patch):
        return patch.to_dict()
    if isinstance(patch, dict):
        return dict(patch)
    raise ValueError("patch must be a Patch instance or dict payload")


def _validate_patch_schema_definition(schema: Dict[str, Any]) -> None:
    if not isinstance(schema, dict):
        raise ValueError("patch schema must be a JSON object")
    if schema.get("version") != PATCH_SCHEMA_VERSION:
        raise ValueError("unsupported patch schema version: {0}".format(schema.get("version")))
    if not isinstance(schema.get("allowed_ops"), list) or not schema["allowed_ops"]:
        raise ValueError("patch schema must define allowed_ops")
    if not isinstance(schema.get("required_fields"), list) or not schema["required_fields"]:
        raise ValueError("patch schema must define required_fields")
    if not isinstance(schema.get("paths"), dict) or not schema["paths"]:
        raise ValueError("patch schema must define path rules")


def _validate_patch_value(value: Any, rule: Dict[str, Any]) -> None:
    value_type = rule["type"]
    if value_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("patch value type mismatch: expected integer")
        minimum = rule.get("minimum")
        if minimum is not None and value < minimum:
            raise ValueError("patch value is below minimum: {0}".format(minimum))
        return

    if value_type == "string":
        if not isinstance(value, str):
            raise ValueError("patch value type mismatch: expected string")
        if len(value.strip()) < rule.get("minLength", 0):
            raise ValueError("patch value is shorter than allowed")
        return

    raise ValueError("unsupported patch value type: {0}".format(value_type))
