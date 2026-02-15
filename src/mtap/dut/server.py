from __future__ import annotations

import json
import importlib.resources as importlib_resources
import socket
import threading
import time
from pathlib import Path
from typing import Dict, Tuple, Optional
import random
import os

import yaml

from .device_model import DeviceModel
from .fault_injection import FaultInjector
from .protocol import E_BAD_ARGS, E_OUT_OF_RANGE, E_UNKNOWN_CMD, err, ok, parse_command


def _load_dut_config(path: Optional[Path]) -> Dict:
    """Load DUT config with robust fallbacks.

    Order:
    1) Explicit path arg (if exists)
    2) MTAP_DUT_CONFIG env var (if set + exists)
    3) CWD-relative dut/config.yaml (dev workflow)
    4) Packaged default (mtap/resources/dut_config.yaml)
    """
    if path is not None and path.exists():
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    env_path = os.getenv("MTAP_DUT_CONFIG", "").strip()
    if env_path:
        p = Path(env_path)
        if p.exists():
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}

    dev = Path("dut/config.yaml")
    if dev.exists():
        return yaml.safe_load(dev.read_text(encoding="utf-8")) or {}

    try:
        txt = importlib_resources.files("mtap").joinpath("resources/dut_config.yaml").read_text(encoding="utf-8")
        return yaml.safe_load(txt) or {}
    except Exception:
        return {}


class DutServer:
    """Multi-client TCP DUT simulator (thread-per-connection)."""

    def __init__(self, host: str, port: int, *, config_path: Optional[Path] = None) -> None:
        self.host = host
        self.port = port
        self._stop = threading.Event()
        self._sock: Optional[socket.socket] = None

        cfg = _load_dut_config(config_path)
        self._cfg = cfg

        seed = int(((cfg.get("determinism") or {}).get("seed")) or 0) or None
        self._rng = random.Random(seed)

        prof_name = os.getenv("MTAP_FAULT_PROFILE", str(cfg.get("default_fault_profile", "clean")))
        prof = (cfg.get("fault_profiles") or {}).get(prof_name) or (cfg.get("fault_profiles") or {}).get("clean") or {}
        self.faults = FaultInjector(self._rng, prof)

        self.device = DeviceModel(self._rng, defaults=(cfg.get("device_defaults") or {}))

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass

    def _handle(self, conn: socket.socket, addr: Tuple[str, int]) -> None:
        with conn:
            buf = b""
            while not self._stop.is_set():
                try:
                    chunk = conn.recv(4096)
                except OSError:
                    return
                if not chunk:
                    return
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    resp = self._dispatch(line)
                    if resp is None:
                        # Simulate "no response" (DROP)
                        return
                    try:
                        conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                    except OSError:
                        return

    def _set_profile(self, name: str) -> None:
        prof = (self._cfg.get("fault_profiles") or {}).get(name) or (self._cfg.get("fault_profiles") or {}).get("clean") or {}
        self.faults.profile = prof

    def _dispatch(self, line: bytes) -> Optional[Dict]:
        try:
            cmd, args = parse_command(line.decode("utf-8"))
        except Exception:
            return err(E_BAD_ARGS, "Invalid UTF-8 request line", cmd="(decode)")

        if cmd == "":
            return err(E_BAD_ARGS, "Empty command", cmd="(empty)")

        if cmd == "SET_FAULT_PROFILE":
            if len(args) != 1:
                return err(E_BAD_ARGS, "SET_FAULT_PROFILE requires 1 argument: <profile>", cmd=cmd)
            name = args[0].strip()
            self._set_profile(name)
            return ok({"profile": name}, cmd=cmd)

        # Commands requiring SN
        if cmd in {"PING", "READ_TEMP", "SELF_TEST", "SET_TEMP"}:
            if cmd == "SET_TEMP":
                if len(args) != 2:
                    return err(E_BAD_ARGS, "SET_TEMP requires 2 arguments: <sn> <temp_c>", cmd=cmd)
                sn = args[0]
                try:
                    temp_c = float(args[1])
                except ValueError:
                    return err(E_BAD_ARGS, "temp_c must be a float", cmd=cmd)
                if temp_c < -40.0 or temp_c > 125.0:
                    return err(E_OUT_OF_RANGE, "temp_c out of range [-40.0, 125.0]", cmd=cmd)

                d = self.device.get_or_create(sn)
                decision = self.faults.evaluate(cmd, sn, d.cycles)
                if decision["action"] == "DELAY":
                    time.sleep(float(decision.get("delay_s", 0.0)))
                elif decision["action"] == "DROP":
                    time.sleep(float(decision.get("delay_s", 0.0)))
                    return None
                elif decision["action"] == "RESPOND":
                    return {"ok": False, "error_code": decision["error_code"], "message": decision["message"], "data": {}, "meta": {"cmd": cmd}}

                return ok(self.device.set_temp(sn, temp_c), cmd=cmd)

            if len(args) != 1:
                return err(E_BAD_ARGS, f"{cmd} requires 1 argument: <sn>", cmd=cmd)
            sn = args[0]
            d = self.device.get_or_create(sn)

            # Apply drift offsets each request (slow baseline shift)
            d.drift_offset_c, d.drift_offset_v = self.faults.apply_drift(
                cmd, d.cycles, temp_offset_c=d.drift_offset_c, vbat_offset_v=d.drift_offset_v
            )

            decision = self.faults.evaluate(cmd, sn, d.cycles)
            if decision["action"] == "DELAY":
                time.sleep(float(decision.get("delay_s", 0.0)))
            elif decision["action"] == "DROP":
                time.sleep(float(decision.get("delay_s", 0.0)))
                return None
            elif decision["action"] == "RESPOND":
                return {"ok": False, "error_code": decision["error_code"], "message": decision["message"], "data": {}, "meta": {"cmd": cmd}}

            if cmd == "PING":
                return ok(self.device.ping(sn), cmd=cmd)
            if cmd == "READ_TEMP":
                return ok(self.device.read_temp(sn), cmd=cmd)
            if cmd == "SELF_TEST":
                return ok(self.device.self_test(sn), cmd=cmd)

        return err(E_UNKNOWN_CMD, f"Unknown command: {cmd}", cmd=cmd)

    def serve_forever(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            self._sock = s
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            s.listen()
            s.settimeout(0.5)
            print(f"[DUT] listening on {self.host}:{self.port}")

            while not self._stop.is_set():
                try:
                    conn, addr = s.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                threading.Thread(target=self._handle, args=(conn, addr), daemon=True).start()

            print("[DUT] shutdown complete")
