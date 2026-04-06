from __future__ import annotations

import importlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .repo_env import describe_repo_env, resolve_provider_runtime_config, resolve_repo_setting

PROXY_ENV_VAR_NAMES = ("ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy")


def collect_dependency_report(repo_root: Path | None = None, app_root: Path | None = None) -> Dict[str, Any]:
    resolved_repo_root = Path(repo_root) if repo_root is not None else _guess_repo_root()
    resolved_app_root = Path(app_root) if app_root is not None else resolved_repo_root
    default_client_value, _ = resolve_repo_setting("FORGE_KNOWLEDGE_CLIENT", resolved_repo_root)
    default_client = "litellm" if default_client_value.strip().lower() == "litellm" else "heuristic"
    default_insight_value, _ = resolve_repo_setting("FORGE_INSIGHT_CLIENT", resolved_repo_root)
    default_insight_value = default_insight_value.strip().lower()
    if default_insight_value:
        default_insight_client = "litellm" if default_insight_value == "litellm" else "heuristic"
    else:
        default_insight_client = default_client
    lark_cli_available = shutil.which("lark-cli") is not None
    proxy_support = _collect_proxy_support_report()
    python_env = _python_environment()
    runtime_lock = _load_runtime_lock(resolved_app_root)
    enabled_sections: List[str] = []
    if default_client == "litellm":
        enabled_sections.append("knowledge")
    if default_insight_client == "litellm":
        enabled_sections.append("insight")
    provider_report = _collect_litellm_provider_report(runtime_lock, resolved_repo_root, enabled_sections=enabled_sections)
    litellm_runtime = _collect_litellm_runtime_report()
    litellm_requested = default_client == "litellm" or default_insight_client == "litellm"
    litellm_ready = bool(
        litellm_requested
        and litellm_runtime["importable"]
        and proxy_support["ready"]
        and provider_report["ready"]
    )
    return {
        "command": "doctor",
        "python_version": sys.version.split()[0],
        "python_environment": python_env,
        "paths": {
            "repo_root": str(resolved_repo_root),
            "app_root": str(resolved_app_root),
        },
        "default_knowledge_client": default_client,
        "default_insight_client": default_insight_client,
        "dependencies": {
            "lark_cli": {
                "available": lark_cli_available,
                "required_for": ["inject --feishu-link"],
                "optional": True,
            },
            "litellm": {
                "installed": litellm_runtime["installed"],
                "importable": litellm_runtime["importable"],
                "import_error": litellm_runtime["import_error"],
                "requested": litellm_requested,
                "ready": litellm_ready,
                "required_for": ["FORGE_KNOWLEDGE_CLIENT=litellm", "FORGE_INSIGHT_CLIENT=litellm"],
                "optional": True,
                "repo_local_enablement": _litellm_repo_local_enablement_steps(python_env),
                "provider_credentials": provider_report,
                "proxy_support": proxy_support,
            },
        },
        "third_party_dependencies": {
            "core_runtime": "python-stdlib",
            "required_python_packages": [],
            "optional_python_packages": [
                {
                    "name": "litellm",
                    "installed": litellm_runtime["installed"],
                    "importable": litellm_runtime["importable"],
                    "used_for": ["knowledge writer/critic/judge", "insight writer/critic/judge"],
                    "install_hint": "uv sync --extra llm",
                },
                {
                    "name": "socksio",
                    "installed": proxy_support["socksio_installed"],
                    "used_for": ["httpx SOCKS proxy support when all_proxy/ALL_PROXY uses socks:// or socks5://"],
                    "install_hint": "uv sync --extra llm --extra proxy",
                },
            ],
            "external_clis": [
                {
                    "name": "lark-cli",
                    "available": lark_cli_available,
                    "used_for": ["inject --feishu-link"],
                }
            ],
        },
    }


def _python_environment() -> Dict[str, Any]:
    base_prefix = getattr(sys, "base_prefix", None)
    in_venv = bool(base_prefix and sys.prefix != base_prefix) or bool(os.environ.get("VIRTUAL_ENV"))
    return {
        "executable": sys.executable,
        "in_venv": in_venv,
        "virtual_env": os.environ.get("VIRTUAL_ENV") or "",
    }


def _collect_proxy_support_report() -> Dict[str, Any]:
    proxy_env = {}
    for name in PROXY_ENV_VAR_NAMES:
        value = os.environ.get(name, "").strip()
        if value:
            proxy_env[name] = value

    socks_proxy_configured = any(value.lower().startswith("socks") for value in proxy_env.values())
    socksio_installed = importlib.util.find_spec("socksio") is not None
    clear_env_command = _proxy_clear_env_command() if proxy_env else ""
    warnings: List[str] = []
    if proxy_env:
        warnings.append(
            "Detected proxy env in current shell ({0}). LiteLLM/httpx will inherit process-level proxies before repo-local .env. "
            "If this is unintended, rerun with `{1} uv run forge ...`.".format(
                ", ".join(sorted(proxy_env.keys())),
                clear_env_command,
            )
        )
    if socks_proxy_configured and not socksio_installed:
        warnings.append(
            "SOCKS proxy detected but `socksio` is not installed; LiteLLM/httpx may fail before any request is sent. "
            "Install via `uv sync --extra llm --extra proxy` or clear the proxy env."
        )
    return {
        "proxy_env_present": bool(proxy_env),
        "proxy_env_names": sorted(proxy_env.keys()),
        "socks_proxy_configured": socks_proxy_configured,
        "socksio_installed": socksio_installed,
        "ready": (not socks_proxy_configured) or socksio_installed,
        "install_hint": "uv sync --extra llm --extra proxy" if socks_proxy_configured and not socksio_installed else "",
        "clear_env_command": clear_env_command,
        "warnings": warnings,
    }


def collect_runtime_proxy_warnings(repo_root: Path | None = None) -> List[str]:
    resolved_repo_root = Path(repo_root) if repo_root is not None else _guess_repo_root()
    default_client_value, _ = resolve_repo_setting("FORGE_KNOWLEDGE_CLIENT", resolved_repo_root)
    default_client = "litellm" if default_client_value.strip().lower() == "litellm" else "heuristic"
    default_insight_value, _ = resolve_repo_setting("FORGE_INSIGHT_CLIENT", resolved_repo_root)
    default_insight_value = default_insight_value.strip().lower()
    if default_insight_value:
        default_insight_client = "litellm" if default_insight_value == "litellm" else "heuristic"
    else:
        default_insight_client = default_client

    if default_client != "litellm" and default_insight_client != "litellm":
        return []

    proxy_support = _collect_proxy_support_report()
    return list(proxy_support["warnings"])


def _proxy_clear_env_command() -> str:
    return "env -u all_proxy -u http_proxy -u https_proxy -u ALL_PROXY -u HTTP_PROXY -u HTTPS_PROXY"


def _collect_litellm_runtime_report() -> Dict[str, Any]:
    installed = importlib.util.find_spec("litellm") is not None
    if not installed:
        return {
            "installed": False,
            "importable": False,
            "import_error": "litellm module not found",
        }

    try:
        responses_module = importlib.import_module("litellm.responses.main")
        getattr(responses_module, "responses")
    except Exception as exc:
        return {
            "installed": True,
            "importable": False,
            "import_error": "litellm.responses.main import failed: {0}: {1}".format(type(exc).__name__, exc),
        }

    return {
        "installed": True,
        "importable": True,
        "import_error": "",
    }


def _guess_repo_root() -> Path:
    # automation/pipeline/doctor.py -> automation/pipeline -> automation -> repo root
    return Path(__file__).resolve().parents[2]


def _load_runtime_lock(repo_root: Path) -> Dict[str, Any]:
    """
    Load the compiled runtime lock if present, otherwise fall back to the in-code defaults.

    Important: this function must not create files; doctor should remain side-effect free.
    """
    lock_path = Path(repo_root) / "automation" / "compiled" / "runtime.lock.json"
    if lock_path.exists():
        try:
            payload = json.loads(lock_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payload["_meta"] = {
                    "source": "file",
                    "path": str(lock_path),
                }
                return payload
        except Exception as exc:
            return {
                "_meta": {"source": "file-error", "path": str(lock_path), "error": str(exc)},
            }

    try:
        from .controller import DEFAULT_RUNTIME_LOCK  # local import to keep doctor lightweight

        payload = dict(DEFAULT_RUNTIME_LOCK)
        payload["_meta"] = {
            "source": "defaults",
            "path": str(lock_path),
            "note": "runtime.lock.json not found; using in-code defaults (no file created by doctor).",
        }
        return payload
    except Exception as exc:
        return {
            "_meta": {"source": "defaults-error", "path": str(lock_path), "error": str(exc)},
        }


def _collect_litellm_provider_report(
    runtime_lock: Dict[str, Any],
    repo_root: Path,
    enabled_sections: List[str] | None = None,
) -> Dict[str, Any]:
    profiles = runtime_lock.get("profiles") if isinstance(runtime_lock, dict) else None
    runtime = runtime_lock.get("runtime") if isinstance(runtime_lock, dict) else None
    meta = runtime_lock.get("_meta") if isinstance(runtime_lock, dict) else None
    repo_env = describe_repo_env(repo_root)
    selected_sections = list(enabled_sections or ["knowledge", "insight"])

    if not isinstance(profiles, dict) or not isinstance(runtime, dict):
        return {
            "runtime_lock": meta or {},
            "repo_env": repo_env,
            "profiles_used": [],
            "providers": [],
            "ready": False,
            "note": "runtime lock unavailable; cannot infer provider credentials requirements.",
        }

    used_profile_names: List[str] = []
    for section in selected_sections:
        section_payload = runtime.get(section)
        if not isinstance(section_payload, dict):
            continue
        for key in ("writer_profile", "critic_profile", "judge_profile"):
            name = section_payload.get(key)
            if isinstance(name, str) and name.strip():
                used_profile_names.append(name.strip())

    used_profile_names = sorted(set(used_profile_names))
    used_models: List[Tuple[str, str]] = []
    for name in used_profile_names:
        profile = profiles.get(name, {})
        if isinstance(profile, dict):
            model = profile.get("model")
            if isinstance(model, str) and model.strip():
                used_models.append((name, model.strip()))

    providers: Dict[str, Dict[str, Any]] = {}
    for profile_name, model in used_models:
        provider = model.split("/", 1)[0].strip().lower() if "/" in model else "unknown"
        providers.setdefault(provider, {"provider": provider, "models": [], "profiles": [], "env_vars": [], "credentials_present": False})
        providers[provider]["models"].append(model)
        providers[provider]["profiles"].append(profile_name)

    for provider, payload in providers.items():
        resolved = resolve_provider_runtime_config(provider, repo_root)
        payload["env_vars"] = resolved["env_vars"]
        payload["credentials_present"] = bool(resolved["api_key"])
        payload["credentials_source"] = resolved["api_key_source"]
        payload["base_url"] = resolved["api_base"]
        payload["base_url_source"] = resolved["api_base_source"]
        payload["models"] = sorted(set(payload["models"]))
        payload["profiles"] = sorted(set(payload["profiles"]))

    providers_list = sorted(providers.values(), key=lambda item: item["provider"])
    ready = bool(providers_list) and all(item["credentials_present"] for item in providers_list)
    return {
        "runtime_lock": meta or {},
        "repo_env": repo_env,
        "sections": selected_sections,
        "profiles_used": used_profile_names,
        "providers": providers_list,
        "ready": ready,
        "note": "Provider config is inferred from model prefixes and resolved from process env first, then repo-local .env.",
    }


def _litellm_repo_local_enablement_steps(python_env: Dict[str, Any]) -> Dict[str, Any]:
    in_venv = bool(python_env.get("in_venv"))
    proxy_support = _collect_proxy_support_report()
    venv_note = (
        "Detected virtualenv; prefer syncing declared extras into this env via uv."
        if in_venv
        else "No virtualenv detected; create a repo-local uv-managed venv to avoid system installs."
    )
    install_step = {
        "name": "Install the repo-declared LiteLLM extras into the uv-managed venv",
        "run": [
            "uv sync --extra llm",
        ],
    }
    if proxy_support["socks_proxy_configured"] and not proxy_support["socksio_installed"]:
        install_step["note"] = (
            "Current shell still exports a SOCKS proxy. If that proxy is intentional, install proxy support via "
            "`uv sync --extra llm --extra proxy`; otherwise clear the inherited proxy env before running Forge."
        )
    steps = [
        {
            "name": "Create and activate a repo-local uv venv (recommended)",
            "run": [
                "uv venv .venv",
                "source .venv/bin/activate",
            ],
            "skip_if": "already_in_venv" if in_venv else "",
        },
    ]
    if proxy_support["proxy_env_present"]:
        steps.append(
            {
                "name": "If the current shell should not use a proxy, clear inherited proxy env first",
                "run": [
                    "{0} uv run forge doctor".format(proxy_support["clear_env_command"]),
                ],
                "note": "LiteLLM/httpx honors process-level proxy env before repo-local .env. Skip this if the proxy is intentional.",
            }
        )
    steps.extend(
        [
            install_step,
            {
                "name": "Write repo-local runtime config into .env",
                "run": [
                    "cat > .env <<'EOF'",
                    "FORGE_KNOWLEDGE_CLIENT=litellm",
                    "FORGE_INSIGHT_CLIENT=litellm",
                    "OPENAI_API_KEY=...",
                    "OPENAI_BASE_URL=https://your-openai-compatible-endpoint/v1",
                    "EOF",
                ],
            },
            {
                "name": "Optional: add other provider keys if your runtime lock uses them",
                "run": [
                    "# ANTHROPIC_API_KEY=...       # if using anthropic/* models",
                    "# ANTHROPIC_BASE_URL=https://your-anthropic-compatible-endpoint",
                ],
            },
            {
                "name": "Verify",
                "run": [
                    "uv run forge doctor",
                ],
            },
        ]
    )
    return {
        "intent": "Enable LiteLLM SDK runtime for knowledge/insight pipelines without system-level installs.",
        "note": venv_note,
        "steps": steps,
        "smoke_test": {
            "name": "Trigger a real LLM-backed knowledge promotion (requires valid provider keys)",
            "run": [
                'uv run forge inject --text "Context:\\nA packet capture confirmed the gateway was rewriting DNS answers after the router reboot.\\n\\nRoot cause:\\nThe repo-local .env was missing the OpenAI-compatible relay base URL, so LiteLLM could not use the intended endpoint.\\n\\nFix steps:\\n- Add OPENAI_API_KEY to .env.\\n- Set OPENAI_BASE_URL to your relay endpoint.\\n- Re-run the doctor command to confirm provider readiness.\\n\\nVerification:\\n- doctor reports the openai provider as ready.\\n- the inject receipt reports pipeline_mode as llm and includes llm_trace_ref plus relay_request_ids." --title "litellm smoke test" --promote-knowledge',
            ],
            "expect": "receipt.pipeline_mode == 'llm' and receipt.llm_trace_ref is not None and receipt.relay_request_ids is not None",
        },
    }
