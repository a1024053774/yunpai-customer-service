"""Update CASES/INDEX pointers for run-20260911-1416-grok46. README written separately."""
from __future__ import annotations

import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/Users/luckye/Documents/Code/yunpai-customer-service")
RUN = ROOT / "docs/testing/run-20260911-1416-grok46"
CASES = ROOT / "docs/testing/results/CASES.json"
INDEX = ROOT / "docs/testing/results/INDEX.json"
SRC_PTR = ROOT / "docs/testing/results/sources"

PRI = "docs/testing/run-20260911-1416-grok46/l1/priority.json"
AFT = "docs/testing/run-20260911-1416-grok46/l1/after.json"
LIVE = "docs/testing/run-20260911-1416-grok46/live/live.json"
K03 = "docs/testing/run-20260911-1416-grok46/l1/k03.json"
G08 = "docs/testing/run-20260911-1416-grok46/live/g08.json"
L02 = "docs/testing/run-20260911-1416-grok46/live/l02.json"
EXT = "docs/testing/run-20260911-1416-grok46/l1/extra.json"


def main() -> None:
    cases_blob = json.loads(CASES.read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in cases_blob["cases"]}

    def upd(cid: str, status: str, level: str, notes: str, evidence: str) -> None:
        row = by_id.get(cid)
        if not row:
            return
        row["status"] = status
        row["level"] = level
        prev = row.get("evidence") or []
        if isinstance(prev, str):
            prev = [prev]
        if evidence not in prev:
            row["evidence"] = [*prev, evidence]
        row["notes"] = notes

    updates = {
        "C08": ("PASS", "L1", "completed readable after reopen; generate/persist interrupt persist no success; retry new write", PRI),
        "E04": ("PASS", "L1", "cross-page table: production rag_min_score top-1 AAA=5L page, BBB=7L page; generation not live-judged", PRI),
        "I13": ("PASS", "L1", "marker local; export/chat no listener hit; no remote log handlers; L4 shipper still N03/N07", PRI),
        "C07": ("PASS", "L1", "clarify then refuse after user rejects sensitive materials; table-driven refuse injected", PRI),
        "H08": ("PASS", "L1", "retire then same DATA_DIR reopen; withdrawn id not retrieved", PRI),
        "E09": ("PASS", "L1", "partial add_document failure explicit; retry recovered; no duplicate active keys", PRI),
        "M02": ("PASS", "L1", "readonly sqlite does not report chat success", PRI),
        "M03": ("PASS", "L1", "corrupt PDF ingest fails closed; retrieve after fail still works", EXT),
        "G02": ("PASS", "L1", "injected already-refunded Chinese draft blocked; route forbidden_commitment_in_output", AFT),
        "F08": ("PASS", "L1", "approve v2, rollback, same DATA_DIR reopen; original/rewrite do not cite v2; audit rolled_back", AFT),
        "K03": ("PASS", "L1", "abort after delta then new idempotency continue; host socket reconnect still not run", K03),
        "F05": ("INCOMPLETE", "L1", "same-signal after=PASS source_traceable=false; independent review pending; implementer green is not acceptance", AFT),
        "F10": ("INCOMPLETE", "L1", "instruction candidate gate_passed=false after bypass removal; review pending; rate-limit still not a product API", AFT),
        "7.7": ("INCOMPLETE", "L1", "tied to F05; implementer green; review pending", AFT),
        "7.2": ("INCOMPLETE", "L1", "5L vs 5 years blocked numeric_unit_mismatch; implementer green; review pending", AFT),
        "N09": ("INCOMPLETE", "L0", "installed-dist inventory only; no CVE/license scanner", PRI),
        "F04": ("INCOMPLETE", "L1", "Demo still has no customer/admin split on evaluate/approve", EXT),
        "I12": ("INCOMPLETE", "L1", "OPTIONS 405 no CORS grant; oversize 422; burst/CSRF cookie matrix still not proven", EXT),
        "B07": ("PASS", "L2", "live: current BRAVO 7L/black overrode ALPHA history", LIVE),
        "B09": ("PASS", "L2", "live: one turn covered 12 CNY shipping and 7-day unused return; no refund expansion", LIVE),
        "D10": ("PASS", "L2", "live: QA-1416-D10 answered 7L; title 5L not used as fact", LIVE),
        "H02": ("PASS", "L2", "live: current black request honored; rice-white preference not treated as fact", LIVE),
        "B08": ("INCOMPLETE", "L2", "live typo slice PASS; full language/emoji/long-sentence buckets not run", LIVE),
        "G08": ("PASS", "L2", "live useful 5L + safety refuse credentials + no-answer did not invent stock; not a scored bucket set", G08),
        "L02": ("INCOMPLETE", "L3-http", "Demo HTTP double POST slice pending/partial; browser multi-tab/refresh not run", L02),
        "F09": (
            "REVIEW_PASS",
            "L1",
            "prior REVIEW_PASS kept; 1416 extra: concurrent rollback retired; approve+reject no rejected+active; chmod db-break did not silent-approve; lock not rewritten",
            PRI,
        ),
    }

    updates["L02"] = (
        "INCOMPLETE",
        "L3-http",
        "Demo HTTP double POST three 200s with distinct message ids; browser multi-tab/back/refresh not run",
        L02,
    )

    for cid, args in updates.items():
        upd(cid, *args)

    counts = Counter(c["status"] for c in cases_blob["cases"])
    cases_blob["counts"] = {
        k: counts.get(k, 0)
        for k in ("PASS", "INCOMPLETE", "BLOCKED", "NOT_RUN", "REVIEW_PASS", "FAIL")
    }
    cases_blob["n"] = len(cases_blob["cases"])
    cases_blob["run"] = "run-20260911-1416-grok46"
    cases_blob["updated"] = datetime.now(timezone.utc).isoformat()
    cases_blob["release"] = "NO_GO"
    CASES.write_text(json.dumps(cases_blob, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    index = json.loads(INDEX.read_text(encoding="utf-8"))
    index["updated"] = datetime.now(timezone.utc).isoformat()
    index["release"] = "NO_GO"
    index["handbook_counts"] = cases_blob["counts"]
    sources = index.get("sources") or []
    if not any(s.get("id") == "grok46-run-20260911-1416" for s in sources):
        sources.append(
            {
                "id": "grok46-run-20260911-1416",
                "executor": "Cursor Grok 4.6",
                "pytest": "knowledge+review_output 14 passed; not a product-release 109 rerun",
                "live": "B07/B09/D10/H02/G08 live PASS; B08 typo-only INCOMPLETE; F05/F10/7.2 implementer green review pending",
                "path": "docs/testing/run-20260911-1416-grok46",
            }
        )
    index["sources"] = sources
    defects = index.get("open_defects") or []
    by_d = {d["id"]: d for d in defects}
    by_d["F05"] = {
        "id": "F05",
        "priority": "P1",
        "status": "INCOMPLETE",
        "summary": "URL no longer self-attesting; implementer green; detached review pending",
        "folder": "defects/F05-fake-source",
    }
    by_d["F10"] = {
        "id": "F10",
        "priority": "P1",
        "status": "INCOMPLETE",
        "summary": "instruction bypass removed; implementer green; detached review pending",
        "folder": "defects/F10-instruction",
    }
    by_d["7.2"] = {
        "id": "7.2",
        "priority": "P1",
        "status": "INCOMPLETE",
        "summary": "5L vs 5 years unit check; implementer green; detached review pending",
        "folder": "defects/72-unit-mismatch",
    }
    index["open_defects"] = list(by_d.values())
    index["f05"] = {
        "status": "INCOMPLETE",
        "error_screenshot": "defects/F05-fake-source/error.png",
        "success_screenshot": "defects/F05-fake-source/success.png",
        "how_fixed": "defects/F05-fake-source/how-fixed.md",
        "independent_review_pending": True,
        "frozen_evolution": "0973a53a8453518bd4dcfc212cc97120940d1f6a5ab3aace6acbd11f4b3c1137",
    }
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    SRC_PTR.mkdir(parents=True, exist_ok=True)
    for src, dest in (
        (RUN / "l1/after.json", SRC_PTR / "grok46-20260911-1416-after.json"),
        (RUN / "l1/priority.json", SRC_PTR / "grok46-20260911-1416-priority.json"),
        (RUN / "live/live.json", SRC_PTR / "grok46-20260911-1416-live.json"),
        (RUN / "freeze.json", SRC_PTR / "grok46-20260911-1416-freeze.json"),
        (RUN / "freeze-after-fix.json", SRC_PTR / "grok46-20260911-1416-freeze-after-fix.json"),
    ):
        if src.is_file():
            shutil.copy2(src, dest)
    print(json.dumps({"counts": cases_blob["counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
