from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple


def load_repo_env(repo_root: Path) -> Dict[str, str]:
    env_path = Path(repo_root) / ".env"
    if not env_path.exists():
        return {}

    values: Dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = _strip_wrapping_quotes(raw_value.strip())
    return values


def describe_repo_env(repo_root: Path) -> Dict[str, Any]:
    env_path = Path(repo_root) / ".env"
    payload = {
        "path": str(env_path),
        "present": env_path.exists(),
        "keys": [],
    }
    if not env_path.exists():
        return payload

    payload["keys"] = sorted(load_repo_env(repo_root).keys())
    return payload


def resolve_provider_runtime_config(provider: str, repo_root: Path) -> Dict[str, Any]:
    repo_env = load_repo_env(repo_root)
    provider_name = provider.strip().lower()

    if provider_name == "openai":
        api_key, api_key_source = _resolve_value(["OPENAI_API_KEY"], repo_env)
        api_base, api_base_source = _resolve_value(["OPENAI_BASE_URL", "OPENAI_API_BASE"], repo_env)
        return {
            "env_vars": ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE"],
            "api_key": api_key,
            "api_key_source": api_key_source,
            "api_base": api_base,
            "api_base_source": api_base_source,
        }

    if provider_name == "anthropic":
        api_key, api_key_source = _resolve_value(["ANTHROPIC_API_KEY"], repo_env)
        api_base, api_base_source = _resolve_value(["ANTHROPIC_BASE_URL", "ANTHROPIC_API_BASE"], repo_env)
        return {
            "env_vars": ["ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_API_BASE"],
            "api_key": api_key,
            "api_key_source": api_key_source,
            "api_base": api_base,
            "api_base_source": api_base_source,
        }

    return {
        "env_vars": [],
        "api_key": "",
        "api_key_source": "",
        "api_base": "",
        "api_base_source": "",
    }


def build_litellm_credentials(model: str, repo_root: Path) -> Dict[str, Any]:
    provider = model.split("/", 1)[0].strip().lower() if "/" in model else "unknown"
    resolved = resolve_provider_runtime_config(provider, repo_root)
    credentials: Dict[str, Any] = {}
    if resolved["api_key"]:
        credentials["api_key"] = resolved["api_key"]
    if resolved["api_base"]:
        credentials["api_base"] = resolved["api_base"]
    return credentials


def resolve_repo_setting(name: str, repo_root: Path, aliases: Iterable[str] = ()) -> Tuple[str, str]:
    repo_env = load_repo_env(repo_root)
    return _resolve_value([name, *aliases], repo_env)


def _resolve_value(names: Iterable[str], repo_env: Dict[str, str]) -> Tuple[str, str]:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value, "env"
    for name in names:
        value = repo_env.get(name, "").strip()
        if value:
            return value, ".env"
    return "", ""


def _strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value
