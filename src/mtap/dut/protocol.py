from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# ==== Error taxonomy (frozen) ====
E_UNKNOWN_CMD = "E_UNKNOWN_CMD"
E_BAD_ARGS = "E_BAD_ARGS"
E_TIMEOUT = "E_TIMEOUT"
E_INTERNAL = "E_INTERNAL"
E_OUT_OF_RANGE = "E_OUT_OF_RANGE"
E_BUSY = "E_BUSY"


def parse_command(line: str) -> Tuple[str, List[str]]:
    """Parse a newline-framed UTF-8 line into (CMD, args).

    Grammar: CMD [arg1] [arg2]
    - CMD is case-insensitive; returned as uppercase.
    - args are whitespace-separated tokens.
    """
    s = line.strip()
    if not s:
        return "", []
    parts = s.split()
    cmd = parts[0].upper()
    args = parts[1:]
    return cmd, args


@dataclass(frozen=True)
class Response:
    ok: bool
    error_code: Optional[str]
    message: str
    data: Dict[str, Any]
    meta: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "ok": self.ok,
            "error_code": self.error_code,
            "message": self.message,
            "data": self.data,
        }
        if self.meta is not None:
            d["meta"] = self.meta
        return d


def ok(data: Optional[Dict[str, Any]] = None, *, cmd: Optional[str] = None) -> Dict[str, Any]:
    return Response(True, None, "OK", data or {}, meta={"cmd": cmd} if cmd else None).to_dict()


def err(code: str, message: str, *, cmd: Optional[str] = None) -> Dict[str, Any]:
    return Response(False, code, message, {}, meta={"cmd": cmd} if cmd else None).to_dict()
