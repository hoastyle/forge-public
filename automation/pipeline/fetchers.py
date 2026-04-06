from __future__ import annotations

import json
import subprocess
from typing import Dict


class LarkCliFeishuFetcher:
    def fetch(self, link: str) -> Dict[str, str]:
        cmd = ["lark-cli", "docs", "+fetch", "--doc", link]
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip() or "lark-cli fetch failed"
            raise RuntimeError(stderr)

        payload = json.loads(completed.stdout)
        title = payload.get("title") or "Imported Feishu Document"
        content = payload.get("markdown") or payload.get("content") or ""
        source_ref = payload.get("document_id") or payload.get("obj_token") or link
        if not content.strip():
            raise RuntimeError("fetched Feishu document is empty")

        return {
            "title": title,
            "content": content,
            "source_ref": source_ref,
        }
