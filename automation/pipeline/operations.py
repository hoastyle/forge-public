from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Optional


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize_value(sub_value) for key, sub_value in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_value(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def normalize_operation_payload(command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = _normalize_value(dict(payload))
    if isinstance(normalized, dict):
        normalized.pop("operation_id", None)
    return {"command": command, "payload": normalized}


def payload_fingerprint(command: str, payload: Dict[str, Any]) -> str:
    normalized = normalize_operation_payload(command, payload)
    serialized = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def new_operation_id(command: str) -> str:
    return "{0}-{1}".format(command, uuid.uuid4().hex[:12])


@dataclass
class OperationRecord:
    operation_id: str
    command: str
    fingerprint: str
    normalized_payload: Dict[str, Any]
    status: str
    created_at: str
    updated_at: str
    response: Optional[Dict[str, Any]] = None
    response_status_code: Optional[int] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "OperationRecord":
        return cls(
            operation_id=str(payload["operation_id"]),
            command=str(payload["command"]),
            fingerprint=str(payload["fingerprint"]),
            normalized_payload=dict(payload.get("normalized_payload") or {}),
            status=str(payload.get("status") or "completed"),
            created_at=str(payload.get("created_at") or _now_iso()),
            updated_at=str(payload.get("updated_at") or _now_iso()),
            response=dict(payload["response"]) if isinstance(payload.get("response"), dict) else None,
            response_status_code=payload.get("response_status_code"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OperationConflictError(RuntimeError):
    def __init__(
        self,
        operation_id: str,
        command: str,
        stored_command: str,
        stored_fingerprint: str,
        requested_fingerprint: str,
    ) -> None:
        self.operation_id = operation_id
        self.command = command
        self.stored_command = stored_command
        self.stored_fingerprint = stored_fingerprint
        self.requested_fingerprint = requested_fingerprint
        super().__init__(
            "operation_id '{0}' already exists for command '{1}' with a different payload fingerprint".format(
                operation_id,
                stored_command,
            )
        )


class OperationStore:
    def __init__(self, state_root: Path):
        self.state_root = Path(state_root)
        self.operations_root = self.state_root / "service" / "operations"
        self.operations_root.mkdir(parents=True, exist_ok=True)

    def _path(self, operation_id: str) -> Path:
        return self.operations_root / "{0}.json".format(operation_id)

    def read(self, operation_id: str) -> Optional[OperationRecord]:
        path = self._path(operation_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return OperationRecord.from_dict(payload)

    def write(self, record: OperationRecord) -> None:
        path = self._path(record.operation_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def claim(
        self,
        command: str,
        payload: Dict[str, Any],
        operation_id: Optional[str],
    ) -> tuple[str, Optional[OperationRecord]]:
        resolved_operation_id = (operation_id or "").strip() or new_operation_id(command)
        requested_fingerprint = payload_fingerprint(command, payload)
        existing = self.read(resolved_operation_id)
        if existing is None:
            return resolved_operation_id, None
        if existing.command != command or existing.fingerprint != requested_fingerprint:
            raise OperationConflictError(
                operation_id=resolved_operation_id,
                command=command,
                stored_command=existing.command,
                stored_fingerprint=existing.fingerprint,
                requested_fingerprint=requested_fingerprint,
            )
        return resolved_operation_id, existing

    def create_record(self, operation_id: str, command: str, payload: Dict[str, Any]) -> OperationRecord:
        now = _now_iso()
        record = OperationRecord(
            operation_id=operation_id,
            command=command,
            fingerprint=payload_fingerprint(command, payload),
            normalized_payload=normalize_operation_payload(command, payload),
            status="completed",
            created_at=now,
            updated_at=now,
        )
        self.write(record)
        return record

    def store_response(self, record: OperationRecord, response: Dict[str, Any], response_status_code: int) -> OperationRecord:
        record.response = dict(response)
        record.response_status_code = int(response_status_code)
        record.status = "completed"
        record.updated_at = _now_iso()
        self.write(record)
        return record
