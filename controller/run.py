#!/usr/bin/env python3
"""bt-analyzer Debian controller — parallel to usb-analyzer.

Default ports (do not collide with usb-analyzer :8080/:9750):
  HTTP / Lab UI : 8081
  Control TCP   : 9751  (reserved; HELLO not required for poll-proxy mode)

Usage:
  PYTHONPATH=. python3 -m controller.run
  PYTHONPATH=. python3 -m controller.run --http-port 8081 --control-port 9751
"""

from __future__ import annotations

import argparse
import socket
import threading

from controller.api.http_server import serve_forever as http_serve


def _control_accept_loop(host: str, port: int) -> None:
    """Placeholder TCP accept for future HELLO/discovery (BT4)."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(8)
    srv.settimeout(1.0)
    while True:
        try:
            conn, _addr = srv.accept()
            conn.close()
        except socket.timeout:
            continue
        except OSError:
            break


def main() -> None:
    ap = argparse.ArgumentParser(description="bt-analyzer controller")
    ap.add_argument("--control-host", default="0.0.0.0")
    ap.add_argument("--control-port", type=int, default=9751)
    ap.add_argument("--http-host", default="0.0.0.0")
    ap.add_argument("--http-port", type=int, default=8081)
    args = ap.parse_args()

    threading.Thread(
        target=_control_accept_loop,
        args=(args.control_host, args.control_port),
        daemon=True,
        name="bt-control-tcp",
    ).start()
    print(f"[bt-analyzer] control TCP :{args.control_port} (placeholder)")
    print(f"[bt-analyzer] lab UI http://0.0.0.0:{args.http_port}/")
    http_serve(args.http_host, args.http_port)


if __name__ == "__main__":
    main()
