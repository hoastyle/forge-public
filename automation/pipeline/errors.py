from __future__ import annotations

from typing import Any, Dict, Optional


class ForgeOperatorError(FileNotFoundError):
    def __init__(
        self,
        message: str,
        *,
        error_code: str,
        next_step: Optional[str] = None,
        status_code: int = 404,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.next_step = next_step
        self.status_code = status_code

    def to_payload(self) -> Dict[str, Any]:
        return {
            "status": "failed",
            "message": str(self),
            "error_code": self.error_code,
            "next_step": self.next_step,
        }
