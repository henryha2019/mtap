from __future__ import annotations

from mtap.config import load_settings
from mtap.dut.server import DutServer


def main(argv: list[str] | None = None) -> None:
    s = load_settings()
    server = DutServer(s.host, s.dut_port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[DUT] KeyboardInterrupt -> stopping")
        server.stop()


if __name__ == "__main__":
    main()
