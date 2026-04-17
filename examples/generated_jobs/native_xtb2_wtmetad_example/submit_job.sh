#!/bin/sh
set -eu

CONDA_ENV="ipi"
ORCA_COMMAND="orca"
JOB_LAUNCHER_PREFIX="${JOB_LAUNCHER_PREFIX:-}"

ORCA_COMMAND_BIN='orca'
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
detect_conda_sh() {
  if [ -n "${CONDA_SH:-}" ] && [ -f "$CONDA_SH" ]; then
    printf "%s\n" "$CONDA_SH"
    return
  fi
  if command -v conda >/dev/null 2>&1; then
    conda_base="$(conda info --base 2>/dev/null || true)"
    if [ -n "$conda_base" ] && [ -f "$conda_base/etc/profile.d/conda.sh" ]; then
      printf "%s\n" "$conda_base/etc/profile.d/conda.sh"
      return
    fi
  fi
  printf "\n"
}
trap cleanup INT TERM EXIT
CONDA_SH="$(detect_conda_sh)"
if [ -f "$CONDA_SH" ]; then
  . "$CONDA_SH"
fi
command -v conda >/dev/null
conda activate "$CONDA_ENV"

detect_ipi_bin() {
  python - <<'PY'
import os
from pathlib import Path
import shutil
import sys

candidate = Path(sys.executable).with_name('i-pi')
if candidate.is_file() and os.access(candidate, os.X_OK):
    print(candidate)
else:
    print(shutil.which('i-pi') or '')
PY
}
IPI_BIN="${IPI_BIN:-$(detect_ipi_bin)}"
test -n "$IPI_BIN"
mkdir -p logs
rm -f "/tmp/ipi_orca_driver"
command -v "$ORCA_COMMAND_BIN" >/dev/null
python -c "import ase, plumed"
"$IPI_BIN" input.xml > logs/ipi.log 2>&1 &
IPI_PID=$!
wait_for_socket unix "/tmp/ipi_orca_driver"
sh -c "${JOB_LAUNCHER_PREFIX} python ase_orca_client.py" > logs/client.log 2>&1
wait "$IPI_PID"
