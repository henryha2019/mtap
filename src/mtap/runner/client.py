from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from typing import Any, Dict, Optional

from mtap.dut.protocol import E_TIMEOUT


@dataclass(frozen=True)
class ClientResult:
    ok: bool
    error_code: Optional[str]
    message: str
    data: Dict[str, Any]
    raw: Dict[str, Any]


class DutClient:
    def __init__(self, host: str, port: int, timeout_s: float) -> None:
        self.host = host
        self.port = port
        self.timeout_s = timeout_s

    def _send_recv_line(self, line: str, *, timeout_s: float) -> Dict[str, Any]:
        payload = (line.rstrip("\n") + "\n").encode("utf-8")
        with socket.create_connection((self.host, self.port), timeout=timeout_s) as sock:
            sock.settimeout(timeout_s)
            sock.sendall(payload)
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(4096)
                if not chunk:
                    # Peer closed without a full line -> treat as no-response.
                    break
                buf += chunk
        if not buf or b"\n" not in buf:
            raise TimeoutError("No complete response line from DUT")
        lineb = buf.split(b"\n", 1)[0]
        return json.loads(lineb.decode("utf-8"))

    def call_line(self, line: str, *, timeout_s: Optional[float] = None) -> ClientResult:
        t = float(timeout_s) if timeout_s is not None else float(self.timeout_s)
        try:
            raw = self._send_recv_line(line, timeout_s=t)
            return ClientResult(
                ok=bool(raw.get("ok")),
                error_code=raw.get("error_code"),
                message=str(raw.get("message", "")),
                data=raw.get("data") or {},
                raw=raw,
            )
        except (socket.timeout, TimeoutError):
            return ClientResult(ok=False, error_code=E_TIMEOUT, message="Client timeout", data={}, raw={})
        except json.JSONDecodeError as e:
            return ClientResult(ok=False, error_code="E_BAD_RESP", message=str(e), data={}, raw={})
        except Exception as e:
            return ClientResult(ok=False, error_code="E_CLIENT", message=str(e), data={}, raw={})

    def call(self, cmd: str, *args: str, timeout_s: Optional[float] = None) -> ClientResult:
        line = " ".join([cmd, *args]).strip()
        return self.call_line(line, timeout_s=timeout_s)
