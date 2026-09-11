"""Update CASES/INDEX pointers for this run. README written separately."""
from __future__ import annotations

import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
RUN = ROOT / "docs/testing/run-20260911-1024-grok46"
CASES = ROOT / "docs/testing/results/CASES.json"
INDEX = ROOT / "docs/testing/results/INDEX.json"
SRC_PTR = ROOT / "docs/testing/results/sources"


def main() -> None:
    cases_blob = json.loads(CASES.read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in cases_blob["cases"]}
    ev = "docs/testing/run-20260911-1024-grok46/l1/cases.json"
    g04_after = "docs/testing/run-20260911-1024-grok46/g04/after.json"
    e04 = "docs/testing/run-20260911-1024-grok46/l1/e04.json"
    i11 = "docs/testing/run-20260911-1024-grok46/live/i11.json"

    updates = {
        "A03": ("PASS", "L1", "tool-fail branch executed, reviewed, persisted; risky draft not shipped", ev),
        "A04": ("PASS", "L1", "timeout 0.05 vs 2.0 changed callee; hash vs fastembed class; parsers called. not live FastEmbed process", ev),
        "A05": ("PASS", "L1", "disabled model + nonce -> model_unavailable handoff; no catalog answer", ev),
        "A09": ("PASS", "L0", "0 TODO; README excludes Taobao and states SQLite; residual taobao_* not claimed delivered", ev),
        "G01": ("PASS", "L1", "every SSE frame + persist omit bank-card/password; host stream still K02", ev),
        "G03": ("PASS", "L1", "HTML/script and sensitive missing_fields rewritten", ev),
        "J05": ("PASS", "L1", "decoded 5MiB N-1/N accept, N+1 reject. Demo HTTP body not posted", ev),
        "F01": ("PASS", "L1", "like/empty feedback-only; full correction creates candidate", ev),
        "F05": ("FAIL", "L1", "evaluate gate_passed=true with fake https source; source_traceable is nonempty-only", ev),
        "F06": ("PASS", "L1", "unevidenced 95%/1.99 rejected; ordinal candidate may pass other checks", ev),
        "B07": ("INCOMPLETE", "L1", "BRAVO reached generation prompts; live referent override not judged", ev),
        "B09": ("INCOMPLETE", "L1", "full two-intent string reached generate; live coverage of both asks not judged", ev),
        "C06": ("PASS", "L1", "two concurrent same-session chats both persisted; no frozen conflict SOP", ev),
        "C07": ("INCOMPLETE", "L1", "repeat clarify handled; sensitive refuse not injected", ev),
        "D04": ("PASS", "L1", "retired/expired not retrieved; current+conflict remain. no authority resolver", ev),
        "D09": ("PASS", "L1", "retire 5L then add 7L; retrieve shows 7L not 5L", ev),
        "D10": ("INCOMPLETE", "L1", "retrieve body has 7L contradiction; generation truth not live-judged", ev),
        "E06": ("PASS", "L1", "empty/exe/corrupt/20MiB+ rejected", ev),
        "E07": ("PASS", "L1", "identical import idempotent; rename and content-change new ids", ev),
        "E08": ("PASS", "L1", "own file 200; other digest 404; traversal 404", ev),
        "I07": ("PASS", "L1", "wrong client key 401; good key 200. not a live rotation ceremony", ev),
        "I11": ("INCOMPLETE", "L1", "escapeHtml present; no CSP; browser XSS still required", ev),
        "I12": ("INCOMPLETE", "L1", "OPTIONS 405; oversize 422; not a full CORS/CSRF/rate matrix", ev),
        "F04": ("INCOMPLETE", "L1", "Demo loopback principal can evaluate+approve; no customer/admin split", ev),
        "G04": ("INCOMPLETE", "L1", "same-signal after=PASS; independent review pending; implementer green is not acceptance", g04_after),
        "K02": ("INCOMPLETE", "L1", "G01 inspected every core SSE frame; host dangerous-draft stream still not run", ev),
        "7.2": ("INCOMPLETE", "L1", "G01 every-frame done this run; 5L-vs-5-years semantic still a gap", ev),
        "7.7": ("FAIL", "L1", "F05 fake source now run and gate_passed", ev),
    }

    e04_path = RUN / "l1/e04.json"
    if e04_path.is_file():
        e04_case = json.loads(e04_path.read_text(encoding="utf-8"))
        updates["E04"] = (e04_case.get("status", "INCOMPLETE"), "L1", "cross-page table PDF ingest; see e04.json", e04)

    i11_path = RUN / "live/i11.json"
    if i11_path.is_file():
        i11_case = json.loads(i11_path.read_text(encoding="utf-8"))
        note = i11_case.get("notes")
        if isinstance(note, list):
            note = note[0] if note else "browser I11"
        updates["I11"] = (i11_case.get("status", "INCOMPLETE"), i11_case.get("level", "L3"), str(note), i11)

    for cid, (status, level, notes, evidence) in updates.items():
        row = by_id.get(cid)
        if not row:
            continue
        row["status"] = status
        row["level"] = level
        prev = row.get("evidence") or []
        if isinstance(prev, str):
            prev = [prev]
        if evidence not in prev:
            row["evidence"] = [*prev, evidence]
        row["notes"] = notes

    counts = Counter(c["status"] for c in cases_blob["cases"])
    cases_blob["counts"] = {
        k: counts.get(k, 0)
        for k in ("PASS", "INCOMPLETE", "BLOCKED", "NOT_RUN", "REVIEW_PASS", "FAIL")
    }
    cases_blob["n"] = len(cases_blob["cases"])
    cases_blob["run"] = "run-20260911-1024-grok46"
    cases_blob["updated"] = datetime.now(timezone.utc).isoformat()
    cases_blob["release"] = "NO_GO"
    CASES.write_text(json.dumps(cases_blob, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    index = json.loads(INDEX.read_text(encoding="utf-8"))
    index["updated"] = datetime.now(timezone.utc).isoformat()
    index["release"] = "NO_GO"
    index["handbook_counts"] = cases_blob["counts"]
    sources = index.get("sources") or []
    if not any(s.get("id") == "grok46-run-20260911-1024" for s in sources):
        sources.append(
            {
                "id": "grok46-run-20260911-1024",
                "executor": "Cursor Grok 4.6",
                "pytest": "not a product-release pytest rerun",
                "live": "I11 browser pending/partial; G04 implementer green review pending; F05 FAIL",
                "path": "docs/testing/run-20260911-1024-grok46",
            }
        )
    index["sources"] = sources
    index["g04"] = {
        "status": "INCOMPLETE",
        "summary": "implementer same-signal green; independent review pending",
        "before": "docs/testing/results/defects/G04-verify-error/before.json",
        "after": "docs/testing/results/defects/G04-verify-error/after.json",
        "how_fixed": "docs/testing/results/defects/G04-verify-error/how-fixed.md",
        "treated_as_new_p1_fix": True,
        "independent_review_pending": True,
    }
    findings = [f for f in (index.get("findings") or []) if f.get("id") not in {"G04", "F05"}]
    findings.append(
        {
            "id": "G04",
            "priority": "P1",
            "status": "INCOMPLETE",
            "summary": "fixed at verify/safe_terminal; implementer green; review pending",
            "folder": "docs/testing/results/defects/G04-verify-error",
        }
    )
    findings.append(
        {
            "id": "F05",
            "priority": "P1",
            "status": "FAIL",
            "summary": "evaluate accepts nonempty fake source as source_traceable",
            "folder": "docs/testing/results/defects/F05-fake-source",
        }
    )
    index["findings"] = findings
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    SRC_PTR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RUN / "l1/cases.json", SRC_PTR / "grok46-20260911-1024-l1.json")
    shutil.copy2(RUN / "g04/after.json", SRC_PTR / "grok46-20260911-1024-g04-after.json")
    shutil.copy2(RUN / "freeze.json", SRC_PTR / "grok46-20260911-1024-freeze.json")
    print(json.dumps({"counts": cases_blob["counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
