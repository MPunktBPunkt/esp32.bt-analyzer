#!/usr/bin/env bash
# bt-analyzer Debian controller: discovery/control :9751 + Lab UI :8081
# Parallel to usb-analyzer (:9750 / :8080).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="${LAB_CONTROLLER_LOG_DIR:-$ROOT/logs}"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/controller.log"
PIDFILE="$LOG_DIR/controller.pid"
HTTP_PORT="${HTTP_PORT:-8081}"
CONTROL_PORT="${CONTROL_PORT:-9751}"

stop_old() {
  if [[ -f "$PIDFILE" ]]; then
    old="$(cat "$PIDFILE" || true)"
    if [[ -n "${old:-}" ]] && kill -0 "$old" 2>/dev/null; then
      echo "stopping pid $old"
      kill "$old" 2>/dev/null || true
      sleep 1
      kill -9 "$old" 2>/dev/null || true
    fi
    rm -f "$PIDFILE"
  fi
  for port in "$HTTP_PORT" "$CONTROL_PORT"; do
    pids="$(ss -lntp "sport = :$port" 2>/dev/null | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | sort -u)"
    for p in $pids; do
      cmd="$(tr '\0' ' ' <"/proc/$p/cmdline" 2>/dev/null || true)"
      if echo "$cmd" | grep -q 'controller.run\|controller.__main__'; then
        echo "killing orphan bt-analyzer controller pid $p on :$port"
        kill "$p" 2>/dev/null || true
        sleep 0.5
        kill -9 "$p" 2>/dev/null || true
      fi
    done
  done
}

start() {
  stop_old
  echo "starting bt-analyzer controller → log $LOG"
  nohup python3 -m controller.run --http-port "$HTTP_PORT" --control-port "$CONTROL_PORT" \
    >>"$LOG" 2>&1 &
  echo $! >"$PIDFILE"
  sleep 0.8
  code="$(curl -sS -m 3 -o /tmp/bt_lab_ctrl_health.json -w '%{http_code}' "http://127.0.0.1:${HTTP_PORT}/api/v1/health" || true)"
  echo "health HTTP $code $(head -c 200 /tmp/bt_lab_ctrl_health.json 2>/dev/null || true)"
  [[ "$code" == "200" ]] || { echo "FAIL: controller did not become healthy"; exit 1; }
  echo "OK http://$(hostname -I | awk '{print $1}'):${HTTP_PORT}/"
}

case "${1:-start}" in
  start) start ;;
  stop) stop_old ;;
  restart) start ;;
  status)
    if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "running pid $(cat "$PIDFILE")"
      curl -sS -m 2 "http://127.0.0.1:${HTTP_PORT}/api/v1/health" || true
      echo
    else
      echo "stopped"
    fi
    ;;
  *) echo "usage: $0 {start|stop|restart|status}"; exit 1 ;;
esac
