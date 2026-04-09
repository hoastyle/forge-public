from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .app import ForgeApp
from .client_config import (
    RemoteConnection,
    clear_remote_connection,
    get_client_config_path,
    resolve_remote_connection,
    save_remote_connection,
)
from .doctor import collect_dependency_report, collect_runtime_proxy_warnings
from .initiators import ALLOWED_INITIATORS, parse_initiator
from .remote_client import RemoteApiError, request_json


REMOTE_CAPABLE_COMMANDS = {
    "doctor",
    "inject",
    "review-raw",
    "review-queue",
    "knowledge",
    "explain",
    "promote-raw",
    "promote-ready",
    "synthesize-insights",
    "receipt",
    "job",
}

REMOTE_MUTATION_COMMANDS = {
    "inject",
    "promote-raw",
    "promote-ready",
    "synthesize-insights",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="forge")
    parser.add_argument("--repo-root")
    parser.add_argument("--state-root")
    parser.add_argument("--server")
    parser.add_argument("--token")
    parser.add_argument("--local", action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)

    login = subparsers.add_parser("login")
    login.add_argument("--server", required=True)
    login.add_argument("--token", required=True)

    subparsers.add_parser("logout")

    serve = subparsers.add_parser("serve")
    serve.add_argument("--app-root")
    serve.add_argument("--repo-root")
    serve.add_argument("--state-root")
    serve.add_argument("--token")
    serve.add_argument("--host", default=os.environ.get("FORGE_SERVICE_HOST", "127.0.0.1"))
    serve.add_argument("--port", type=int, default=int(os.environ.get("FORGE_SERVICE_PORT", "8000")))

    inject = subparsers.add_parser("inject")
    source_group = inject.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--text")
    source_group.add_argument("--file")
    source_group.add_argument("--feishu-link")
    inject.add_argument("--title")
    inject.add_argument("--source")
    inject.add_argument("--tag", dest="tags", action="append", default=[])
    inject.add_argument("--initiator", default="manual", type=parse_initiator, choices=ALLOWED_INITIATORS)
    inject.add_argument("--promote-knowledge", action="store_true")
    inject.add_argument("--detach", action="store_true")
    inject.add_argument("--wait", action="store_true")
    inject.add_argument("--operation-id")

    tune = subparsers.add_parser("tune")
    tune.add_argument("intent")
    tune.add_argument("--initiator", default="manual", type=parse_initiator, choices=ALLOWED_INITIATORS)

    synthesize = subparsers.add_parser("synthesize-insights")
    synthesize.add_argument("--initiator", default="manual", type=parse_initiator, choices=ALLOWED_INITIATORS)
    synthesize.add_argument("--dry-run", action="store_true")
    synthesize.add_argument("--confirm-receipt")
    synthesize.add_argument("--detach", action="store_true")
    synthesize.add_argument("--wait", action="store_true")
    synthesize.add_argument("--operation-id")

    replay = subparsers.add_parser("replay-failure")
    replay.add_argument("case_ref")
    replay.add_argument("--initiator", default="manual", type=parse_initiator, choices=ALLOWED_INITIATORS)

    review_failures = subparsers.add_parser("review-failures")
    review_failures.add_argument("--initiator", default="manual", type=parse_initiator, choices=ALLOWED_INITIATORS)
    review_failures.add_argument("--limit", type=int, default=20)

    review_raw = subparsers.add_parser("review-raw")
    review_raw.add_argument("--initiator", default="manual", type=parse_initiator, choices=ALLOWED_INITIATORS)

    review_queue = subparsers.add_parser("review-queue")
    review_queue.add_argument("--initiator", default="manual", type=parse_initiator, choices=ALLOWED_INITIATORS)

    promote_raw = subparsers.add_parser("promote-raw")
    promote_raw.add_argument("raw_ref", nargs="?")
    promote_raw.add_argument("--all", action="store_true")
    promote_raw.add_argument("--initiator", default="manual", type=parse_initiator, choices=ALLOWED_INITIATORS)
    promote_raw.add_argument("--detach", action="store_true")
    promote_raw.add_argument("--wait", action="store_true")
    promote_raw.add_argument("--operation-id")

    promote_ready = subparsers.add_parser("promote-ready")
    promote_ready.add_argument("--initiator", default="manual", type=parse_initiator, choices=ALLOWED_INITIATORS)
    promote_ready.add_argument("--dry-run", action="store_true")
    promote_ready.add_argument("--limit", type=int)
    promote_ready.add_argument("--confirm-receipt")
    promote_ready.add_argument("--detach", action="store_true")
    promote_ready.add_argument("--wait", action="store_true")
    promote_ready.add_argument("--operation-id")

    auto_retune = subparsers.add_parser("auto-retune")
    auto_retune.add_argument("--initiator", default="manual", type=parse_initiator, choices=ALLOWED_INITIATORS)
    auto_retune.add_argument("--limit", type=int, default=20)

    subparsers.add_parser("doctor")

    knowledge = subparsers.add_parser("knowledge")
    knowledge_subparsers = knowledge.add_subparsers(dest="knowledge_command", required=True)
    knowledge_get = knowledge_subparsers.add_parser("get")
    knowledge_get.add_argument("selector")

    explain = subparsers.add_parser("explain")
    explain_subparsers = explain.add_subparsers(dest="explain_command", required=True)
    explain_insight = explain_subparsers.add_parser("insight")
    explain_insight.add_argument("receipt_ref")

    receipt = subparsers.add_parser("receipt")
    receipt_subparsers = receipt.add_subparsers(dest="receipt_command", required=True)
    receipt_get = receipt_subparsers.add_parser("get")
    receipt_get.add_argument("selector")

    job = subparsers.add_parser("job")
    job_subparsers = job.add_subparsers(dest="job_command", required=True)
    job_get = job_subparsers.add_parser("get")
    job_get.add_argument("job_id")

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "login":
        return _login(args.server, args.token)
    if args.command == "logout":
        return _logout()
    if args.command == "serve":
        return _serve(args)

    explicit_repo_root = bool(args.repo_root)
    repo_root = Path(args.repo_root or ".")
    state_root = Path(args.state_root) if args.state_root else None
    connection = resolve_remote_connection(
        explicit_server=getattr(args, "server", "") or "",
        explicit_token=getattr(args, "token", "") or "",
    )

    if _should_use_remote(args, connection, explicit_repo_root):
        _validate_remote_mutation_flags(parser, args)
        try:
            exit_code, payload = execute_remote_command(args.command, connection, _build_remote_payload(args))
        except RemoteApiError as exc:
            payload = exc.payload or {"status": "failed", "message": str(exc)}
            sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            return 1
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        return exit_code

    if args.command == "job":
        payload = {"status": "failed", "message": "job commands require a configured remote server"}
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        return 1

    if args.command in {
        "inject",
        "doctor",
        "synthesize-insights",
        "replay-failure",
        "review-failures",
        "promote-raw",
        "promote-ready",
        "auto-retune",
    }:
        _emit_runtime_warnings(repo_root)

    if args.command == "doctor":
        sys.stdout.write(json.dumps(collect_dependency_report(repo_root), indent=2, ensure_ascii=False) + "\n")
        return 0

    app = _build_local_app(repo_root, state_root)

    if args.command == "inject":
        if args.text is not None:
            receipt = app.inject_text(
                text=args.text,
                title=args.title,
                source=args.source,
                tags=args.tags,
                initiator=args.initiator,
                promote_knowledge=args.promote_knowledge,
            )
        elif args.file is not None:
            receipt = app.inject_file(
                Path(args.file),
                title=args.title,
                source=args.source,
                tags=args.tags,
                initiator=args.initiator,
                promote_knowledge=args.promote_knowledge,
            )
        else:
            receipt = app.inject_feishu_link(
                args.feishu_link,
                title=args.title,
                source=args.source,
                tags=args.tags,
                initiator=args.initiator,
                promote_knowledge=args.promote_knowledge,
            )
        sys.stdout.write(json.dumps(receipt.to_dict(), indent=2, ensure_ascii=False) + "\n")
        return 0 if receipt.status == "success" else 1

    if args.command == "synthesize-insights":
        if args.confirm_receipt and args.dry_run:
            parser.error("synthesize-insights does not allow --confirm-receipt together with --dry-run")
        receipt = app.synthesize_insights(
            initiator=args.initiator,
            dry_run=args.dry_run,
            confirm_receipt_ref=args.confirm_receipt,
        )
        sys.stdout.write(json.dumps(receipt.to_dict(), indent=2, ensure_ascii=False) + "\n")
        return 0 if receipt.status != "failed" else 1

    if args.command == "replay-failure":
        receipt = app.replay_failure_case(args.case_ref, initiator=args.initiator)
        sys.stdout.write(json.dumps(receipt.to_dict(), indent=2, ensure_ascii=False) + "\n")
        return 0 if receipt.status == "success" else 1

    if args.command == "review-failures":
        receipt = app.review_failures(initiator=args.initiator, limit=args.limit)
        sys.stdout.write(json.dumps(receipt.to_dict(), indent=2, ensure_ascii=False) + "\n")
        return 0 if receipt.status == "success" else 1

    if args.command == "review-raw":
        receipt = app.review_raw(initiator=args.initiator)
        sys.stdout.write(json.dumps(receipt.to_dict(), indent=2, ensure_ascii=False) + "\n")
        return 0 if receipt.status == "success" else 1

    if args.command == "review-queue":
        receipt = app.review_queue(initiator=args.initiator)
        sys.stdout.write(json.dumps(receipt.to_dict(), indent=2, ensure_ascii=False) + "\n")
        return 0 if receipt.status == "success" else 1

    if args.command == "promote-raw":
        if bool(args.raw_ref) == bool(args.all):
            parser.error("promote-raw requires exactly one of <raw_ref> or --all")
        if args.all:
            receipt = app.promote_all_raw(initiator=args.initiator)
        else:
            receipt = app.promote_raw(args.raw_ref, initiator=args.initiator)
        sys.stdout.write(json.dumps(receipt.to_dict(), indent=2, ensure_ascii=False) + "\n")
        return 0 if receipt.status != "failed" else 1

    if args.command == "promote-ready":
        if args.confirm_receipt and args.dry_run:
            parser.error("promote-ready does not allow --confirm-receipt together with --dry-run")
        if args.confirm_receipt and args.limit is not None:
            parser.error("promote-ready does not allow --confirm-receipt together with --limit")
        receipt = app.promote_ready(
            initiator=args.initiator,
            dry_run=args.dry_run,
            limit=args.limit,
            confirm_receipt_ref=args.confirm_receipt,
        )
        sys.stdout.write(json.dumps(receipt.to_dict(), indent=2, ensure_ascii=False) + "\n")
        return 0 if receipt.status != "failed" else 1

    if args.command == "auto-retune":
        receipt = app.auto_retune(initiator=args.initiator, limit=args.limit)
        sys.stdout.write(json.dumps(receipt.to_dict(), indent=2, ensure_ascii=False) + "\n")
        return 0 if receipt.status != "failed" else 1

    if args.command == "receipt":
        try:
            payload = app.read_receipt(args.selector)
        except FileNotFoundError as exc:
            payload = {"status": "failed", "message": str(exc)}
            sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            return 1
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        return 0

    if args.command == "knowledge":
        try:
            payload = app.read_knowledge_status(args.selector)
        except FileNotFoundError as exc:
            payload = {"status": "failed", "message": str(exc)}
            sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            return 1
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        return 0

    if args.command == "explain":
        try:
            payload = app.explain_insight_receipt(args.receipt_ref)
        except FileNotFoundError as exc:
            payload = {"status": "failed", "message": str(exc)}
            sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            return 1
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        return 0

    receipt = app.tune(args.intent, initiator=args.initiator)
    sys.stdout.write(json.dumps(receipt.to_dict(), indent=2, ensure_ascii=False) + "\n")
    return 0


def execute_remote_command(command_name: str, connection: RemoteConnection, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    base_url = connection.server.rstrip("/")

    if command_name == "doctor":
        response = request_json("GET", "{0}/v1/doctor".format(base_url), token=connection.token)
    elif command_name == "review-raw":
        response = request_json(
            "GET",
            "{0}/v1/review-raw".format(base_url),
            token=connection.token,
            query={"initiator": payload.get("initiator")},
        )
    elif command_name == "review-queue":
        response = request_json(
            "GET",
            "{0}/v1/review-queue".format(base_url),
            token=connection.token,
            query={"initiator": payload.get("initiator")},
        )
    elif command_name == "knowledge":
        response = request_json(
            "GET",
            "{0}/v1/knowledge".format(base_url),
            token=connection.token,
            query={"selector": payload.get("selector")},
        )
    elif command_name == "explain":
        response = request_json(
            "GET",
            "{0}/v1/explain/insight".format(base_url),
            token=connection.token,
            query={"receipt_ref": payload.get("receipt_ref")},
        )
    elif command_name == "receipt":
        response = request_json(
            "GET",
            "{0}/v1/receipt".format(base_url),
            token=connection.token,
            query={"selector": payload.get("selector")},
        )
    elif command_name == "job":
        response = request_json(
            "GET",
            "{0}/v1/jobs/{1}".format(base_url, payload["job_id"]),
            token=connection.token,
        )
    elif command_name == "inject":
        response = request_json("POST", "{0}/v1/inject".format(base_url), token=connection.token, payload=payload)
    elif command_name == "promote-raw":
        response = request_json("POST", "{0}/v1/promote-raw".format(base_url), token=connection.token, payload=payload)
    elif command_name == "promote-ready":
        response = request_json("POST", "{0}/v1/promote-ready".format(base_url), token=connection.token, payload=payload)
    elif command_name == "synthesize-insights":
        response = request_json(
            "POST",
            "{0}/v1/synthesize-insights".format(base_url),
            token=connection.token,
            payload=payload,
        )
    else:
        raise RemoteApiError(0, "remote command not supported: {0}".format(command_name))

    return _exit_code_from_payload(response), response


def _login(server: str, token: str) -> int:
    config_path = save_remote_connection(server=server, token=token)
    payload = {
        "status": "success",
        "server": server.rstrip("/"),
        "config_path": str(config_path),
        "message": "remote server saved",
    }
    sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return 0


def _logout() -> int:
    config_path = clear_remote_connection()
    payload = {
        "status": "success",
        "config_path": str(config_path),
        "message": "remote server cleared",
    }
    sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return 0


def _load_create_app():
    from .service_api import create_app

    return create_app


def _load_uvicorn_run():
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("uvicorn is required for `forge serve`; install with `uv sync --extra server`") from exc

    return uvicorn.run


def _serve(args) -> int:
    repo_root = Path(args.repo_root or os.environ.get("FORGE_SERVICE_REPO_ROOT", "."))
    app_root = Path(args.app_root or os.environ.get("FORGE_SERVICE_APP_ROOT", repo_root))
    state_root = Path(args.state_root or os.environ.get("FORGE_STATE_ROOT", repo_root / "state"))
    bearer_token = (args.token or os.environ.get("FORGE_SERVER_TOKEN", "")).strip()

    create_app = _load_create_app()
    uvicorn_run = _load_uvicorn_run()
    app = create_app(repo_root=repo_root, state_root=state_root, bearer_token=bearer_token, app_root=app_root)
    uvicorn_run(app, host=args.host, port=args.port)
    return 0


def _should_use_remote(args, connection: Optional[RemoteConnection], explicit_repo_root: bool) -> bool:
    if args.local or explicit_repo_root:
        return False
    if connection is None:
        return False
    return args.command in REMOTE_CAPABLE_COMMANDS


def _build_remote_payload(args) -> Dict[str, Any]:
    if args.command == "doctor":
        return {}
    if args.command in {"review-raw", "review-queue"}:
        return {"initiator": args.initiator}
    if args.command == "inject":
        payload: Dict[str, Any] = {
            "title": args.title,
            "source": args.source,
            "tags": args.tags,
            "initiator": args.initiator,
            "promote_knowledge": args.promote_knowledge,
            "detach": _resolve_remote_detach(args),
            "operation_id": args.operation_id,
        }
        if args.text is not None:
            payload.update({"input_kind": "text", "content": args.text, "source_ref": "inline:text"})
        elif args.file is not None:
            file_path = Path(args.file)
            payload.update(
                {
                    "input_kind": "file",
                    "content": file_path.read_text(encoding="utf-8"),
                    "source_ref": str(file_path),
                }
            )
        else:
            payload.update({"input_kind": "feishu_link", "link": args.feishu_link})
        return payload
    if args.command == "promote-raw":
        if bool(args.raw_ref) == bool(args.all):
            raise SystemExit("promote-raw requires exactly one of <raw_ref> or --all")
        if args.all:
            raise SystemExit("remote promote-raw does not support --all; use promote-ready or maintain the repo locally")
        return {
            "raw_ref": args.raw_ref,
            "initiator": args.initiator,
            "detach": _resolve_remote_detach(args),
            "operation_id": args.operation_id,
        }
    if args.command == "promote-ready":
        return {
            "initiator": args.initiator,
            "dry_run": args.dry_run,
            "limit": args.limit,
            "confirm_receipt": args.confirm_receipt,
            "detach": _resolve_remote_detach(args),
            "operation_id": args.operation_id,
        }
    if args.command == "synthesize-insights":
        return {
            "initiator": args.initiator,
            "dry_run": args.dry_run,
            "confirm_receipt": args.confirm_receipt,
            "detach": _resolve_remote_detach(args),
            "operation_id": args.operation_id,
        }
    if args.command == "receipt":
        return {"selector": args.selector}
    if args.command == "knowledge":
        return {"selector": args.selector}
    if args.command == "explain":
        return {"receipt_ref": args.receipt_ref}
    if args.command == "job":
        return {"job_id": args.job_id}
    return {}


def _exit_code_from_payload(payload: Dict[str, Any]) -> int:
    status = str(payload.get("status") or "").strip().lower()
    if status in {"failed", "error"}:
        return 1
    return 0


def _validate_remote_mutation_flags(parser: argparse.ArgumentParser, args) -> None:
    if args.command not in REMOTE_MUTATION_COMMANDS:
        return
    if getattr(args, "wait", False) and getattr(args, "detach", False):
        parser.error("--wait does not allow --detach; remote mutations already default to detached jobs")


def _resolve_remote_detach(args) -> bool:
    if getattr(args, "wait", False):
        return False
    if getattr(args, "detach", False):
        return True
    return True


def _build_local_app(repo_root: Path, state_root: Optional[Path]) -> ForgeApp:
    if state_root is None:
        return ForgeApp(repo_root)
    return ForgeApp(repo_root, state_root=state_root)


def _emit_runtime_warnings(repo_root: Path) -> None:
    for warning in collect_runtime_proxy_warnings(repo_root):
        sys.stderr.write("forge warning: {0}\n".format(warning))


if __name__ == "__main__":
    raise SystemExit(main())
