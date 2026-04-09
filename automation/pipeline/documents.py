from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List


def load_knowledge_documents(repo_root: Path) -> List[Dict[str, object]]:
    documents = []
    for path in sorted((Path(repo_root) / "knowledge").glob("**/*.md")):
        if not path.is_file():
            continue
        metadata, body = parse_markdown_document(path)
        documents.append(
            {
                "path": str(path.relative_to(repo_root)),
                "title": metadata.get("title") or path.stem,
                "status": metadata.get("status") or "draft",
                "updated_at": metadata.get("updated") or None,
                "tags": metadata.get("tags") or [],
                "derived_from": metadata.get("derived_from") or [],
                "knowledge_kind": metadata.get("knowledge_kind") or "",
                "supersedes": metadata.get("supersedes") or [],
                "superseded_by": metadata.get("superseded_by") or [],
                "judge_score": metadata.get("judge_score") or None,
                "judge_decision": metadata.get("judge_decision") or None,
                "release_reason": metadata.get("release_reason") or None,
                "body": body,
            }
        )
    return documents


def load_raw_documents(repo_root: Path) -> List[Dict[str, object]]:
    documents = []
    for path in sorted((Path(repo_root) / "raw").glob("**/*.md")):
        if not path.is_file():
            continue
        metadata, body = parse_markdown_document(path)
        promotion_content = extract_raw_promotion_content(body)
        relative_path = str(path.relative_to(repo_root))
        path_parts = Path(relative_path).parts
        raw_kind = path_parts[1] if len(path_parts) > 1 else "captures"
        documents.append(
            {
                "path": relative_path,
                "title": metadata.get("title") or path.stem,
                "status": metadata.get("status") or "draft",
                "tags": metadata.get("tags") or [],
                "source": metadata.get("source") or "",
                "body": body,
                "raw_kind": raw_kind,
                "promotion_content": promotion_content,
                "content_chars": len(promotion_content.strip()),
            }
        )
    return documents


def parse_markdown_document(path: Path) -> (Dict[str, object], str):
    text = Path(path).read_text(encoding="utf-8")
    metadata: Dict[str, object] = {}
    body = text
    if text.startswith("---\n"):
        _, remainder = text.split("---\n", 1)
        frontmatter, body = remainder.split("\n---\n", 1)
        for line in frontmatter.splitlines():
            if ":" not in line:
                continue
            key, raw_value = line.split(":", 1)
            key = key.strip()
            value = raw_value.strip()
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                metadata[key] = [] if not inner else [item.strip() for item in inner.split(",")]
            else:
                metadata[key] = value
    return metadata, body.lstrip()


def extract_raw_promotion_content(body: str) -> str:
    content_section = _extract_markdown_section(body, "Content")
    if content_section:
        return content_section

    distillation_match = re.search(r"^##\s+Distillation\s*$", body, flags=re.MULTILINE)
    if distillation_match:
        return body[: distillation_match.start()].rstrip()
    return body.rstrip()


def _extract_markdown_section(body: str, heading: str) -> str:
    heading_match = re.search(r"^##\s+{0}\s*$".format(re.escape(heading)), body, flags=re.MULTILINE)
    if not heading_match:
        return ""
    start = heading_match.end()
    next_heading = re.search(r"^##\s+.+$", body[start:], flags=re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(body)
    return body[start:end].strip()
