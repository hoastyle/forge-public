from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass
import datetime as _datetime
from datetime import datetime, timezone

if not hasattr(_datetime, "UTC"):
    _datetime.UTC = timezone.utc
UTC = _datetime.UTC
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .app import ForgeApp
from .doctor import collect_dependency_report
from .errors import ForgeOperatorError
from .operations import OperationConflictError, OperationStore


class InjectRequest(BaseModel):
    input_kind: str
    content: Optional[str] = None
    link: Optional[str] = None
    source_ref: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    initiator: str = "manual"
    promote_knowledge: bool = False
    detach: bool = False
    operation_id: Optional[str] = None


class PromoteRawRequest(BaseModel):
    raw_ref: str
    initiator: str = "manual"
    detach: bool = False
    operation_id: Optional[str] = None


class PromoteReadyRequest(BaseModel):
    initiator: str = "manual"
    dry_run: bool = False
    limit: Optional[int] = None
    confirm_receipt: Optional[str] = None
    detach: bool = False
    operation_id: Optional[str] = None


class SynthesizeRequest(BaseModel):
    initiator: str = "manual"
    dry_run: bool = False
    confirm_receipt: Optional[str] = None
    detach: bool = False
    operation_id: Optional[str] = None


@dataclass
class ServiceRuntime:
    app_root: Path
    repo_root: Path
    state_root: Path
    bearer_token: str

    def __post_init__(self) -> None:
        self.app_root = Path(self.app_root)
        self.repo_root = Path(self.repo_root)
        self.state_root = Path(self.state_root)
        self.bearer_token = self.bearer_token.strip()
        self.mutation_lock = threading.Lock()
        self.jobs_root = self.state_root / "service" / "jobs"
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self.operation_store = OperationStore(self.state_root)

    def build_app(self) -> ForgeApp:
        return ForgeApp(repo_root=self.repo_root, state_root=self.state_root, app_root=self.app_root)

    def _job_path(self, job_id: str) -> Path:
        return self.jobs_root / "{0}.json".format(job_id)

    def _write_job(self, payload: Dict[str, Any]) -> None:
        path = self._job_path(str(payload["job_id"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def create_job(self, command: str, operation_id: str) -> Dict[str, Any]:
        job_id = "{0}-{1}".format(command, uuid.uuid4().hex[:12])
        payload = {
            "job_id": job_id,
            "command": command,
            "operation_id": operation_id,
            "status": "queued",
            "submitted_at": self._now_iso(),
            "started_at": None,
            "completed_at": None,
            "receipt_ref": None,
            "result": None,
            "message": "job queued",
        }
        self._write_job(payload)
        return payload

    def read_job(self, job_id: str) -> Dict[str, Any]:
        path = self._job_path(job_id)
        if not path.exists():
            raise FileNotFoundError("job not found: {0}".format(job_id))
        return json.loads(path.read_text(encoding="utf-8"))

    def run_inline(self, func: Callable[[], Any]) -> Dict[str, Any]:
        with self.mutation_lock:
            return self._run_inline_unlocked(func)

    def _run_inline_unlocked(self, func: Callable[[], Any]) -> Dict[str, Any]:
        result = func()
        return _serialize_result(result)

    def submit_job(self, command: str, func: Callable[[], Any], operation_id: str) -> Dict[str, Any]:
        payload = self.create_job(command, operation_id=operation_id)

        thread = threading.Thread(
            target=self._run_job,
            args=(str(payload["job_id"]), func),
            daemon=True,
        )
        thread.start()
        return payload

    def execute_mutation(
        self,
        command: str,
        request_payload: Dict[str, Any],
        operation_id: Optional[str],
        detach: bool,
        func: Callable[[], Any],
    ) -> tuple[int, Dict[str, Any]]:
        with self.mutation_lock:
            try:
                resolved_operation_id, existing = self.operation_store.claim(command, request_payload, operation_id)
            except OperationConflictError as exc:
                return 409, {
                    "status": "failed",
                    "message": str(exc),
                    "operation_id": exc.operation_id,
                    "command": exc.command,
                    "stored_command": exc.stored_command,
                    "stored_fingerprint": exc.stored_fingerprint,
                    "requested_fingerprint": exc.requested_fingerprint,
                }

            if existing is not None and existing.response is not None:
                replayed = dict(existing.response)
                replayed["operation_id"] = resolved_operation_id
                status_code = _replay_status_code(existing.response_status_code, replayed)
                return status_code, replayed

            if detach:
                response = self.submit_job(command, func, operation_id=resolved_operation_id)
                status_code = 202
            else:
                response = self._run_inline_unlocked(func)
                status_code = 200

            response = dict(response)
            response["operation_id"] = resolved_operation_id
            record = self.operation_store.create_record(
                operation_id=resolved_operation_id,
                command=command,
                payload=request_payload,
            )
            self.operation_store.store_response(record, response=response, response_status_code=status_code)
            return status_code, response

    def _run_job(self, job_id: str, func: Callable[[], Any]) -> None:
        payload = self.read_job(job_id)
        payload["status"] = "running"
        payload["started_at"] = self._now_iso()
        payload["message"] = "job running"
        self._write_job(payload)

        try:
            result = self.run_inline(func)
        except Exception as exc:
            payload["status"] = "failed"
            payload["completed_at"] = self._now_iso()
            payload["message"] = str(exc)
            self._write_job(payload)
            return

        payload["status"] = "success"
        payload["completed_at"] = self._now_iso()
        payload["receipt_ref"] = result.get("receipt_ref")
        payload["result"] = result
        payload["message"] = result.get("message") or "job completed"
        self._write_job(payload)

    def _now_iso(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def create_app(
    repo_root: Path,
    state_root: Optional[Path] = None,
    bearer_token: str = "",
    app_root: Optional[Path] = None,
) -> FastAPI:
    runtime = ServiceRuntime(
        app_root=Path(app_root) if app_root is not None else Path(repo_root),
        repo_root=Path(repo_root),
        state_root=Path(state_root) if state_root is not None else Path(repo_root) / "state",
        bearer_token=bearer_token,
    )
    app = FastAPI(title="Forge Service", version="0.1.0")

    def require_auth(authorization: Optional[str] = Header(default=None)) -> None:
        if not runtime.bearer_token:
            return
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        token = authorization.split(" ", 1)[1].strip()
        if token != runtime.bearer_token:
            raise HTTPException(status_code=401, detail="invalid bearer token")

    @app.get("/healthz")
    def healthz() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/doctor", dependencies=[Depends(require_auth)])
    def doctor() -> Dict[str, Any]:
        payload = collect_dependency_report(runtime.repo_root, app_root=runtime.app_root)
        provider_credentials = payload.get("dependencies", {}).get("litellm", {}).get("provider_credentials", {})
        runtime_lock = provider_credentials.get("runtime_lock")
        if isinstance(runtime_lock, dict):
            runtime_lock["path"] = "automation/compiled/runtime.lock.json"
        payload["transport"] = "service"
        payload["service_mode"] = "single-tenant"
        payload["application_storage"] = "separate" if runtime.app_root != runtime.repo_root else "co-located"
        payload["content_storage"] = "external" if runtime.app_root != runtime.repo_root else "repo-local"
        payload["state_storage"] = "external" if runtime.state_root != runtime.repo_root / "state" else "repo-local"
        return payload

    @app.get("/v1/review-raw", dependencies=[Depends(require_auth)])
    def review_raw(initiator: str = Query(default="manual")) -> Dict[str, Any]:
        with runtime.mutation_lock:
            return _serialize_result(runtime.build_app().review_raw(initiator=initiator))

    @app.get("/v1/review-queue", dependencies=[Depends(require_auth)])
    def review_queue(initiator: str = Query(default="manual")) -> Dict[str, Any]:
        with runtime.mutation_lock:
            return _serialize_result(runtime.build_app().review_queue(initiator=initiator))

    @app.post("/v1/inject", dependencies=[Depends(require_auth)])
    def inject(request: InjectRequest):
        runner = _build_inject_runner(runtime, request)
        status_code, payload = runtime.execute_mutation(
            command="inject",
            request_payload=request.model_dump(mode="python"),
            operation_id=request.operation_id,
            detach=request.detach,
            func=runner,
        )
        if status_code == 200:
            return payload
        return JSONResponse(payload, status_code=status_code)

    @app.post("/v1/promote-raw", dependencies=[Depends(require_auth)])
    def promote_raw(request: PromoteRawRequest):
        runner = lambda: runtime.build_app().promote_raw(request.raw_ref, initiator=request.initiator)
        status_code, payload = runtime.execute_mutation(
            command="promote-raw",
            request_payload=request.model_dump(mode="python"),
            operation_id=request.operation_id,
            detach=request.detach,
            func=runner,
        )
        if status_code == 200:
            return payload
        return JSONResponse(payload, status_code=status_code)

    @app.post("/v1/promote-ready", dependencies=[Depends(require_auth)])
    def promote_ready(request: PromoteReadyRequest):
        runner = lambda: runtime.build_app().promote_ready(
            initiator=request.initiator,
            dry_run=request.dry_run,
            limit=request.limit,
            confirm_receipt_ref=request.confirm_receipt,
        )
        status_code, payload = runtime.execute_mutation(
            command="promote-ready",
            request_payload=request.model_dump(mode="python"),
            operation_id=request.operation_id,
            detach=request.detach,
            func=runner,
        )
        if status_code == 200:
            return payload
        return JSONResponse(payload, status_code=status_code)

    @app.post("/v1/synthesize-insights", dependencies=[Depends(require_auth)])
    def synthesize_insights(request: SynthesizeRequest):
        runner = lambda: runtime.build_app().synthesize_insights(
            initiator=request.initiator,
            dry_run=request.dry_run,
            confirm_receipt_ref=request.confirm_receipt,
        )
        status_code, payload = runtime.execute_mutation(
            command="synthesize-insights",
            request_payload=request.model_dump(mode="python"),
            operation_id=request.operation_id,
            detach=request.detach,
            func=runner,
        )
        if status_code == 200:
            return payload
        return JSONResponse(payload, status_code=status_code)

    @app.get("/v1/receipt", dependencies=[Depends(require_auth)])
    def receipt(selector: str = Query(...)) -> Dict[str, Any]:
        try:
            with runtime.mutation_lock:
                return runtime.build_app().read_receipt(selector)
        except ForgeOperatorError as exc:
            return JSONResponse(exc.to_payload(), status_code=exc.status_code)
        except FileNotFoundError as exc:
            return JSONResponse({"status": "failed", "message": str(exc)}, status_code=404)

    @app.get("/v1/knowledge", dependencies=[Depends(require_auth)])
    def knowledge(selector: str = Query(...)) -> Dict[str, Any]:
        try:
            with runtime.mutation_lock:
                return runtime.build_app().read_knowledge_status(selector)
        except ForgeOperatorError as exc:
            return JSONResponse(exc.to_payload(), status_code=exc.status_code)
        except FileNotFoundError as exc:
            return JSONResponse({"status": "failed", "message": str(exc)}, status_code=404)

    @app.get("/v1/explain/insight", dependencies=[Depends(require_auth)])
    def explain_insight(receipt_ref: str = Query(...)) -> Dict[str, Any]:
        try:
            with runtime.mutation_lock:
                return runtime.build_app().explain_insight_receipt(receipt_ref)
        except ForgeOperatorError as exc:
            return JSONResponse(exc.to_payload(), status_code=exc.status_code)
        except FileNotFoundError as exc:
            return JSONResponse({"status": "failed", "message": str(exc)}, status_code=404)

    @app.get("/v1/jobs/{job_id}", dependencies=[Depends(require_auth)])
    def job(job_id: str) -> Dict[str, Any]:
        try:
            return runtime.read_job(job_id)
        except FileNotFoundError as exc:
            return JSONResponse({"status": "failed", "message": str(exc)}, status_code=404)

    return app


def _build_inject_runner(runtime: ServiceRuntime, request: InjectRequest) -> Callable[[], Any]:
    if request.input_kind not in {"text", "file", "feishu_link"}:
        raise HTTPException(status_code=422, detail="input_kind must be text, file, or feishu_link")
    if request.input_kind in {"text", "file"} and not request.content:
        raise HTTPException(status_code=422, detail="content is required for text and file input")
    if request.input_kind == "feishu_link" and not request.link:
        raise HTTPException(status_code=422, detail="link is required for feishu_link input")

    def runner():
        app = runtime.build_app()
        if request.input_kind == "feishu_link":
            return app.inject_feishu_link(
                request.link or "",
                title=request.title,
                source=request.source,
                tags=request.tags,
                initiator=request.initiator,
                promote_knowledge=request.promote_knowledge,
            )
        return app.inject_content(
            input_kind=request.input_kind,
            content=request.content or "",
            source_ref=request.source_ref or ("inline:text" if request.input_kind == "text" else "remote:file"),
            title=request.title,
            source=request.source,
            tags=request.tags,
            initiator=request.initiator,
            promote_knowledge=request.promote_knowledge,
        )

    return runner


def _serialize_result(result: Any) -> Dict[str, Any]:
    if hasattr(result, "to_dict"):
        return result.to_dict()
    if isinstance(result, dict):
        return result
    raise TypeError("unsupported service result type: {0}".format(type(result).__name__))


def _replay_status_code(stored_status_code: Optional[int], response_payload: Dict[str, Any]) -> int:
    if isinstance(stored_status_code, int):
        return stored_status_code
    if "job_id" in response_payload:
        return 202
    return 200
