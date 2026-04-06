from __future__ import annotations

import argparse
from typing import Final, Tuple

ALLOWED_INITIATORS: Final[Tuple[str, ...]] = (
    "manual",
    "codex",
    "claude-code",
    "openclaw",
    "ci",
)


def normalize_initiator(value: str) -> str:
    candidate = str(value).strip().lower()
    if candidate in ALLOWED_INITIATORS:
        return candidate
    raise ValueError(
        "invalid initiator: {0}; expected one of: {1}".format(
            value,
            ", ".join(ALLOWED_INITIATORS),
        )
    )


def parse_initiator(value: str) -> str:
    try:
        return normalize_initiator(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
