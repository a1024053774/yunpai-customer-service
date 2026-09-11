"""ISO-001: starting with workspace data/ must refuse."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
EVIDENCE = Path(__file__).resolve().parent
START = EVIDENCE / "start_servers.py"


def main() -> None:
    proc = subprocess.run(
        [str(WORKSPACE / ".venv" / "bin" / "python"), str(START)],
        cwd=str(WORKSPACE),
        text=True,
        capture_output=True,
        env={
            "DATA_DIR": str(WORKSPACE / "data"),
            "PATH": __import__("os").environ.get("PATH", ""),
        },
        timeout=20,
    )
    combined = (proc.stdout or "") + (proc.stderr or "")
    ok = proc.returncode != 0 and "ISO-001" in combined
    payload = {
        "saved_utc": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(WORKSPACE / "data"),
        "returncode": proc.returncode,
        "stdout_preview": (proc.stdout or "")[:500],
        "stderr_preview": (proc.stderr or "")[:800],
        "status": "PASS" if ok else "FAIL",
    }
    out = EVIDENCE / "baseline" / "iso-001-refuse.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": ok, "returncode": proc.returncode}))


if __name__ == "__main__":
    main()
