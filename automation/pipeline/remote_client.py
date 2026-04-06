from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional


class RemoteApiError(RuntimeError):
    def __init__(self, status_code: int, message: str, payload: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


def request_json(
    method: str,
    url: str,
    token: str = "",
    payload: Optional[Dict[str, Any]] = None,
    query: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if query:
        filtered = {key: value for key, value in query.items() if value is not None and value != ""}
        if filtered:
            url = "{0}?{1}".format(url, urllib.parse.urlencode(filtered))

    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer {0}".format(token)

    request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        payload_body = {}
        message = exc.reason
        body = exc.read().decode("utf-8")
        if body:
            try:
                payload_body = json.loads(body)
                message = str(payload_body.get("message") or payload_body.get("detail") or message)
            except json.JSONDecodeError:
                message = body
        raise RemoteApiError(exc.code, str(message), payload_body) from exc
    except urllib.error.URLError as exc:
        raise RemoteApiError(0, str(exc.reason), {}) from exc
