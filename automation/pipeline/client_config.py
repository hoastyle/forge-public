from __future__ import annotations

import os
import tomllib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class RemoteConnection:
    server: str
    token: str
    source: str
    config_path: Optional[str] = None


def get_client_config_path() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(config_home) if config_home else Path.home() / ".config"
    return base / "forge" / "config.toml"


def save_remote_connection(server: str, token: str) -> Path:
    config_path = get_client_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = "server = {0}\n".format(json.dumps(server.rstrip("/"), ensure_ascii=False))
    payload += "token = {0}\n".format(json.dumps(token, ensure_ascii=False))
    config_path.write_text(payload, encoding="utf-8")
    return config_path


def clear_remote_connection() -> Path:
    config_path = get_client_config_path()
    if config_path.exists():
        config_path.unlink()
    try:
        config_path.parent.rmdir()
    except OSError:
        pass
    return config_path


def load_remote_connection() -> Optional[RemoteConnection]:
    config_path = get_client_config_path()
    if not config_path.exists():
        return None
    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    server = str(payload.get("server") or "").strip().rstrip("/")
    token = str(payload.get("token") or "").strip()
    if not server:
        return None
    return RemoteConnection(
        server=server,
        token=token,
        source="config",
        config_path=str(config_path),
    )


def resolve_remote_connection(explicit_server: str = "", explicit_token: str = "") -> Optional[RemoteConnection]:
    server = explicit_server.strip().rstrip("/")
    token = explicit_token.strip()
    if server:
        if not token:
            token = os.environ.get("FORGE_TOKEN", "").strip()
        if not token:
            config_connection = load_remote_connection()
            if config_connection is not None:
                token = config_connection.token
        return RemoteConnection(server=server, token=token, source="argument")

    env_server = os.environ.get("FORGE_SERVER", "").strip().rstrip("/")
    if env_server:
        return RemoteConnection(
            server=env_server,
            token=token or os.environ.get("FORGE_TOKEN", "").strip(),
            source="environment",
        )

    return load_remote_connection()
