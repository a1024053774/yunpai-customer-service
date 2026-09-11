"""Independent oracle: does the Skill text contain operational constraints?

Red = current skill misses required phrases.
This is a Skill-contract test, not a product test. No secrets.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL = Path("/Users/luckye/Documents/SKILLS/agent-acceptance-testing/SKILL.md")
OPS = Path("/Users/luckye/Documents/SKILLS/agent-acceptance-testing/references/operational-templates.md")
EVIDENCE = Path(
    "/Users/luckye/Documents/Code/yunpai-customer-service/docs/testing/run-20260911-acceptance-handoff/skill-fix"
)

REQUIRED = [
    {
        "id": "SK-ISO-001",
        "needles": ["source env.md then export DATA_DIR", "refuse workspace data/"],
        "why": "env.md can clobber DATA_DIR onto repo data/; ISO-001 already happened",
    },
    {
        "id": "SK-EXECUTOR-PIN",
        "needles": ["do not substitute Orca", "Codex", "Luna"],
        "why": "user-frozen executor; plan.md already drifted to Orca",
    },
    {
        "id": "SK-FRESH-REVIEWER",
        "needles": ["Task tool", "run_in_background", "forbid resume"],
        "why": "fresh-context verifier is named but not operationalized",
    },
    {
        "id": "SK-CJK",
        "needles": ["unicode escapes", "Path.write_text"],
        "why": "this repo forbids Write/StrReplace CJK in docs",
    },
    {
        "id": "SK-FILE-URI",
        "needles": ["file://", "localhost HTTP"],
        "why": "sidebar browser blocks file:// screenshots",
    },
    {
        "id": "SK-REVIEW-PASS-FREEZE",
        "needles": ["REVIEW_PASS", "must not be reverted to FAIL"],
        "why": "ledger already has REVIEW_PASS defects",
    },
    {
        "id": "SK-LEDGER-PHASE",
        "needles": ["do not edit CASES.json during freeze"],
        "why": "skill currently pushes unique ledger writes too early",
    },
    {
        "id": "SK-SEPARATE-DIGEST",
        "needles": ["skill_sha256", "product candidate digest"],
        "why": "skill edits must not be confused with product freeze",
    },
    {
        "id": "SK-NO-WAIT",
        "needles": ["do not stop to wait for the user when instructed to continue"],
        "why": "grilling wait conflicts with continue-to-completion runs",
    },
    {
        "id": "SK-10-2-NO-GO",
        "needles": ["incomplete 10.2", "NO_GO"],
        "why": "green pytest must not become product GO",
    },
]


def main() -> int:
    text = SKILL.read_text(encoding="utf-8")
    ops = OPS.read_text(encoding="utf-8") if OPS.is_file() else ""
    blob = text + "\n" + ops
    rows = []
    missing = 0
    for item in REQUIRED:
        present = [n for n in item["needles"] if n in blob]
        absent = [n for n in item["needles"] if n not in blob]
        ok = not absent
        if not ok:
            missing += 1
        rows.append(
            {
                "id": item["id"],
                "status": "PASS" if ok else "FAIL",
                "present": present,
                "absent": absent,
                "why": item["why"],
            }
        )
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    out = {
        "saved_utc": datetime.now(timezone.utc).isoformat(),
        "skill": str(SKILL),
        "skill_sha256_note": "compare freeze.json skill_sha256",
        "status": "FAIL" if missing else "PASS",
        "missing": missing,
        "cases": rows,
        "note": "FAIL here is a Skill-contract red state, not a product defect",
    }
    (EVIDENCE / "checklist.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": out["status"], "missing": missing, "n": len(rows)}))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
