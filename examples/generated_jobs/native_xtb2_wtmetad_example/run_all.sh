#!/bin/sh
set -eu
wait_for_socket() {
  mode="$1"
  target="$2"
  port="${3:-}"
  python - "$mode" "$target" "$port" <<'PY'
import os
import socket
import sys
import time

mode, target, port = sys.argv[1], sys.argv[2], sys.argv[3]
deadline = time.time() + 120
if mode == 'unix':
    while time.time() < deadline:
        if os.path.exists(target):
            time.sleep(1)
            raise SystemExit(0)
        time.sleep(1)
else:
    host = target
    port = int(port)
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                raise SystemExit(0)
        except OSError:
            time.sleep(1)
raise SystemExit(1)
PY
}

cleanup() {
  if [ -n "${IPI_PID:-}" ]; then
    kill "$IPI_PID" 2>/dev/null || true
    wait "$IPI_PID" 2>/dev/null || true
  fi
  rm -f "/tmp/ipi_orca_driver"
}
trap cleanup INT TERM EXIT
mkdir -p logs
rm -f "/tmp/ipi_orca_driver"
sh run_ipi.sh > logs/ipi.log 2>&1 &
IPI_PID=$!
wait_for_socket unix "/tmp/ipi_orca_driver"
sh run_client.sh > logs/client.log 2>&1
wait "$IPI_PID"
