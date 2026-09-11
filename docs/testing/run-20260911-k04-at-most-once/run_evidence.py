"""Capture immutable counterfactual and repaired K04 at-most-once evidence."""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[2]
SOURCE = WORKSPACE / "src" / "yunpai_customer_service" / "customer_service" / "core.py"
PROBE = ROOT / "probe.py"


def prepare_baseline(source: Path) -> Path:
    text = source.read_text(encoding="utf-8")
    start = text.index("    def prepare_invocation(\n")
    end = text.index("    @staticmethod\n    def invocation_response", start)
    baseline = subprocess.check_output(
        ["git", "show", "HEAD:src/yunpai_customer_service/customer_service/core.py"],
        cwd=WORKSPACE,
        text=True,
    )
    old_start = baseline.index("    def prepare_invocation(\n")
    old_end = baseline.index("    @staticmethod\n    def invocation_response", old_start)
    result = text[:start] + baseline[old_start:old_end] + text[end:]
    source.write_text(result, encoding="utf-8")
    return source


def run_probe(source_root: Path, output: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(WORKSPACE / "tests"), str(source_root), str(WORKSPACE / ".venv" / "lib" / "python3.11" / "site-packages")]
    )
    return subprocess.run(
        [sys.executable, str(PROBE), "--output", str(output)],
        cwd=WORKSPACE,
        env=env,
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="yunpai-k04-baseline-") as baseline_dir:
        baseline_root = Path(baseline_dir) / "src"
        shutil.copytree(WORKSPACE / "src", baseline_root)
        baseline_core = prepare_baseline(baseline_root / "yunpai_customer_service" / "customer_service" / "core.py")
        baseline = run_probe(baseline_root, args.output_dir / "before.json")
        repaired = run_probe(WORKSPACE / "src", args.output_dir / "after.json")
        manifest = {
            "status": "PASS" if baseline.returncode != 0 and repaired.returncode == 0 else "FAIL",
            "before_exit": baseline.returncode,
            "after_exit": repaired.returncode,
            "before_stdout": baseline.stdout,
            "before_stderr": baseline.stderr,
            "after_stdout": repaired.stdout,
            "after_stderr": repaired.stderr,
            "baseline_core_sha256": hashlib.sha256(baseline_core.read_bytes()).hexdigest(),
            "repaired_core_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "source": str(SOURCE),
            "probe": str(PROBE),
            "counterfactual": "HEAD implementation of prepare_invocation restored in isolated copy",
            "scope": "L1 same-process concurrent duplicate graph execution",
        }
    (args.output_dir / "manifest.json").write_text(
        __import__("json").dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(__import__("json").dumps(manifest, ensure_ascii=False, indent=2))
    raise SystemExit(0 if manifest["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
