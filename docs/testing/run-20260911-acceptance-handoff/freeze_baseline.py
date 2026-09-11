"""Phase-0 freeze. No secrets in stdout or evidence files."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
EVIDENCE = Path(__file__).resolve().parent
BASELINE = EVIDENCE / "baseline"
SECRET_NAME_RE = re.compile(r"(key|secret|token|password|authorization|credential)", re.I)
EXPORT_RE = re.compile(r"^\s*export\s+([A-Za-z_][A-Za-z0-9_]*)=", re.M)
PY_FILES = [
    "src/yunpai_customer_service",
    "tests",
]


def sh(args: list[str], cwd: Path = WORKSPACE) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def env_names(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    names = sorted(set(EXPORT_RE.findall(text)))
    return names


def collect_source_files() -> list[Path]:
    files: list[Path] = []
    for root in PY_FILES:
        base = WORKSPACE / root
        if base.is_file():
            files.append(base)
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix in {".py", ".json", ".html", ".md"}:
                files.append(p)
    return files


def main() -> None:
    BASELINE.mkdir(parents=True, exist_ok=True)
    pwd = str(Path.cwd())
    write(BASELINE / "pwd.txt", pwd + "\n")

    head = sh(["git", "rev-parse", "HEAD"]).stdout.strip()
    write(BASELINE / "git-head.txt", head + "\n")
    status = sh(["git", "status", "--porcelain=v1"])
    write(BASELINE / "git-status.txt", status.stdout)
    branch = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    write(BASELINE / "git-branch.txt", branch + "\n")

    diff = sh(["git", "diff", "--binary"])
    staged = sh(["git", "diff", "--cached", "--binary"])
    dirty = (diff.stdout + staged.stdout).encode("utf-8")
    dirty_sha = sha256_bytes(dirty)
    write(BASELINE / "dirty-diff.sha256", dirty_sha + "\n")
    stat = sh(["git", "diff", "--stat"])
    write(BASELINE / "dirty-diff-stat.txt", stat.stdout)

    untracked = sh(["git", "ls-files", "--others", "--exclude-standard"])
    untracked_list = [line for line in untracked.stdout.splitlines() if line]
    src_untracked = [
        p
        for p in untracked_list
        if p.startswith("src/") or p.startswith("tests/")
    ]
    write(
        BASELINE / "untracked-summary.txt",
        "count={0}\nsrc_tests_count={1}\nsrc_tests:\n{2}\n".format(
            len(untracked_list),
            len(src_untracked),
            "\n".join(src_untracked),
        ),
    )
    untracked_src_bytes = "\n".join(src_untracked).encode("utf-8")
    untracked_src_sha = sha256_bytes(untracked_src_bytes)

    env_path = WORKSPACE / "env.md"
    names = env_names(env_path) if env_path.is_file() else []
    env_file_sha = sha256_file(env_path) if env_path.is_file() else None
    write(
        BASELINE / "env-names.json",
        json.dumps(
            {
                "file": "env.md",
                "exists": env_path.is_file(),
                "sha256": env_file_sha,
                "variable_names": names,
                "contains_DATA_DIR": "DATA_DIR" in names,
                "note": "values omitted; ISO-001: source env.md then export DATA_DIR under /tmp",
            },
            indent=2,
        )
        + "\n",
    )

    py = WORKSPACE / ".venv" / "bin" / "python"
    pkgs = [
        "fastapi",
        "uvicorn",
        "httpx",
        "pydantic",
        "fastembed",
        "onnxruntime",
        "pdfplumber",
        "docling",
        "pytest",
        "starlette",
        "sqlite3",
    ]
    dep_cmd = [
        str(py),
        "-c",
        (
            "import importlib, json, sys\n"
            "pkgs = sys.argv[1:]\n"
            "out = {'python': sys.version.split()[0], 'executable': sys.executable, 'packages': {}}\n"
            "for name in pkgs:\n"
            "    try:\n"
            "        mod = importlib.import_module(name)\n"
            "        out['packages'][name] = {\n"
            "            'present': True,\n"
            "            'version': getattr(mod, '__version__', None),\n"
            "            'file': getattr(mod, '__file__', None),\n"
            "        }\n"
            "    except Exception as exc:\n"
            "        out['packages'][name] = {'present': False, 'error': type(exc).__name__}\n"
            "print(json.dumps(out, indent=2))\n"
        ),
        *pkgs,
    ]
    deps = sh(dep_cmd)
    write(BASELINE / "deps.json", deps.stdout or (deps.stderr + "\n"))

    sys.path.insert(0, str(WORKSPACE / "src"))
    from yunpai_customer_service.database import Database  # noqa: E402

    schema = Database.SCHEMA_VERSION
    write(BASELINE / "schema.txt", f"{schema}\n")

    file_hashes = {}
    for path in collect_source_files():
        rel = str(path.relative_to(WORKSPACE))
        file_hashes[rel] = sha256_file(path)
    candidate_blob = json.dumps(
        {"head": head, "dirty_diff_sha256": dirty_sha, "files": file_hashes},
        sort_keys=True,
    ).encode("utf-8")
    candidate_sha = sha256_bytes(candidate_blob)

    listen = sh(
        [
            "bash",
            "-lc",
            "lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | awk 'NR==1 || /python|uvicorn|8765|18765|18767/'",
        ]
    )
    write(BASELINE / "listen-before-start.txt", listen.stdout)

    freeze = {
        "run_id": "run-20260911-acceptance-handoff",
        "executor": "cursor-grok-4.6-xhigh-fast",
        "not_orca": True,
        "not_codex": True,
        "not_luna": True,
        "not_gpt_5_6_luna": True,
        "candidate": "HEAD 8ea1329e + complete dirty tree",
        "head": head,
        "head_expected": "8ea1329e8fd495cff3887bbed05ab4b5b9da8c99",
        "head_matches": head == "8ea1329e8fd495cff3887bbed05ab4b5b9da8c99",
        "branch": branch,
        "workspace": str(WORKSPACE),
        "pwd": pwd,
        "dirty_diff_sha256": dirty_sha,
        "untracked_source_sha256": untracked_src_sha,
        "untracked_source_count": len(src_untracked),
        "untracked_total_count": len(untracked_list),
        "candidate_sha256": candidate_sha,
        "file_count": len(file_hashes),
        "files": file_hashes,
        "schema_version": schema,
        "env_key_names": names,
        "env_file_sha256": env_file_sha,
        "env_contains_DATA_DIR": "DATA_DIR" in names,
        "iso_001": {
            "rule": "source env.md then export DATA_DIR under /tmp or /private/tmp; refuse workspace data/",
            "env_md_sets_DATA_DIR": "DATA_DIR" in names,
        },
        "skill_path": "/Users/luckye/Documents/SKILLS/agent-acceptance-testing/SKILL.md",
        "skill_sha256": sha256_file(
            Path("/Users/luckye/Documents/SKILLS/agent-acceptance-testing/SKILL.md")
        ),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "note": "HEAD alone does not identify the candidate. Do not overwrite old evidence.",
        "key_file_sha256": {
            "evolution.py": file_hashes.get("src/yunpai_customer_service/evolution.py"),
            "policy.py": file_hashes.get("src/yunpai_customer_service/policy.py"),
            "database.py": file_hashes.get("src/yunpai_customer_service/database.py"),
            "config.py": file_hashes.get("src/yunpai_customer_service/config.py"),
            "rag.py": file_hashes.get("src/yunpai_customer_service/rag.py"),
            "embeddings.py": file_hashes.get("src/yunpai_customer_service/embeddings.py"),
        },
        "compare_1416_after_fix": {
            "evolution_expected": "0973a53a8453518bd4dcfc212cc97120940d1f6a5ab3aace6acbd11f4b3c1137",
            "policy_expected": "7d05f60604b3121d4b360f0e14e07499450f1405ae8a13b1b427bfd892628014",
            "evolution_match": file_hashes.get("src/yunpai_customer_service/evolution.py")
            == "0973a53a8453518bd4dcfc212cc97120940d1f6a5ab3aace6acbd11f4b3c1137",
            "policy_match": file_hashes.get("src/yunpai_customer_service/policy.py")
            == "7d05f60604b3121d4b360f0e14e07499450f1405ae8a13b1b427bfd892628014",
        },
    }
    write(EVIDENCE / "freeze.json", json.dumps(freeze, indent=2) + "\n")

    manifest_path = EVIDENCE / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["owner"] = "cursor-grok-4.6-xhigh-fast"
    manifest["execution_entrypoint"] = "Cursor Desktop Agent; not Orca/Codex/Luna"
    manifest["model_requested"] = "Cursor Grok 4.6 Extra High Fast"
    manifest["dirty_diff_digest"] = dirty_sha
    manifest["untracked_source_digest"] = untracked_src_sha
    manifest["candidate_digest"] = candidate_sha
    manifest["database_schema"] = schema
    manifest["env_key_names"] = names
    manifest["env_file_sha256"] = env_file_sha
    manifest["isolated_data_dir"] = "/tmp/yunpai-handoff-20260911"
    manifest["skill_sha256"] = freeze["skill_sha256"]
    manifest["baseline_frozen_utc"] = freeze["started_utc"]
    write(manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "ok": True,
                "head": head,
                "dirty_diff_sha256": dirty_sha,
                "schema_version": schema,
                "env_name_count": len(names),
                "file_count": len(file_hashes),
                "listen_preview_bytes": len(listen.stdout),
            }
        )
    )


if __name__ == "__main__":
    main()
