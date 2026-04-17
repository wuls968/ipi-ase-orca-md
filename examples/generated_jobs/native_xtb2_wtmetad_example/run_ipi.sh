#!/bin/sh
set -eu
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
"$IPI_BIN" input.xml
