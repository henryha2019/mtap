# MTAP Manufacturing Protocol (TCP, newline-framed)

This document **freezes the communication contract** between the **Test Harness (client)** and the **DUT Simulator (server)**.

The implementation is in `src/mtap/dut/protocol.py` and must match this document exactly.

---

## Transport + framing

- **Transport:** TCP socket
- **Encoding:** UTF-8
- **Framing:** **one request per line**, terminated by `\n` (LF)
- **Server response:** **one JSON object per line**, terminated by `\n` (LF)

Client sends:
```
CMD [arg1] [arg2]\n
```

Server replies:
```
{"ok": true, ...}\n
```

---

## Command grammar

```
CMD [arg1] [arg2]
```

- Tokens are separated by **one or more spaces**
- `CMD` is **case-insensitive**; server normalizes to uppercase
- Arguments are positional (no key/value parsing)

---

## Command list (frozen)

### 1) `PING <sn>`
Health check and identity readback. Includes `vbat_v` (battery voltage estimate).

Example:
```
PING SN0001
```

### 2) `READ_TEMP <sn>`
Read current DUT temperature in Celsius.

Example:
```
READ_TEMP SN0001
```

### 3) `SELF_TEST <sn>`
Run DUT self-test (logical, simulated).

Example:
```
SELF_TEST SN0001
```

### 4) `SET_TEMP <sn> <temp_c>`
Set the DUT baseline temperature (used to simulate environment changes).

Example:
```
SET_TEMP SN0001 35.5
```

Validation:
- `temp_c` must parse as float
- allowed range: **[-40.0, 125.0]**
- out of range returns `E_OUT_OF_RANGE`

### 5) `SET_FAULT_PROFILE <profile>`
Set global fault profile on the simulator (affects subsequent commands).

Allowed `<profile>` values:
- `clean`
- `intermittent`
- `timeout-heavy`
- `drift`

Example:
```
SET_FAULT_PROFILE intermittent
```

Notes:
- Profile selection is **global** for the server process (simple v1 behavior)

---

## JSON response schema (frozen)

Each response is a single JSON object with **required keys**:

Required keys:
- `ok` (bool): success flag
- `error_code` (string | null): error taxonomy code
- `message` (string): short human-readable message
- `data` (object): command-specific payload (empty object on error)

Optional keys:
- `meta` (object): optional metadata (server version, timings, etc.)

Example success:
```json
{"ok": true, "error_code": null, "message": "OK", "data": {"sn":"SN0001","fw":"1.0.0"}, "meta": {"cmd":"PING"}}
```

Example error:
```json
{"ok": false, "error_code": "E_BAD_ARGS", "message": "READ_TEMP requires 1 argument: <sn>", "data": {}, "meta":{"cmd":"READ_TEMP"}}
```

---

## Timeouts

- **Client default timeout:** `MTAP_TIMEOUT_S` (default 2.0s) in `.env`
- **Per-command override:** not implemented in v1; client uses a single timeout for all commands.

Timeout behavior:
- If the client times out waiting for a response line, the client returns `E_TIMEOUT`.

---

## Error code taxonomy (frozen)

| Code | Meaning | Typical cause |
|------|---------|---------------|
| `E_UNKNOWN_CMD` | Unknown command | CMD not recognized |
| `E_BAD_ARGS` | Bad or missing arguments | wrong arg count/type |
| `E_TIMEOUT` | Timeout | simulated server stall or network timeout |
| `E_INTERNAL` | Internal fault | simulated intermittent failure, unexpected exception |
| `E_OUT_OF_RANGE` | Value out of allowed range | `SET_TEMP` outside [-40, 125] |
| `E_BUSY` | Device busy | command rejected due to mode/state |

---

## Deterministic examples (request → response)

### A) PING
Request:
```
PING SN0001
```

Response:
```json
{"ok": true, "error_code": null, "message": "OK", "data": {"sn":"SN0001","fw":"1.0.0","mode":"NORMAL","vbat_v":12.0}, "meta":{"cmd":"PING"}}
```

### B) READ_TEMP
Request:
```
READ_TEMP SN0001
```

Response:
```json
{"ok": true, "error_code": null, "message": "OK", "data": {"sn":"SN0001","temp_c":25.05,"vbat_v":12.01,"cycles":1}, "meta":{"cmd":"READ_TEMP"}}
```

### C) SET_TEMP (out of range)
Request:
```
SET_TEMP SN0001 999
```

Response:
```json
{"ok": false, "error_code": "E_OUT_OF_RANGE", "message": "temp_c out of range [-40.0, 125.0]", "data": {}, "meta":{"cmd":"SET_TEMP"}}
```
