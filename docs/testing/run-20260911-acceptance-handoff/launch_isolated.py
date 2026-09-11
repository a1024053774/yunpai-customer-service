"""Start isolated servers: source env.md THEN export DATA_DIR. No secret dumps."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
EVIDENCE = Path(__file__).resolve().parent
DATA_DIR = Path("/tmp/yunpai-handoff-20260911")
START = EVIDENCE / "start_servers.py"


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    env_file = WORKSPACE / "env.md"
    # Parse names only for the launch record.
    names = []
    for line in env_file.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("export ") and "=" in s:
            names.append(s.split("=", 1)[0].replace("export ", "").strip())
    record = {
        "order": "source env.md then export DATA_DIR",
        "env_names": sorted(set(names)),
        "data_dir_after_override": str(DATA_DIR),
        "workspace_data": str((WORKSPACE / "data").resolve()),
        "iso_001": "override after source; refuse workspace data/",
    }
    (EVIDENCE / "baseline" / "iso-001-launch.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    bash = f"""
set -euo pipefail
cd {WORKSPACE}
set -a
source ./env.md
set +a
export DATA_DIR={DATA_DIR}
export KG_IMPORT_ENABLED=false
export KG_DREAM_WORKER_ENABLED=false
export MODEL_RETRY_ATTEMPTS=0
if [ "$DATA_DIR" = "{WORKSPACE}/data" ]; then
  echo 'ISO-001 failed: DATA_DIR still workspace data/' >&2
  exit 2
fi
exec {WORKSPACE}/.venv/bin/python {START}
"""
    os.execvp("bash", ["bash", "-lc", bash])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
